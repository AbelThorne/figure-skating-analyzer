"""
Seed script — bootstraps the DB with the known competitions.
Run from the backend directory:
    uv run python seed.py
"""

import asyncio
from datetime import date as date_type

from sqlalchemy import select

from app.database import async_session_factory, init_db
from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.services.scraper_factory import get_scraper

COMPETITIONS = [
    {
        "name": "Toulouse 2025 - Coupe de l'Automne",
        "url": "http://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/CSNPA_AUTOMNE_2025/index.htm",
        "season": "2025-2026",
    },
    {
        "name": "Nîmes 2025 - TF",
        "url": "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2025-TF-Nimes/index.htm",
        "season": "2025-2026",
    },
    {
        "name": "Nîmes 2026 - TDF",
        "url": "https://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/TDF_C7_NIMES_2026/index.htm",
        "season": "2025-2026",
    },
    {
        "name": "Castres 2026 - CR",
        "url": "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Castres/index.htm",
        "season": "2025-2026",
    },
    {
        "name": "Montpellier 2026 - CR",
        "url": "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Montpellier/index.htm",
        "season": "2025-2026",
    },
    {
        "name": "Toulouse 2026 - SFC-SO",
        "url": "https://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/SFC_SO_2026/index.htm",
        "season": "2025-2026",
    },
]


async def _get_or_create_skater(session, name, nationality, club):
    skater = (
        await session.execute(select(Skater).where(Skater.name == name))
    ).scalar_one_or_none()
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


async def seed():
    await init_db()

    async with async_session_factory() as session:
        for comp_data in COMPETITIONS:
            # Get or create competition
            existing = (
                await session.execute(
                    select(Competition).where(Competition.url == comp_data["url"])
                )
            ).scalar_one_or_none()

            if existing:
                comp = existing
                print(f"[exists] {comp.name}")
            else:
                comp = Competition(**comp_data)
                session.add(comp)
                await session.flush()
                print(f"[created] {comp.name}")

            # Scrape
            scraper = get_scraper(comp.url)
            print(f"  Scraping {comp.url} ...")
            events, results, cat_results, comp_info = await scraper.scrape(comp.url)
            print(f"  Found {len(events)} events, {len(results)} results, {len(cat_results)} category results")

            # Update competition name/date from scraped metadata
            if comp_info.name:
                comp.name = comp_info.name
            if comp_info.date and not comp.date:
                comp.date = date_type.fromisoformat(comp_info.date)

            # Import segment scores
            imported = skipped = 0
            errors = []
            for r in results:
                try:
                    skater = await _get_or_create_skater(session, r.name, r.nationality, r.club)

                    existing_score = (
                        await session.execute(
                            select(Score).where(
                                Score.competition_id == comp.id,
                                Score.skater_id == skater.id,
                                Score.category == r.category,
                                Score.segment == r.segment,
                            )
                        )
                    ).scalar_one_or_none()

                    if existing_score:
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
                    errors.append(f"{r.name}: {e}")

            # Import category results
            cat_imported = cat_skipped = 0
            for cr in cat_results:
                try:
                    skater = await _get_or_create_skater(session, cr.name, cr.nationality, cr.club)

                    existing_cr = (
                        await session.execute(
                            select(CategoryResult).where(
                                CategoryResult.competition_id == comp.id,
                                CategoryResult.skater_id == skater.id,
                                CategoryResult.category == cr.category,
                            )
                        )
                    ).scalar_one_or_none()

                    if existing_cr:
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
                    errors.append(f"{cr.name}: {e}")

            await session.commit()
            print(
                f"  Scores: {imported} imported, {skipped} skipped"
                f" | Cat results: {cat_imported} imported, {cat_skipped} skipped"
                f"{f' | {len(errors)} errors' if errors else ''}"
            )
            for err in errors:
                print(f"    ERROR: {err}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
