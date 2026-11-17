from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from packages.domain.errors import DomainError
from packages.domain.models import Attempt, Job, Permit, Task, new_id, now
from packages.jobs.queue import assert_current, claim, recover_expired

pytestmark = pytest.mark.postgres


def make_job(db):
    with db.transaction() as session:
        job = Job(id=new_id('job'), stage='translate', budget_micro=100)
        session.add(job)
        session.flush()
        session.add(Task(id=new_id('task'), job_id=job.id, kind='translate'))
    return job


def test_expired_local_fence_cannot_commit(database):
    db, _ = database
    make_job(db)
    old = claim(db)
    with db.transaction() as session:
        session.get(Task, old.task_id).lease_expires = now() - timedelta(seconds=1)
    recover_expired(db)
    new = claim(db)
    assert new.fence > old.fence
    with pytest.raises(DomainError, match='Fence expired'):
        with db.transaction() as session:
            assert_current(session, old)


def test_pending_task_waits_for_not_before_after_wall_clock_moves_back(database, monkeypatch):
    db, _ = database
    job = make_job(db)
    available_at = now()
    with db.transaction() as session:
        task = session.scalar(select(Task).where(Task.job_id == job.id))
        task.available_at = available_at
        task_id = task.id
    clock = [available_at - timedelta(milliseconds=50)]
    monkeypatch.setattr('packages.jobs.queue.now', lambda: clock[0])
    assert claim(db) is None
    with db.transaction() as session:
        assert session.get(Task, task_id).status == 'pending'
        assert session.get(Job, job.id).status == 'pending'
    clock[0] = available_at + timedelta(milliseconds=1)
    lease = claim(db)
    assert lease is not None and lease.task_id == task_id


def test_fixture_clock_keeps_new_work_due_when_system_wall_clock_moves_back(database, monkeypatch):
    from packages.domain import models
    from tests.conftest import monotonic_datetime
    db, _ = database
    wall = [datetime(2026, 11, 4, tzinfo=timezone.utc)]
    elapsed = [0.0]
    clock = monotonic_datetime(utc_now=lambda tz: wall[0], elapsed=lambda: elapsed[0])
    monkeypatch.setattr(models, 'datetime', clock)
    job = make_job(db)
    wall[0] -= timedelta(seconds=3)
    elapsed[0] += .16
    lease = claim(db)
    assert lease is not None and lease.job_id == job.id


def test_dispatched_timeout_keeps_risk_and_never_reclaims(database):
    db, _ = database
    job = make_job(db)
    lease = claim(db)
    with db.transaction() as session:
        session.get(Task, lease.task_id).lease_expires = now() - timedelta(seconds=1)
        session.get(Attempt, lease.attempt_id).state = 'dispatching'
        session.add(Permit(id=new_id('permit'), attempt_id=lease.attempt_id, job_id=job.id, control_epoch=0, price_snapshot={'version': 'test'}, reserved_micro=80))
    recover_expired(db)
    assert claim(db) is None
    with db.transaction() as session:
        assert session.get(Job, job.id).status == 'outcome_unknown'
        permit = session.scalar(select(Permit))
        assert permit.state == 'unknown' and permit.reserved_micro == 80
