"""Parser preferences and queues respect deployment capability."""
import time

import httpx
import pytest
from sqlalchemy import select

from packages.domain.models import Job, Task
from packages.ir import canonical_bytes
from packages.parsers.profiles import OXR_PROFILE
from tests.support import seed_editor

pytestmark = pytest.mark.postgres

PENDING = [
    ('prokope-4b-eagle-eye-v1', 'PARSER_MODEL_ACCESS_REQUIRED',
     'ProKope-AI/ProKope-4B-Eagle-Eye'),
    (OXR_PROFILE, 'PARSER_MODEL_PLUGIN_REQUIRED', 'SoMarkAI/OXR-1.0'),
]


@pytest.fixture(autouse=True)
def default_parser_deployment(monkeypatch):
    monkeypatch.delenv('PARSER_DMR_OXR', raising=False)
    monkeypatch.setenv('PARSER_DMR_BACKEND', 'vllm')


@pytest.mark.parametrize('profile,code,repository', PENDING)
def test_pending_preference_roundtrip_and_cas_do_not_contact_models(
        client, database, monkeypatch, profile, code, repository):
    monkeypatch.setattr(httpx, 'Client', lambda **_: pytest.fail('Saving a preference must not contact models'))
    before = client.get('/api/v1/settings/preferences')
    saved = client.patch('/api/v1/settings/preferences',
        json={'parser_profile_revision': profile}, headers={'If-Match': before.headers['etag']})
    assert saved.status_code == 200, saved.text
    assert saved.json()['parser_profile_revision'] == profile
    assert saved.json()['parser_profile_status'] == 'unavailable'
    assert saved.json()['parser_timeout_seconds'] == before.json()['parser_timeout_seconds']
    assert client.get('/api/v1/settings/preferences').json() == saved.json()
    stale = client.patch('/api/v1/settings/preferences',
        json={'parser_profile_revision': 'surya-ocr-2-v1'},
        headers={'If-Match': before.headers['etag']})
    assert stale.status_code == 412
    assert client.get('/api/v1/settings/preferences').json() == saved.json()
    with database[0].transaction() as session:
        assert not list(session.scalars(select(Job)))
        assert not list(session.scalars(select(Task)))


@pytest.mark.parametrize('profile,code,repository', PENDING)
def test_pending_default_and_explicit_parse_and_prepare_refuse_before_queue_or_network(
        client, database, monkeypatch, profile, code, repository):
    db, cfg = database
    seed_editor(db, cfg)
    monkeypatch.setattr(httpx, 'Client', lambda **_: pytest.fail('Unavailable parser must not contact model services'))
    before = client.get('/api/v1/settings/preferences')
    saved = client.patch('/api/v1/settings/preferences',
        json={'parser_profile_revision': profile}, headers={'If-Match': before.headers['etag']})
    assert saved.status_code == 200, saved.text
    for explicit in (False, True):
        body = {'source_asset_id': 'source_pdf'}
        if explicit:
            body['parser_profile_revision'] = profile
        parsed = client.post('/api/v1/documents/doc_fixture/parse', json=body,
            headers={'If-Match': '"1"', 'Idempotency-Key': f'pending-parse-{explicit}'})
        assert parsed.status_code == 409, parsed.text
        assert parsed.json()['error']['code'] == code
    prepared = client.post('/api/v1/settings/parser-models/prepare',
        json={'parser_profile_revision': profile}, headers={'Idempotency-Key': 'pending-prepare'})
    assert prepared.status_code == 409, prepared.text
    assert prepared.json()['error']['code'] == code
    assert client.get('/api/v1/settings/preferences').json() == saved.json()
    with db.transaction() as session:
        assert not list(session.scalars(select(Job)))
        assert not list(session.scalars(select(Task)))


def test_pending_catalog_cannot_be_promoted_by_a_stale_preparation_service(client, monkeypatch):
    calls = []
    def wire(request):
        calls.append(request)
        assert request.method == 'GET' and request.url.path == '/models'
        return httpx.Response(200, json={'models': [
            {'id': profile, 'status': 'ready', 'code': 'STALE_SERVICE_CODE',
             'downloaded_bytes': 999, 'total_bytes': 999}
            for profile, _, _ in PENDING]})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(
        transport=httpx.MockTransport(wire), **kwargs))
    listing = client.get('/api/v1/settings/parser-models')
    assert listing.status_code == 200, listing.text
    rows = {row['id']: row for row in listing.json()['models']}
    for profile, code, repository in PENDING:
        row = rows[profile]
        assert row['status'] == row['availability'] == 'unavailable'
        assert row['code'] == code and row['model_id'] == repository
        assert row.get('downloaded_bytes') is None and row.get('total_bytes') is None
    assert rows['prokope-4b-eagle-eye-v1']['download_bytes'] is None
    assert rows['prokope-4b-eagle-eye-v1']['manifest_id'] is None
    assert rows['prokope-4b-eagle-eye-v1']['memory_reference'] is None
    assert rows[OXR_PROFILE]['download_bytes'] > 0
    assert len(calls) == 1


def write_heartbeat(cfg, *, backend='vllm', age=0):
    stamp = time.time() - age
    body = {'timestamp': stamp, 'service_ready': True,
            'environment': {'detected_at': stamp, 'default': 'dmr', 'backend': backend,
                            'options': [{'id': 'dmr', 'profiles': [OXR_PROFILE]}]}}
    (cfg.parser_outputs / 'heartbeat.json').write_bytes(canonical_bytes(body))


def test_opted_in_oxr_queues_saved_selection_and_explicit_preparation(client, database, monkeypatch):
    db, cfg = database
    seed_editor(db, cfg)
    monkeypatch.setenv('PARSER_DMR_OXR', '1')
    write_heartbeat(cfg)
    monkeypatch.setattr(httpx, 'Client', lambda **_: pytest.fail('Queue admission must not contact model services'))

    before = client.get('/api/v1/settings/preferences')
    saved = client.patch('/api/v1/settings/preferences',
        json={'parser_profile_revision': OXR_PROFILE}, headers={'If-Match': before.headers['etag']})
    assert saved.status_code == 200, saved.text
    assert saved.json()['parser_profile_status'] == 'active'
    parsed = client.post('/api/v1/documents/doc_fixture/parse',
        json={'source_asset_id': 'source_pdf'}, headers={'If-Match': '"1"', 'Idempotency-Key': 'oxr-parse'})
    assert parsed.status_code == 202, parsed.text
    prepared = client.post('/api/v1/settings/parser-models/prepare',
        json={'parser_profile_revision': OXR_PROFILE}, headers={'Idempotency-Key': 'oxr-prepare'})
    assert prepared.status_code == 202, prepared.text
    assert prepared.json()['status'] == 'queued'

    with db.transaction() as session:
        parse = session.scalar(select(Task).where(Task.job_id == parsed.json()['job_id']))
        prep = session.scalar(select(Task).where(Task.job_id == prepared.json()['job_id']))
        assert parse.kind == 'parse'
        assert parse.payload['parser_profile_revision'] == OXR_PROFILE
        assert parse.payload['parser_accelerator'] == 'dmr'
        assert parse.payload['parser_backend'] == 'vllm'
        assert prep.kind == 'prepare_parser_model'
        assert prep.payload == {'parser_profile_revision': OXR_PROFILE, 'backend': 'vllm'}


@pytest.mark.parametrize('heartbeat', ['missing', 'stale', 'mlx'])
def test_opted_in_oxr_requires_a_fresh_vllm_heartbeat(client, database, monkeypatch, heartbeat):
    db, cfg = database
    seed_editor(db, cfg)
    monkeypatch.setenv('PARSER_DMR_OXR', '1')
    if heartbeat != 'missing':
        # A heartbeat that lists OXR on an incompatible engine cannot admit it.
        write_heartbeat(cfg, backend='mlx' if heartbeat == 'mlx' else 'vllm',
                        age=120 if heartbeat == 'stale' else 0)
    monkeypatch.setattr(httpx, 'Client', lambda **_: pytest.fail('Unavailable OXR must not contact model services'))

    parsed = client.post('/api/v1/documents/doc_fixture/parse',
        json={'source_asset_id': 'source_pdf', 'parser_profile_revision': OXR_PROFILE},
        headers={'If-Match': '"1"', 'Idempotency-Key': 'ineligible-oxr-parse'})
    prepared = client.post('/api/v1/settings/parser-models/prepare',
        json={'parser_profile_revision': OXR_PROFILE}, headers={'Idempotency-Key': 'ineligible-oxr-prepare'})
    for result in (parsed, prepared):
        assert result.status_code == 409, result.text
        assert result.json()['error']['code'] == 'PARSER_MODEL_PLUGIN_REQUIRED'
    with db.transaction() as session:
        assert not list(session.scalars(select(Job)))
        assert not list(session.scalars(select(Task)))
