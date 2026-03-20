from __future__ import annotations

from datetime import date as date_type

from litestar import Router, get, post, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.services.scraper_factory import get_scraper
from app.services.downloader import download_pdfs, url_to_slug
from app.services.parser import parse_elements


# --- DTOs ---

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


async def _get_or_create_skater(
    session: AsyncSession,
    name: str,
    nationality: str | None,
    club: str | None,
) -> Skater:
    """Get an existing skater by name or create a new one."""
    stmt = select(Skater).where(Skater.name == name)
    skater = (await session.execute(stmt)).scalar_one_or_none()
    if not skater:
        skater = Skater(name=name, nationality=nationality, club=club)
        session.add(skater)
        await session.flush()
    else:
        if not skater.nationality and nationality:
            skater.nationality = nationality
        if not skater.club and club:
            skater.club = club
    return skater


@post("/{competition_id:int}/import")
async def import_competition(competition_id: int, session: AsyncSession, force: bool = False) -> dict:
    """Import competition results from website HTML (SEG + CAT pages)."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")

    if force:
        await session.execute(
            sa_delete(Score).where(Score.competition_id == competition_id)
        )
        await session.execute(
            sa_delete(CategoryResult).where(CategoryResult.competition_id == competition_id)
        )
        await session.flush()

    scraper = get_scraper(comp.url)
    events, results, cat_results, comp_info = await scraper.scrape(comp.url)

    # Update competition name and date from scraped metadata
    if comp_info.name and (comp.name == comp.url or not comp.name or comp.name == "index.htm"):
        comp.name = comp_info.name
    if comp_info.date and not comp.date:
        comp.date = date_type.fromisoformat(comp_info.date)

    imported = 0
    skipped = 0
    cat_imported = 0
    cat_skipped = 0
    errors = []

    # --- Import segment scores ---
    for r in results:
        try:
            skater = await _get_or_create_skater(session, r.name, r.nationality, r.club)

            # Check for existing score (idempotency)
            existing = await session.execute(
                select(Score).where(
                    Score.competition_id == comp.id,
                    Score.skater_id == skater.id,
                    Score.category == r.category,
                    Score.segment == r.segment,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            score = Score(
                competition_id=comp.id,
                skater_id=skater.id,
                segment=r.segment or "UNKNOWN",
                category=r.category,
                rank=r.rank,
                total_score=r.total_score,
                technical_score=r.technical_score,
                component_score=r.component_score,
                components=r.components,
                deductions=r.deductions,
                starting_number=r.starting_number,
                event_date=date_type.fromisoformat(r.event_date) if r.event_date else None,
            )
            session.add(score)
            imported += 1
        except Exception as e:
            errors.append({"skater": r.name, "error": str(e)})

    # --- Import category results (overall standings) ---
    for cr in cat_results:
        try:
            skater = await _get_or_create_skater(session, cr.name, cr.nationality, cr.club)

            # Check for existing category result (idempotency)
            existing = await session.execute(
                select(CategoryResult).where(
                    CategoryResult.competition_id == comp.id,
                    CategoryResult.skater_id == skater.id,
                    CategoryResult.category == cr.category,
                )
            )
            if existing.scalar_one_or_none():
                cat_skipped += 1
                continue

            cat_result = CategoryResult(
                competition_id=comp.id,
                skater_id=skater.id,
                category=cr.category or "UNKNOWN",
                overall_rank=cr.overall_rank,
                combined_total=cr.combined_total,
                segment_count=cr.segment_count,
                sp_rank=cr.sp_rank,
                fs_rank=cr.fs_rank,
            )
            session.add(cat_result)
            cat_imported += 1
        except Exception as e:
            errors.append({"skater": cr.name, "error": str(e)})

    status = "success" if not errors else "partial"
    import_log = {
        "status": status,
        "events_found": len(events),
        "scores_imported": imported,
        "scores_skipped": skipped,
        "category_results_imported": cat_imported,
        "category_results_skipped": cat_skipped,
        "errors": errors,
    }
    comp.last_import_log = import_log
    await session.commit()

    return {
        "competition_id": competition_id,
        "status": status,
        "events_found": len(events),
        "scores_imported": imported,
        "scores_skipped": skipped,
        "category_results_imported": cat_imported,
        "category_results_skipped": cat_skipped,
        "errors": errors,
    }


@get("/{competition_id:int}/import-status")
async def get_import_status(competition_id: int, session: AsyncSession) -> dict:
    """Return the last import log for a competition."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    if comp.last_import_log is None:
        return {"status": "never_imported"}
    return comp.last_import_log


@post("/{competition_id:int}/enrich")
async def enrich_competition(competition_id: int, session: AsyncSession, force: bool = False) -> dict:
    """Enrich existing scores with element details from PDF score cards."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")

    # Discover PDF URLs from site
    scraper = get_scraper(comp.url)
    events, _, _, _ = await scraper.scrape(comp.url)
    pdf_urls = [e.pdf_url for e in events if e.pdf_url]

    if not pdf_urls:
        return {"competition_id": competition_id, "pdfs_downloaded": 0, "scores_enriched": 0, "errors": []}

    # Download PDFs
    slug = url_to_slug(comp.url)
    pdf_paths = await download_pdfs(pdf_urls, slug)

    # Parse elements and match to scores
    enriched = 0
    unmatched = []
    errors = []

    for pdf_path in pdf_paths:
        try:
            parsed = parse_elements(pdf_path)
            for entry in parsed:
                skater_name = entry["skater_name"]
                elements = entry["elements"]

                # Find all matching scores for this skater in this competition
                result = await session.execute(
                    select(Score)
                    .join(Skater)
                    .where(
                        Score.competition_id == comp.id,
                        Skater.name == skater_name,
                    )
                )
                scores = result.scalars().all()
                if scores:
                    for score in scores:
                        if not score.elements or force:  # don't overwrite unless forced
                            score.elements = elements
                            score.pdf_path = str(pdf_path)
                            enriched += 1
                else:
                    unmatched.append(skater_name)
        except Exception as e:  # noqa: BLE001 — intentional: enrich is fault-tolerant per PDF
            errors.append({"file": str(pdf_path), "error": str(e)})

    await session.commit()
    return {
        "competition_id": competition_id,
        "pdfs_downloaded": len(pdf_paths),
        "scores_enriched": enriched,
        "unmatched": unmatched,
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
        get_import_status,
        enrich_competition,
    ],
    dependencies={"session": Provide(get_session)},
)
