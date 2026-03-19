from __future__ import annotations

from typing import Annotated

from litestar import Router, get, post, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.params import Parameter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.services.downloader import download_competition_pdfs
from app.services.parser import parse_scorecard
from app.services.site_scraper import scrape_competition_site, build_lookup, normalize_name


# --- DTOs (plain dicts for simplicity) ---

def competition_to_dict(c: Competition) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "url": c.url,
        "date": c.date.isoformat() if c.date else None,
        "season": c.season,
        "discipline": c.discipline,
    }


# --- Handlers ---

@get("/")
async def list_competitions(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Competition).order_by(Competition.date.desc()))
    return [competition_to_dict(c) for c in result.scalars()]


@get("/{competition_id:int}")
async def get_competition(competition_id: int, session: AsyncSession) -> dict:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    return competition_to_dict(comp)


@post("/")
async def create_competition(data: dict, session: AsyncSession) -> dict:
    comp = Competition(
        name=data["name"],
        url=data["url"],
        date=data.get("date"),
        season=data.get("season"),
        discipline=data.get("discipline"),
    )
    session.add(comp)
    await session.commit()
    await session.refresh(comp)
    return competition_to_dict(comp)


@delete("/{competition_id:int}", status_code=204)
async def delete_competition(competition_id: int, session: AsyncSession) -> None:
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    await session.delete(comp)
    await session.commit()


@post("/{competition_id:int}/import")
async def import_competition(competition_id: int, session: AsyncSession) -> dict:
    """
    Two-pass import:
    1. Scrape the competition website for competitor metadata (club, birth year, category, etc.)
    2. Download and parse PDF score sheets for scores
    3. Merge both sources by skater name
    """
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")

    # --- Pass 1: scrape site metadata ---
    site_competitors = await scrape_competition_site(comp.url)
    site_lookup = build_lookup(site_competitors)

    # --- Pass 2: download & parse PDFs ---
    pdf_paths = await download_competition_pdfs(comp.url)
    imported = 0
    errors = []

    for pdf_path in pdf_paths:
        try:
            parsed_scores = parse_scorecard(pdf_path)
            for ps in parsed_scores:
                if not ps.skater_name:
                    continue

                # Look up site metadata for this skater
                site_info = site_lookup.get(normalize_name(ps.skater_name))

                # Get or create skater, enriching with site metadata
                result = await session.execute(
                    select(Skater).where(Skater.name == ps.skater_name)
                )
                skater = result.scalar_one_or_none()
                if not skater:
                    skater = Skater(
                        name=ps.skater_name,
                        nationality=ps.nationality or (site_info.nationality if site_info else None),
                        club=site_info.club if site_info else None,
                        birth_year=site_info.birth_year if site_info else None,
                    )
                    session.add(skater)
                    await session.flush()
                else:
                    # Update missing fields from site data
                    if site_info:
                        if not skater.nationality and site_info.nationality:
                            skater.nationality = site_info.nationality
                        if not skater.club and site_info.club:
                            skater.club = site_info.club
                        if not skater.birth_year and site_info.birth_year:
                            skater.birth_year = site_info.birth_year

                score = Score(
                    competition_id=comp.id,
                    skater_id=skater.id,
                    segment=ps.segment or (site_info.segment if site_info else None) or "UNKNOWN",
                    category=site_info.category if site_info else None,
                    starting_number=site_info.starting_number if site_info else None,
                    rank=ps.rank or (site_info.rank if site_info else None),
                    total_score=ps.total_score,
                    technical_score=ps.technical_score,
                    component_score=ps.component_score,
                    deductions=ps.deductions,
                    pdf_path=str(pdf_path),
                    raw_data=ps.raw_data,
                )
                session.add(score)
                imported += 1
        except Exception as e:
            errors.append({"file": str(pdf_path), "error": str(e)})

    await session.commit()
    return {
        "competition_id": competition_id,
        "site_competitors_found": len(site_competitors),
        "pdfs_downloaded": len(pdf_paths),
        "scores_imported": imported,
        "errors": errors,
    }


router = Router(
    path="/api/competitions",
    route_handlers=[
        list_competitions,
        get_competition,
        create_competition,
        delete_competition,
        import_competition,
    ],
    dependencies={"session": Provide(get_session)},
)
