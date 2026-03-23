# backend/app/services/import_service.py
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.services.scraper_factory import get_scraper
from app.services.downloader import download_pdfs, url_to_slug
from app.services.parser import parse_elements, extract_segment_code


async def _get_or_create_skater(
    session: AsyncSession,
    name: str,
    nationality: str | None,
    club: str | None,
) -> Skater:
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


async def run_import(session: AsyncSession, competition_id: int, force: bool = False) -> dict:
    """Import competition results. Returns the import result dict."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise ValueError(f"Competition {competition_id} not found")

    if force:
        await session.execute(
            sa_delete(Score).where(Score.competition_id == competition_id)
        )
        await session.execute(
            sa_delete(CategoryResult).where(CategoryResult.competition_id == competition_id)
        )
        await session.flush()

    scraper = get_scraper(comp.url)
    events, results, cat_results, comp_info, index_html = await scraper.scrape(comp.url)

    if comp_info.name and (comp.name == comp.url or not comp.name or comp.name == "index.htm"):
        comp.name = comp_info.name
    if comp_info.date and not comp.date:
        comp.date = date_type.fromisoformat(comp_info.date)

    # Detect metadata from URL + HTML content
    from app.services.competition_metadata import detect_metadata
    meta = detect_metadata(comp.url, index_html)
    if not comp.metadata_confirmed:
        # Overwrite all detectable fields when metadata is not yet confirmed
        if meta["competition_type"]:
            comp.competition_type = meta["competition_type"]
        if meta["city"]:
            comp.city = meta["city"]
        if meta["country"]:
            comp.country = meta["country"]
        if meta["season"]:
            comp.season = meta["season"]

    imported = 0
    skipped = 0
    cat_imported = 0
    cat_skipped = 0
    errors = []

    for r in results:
        try:
            skater = await _get_or_create_skater(session, r.name, r.nationality, r.club)
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

    for cr in cat_results:
        try:
            skater = await _get_or_create_skater(session, cr.name, cr.nationality, cr.club)
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
        **import_log,
    }


async def run_enrich(session: AsyncSession, competition_id: int, force: bool = False) -> dict:
    """Enrich scores with PDF element details. Returns the enrich result dict."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise ValueError(f"Competition {competition_id} not found")

    scraper = get_scraper(comp.url)
    events, _, _, _, _ = await scraper.scrape(comp.url)
    pdf_urls = [e.pdf_url for e in events if e.pdf_url]

    if not pdf_urls:
        return {"competition_id": competition_id, "pdfs_downloaded": 0, "scores_enriched": 0, "errors": []}

    slug = url_to_slug(comp.url)
    pdf_paths = await download_pdfs(pdf_urls, slug)

    enriched = 0
    unmatched = []
    errors = []

    for pdf_path in pdf_paths:
        try:
            parsed = parse_elements(pdf_path)
            for entry in parsed:
                skater_name = entry["skater_name"]
                elements = entry["elements"]
                seg_code = extract_segment_code(entry.get("category_segment"))
                stmt = (
                    select(Score)
                    .join(Skater)
                    .where(
                        Score.competition_id == comp.id,
                        Skater.name == skater_name,
                    )
                )
                if seg_code:
                    stmt = stmt.where(Score.segment == seg_code)
                result = await session.execute(stmt)
                scores = result.scalars().all()
                if scores:
                    for score in scores:
                        if not score.elements or force:
                            score.elements = elements
                            score.pdf_path = str(pdf_path)
                            enriched += 1
                else:
                    unmatched.append(skater_name)
        except Exception as e:
            errors.append({"file": str(pdf_path), "error": str(e)})

    await session.commit()
    return {
        "competition_id": competition_id,
        "pdfs_downloaded": len(pdf_paths),
        "scores_enriched": enriched,
        "unmatched": unmatched,
        "errors": errors,
    }
