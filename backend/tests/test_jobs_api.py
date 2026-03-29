import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.competition import Competition
from app.models.job import Job


@pytest_asyncio.fixture(autouse=True)
async def setup_job_queue(db_session):
    from app.services.job_queue import job_queue
    job_queue.set_session_factory(lambda: db_session)
    yield


@pytest_asyncio.fixture
async def competition(db_session: AsyncSession):
    comp = Competition(name="API Test Comp", url="http://example.com/api-test")
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)
    return comp


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, competition):
    job = Job(
        id="testjob12345",
        type="import",
        trigger="manual",
        competition_id=competition.id,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()
    return job


async def test_list_jobs_requires_admin(client, reader_token):
    resp = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 403


async def test_list_jobs_as_admin(client, admin_token, sample_job):
    resp = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == "testjob12345"
    assert data[0]["competition_name"] == "API Test Comp"
    assert data[0]["trigger"] == "manual"


async def test_get_job_as_admin(client, admin_token, sample_job):
    resp = await client.get("/api/jobs/testjob12345", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "testjob12345"
    assert data["competition_name"] == "API Test Comp"


async def test_get_job_not_found(client, admin_token):
    resp = await client.get("/api/jobs/nonexistent", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404


async def test_cancel_queued_job(client, admin_token, sample_job):
    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_non_queued_job_fails(client, admin_token, sample_job, db_session):
    sample_job.status = "completed"
    await db_session.commit()
    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 400


async def test_cancel_requires_admin(client, reader_token, sample_job):
    resp = await client.post("/api/jobs/testjob12345/cancel", headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 403
