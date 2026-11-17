import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic

import pytest


@pytest.fixture(scope='module')
def archived_reader_assets(tmp_path_factory):
    from tests.historical_readers import historical_reader_resources

    with historical_reader_resources(tmp_path_factory.mktemp('archived-reader')):
        yield


def pytest_runtest_setup(item):
    if item.get_closest_marker('parser_container'):
        from packages.parsers.inspect import PDFError
        from workers.parser.main import verify_memory_envelope
        try:
            verify_memory_envelope()
        except PDFError:
            pytest.skip('Requires the real parser in a Linux container with a finite memory limit <= 16 GiB; run tests from compose.example.yaml in a dedicated project.')


def monotonic_datetime(*, utc_now, elapsed):
    """A per-test UTC timeline that survives host/VM wall-clock corrections."""
    anchor, started = utc_now(timezone.utc), elapsed()

    class FixtureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = anchor + timedelta(seconds=elapsed() - started)
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    return FixtureDateTime


@pytest.fixture
def database_clock(monkeypatch):
    from packages.domain import models
    # Capture the real callable, not a module attribute another test can patch.
    clock = monotonic_datetime(utc_now=datetime.now, elapsed=monotonic)
    # Imported now() aliases and ORM timestamp defaults retain this function's
    # reference; replacing its datetime global keeps both on the same timeline.
    monkeypatch.setattr(models, 'datetime', clock)


@pytest.fixture
def database(tmp_path, monkeypatch, database_clock):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('A dedicated PostgreSQL TEST_DATABASE_URL is required; SQLite is not a substitute.')
    monkeypatch.setenv('LIBRARY_TEST_MODE', '1')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('UPLOADS_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('PARSER_INPUTS_DIR', str(tmp_path / 'inputs'))
    monkeypatch.setenv('PARSER_OUTPUTS_DIR', str(tmp_path / 'outputs'))
    from packages.domain.config import Config
    from packages.domain.db import Database
    from sqlalchemy import create_engine, text
    # Explicit opt-in test URL only; production configuration is never reset.
    assert 'test' in url.rsplit('/', 1)[-1], 'Use a database explicitly named for tests'
    schema = 'library_test_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    monkeypatch.setenv('TEST_DATABASE_SCHEMA', schema)
    cfg = Config.load()
    db = Database(cfg)
    db.migrate()
    for p in (cfg.data, cfg.uploads, cfg.parser_inputs, cfg.parser_outputs):
        p.mkdir(parents=True, exist_ok=True)
    yield db, cfg
    db.engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from apps.api.main import create_app
    db, cfg = database
    with TestClient(create_app(cfg, db)) as http:
        http.headers['X-Library-Request'] = '1'
        yield http
