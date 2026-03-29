import asyncio
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import select

from app.models.competition import Competition
from app.models.job import Job
from app.services.job_queue import JobQueue


@pytest_asyncio.fixture
async def competition(db_session):
    comp = Competition(
        name="Test Competition",
        url="http://example.com/comp",
        season="2025-2026",
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)
    return comp


@pytest_asyncio.fixture
async def queue(db_session):
    q = JobQueue()
    q.set_session_factory(lambda: db_session, owns_session=False)
    return q


async def test_create_job_persists(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    assert job["id"] is not None
    assert job["type"] == "import"
    assert job["competition_id"] == competition.id
    assert job["status"] == "queued"

    row = await db_session.get(Job, job["id"])
    assert row is not None
    assert row.type == "import"
    assert row.status == "queued"
    assert row.trigger == "manual"


async def test_list_jobs_from_db(queue, competition):
    await queue.create_job("import", competition.id)
    await queue.create_job("enrich", competition.id)

    jobs = await queue.list_jobs()
    assert len(jobs) == 2
    # Newest first
    assert jobs[0]["type"] == "enrich"
    assert jobs[1]["type"] == "import"


async def test_get_job_from_db(queue, competition):
    job = await queue.create_job("import", competition.id)
    fetched = await queue.get_job(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]
    assert fetched["competition_name"] == "Test Competition"


async def test_get_job_not_found(queue):
    result = await queue.get_job("nonexistent")
    assert result is None


async def test_cancel_queued_job(queue, competition):
    job = await queue.create_job("import", competition.id)
    result = await queue.cancel_job(job["id"])
    assert result is True

    fetched = await queue.get_job(job["id"])
    assert fetched["status"] == "cancelled"
    assert fetched["completed_at"] is not None


async def test_cancel_running_job_fails(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    # Manually set to running
    row = await db_session.get(Job, job["id"])
    row.status = "running"
    await db_session.commit()

    result = await queue.cancel_job(job["id"])
    assert result is False


async def test_cancel_nonexistent_job_fails(queue):
    result = await queue.cancel_job("nonexistent")
    assert result is False


async def test_cleanup_old_jobs(queue, competition, db_session):
    # Create an old job (10 days ago)
    old_job = await queue.create_job("import", competition.id)
    row = await db_session.get(Job, old_job["id"])
    row.status = "completed"
    row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    row.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    await db_session.commit()

    # Create a recent job (1 day ago)
    recent_job = await queue.create_job("enrich", competition.id)
    row2 = await db_session.get(Job, recent_job["id"])
    row2.status = "completed"
    row2.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    row2.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    await db_session.commit()

    deleted = await queue.cleanup(days=7)
    assert deleted >= 1

    # Old job should be gone
    assert await db_session.get(Job, old_job["id"]) is None
    # Recent job should still exist
    assert await db_session.get(Job, recent_job["id"]) is not None


async def test_cleanup_marks_stale_running_as_failed(queue, competition, db_session):
    job = await queue.create_job("import", competition.id)
    row = await db_session.get(Job, job["id"])
    row.status = "running"
    row.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    await db_session.commit()

    await queue.cleanup(days=7)

    await db_session.refresh(row)
    assert row.status == "failed"
    assert row.error == "Server restarted during execution"
    assert row.completed_at is not None


async def test_worker_processes_and_persists(queue, competition, db_session):
    async def handler(job):
        return {"scores_imported": 5}

    queue.set_handler(handler)
    job = await queue.create_job("import", competition.id)
    await queue.start_worker()

    await asyncio.wait_for(queue._queue.join(), timeout=2.0)
    await queue.stop_worker()

    row = await db_session.get(Job, job["id"])
    await db_session.refresh(row)
    assert row.status == "completed"
    assert row.result == {"scores_imported": 5}
    assert row.started_at is not None
    assert row.completed_at is not None


async def test_worker_handles_failure_and_persists(queue, competition, db_session):
    async def handler(job):
        raise ValueError("scrape failed")

    queue.set_handler(handler)
    job = await queue.create_job("import", competition.id)
    await queue.start_worker()

    await asyncio.wait_for(queue._queue.join(), timeout=2.0)
    await queue.stop_worker()

    row = await db_session.get(Job, job["id"])
    await db_session.refresh(row)
    assert row.status == "failed"
    assert "scrape failed" in row.error
    assert row.completed_at is not None
