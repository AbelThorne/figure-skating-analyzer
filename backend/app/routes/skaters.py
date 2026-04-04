from __future__ import annotations

from typing import Optional

from litestar import Request, Router, delete, get, patch, post
from litestar.di import Provide
from litestar.exceptions import ClientException, NotFoundException
from sqlalchemy import func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.guards import reject_skater_role, require_admin, require_skater_access
from app.models.user_skater import UserSkater
from app.models.skater_alias import SkaterAlias
from app.config import PDF_DIR
from app.database import get_session
from app.models.skater import Skater
from app.models.score import Score
from app.models.competition import Competition
from app.models.category_result import CategoryResult


@get("/")
async def list_skaters(request: Request, session: AsyncSession, club: Optional[str] = None, search: Optional[str] = None, training_tracked: Optional[bool] = None) -> list[dict]:
    reject_skater_role(request)
    stmt = select(Skater)
    if club:
        stmt = stmt.where(
            or_(
                func.lower(Skater.club) == club.lower(),
                Skater.id.in_(
                    select(Score.skater_id).where(func.lower(Score.club) == club.lower())
                ),
            )
        )
    if training_tracked is not None:
        stmt = stmt.where(Skater.training_tracked == training_tracked)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (Skater.first_name.ilike(pattern)) | (Skater.last_name.ilike(pattern))
        )
    result = await session.execute(stmt)
    skaters = sorted(result.scalars(), key=lambda s: (s.last_name.upper(), s.first_name.upper()))
    return [_skater_to_dict(s) for s in skaters]


@get("/{skater_id:int}")
async def get_skater(skater_id: int, request: Request, session: AsyncSession) -> dict:
    await require_skater_access(request, skater_id, session)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")
    return _skater_to_dict(skater)


def _skater_to_dict(s: Skater) -> dict:
    return {
        "id": s.id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "nationality": s.nationality,
        "club": s.club,
        "birth_year": s.birth_year,
        "training_tracked": s.training_tracked,
        "manual_create": s.manual_create,
    }


@get("/{skater_id:int}/elements")
async def get_skater_elements(
    skater_id: int,
    request: Request,
    session: AsyncSession,
    element_type: Optional[str] = None,
    season: Optional[str] = None,
) -> list[dict]:
    await require_skater_access(request, skater_id, session)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .options(selectinload(Score.competition))
        .order_by(Competition.date)
        .join(Score.competition)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()

    records = []
    for s in scores:
        if not s.elements:
            continue
        for element in s.elements:
            name = element.get("name", "")
            if element_type is not None and not name.lower().startswith(element_type.lower()):
                continue
            records.append({
                "score_id": s.id,
                "competition_id": s.competition_id,
                "competition_name": s.competition.name if s.competition else None,
                "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
                "segment": s.segment,
                "category": s.category,
                "element_name": name,
                "base_value": element.get("base_value"),
                "goe": element.get("goe"),
                "judges": element.get("judge_goe") or element.get("judges"),
                "total": element.get("score") or element.get("total"),
                "markers": element.get("markers") or [],
            })
    return records


@get("/{skater_id:int}/element-names")
async def get_skater_element_names(
    skater_id: int,
    request: Request,
    session: AsyncSession,
) -> list[str]:
    """Return distinct element names seen in competition for this skater."""
    await require_skater_access(request, skater_id, session)
    stmt = select(Score).where(Score.skater_id == skater_id)
    result = await session.execute(stmt)
    names: set[str] = set()
    for s in result.scalars().all():
        if not s.elements:
            continue
        for element in s.elements:
            name = element.get("name", "")
            if name:
                names.add(name)
    return sorted(names)


@get("/{skater_id:int}/scores")
async def get_skater_scores(skater_id: int, request: Request, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    await require_skater_access(request, skater_id, session)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(Score)
        .where(Score.skater_id == skater_id)
        .join(Score.competition)
        .options(selectinload(Score.competition))
        .order_by(Score.id)
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    scores = result.scalars().all()
    return [
        {
            "id": s.id,
            "competition_id": s.competition_id,
            "competition_name": s.competition.name if s.competition else None,
            "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
            "segment": s.segment,
            "category": s.category,
            "starting_number": s.starting_number,
            "rank": s.rank,
            "total_score": s.total_score,
            "technical_score": s.technical_score,
            "component_score": s.component_score,
            "deductions": s.deductions,
            "components": s.components,
            "elements": s.elements,
            "skating_level": s.skating_level,
            "age_group": s.age_group,
            "gender": s.gender,
            "event_date": s.event_date.isoformat() if s.event_date else None,
            "pdf_url": _pdf_serving_url(s.pdf_path),
            "skater_club": s.club or (skater.club if skater else None),
        }
        for s in scores
    ]


def _pdf_serving_url(pdf_path: str | None) -> str | None:
    """Convert an absolute pdf_path to a /api/pdfs/... serving URL."""
    if not pdf_path:
        return None
    from pathlib import Path
    try:
        rel = Path(pdf_path).relative_to(PDF_DIR)
        return f"/api/pdfs/{rel}"
    except ValueError:
        return None


@get("/{skater_id:int}/category-results")
async def get_skater_category_results(skater_id: int, request: Request, session: AsyncSession, season: Optional[str] = None) -> list[dict]:
    await require_skater_access(request, skater_id, session)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    stmt = (
        select(CategoryResult)
        .where(CategoryResult.skater_id == skater_id)
        .options(selectinload(CategoryResult.competition))
        .join(CategoryResult.competition)
        .order_by(Competition.date.desc())
    )
    if season:
        stmt = stmt.where(Competition.season == season)

    result = await session.execute(stmt)
    cat_results = result.scalars().all()
    return [
        {
            "id": cr.id,
            "competition_id": cr.competition_id,
            "competition_name": cr.competition.name if cr.competition else None,
            "competition_date": cr.competition.date.isoformat() if cr.competition and cr.competition.date else None,
            "category": cr.category,
            "overall_rank": cr.overall_rank,
            "combined_total": cr.combined_total,
            "segment_count": cr.segment_count,
            "sp_rank": cr.sp_rank,
            "fs_rank": cr.fs_rank,
            "skating_level": cr.skating_level,
            "age_group": cr.age_group,
            "gender": cr.gender,
        }
        for cr in cat_results
    ]


@get("/{skater_id:int}/seasons")
async def get_skater_seasons(skater_id: int, request: Request, session: AsyncSession) -> list[str]:
    await require_skater_access(request, skater_id, session)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    score_comp_ids = select(Score.competition_id).where(Score.skater_id == skater_id)
    cat_comp_ids = select(CategoryResult.competition_id).where(CategoryResult.skater_id == skater_id)
    all_comp_ids = union_all(score_comp_ids, cat_comp_ids).subquery()

    stmt = (
        select(Competition.season)
        .join(all_comp_ids, Competition.id == all_comp_ids.c.competition_id)
        .where(Competition.season.isnot(None))
        .distinct()
        .order_by(Competition.season.desc())
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


@post("/merge", status_code=200)
async def merge_skaters(request: Request, session: AsyncSession, data: dict) -> dict:
    require_admin(request)

    target_id = data.get("target_id")
    source_ids = data.get("source_ids", [])

    if not source_ids:
        raise ClientException(detail="source_ids must not be empty", status_code=400)
    if target_id in source_ids:
        raise ClientException(detail="target_id must not be in source_ids", status_code=400)

    target = await session.get(Skater, target_id)
    if not target:
        raise NotFoundException(detail=f"Target skater {target_id} not found")

    sources = []
    for sid in source_ids:
        s = await session.get(Skater, sid)
        if not s:
            raise NotFoundException(detail=f"Source skater {sid} not found")
        sources.append(s)

    aliases_created = 0
    for source in sources:
        # 1. Reassign scores (delete on conflict)
        source_scores = (await session.execute(
            select(Score).where(Score.skater_id == source.id)
        )).scalars().all()
        for score in source_scores:
            existing = (await session.execute(
                select(Score).where(
                    Score.skater_id == target.id,
                    Score.competition_id == score.competition_id,
                    Score.category == score.category,
                    Score.segment == score.segment,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(score)
            else:
                score.skater_id = target.id

        # 2. Reassign category results (delete on conflict)
        source_crs = (await session.execute(
            select(CategoryResult).where(CategoryResult.skater_id == source.id)
        )).scalars().all()
        for cr in source_crs:
            existing = (await session.execute(
                select(CategoryResult).where(
                    CategoryResult.skater_id == target.id,
                    CategoryResult.competition_id == cr.competition_id,
                    CategoryResult.category == cr.category,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(cr)
            else:
                cr.skater_id = target.id

        # 3. Reassign user_skater links (delete on conflict)
        source_links = (await session.execute(
            select(UserSkater).where(UserSkater.skater_id == source.id)
        )).scalars().all()
        for link in source_links:
            existing = (await session.execute(
                select(UserSkater).where(
                    UserSkater.user_id == link.user_id,
                    UserSkater.skater_id == target.id,
                )
            )).scalar_one_or_none()
            if existing:
                await session.delete(link)
            else:
                link.skater_id = target.id

        # 4. Flush before deleting source (no CASCADE on Score/CategoryResult FKs)
        await session.flush()

        # 5. Fill blank metadata
        if not target.nationality and source.nationality:
            target.nationality = source.nationality
        if not target.club and source.club:
            target.club = source.club
        if not target.birth_year and source.birth_year:
            target.birth_year = source.birth_year

        # 6. Create alias
        existing_alias = (await session.execute(
            select(SkaterAlias).where(
                SkaterAlias.first_name == source.first_name,
                SkaterAlias.last_name == source.last_name,
            )
        )).scalar_one_or_none()
        if existing_alias and existing_alias.skater_id != target.id:
            raise ClientException(
                detail=f"Alias conflict: {source.first_name} {source.last_name} is already an alias for skater {existing_alias.skater_id}",
                status_code=400,
            )
        if not existing_alias:
            session.add(SkaterAlias(
                first_name=source.first_name,
                last_name=source.last_name,
                skater_id=target.id,
            ))
            aliases_created += 1

        # 7. Delete source
        await session.delete(source)

    await session.commit()
    return {"merged": len(sources), "aliases_created": aliases_created}


@patch("/{skater_id:int}")
async def update_skater(skater_id: int, request: Request, session: AsyncSession, data: dict) -> dict:
    """Update skater fields. Admin only.

    All skaters: training_tracked can be toggled.
    Manual-create skaters: first_name, last_name, nationality, club are also editable.
    """
    require_admin(request)
    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    if "training_tracked" in data:
        skater.training_tracked = bool(data["training_tracked"])

    # Only allow editing identity fields on manually created skaters
    if skater.manual_create:
        for field in ("first_name", "last_name", "nationality", "club"):
            if field in data:
                setattr(skater, field, data[field])

    await session.commit()
    await session.refresh(skater)
    return _skater_to_dict(skater)


@post("/", status_code=201)
async def create_skater(request: Request, session: AsyncSession, data: dict) -> dict:
    """Create a manual skater (no competition scores). Admin only."""
    require_admin(request)

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    if not last_name:
        raise ClientException(detail="last_name is required", status_code=400)

    # Check for duplicate
    existing = (await session.execute(
        select(Skater).where(
            func.lower(Skater.first_name) == first_name.lower(),
            func.lower(Skater.last_name) == last_name.lower(),
        )
    )).scalar_one_or_none()
    if existing:
        raise ClientException(detail=f"Un patineur nommé {first_name} {last_name} existe déjà", status_code=409)

    skater = Skater(
        first_name=first_name,
        last_name=last_name,
        nationality=data.get("nationality"),
        club=data.get("club"),
        manual_create=True,
        training_tracked=True,
    )
    session.add(skater)
    await session.commit()
    await session.refresh(skater)
    return _skater_to_dict(skater)


@delete("/{skater_id:int}/training-data", status_code=200)
async def clear_training_data(skater_id: int, request: Request, session: AsyncSession) -> dict:
    """Delete all training reviews and incidents for a skater. Admin only."""
    require_admin(request)
    from app.models.weekly_review import WeeklyReview
    from app.models.incident import Incident

    skater = await session.get(Skater, skater_id)
    if not skater:
        raise NotFoundException(f"Skater {skater_id} not found")

    reviews = (await session.execute(
        select(WeeklyReview).where(WeeklyReview.skater_id == skater_id)
    )).scalars().all()
    incidents = (await session.execute(
        select(Incident).where(Incident.skater_id == skater_id)
    )).scalars().all()

    count = len(reviews) + len(incidents)
    for r in reviews:
        await session.delete(r)
    for i in incidents:
        await session.delete(i)

    await session.commit()
    return {"deleted": count}


router = Router(
    path="/api/skaters",
    route_handlers=[
        list_skaters, get_skater, get_skater_elements, get_skater_element_names, get_skater_scores,
        get_skater_category_results, get_skater_seasons, merge_skaters,
        update_skater, create_skater, clear_training_data,
    ],
    dependencies={"session": Provide(get_session)},
)
