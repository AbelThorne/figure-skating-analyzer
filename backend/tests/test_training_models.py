import pytest
from datetime import date


async def test_create_weekly_review(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.weekly_review import WeeklyReview
    from app.auth.passwords import hash_password

    skater = Skater(first_name="Alice", last_name="Dupont", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    review = WeeklyReview(
        skater_id=skater.id,
        coach_id=coach.id,
        week_start=date(2026, 3, 23),
        attendance="3/4",
        engagement=4,
        progression=3,
        attitude=5,
        strengths="Bon travail sur les sauts",
        improvements="Travailler les pirouettes",
        visible_to_skater=True,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    assert review.id is not None
    assert review.week_start == date(2026, 3, 23)
    assert review.engagement == 4
    assert review.visible_to_skater is True


async def test_weekly_review_unique_constraint(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.weekly_review import WeeklyReview
    from app.auth.passwords import hash_password
    from sqlalchemy.exc import IntegrityError

    skater = Skater(first_name="Bob", last_name="Martin", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach2@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach2",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    review1 = WeeklyReview(
        skater_id=skater.id, coach_id=coach.id, week_start=date(2026, 3, 23),
        attendance="4/4", engagement=3, progression=3, attitude=3,
        strengths="", improvements="", visible_to_skater=True,
    )
    db_session.add(review1)
    await db_session.commit()

    review2 = WeeklyReview(
        skater_id=skater.id, coach_id=coach.id, week_start=date(2026, 3, 23),
        attendance="3/4", engagement=4, progression=4, attitude=4,
        strengths="", improvements="", visible_to_skater=True,
    )
    db_session.add(review2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_create_incident(db_session):
    from app.models.skater import Skater
    from app.models.user import User
    from app.models.incident import Incident
    from app.auth.passwords import hash_password

    skater = Skater(first_name="Claire", last_name="Duval", club="TestClub")
    db_session.add(skater)
    coach = User(
        email="coach3@test.com",
        password_hash=hash_password("pass"),
        display_name="Coach3",
        role="coach",
    )
    db_session.add(coach)
    await db_session.flush()

    incident = Incident(
        skater_id=skater.id,
        coach_id=coach.id,
        date=date(2026, 3, 24),
        incident_type="injury",
        description="Chute sur un axel, douleur au genou",
        visible_to_skater=False,
    )
    db_session.add(incident)
    await db_session.commit()
    await db_session.refresh(incident)

    assert incident.id is not None
    assert incident.incident_type == "injury"
    assert incident.visible_to_skater is False
