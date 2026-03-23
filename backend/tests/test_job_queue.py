import pytest
from app.services.job_queue import JobQueue


def test_create_job():
    q = JobQueue()
    job = q.create_job("import", competition_id=1)
    assert job["id"] is not None
    assert job["type"] == "import"
    assert job["competition_id"] == 1
    assert job["status"] == "queued"
    assert job["result"] is None
    assert job["error"] is None


def test_get_job():
    q = JobQueue()
    job = q.create_job("enrich", competition_id=2)
    fetched = q.get_job(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]


def test_get_job_not_found():
    q = JobQueue()
    assert q.get_job("nonexistent") is None


def test_list_jobs():
    q = JobQueue()
    q.create_job("import", competition_id=1)
    q.create_job("enrich", competition_id=2)
    jobs = q.list_jobs()
    assert len(jobs) == 2


import asyncio


@pytest.mark.asyncio
async def test_worker_processes_job():
    q = JobQueue()
    results = []

    async def handler(job):
        results.append(job["id"])
        return {"scores_imported": 5}

    q.set_handler(handler)
    job = q.create_job("import", competition_id=1)
    await q.start_worker()

    # Wait for processing
    await asyncio.wait_for(q._queue.join(), timeout=2.0)
    await q.stop_worker()

    assert job["status"] == "completed"
    assert job["result"] == {"scores_imported": 5}
    assert len(results) == 1


@pytest.mark.asyncio
async def test_worker_handles_failure():
    q = JobQueue()

    async def handler(job):
        raise ValueError("scrape failed")

    q.set_handler(handler)
    job = q.create_job("import", competition_id=1)
    await q.start_worker()

    await asyncio.wait_for(q._queue.join(), timeout=2.0)
    await q.stop_worker()

    assert job["status"] == "failed"
    assert "scrape failed" in job["error"]


@pytest.mark.asyncio
async def test_worker_sequential_processing():
    q = JobQueue()
    order = []

    async def handler(job):
        order.append(job["competition_id"])
        await asyncio.sleep(0.01)
        return {}

    q.set_handler(handler)
    q.create_job("import", competition_id=1)
    q.create_job("enrich", competition_id=2)
    q.create_job("import", competition_id=3)
    await q.start_worker()

    await asyncio.wait_for(q._queue.join(), timeout=5.0)
    await q.stop_worker()

    assert order == [1, 2, 3]
