import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition


@pytest_asyncio.fixture(autouse=True)
async def setup_job_queue(db_session):
    from app.services.job_queue import job_queue
    job_queue.set_session_factory(lambda: db_session, owns_session=False)
    yield


@pytest_asyncio.fixture
async def competitions(db_session: AsyncSession):
    comps = []
    for i in range(3):
        comp = Competition(name=f"Comp {i}", url=f"http://example.com/comp{i}")
        db_session.add(comp)
        comps.append(comp)
    await db_session.commit()
    for comp in comps:
        await db_session.refresh(comp)
    return comps


async def test_bulk_action_reimport(client, admin_token, competitions):
    ids = [c.id for c in competitions]
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": ids, "action": "reimport"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 3
    assert len(data["job_ids"]) == 3


async def test_bulk_action_enrich(client, admin_token, competitions):
    ids = [c.id for c in competitions]
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": ids, "action": "enrich"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 3
    assert len(data["job_ids"]) == 3


async def test_bulk_action_reimport_and_enrich(client, admin_token, competitions):
    ids = [c.id for c in competitions]
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": ids, "action": "reimport+enrich"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    # 3 reimport + 3 enrich = 6
    assert data["total"] == 6
    assert len(data["job_ids"]) == 6


async def test_bulk_action_empty_ids(client, admin_token):
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": [], "action": "reimport"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] == 0


async def test_bulk_action_missing_competition(client, admin_token, competitions):
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": [99999], "action": "reimport"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


async def test_bulk_action_requires_admin(client, reader_token, competitions):
    ids = [c.id for c in competitions]
    resp = await client.post(
        "/api/competitions/bulk-action",
        json={"competition_ids": ids, "action": "reimport"},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403
