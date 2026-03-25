import pytest
from sqlalchemy import select, func

from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.user_skater import UserSkater
from app.models.skater_alias import SkaterAlias


@pytest.mark.asyncio
async def test_merge_skaters_basic(client, db_session, admin_token):
    """Merge reassigns scores, category results, creates alias, deletes source."""
    comp = Competition(name="Test Comp", url="http://example.com")
    db_session.add(comp)
    target = Skater(first_name="Alice", last_name="MARTIN", club="ClubA")
    source = Skater(first_name="Alice", last_name="DUPONT", nationality="FRA")
    db_session.add_all([target, source])
    await db_session.flush()

    target_id = target.id
    source_id = source.id

    score = Score(
        competition_id=comp.id, skater_id=source.id,
        segment="FS", category="Novice Dames", total_score=50.0,
    )
    cat_result = CategoryResult(
        competition_id=comp.id, skater_id=source.id,
        category="Novice Dames", overall_rank=1,
    )
    db_session.add_all([score, cat_result])
    await db_session.commit()

    score_id = score.id
    cr_id = cat_result.id

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target_id, "source_ids": [source_id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merged"] == 1
    assert data["aliases_created"] == 1

    # Score reassigned
    row = (await db_session.execute(
        select(Score.skater_id).where(Score.id == score_id)
    )).one()
    assert row[0] == target_id

    # Category result reassigned
    row = (await db_session.execute(
        select(CategoryResult.skater_id).where(CategoryResult.id == cr_id)
    )).one()
    assert row[0] == target_id

    # Source deleted
    count = (await db_session.execute(
        select(func.count()).select_from(Skater).where(Skater.id == source_id)
    )).scalar()
    assert count == 0

    # Alias created
    alias = (await db_session.execute(
        select(SkaterAlias).where(SkaterAlias.last_name == "DUPONT")
    )).scalar_one()
    assert alias.skater_id == target_id

    # Metadata filled (target had no nationality, source had FRA)
    t = (await db_session.execute(
        select(Skater).where(Skater.id == target_id)
    )).scalar_one()
    assert t.nationality == "FRA"
    # Target's existing club preserved
    assert t.club == "ClubA"


@pytest.mark.asyncio
async def test_merge_skaters_duplicate_score(client, db_session, admin_token):
    """When both target and source have a score for the same comp/cat/seg, source's is deleted."""
    comp = Competition(name="Comp", url="http://example.com/2")
    db_session.add(comp)
    target = Skater(first_name="Bob", last_name="TARGET")
    source = Skater(first_name="Bob", last_name="SOURCE")
    db_session.add_all([target, source])
    await db_session.flush()

    target_score = Score(
        competition_id=comp.id, skater_id=target.id,
        segment="SP", category="Junior Messieurs", total_score=60.0,
    )
    source_score = Score(
        competition_id=comp.id, skater_id=source.id,
        segment="SP", category="Junior Messieurs", total_score=55.0,
    )
    target_cr = CategoryResult(
        competition_id=comp.id, skater_id=target.id,
        category="Junior Messieurs", overall_rank=1,
    )
    source_cr = CategoryResult(
        competition_id=comp.id, skater_id=source.id,
        category="Junior Messieurs", overall_rank=2,
    )
    db_session.add_all([target_score, source_score, target_cr, source_cr])
    await db_session.commit()

    target_score_id = target_score.id
    source_score_id = source_score.id
    target_cr_id = target_cr.id
    source_cr_id = source_cr.id

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [source.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Target's score preserved, source's deleted
    row = (await db_session.execute(
        select(Score.total_score).where(Score.id == target_score_id)
    )).one()
    assert row[0] == 60.0

    count = (await db_session.execute(
        select(func.count()).select_from(Score).where(Score.id == source_score_id)
    )).scalar()
    assert count == 0

    # Target's category result preserved, source's deleted
    row = (await db_session.execute(
        select(CategoryResult.overall_rank).where(CategoryResult.id == target_cr_id)
    )).one()
    assert row[0] == 1

    count = (await db_session.execute(
        select(func.count()).select_from(CategoryResult).where(CategoryResult.id == source_cr_id)
    )).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_merge_skaters_user_skater_links(client, db_session, admin_token):
    """UserSkater links are reassigned; duplicates are deleted."""
    from app.models.user import User
    from app.auth.passwords import hash_password

    target = Skater(first_name="Claire", last_name="TARGET")
    source = Skater(first_name="Claire", last_name="SOURCE")
    db_session.add_all([target, source])
    await db_session.flush()

    user = User(
        email="parent@test.com", password_hash=hash_password("pass"),
        display_name="Parent", role="skater",
    )
    db_session.add(user)
    await db_session.flush()

    target_id = target.id
    user_id = user.id

    # User linked to both target and source
    link1 = UserSkater(user_id=user.id, skater_id=target.id)
    link2 = UserSkater(user_id=user.id, skater_id=source.id)
    db_session.add_all([link1, link2])
    await db_session.commit()

    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [source.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Source link deleted (was duplicate), target link preserved
    links = (await db_session.execute(
        select(UserSkater).where(UserSkater.user_id == user_id)
    )).scalars().all()
    assert len(links) == 1
    assert links[0].skater_id == target_id


@pytest.mark.asyncio
async def test_merge_skaters_validation(client, db_session, admin_token):
    """Validation: target must exist, source must not contain target."""
    target = Skater(first_name="D", last_name="TARGET")
    db_session.add(target)
    await db_session.commit()

    # source_ids contains target_id
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": [target.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400

    # target does not exist
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": 99999, "source_ids": [target.id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404

    # empty source_ids
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": target.id, "source_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_merge_skaters_reader_forbidden(client, db_session, reader_token):
    """Non-admin users cannot merge."""
    resp = await client.post(
        "/api/skaters/merge",
        json={"target_id": 1, "source_ids": [2]},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403
