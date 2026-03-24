# PDF Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate on-demand PDF season reports for individual skaters and the club, using WeasyPrint (HTML→PDF) with Jinja2 templates. Tables and text only, no charts.

**Architecture:** New `backend/app/routes/reports.py` router exposes two GET endpoints that query the DB, render Jinja2 HTML templates, convert to PDF via WeasyPrint, and stream the result. A `report_data.py` service handles data aggregation. Frontend adds download buttons on existing pages.

**Tech Stack:** WeasyPrint, Jinja2, SQLAlchemy async, Litestar, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-pdf-reports-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/pyproject.toml` | Modify | Add weasyprint + jinja2 deps |
| `backend/app/services/report_data.py` | Create | Data aggregation functions for both reports |
| `backend/app/templates/reports/base.html` | Create | Shared HTML/CSS layout for A4 PDF |
| `backend/app/templates/reports/skater_season.html` | Create | Skater report template |
| `backend/app/templates/reports/club_season.html` | Create | Club report template |
| `backend/app/routes/reports.py` | Create | Report endpoints + Jinja2 rendering |
| `backend/app/main.py` | Modify | Register reports router |
| `backend/tests/test_reports.py` | Create | Tests for report data + endpoints |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Modify | Add export button |
| `frontend/src/pages/HomePage.tsx` | Modify | Add export button |
| `Dockerfile.backend` | Modify | Add WeasyPrint system deps |

---

### Task 1: Add dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add weasyprint and jinja2 to pyproject.toml**

Add to the `[project.dependencies]` list:
```toml
"weasyprint>=62.0",
"jinja2>=3.1",
```

- [ ] **Step 2: Install dependencies**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv sync
```

Expected: installs successfully, lock file updated.

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat: add weasyprint and jinja2 dependencies for PDF reports"
```

---

### Task 2: Report data service — skater report

**Files:**
- Create: `backend/app/services/report_data.py`
- Create: `backend/tests/test_reports.py`

- [ ] **Step 1: Write test for `get_skater_report_data`**

Create `backend/tests/test_reports.py`:

```python
import pytest
import pytest_asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.services.report_data import get_skater_report_data


async def _seed_skater_data(session: AsyncSession):
    """Create a skater with scores across two competitions in one season."""
    skater = Skater(first_name="Alice", last_name="DUPONT", club="CSG Chambéry", nationality="FRA")
    session.add(skater)
    await session.flush()

    comp1 = Competition(name="CSNPA Automne", url="http://example.com/c1", date=date(2025, 10, 15), season="2025-2026")
    comp2 = Competition(name="Coupe Régionale", url="http://example.com/c2", date=date(2026, 1, 20), season="2025-2026")
    comp_other = Competition(name="Old Comp", url="http://example.com/c3", date=date(2024, 11, 1), season="2024-2025")
    session.add_all([comp1, comp2, comp_other])
    await session.flush()

    scores = [
        Score(competition_id=comp1.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=30.0, technical_score=18.0,
              component_score=12.0, deductions=0.0, event_date=comp1.date, rank=2),
        Score(competition_id=comp1.id, skater_id=skater.id, segment="Free Skating",
              category="Novice Dames", total_score=55.0, technical_score=33.0,
              component_score=22.0, deductions=0.0, event_date=comp1.date, rank=1),
        Score(competition_id=comp2.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=35.0, technical_score=20.0,
              component_score=15.0, deductions=0.0, event_date=comp2.date, rank=1),
        Score(competition_id=comp2.id, skater_id=skater.id, segment="Free Skating",
              category="Novice Dames", total_score=50.0, technical_score=30.0,
              component_score=20.0, deductions=0.0, event_date=comp2.date, rank=3),
        # Score from other season — should be excluded
        Score(competition_id=comp_other.id, skater_id=skater.id, segment="Short Program",
              category="Novice Dames", total_score=99.0, technical_score=60.0,
              component_score=39.0, deductions=0.0, event_date=comp_other.date, rank=1),
    ]
    session.add_all(scores)

    cr1 = CategoryResult(competition_id=comp1.id, skater_id=skater.id, category="Novice Dames",
                         overall_rank=1, combined_total=85.0, segment_count=2)
    cr2 = CategoryResult(competition_id=comp2.id, skater_id=skater.id, category="Novice Dames",
                         overall_rank=2, combined_total=85.0, segment_count=2)
    session.add_all([cr1, cr2])
    await session.commit()

    return skater


@pytest.mark.asyncio
async def test_skater_report_data(db_session: AsyncSession):
    skater = await _seed_skater_data(db_session)
    data = await get_skater_report_data(skater.id, "2025-2026", db_session)

    assert data.skater_name == "Alice DUPONT"
    assert data.season == "2025-2026"

    # 4 scores in season (not the one from 2024-2025)
    assert len(data.results) == 4

    # Personal bests
    assert "Short Program" in data.personal_bests
    assert data.personal_bests["Short Program"]["tss"] == 35.0
    assert "Free Skating" in data.personal_bests
    assert data.personal_bests["Free Skating"]["tss"] == 55.0

    # No element data seeded
    assert data.element_summary is None


@pytest.mark.asyncio
async def test_skater_report_data_empty_season(db_session: AsyncSession):
    skater = await _seed_skater_data(db_session)
    data = await get_skater_report_data(skater.id, "2030-2031", db_session)
    assert len(data.results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py -v
```

Expected: ImportError — `report_data` module doesn't exist yet.

- [ ] **Step 3: Implement `get_skater_report_data`**

Create `backend/app/services/report_data.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competition import Competition
from app.models.score import Score
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.app_settings import AppSettings


@dataclass
class SkaterReportResult:
    competition_name: str
    competition_date: Optional[date]
    category: Optional[str]
    segment: str
    rank: Optional[int]
    tss: Optional[float]
    tes: Optional[float]
    pcs: Optional[float]
    deductions: Optional[float]


@dataclass
class ElementStats:
    name: str
    attempts: int
    avg_goe: float


@dataclass
class ElementSummary:
    most_attempted: list[ElementStats]
    best_goe: list[ElementStats]
    total_elements_tracked: int


@dataclass
class SkaterReportData:
    skater_name: str
    club: Optional[str]
    season: str
    generated_at: str
    personal_bests: dict[str, dict]  # segment -> {tss, tes, pcs, competition, date}
    results: list[SkaterReportResult]
    element_summary: Optional[ElementSummary]


async def get_skater_report_data(
    skater_id: int,
    season: str,
    session: AsyncSession,
) -> SkaterReportData:
    # Fetch skater
    skater_row = await session.get(Skater, skater_id)
    skater_name = skater_row.display_name if skater_row else f"Patineur #{skater_id}"
    club = skater_row.club if skater_row else None

    # Fetch scores for the season
    stmt = (
        select(Score, Competition.name, Competition.date)
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.skater_id == skater_id, Competition.season == season)
        .order_by(Competition.date, Score.segment)
    )
    rows = (await session.execute(stmt)).all()

    results: list[SkaterReportResult] = []
    personal_bests: dict[str, dict] = {}

    for score, comp_name, comp_date in rows:
        results.append(SkaterReportResult(
            competition_name=comp_name,
            competition_date=comp_date,
            category=score.category,
            segment=score.segment,
            rank=score.rank,
            tss=score.total_score,
            tes=score.technical_score,
            pcs=score.component_score,
            deductions=score.deductions,
        ))

        # Track personal bests per segment
        tss = score.total_score or 0
        seg = score.segment
        if seg not in personal_bests or tss > personal_bests[seg]["tss"]:
            personal_bests[seg] = {
                "tss": score.total_score,
                "tes": score.technical_score,
                "pcs": score.component_score,
                "competition": comp_name,
                "date": comp_date,
            }

    # Element summary (only if enriched data exists)
    element_summary = _compute_element_summary(
        [score for score, _, _ in rows]
    )

    return SkaterReportData(
        skater_name=skater_name,
        club=club,
        season=season,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        personal_bests=personal_bests,
        results=results,
        element_summary=element_summary,
    )


def _compute_element_summary(scores: list[Score]) -> Optional[ElementSummary]:
    """Aggregate element stats across all scores. Returns None if no element data."""
    element_data: dict[str, list[float]] = {}  # name -> list of GOE values

    for score in scores:
        if not score.elements:
            continue
        elements_list = score.elements if isinstance(score.elements, list) else score.elements.get("elements", [])
        for el in elements_list:
            name = el.get("name", "")
            goe = el.get("goe")
            if name and goe is not None:
                element_data.setdefault(name, []).append(float(goe))

    if not element_data:
        return None

    stats = [
        ElementStats(
            name=name,
            attempts=len(goes),
            avg_goe=round(sum(goes) / len(goes), 2),
        )
        for name, goes in element_data.items()
    ]

    most_attempted = sorted(stats, key=lambda s: s.attempts, reverse=True)[:5]
    best_goe = sorted(
        [s for s in stats if s.attempts >= 2],
        key=lambda s: s.avg_goe,
        reverse=True,
    )[:5]

    return ElementSummary(
        most_attempted=most_attempted,
        best_goe=best_goe,
        total_elements_tracked=sum(s.attempts for s in stats),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/report_data.py backend/tests/test_reports.py
git commit -m "feat: add skater report data aggregation service with tests"
```

---

### Task 3: Report data service — club report

**Files:**
- Modify: `backend/app/services/report_data.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write test for `get_club_report_data`**

Append to `backend/tests/test_reports.py`:

```python
from app.services.report_data import get_club_report_data


async def _seed_club_data(session: AsyncSession):
    """Create club data: 2 skaters, 2 competitions, medals, improvement."""
    settings = AppSettings(club_name="CSG Chambéry", club_short="CSG", current_season="2025-2026")
    session.add(settings)

    s1 = Skater(first_name="Alice", last_name="DUPONT", club="CSG Chambéry")
    s2 = Skater(first_name="Bob", last_name="MARTIN", club="CSG Chambéry")
    s3 = Skater(first_name="Eve", last_name="OTHER", club="Autre Club")
    session.add_all([s1, s2, s3])
    await session.flush()

    comp1 = Competition(name="CSNPA Automne", url="http://example.com/c1", date=date(2025, 10, 15), season="2025-2026")
    comp2 = Competition(name="Coupe Régionale", url="http://example.com/c2", date=date(2026, 1, 20), season="2025-2026")
    session.add_all([comp1, comp2])
    await session.flush()

    session.add_all([
        Score(competition_id=comp1.id, skater_id=s1.id, segment="Short Program",
              category="Novice Dames", total_score=30.0, technical_score=18.0,
              component_score=12.0, deductions=0.0, event_date=comp1.date, rank=1),
        Score(competition_id=comp2.id, skater_id=s1.id, segment="Short Program",
              category="Novice Dames", total_score=38.0, technical_score=22.0,
              component_score=16.0, deductions=0.0, event_date=comp2.date, rank=1),
        Score(competition_id=comp1.id, skater_id=s2.id, segment="Short Program",
              category="Junior Messieurs", total_score=45.0, technical_score=28.0,
              component_score=17.0, deductions=0.0, event_date=comp1.date, rank=3),
        # Other club skater — should be excluded
        Score(competition_id=comp1.id, skater_id=s3.id, segment="Short Program",
              category="Novice Dames", total_score=99.0, technical_score=60.0,
              component_score=39.0, deductions=0.0, event_date=comp1.date, rank=1),
    ])

    session.add_all([
        CategoryResult(competition_id=comp1.id, skater_id=s1.id, category="Novice Dames",
                       overall_rank=1, combined_total=30.0, segment_count=1),
        CategoryResult(competition_id=comp2.id, skater_id=s1.id, category="Novice Dames",
                       overall_rank=1, combined_total=38.0, segment_count=1),
        CategoryResult(competition_id=comp1.id, skater_id=s2.id, category="Junior Messieurs",
                       overall_rank=3, combined_total=45.0, segment_count=1),
    ])
    await session.commit()
    return s1, s2


@pytest.mark.asyncio
async def test_club_report_data(db_session: AsyncSession):
    s1, s2 = await _seed_club_data(db_session)
    data = await get_club_report_data("2025-2026", db_session)

    assert data.club_name == "CSG Chambéry"
    assert data.season == "2025-2026"
    assert data.stats["active_skaters"] == 2
    assert data.stats["total_programs"] == 3

    # Skater summary: 2 club skaters, not the other club one
    assert len(data.skaters_summary) == 2
    names = [s["name"] for s in data.skaters_summary]
    assert "Alice DUPONT" in names
    assert "Bob MARTIN" in names
    assert "Eve OTHER" not in names

    # Medals: rank <= 3
    assert len(data.medals) >= 2

    # Most improved: Alice went from 30 to 38
    assert len(data.most_improved) >= 1
    assert data.most_improved[0]["name"] == "Alice DUPONT"
    assert data.most_improved[0]["delta"] == 8.0
```

- [ ] **Step 2: Run tests to verify new test fails**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py::test_club_report_data -v
```

Expected: ImportError — `get_club_report_data` not defined.

- [ ] **Step 3: Implement `get_club_report_data`**

Add to `backend/app/services/report_data.py`:

```python
from sqlalchemy import func


@dataclass
class ClubReportData:
    club_name: str
    club_logo_path: Optional[str]
    season: str
    generated_at: str
    stats: dict  # active_skaters, competitions_tracked, total_programs, total_podiums
    skaters_summary: list[dict]  # name, category, competitions_entered, best_tss, best_tes, best_pcs
    medals: list[dict]  # skater_name, competition_name, competition_date, category, rank
    most_improved: list[dict]  # name, category, first_tss, last_tss, delta


async def get_club_report_data(
    season: str,
    session: AsyncSession,
) -> ClubReportData:
    # Get club settings
    settings = (await session.execute(select(AppSettings))).scalar_one_or_none()
    club_name = settings.club_name if settings else "Club"
    club_logo = settings.logo_path if settings else None

    # Get club skater IDs
    club_skaters_stmt = select(Skater).where(
        func.lower(Skater.club) == club_name.lower()
    )
    club_skaters = (await session.execute(club_skaters_stmt)).scalars().all()
    club_skater_ids = [s.id for s in club_skaters]

    if not club_skater_ids:
        return ClubReportData(
            club_name=club_name,
            club_logo_path=club_logo,
            season=season,
            generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
            stats={"active_skaters": 0, "competitions_tracked": 0, "total_programs": 0, "total_podiums": 0},
            skaters_summary=[],
            medals=[],
            most_improved=[],
        )

    # Fetch all scores for club skaters in this season
    scores_stmt = (
        select(Score, Competition.name, Competition.date)
        .join(Competition, Score.competition_id == Competition.id)
        .where(Score.skater_id.in_(club_skater_ids), Competition.season == season)
        .order_by(Competition.date)
    )
    score_rows = (await session.execute(scores_stmt)).all()

    # Fetch category results for medals
    cr_stmt = (
        select(CategoryResult)
        .join(Competition, CategoryResult.competition_id == Competition.id)
        .options(selectinload(CategoryResult.competition), selectinload(CategoryResult.skater))
        .where(CategoryResult.skater_id.in_(club_skater_ids), Competition.season == season)
        .order_by(Competition.date)
    )
    cat_results = (await session.execute(cr_stmt)).scalars().all()

    # Stats
    active_ids = set()
    comp_ids = set()
    for score, comp_name, comp_date in score_rows:
        active_ids.add(score.skater_id)
        comp_ids.add(score.competition_id)

    medals_list = []
    podium_count = 0
    for cr in cat_results:
        if cr.overall_rank and cr.overall_rank <= 3:
            podium_count += 1
            medals_list.append({
                "skater_name": cr.skater.display_name,
                "competition_name": cr.competition.name,
                "competition_date": cr.competition.date,
                "category": cr.category,
                "rank": cr.overall_rank,
            })

    # Per-skater summary
    skater_map: dict[int, dict] = {}
    for score, comp_name, comp_date in score_rows:
        sid = score.skater_id
        if sid not in skater_map:
            sk = next(s for s in club_skaters if s.id == sid)
            skater_map[sid] = {
                "name": sk.display_name,
                "category": score.category,
                "comp_ids": set(),
                "best_tss": 0.0,
                "best_tes": 0.0,
                "best_pcs": 0.0,
                "first_tss": None,
                "first_date": None,
                "last_tss": None,
                "last_date": None,
            }
        entry = skater_map[sid]
        entry["comp_ids"].add(score.competition_id)
        entry["category"] = score.category  # Use most recent
        tss = score.total_score or 0
        tes = score.technical_score or 0
        pcs = score.component_score or 0
        if tss > entry["best_tss"]:
            entry["best_tss"] = tss
        if tes > entry["best_tes"]:
            entry["best_tes"] = tes
        if pcs > entry["best_pcs"]:
            entry["best_pcs"] = pcs
        # Track first/last for improvement
        score_date = comp_date or score.event_date
        if entry["first_date"] is None or (score_date and score_date < entry["first_date"]):
            entry["first_date"] = score_date
            entry["first_tss"] = tss
        if entry["last_date"] is None or (score_date and score_date > entry["last_date"]):
            entry["last_date"] = score_date
            entry["last_tss"] = tss

    skaters_summary = sorted(
        [
            {
                "name": v["name"],
                "category": v["category"],
                "competitions_entered": len(v["comp_ids"]),
                "best_tss": v["best_tss"],
                "best_tes": v["best_tes"],
                "best_pcs": v["best_pcs"],
            }
            for v in skater_map.values()
        ],
        key=lambda x: x["name"],
    )

    # Most improved (need at least 2 different dates)
    improvements = []
    for v in skater_map.values():
        if (
            v["first_tss"] is not None
            and v["last_tss"] is not None
            and v["first_date"] != v["last_date"]
        ):
            delta = v["last_tss"] - v["first_tss"]
            improvements.append({
                "name": v["name"],
                "category": v["category"],
                "first_tss": v["first_tss"],
                "last_tss": v["last_tss"],
                "delta": round(delta, 2),
            })
    most_improved = sorted(improvements, key=lambda x: x["delta"], reverse=True)[:3]

    return ClubReportData(
        club_name=club_name,
        club_logo_path=club_logo,
        season=season,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        stats={
            "active_skaters": len(active_ids),
            "competitions_tracked": len(comp_ids),
            "total_programs": len(score_rows),
            "total_podiums": podium_count,
        },
        skaters_summary=skaters_summary,
        medals=medals_list,
        most_improved=most_improved,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/report_data.py backend/tests/test_reports.py
git commit -m "feat: add club report data aggregation with tests"
```

---

### Task 4: HTML templates

**Files:**
- Create: `backend/app/templates/reports/base.html`
- Create: `backend/app/templates/reports/skater_season.html`
- Create: `backend/app/templates/reports/club_season.html`

- [ ] **Step 1: Create base template**

Create `backend/app/templates/reports/base.html`:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page {
    size: A4 portrait;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-right {
      content: "Page " counter(page) " / " counter(pages);
      font-size: 8pt;
      color: #49454f;
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 10pt;
    color: #191c1e;
    line-height: 1.4;
  }
  h1, h2, h3 {
    font-family: Manrope, Inter, sans-serif;
    color: #2e6385;
  }
  h1 { font-size: 18pt; margin-bottom: 4pt; }
  h2 { font-size: 13pt; margin-top: 16pt; margin-bottom: 6pt; }
  h3 { font-size: 11pt; margin-top: 12pt; margin-bottom: 4pt; }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12pt;
    padding-bottom: 8pt;
    border-bottom: 2pt solid #2e6385;
  }
  .header-logo { height: 40pt; }
  .header-meta { text-align: right; font-size: 8pt; color: #49454f; }
  .subtitle { font-size: 10pt; color: #49454f; margin-bottom: 2pt; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 4pt;
    font-size: 9pt;
  }
  th {
    background-color: #e8f0f6;
    color: #2e6385;
    text-align: left;
    padding: 4pt 6pt;
    font-weight: 700;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.3pt;
  }
  td {
    padding: 4pt 6pt;
    border-bottom: 0.5pt solid #e0e0e0;
  }
  tr:nth-child(even) td { background-color: #f8fafb; }
  .num { text-align: right; font-family: "SF Mono", "Fira Code", monospace; }
  .kpi-row {
    display: flex;
    gap: 12pt;
    margin: 8pt 0 12pt 0;
  }
  .kpi-box {
    flex: 1;
    background: #e8f0f6;
    border-radius: 6pt;
    padding: 8pt 10pt;
    text-align: center;
  }
  .kpi-value {
    font-size: 18pt;
    font-weight: 800;
    font-family: Manrope, sans-serif;
    color: #2e6385;
  }
  .kpi-label {
    font-size: 7pt;
    text-transform: uppercase;
    letter-spacing: 0.3pt;
    color: #49454f;
    margin-top: 2pt;
  }
  .medal-1 { color: #b8860b; font-weight: 700; }
  .medal-2 { color: #808080; font-weight: 700; }
  .medal-3 { color: #cd7f32; font-weight: 700; }
  .section { page-break-inside: avoid; }
  .improvement-positive { color: #2e6385; font-weight: 700; }
  .improvement-negative { color: #ba1a1a; font-weight: 700; }
</style>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create skater season template**

Create `backend/app/templates/reports/skater_season.html`:

```html
{% extends "reports/base.html" %}
{% block content %}
<div class="header">
  <div>
    <h1>{{ data.skater_name }}</h1>
    <p class="subtitle">
      {% if data.club %}{{ data.club }} · {% endif %}Saison {{ data.season }}
    </p>
  </div>
  <div class="header-meta">
    {% if logo_base64 %}
    <img src="data:image/png;base64,{{ logo_base64 }}" class="header-logo" alt="Logo">
    {% endif %}
    <div>Généré le {{ data.generated_at }}</div>
  </div>
</div>

{% if data.personal_bests %}
<div class="section">
  <h2>Records personnels</h2>
  <table>
    <thead>
      <tr>
        <th>Segment</th>
        <th class="num">TSS</th>
        <th class="num">TES</th>
        <th class="num">PCS</th>
        <th>Compétition</th>
        <th>Date</th>
      </tr>
    </thead>
    <tbody>
      {% for seg, pb in data.personal_bests.items() %}
      <tr>
        <td>{{ seg }}</td>
        <td class="num">{{ "%.2f"|format(pb.tss) if pb.tss is not none else "—" }}</td>
        <td class="num">{{ "%.2f"|format(pb.tes) if pb.tes is not none else "—" }}</td>
        <td class="num">{{ "%.2f"|format(pb.pcs) if pb.pcs is not none else "—" }}</td>
        <td>{{ pb.competition }}</td>
        <td>{{ pb.date.strftime("%d/%m/%Y") if pb.date else "—" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% if data.results %}
<div class="section">
  <h2>Résultats de la saison</h2>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Compétition</th>
        <th>Catégorie</th>
        <th>Segment</th>
        <th class="num">Rang</th>
        <th class="num">TSS</th>
        <th class="num">TES</th>
        <th class="num">PCS</th>
        <th class="num">Déd.</th>
      </tr>
    </thead>
    <tbody>
      {% for r in data.results %}
      <tr>
        <td>{{ r.competition_date.strftime("%d/%m/%Y") if r.competition_date else "—" }}</td>
        <td>{{ r.competition_name }}</td>
        <td>{{ r.category or "—" }}</td>
        <td>{{ r.segment }}</td>
        <td class="num">{{ r.rank or "—" }}</td>
        <td class="num">{{ "%.2f"|format(r.tss) if r.tss is not none else "—" }}</td>
        <td class="num">{{ "%.2f"|format(r.tes) if r.tes is not none else "—" }}</td>
        <td class="num">{{ "%.2f"|format(r.pcs) if r.pcs is not none else "—" }}</td>
        <td class="num">{{ "%.2f"|format(r.deductions) if r.deductions is not none else "—" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% if data.element_summary %}
<div class="section">
  <h2>Analyse des éléments</h2>
  <p class="subtitle">{{ data.element_summary.total_elements_tracked }} éléments analysés</p>

  {% if data.element_summary.most_attempted %}
  <h3>Éléments les plus travaillés</h3>
  <table>
    <thead>
      <tr><th>Élément</th><th class="num">Tentatives</th><th class="num">GOE moyen</th></tr>
    </thead>
    <tbody>
      {% for el in data.element_summary.most_attempted %}
      <tr>
        <td>{{ el.name }}</td>
        <td class="num">{{ el.attempts }}</td>
        <td class="num">{{ "%+.2f"|format(el.avg_goe) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if data.element_summary.best_goe %}
  <h3>Meilleurs GOE (min. 2 tentatives)</h3>
  <table>
    <thead>
      <tr><th>Élément</th><th class="num">GOE moyen</th><th class="num">Tentatives</th></tr>
    </thead>
    <tbody>
      {% for el in data.element_summary.best_goe %}
      <tr>
        <td>{{ el.name }}</td>
        <td class="num">{{ "%+.2f"|format(el.avg_goe) }}</td>
        <td class="num">{{ el.attempts }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create club season template**

Create `backend/app/templates/reports/club_season.html`:

```html
{% extends "reports/base.html" %}
{% block content %}
<div class="header">
  <div>
    <h1>{{ data.club_name }}</h1>
    <p class="subtitle">Rapport de saison {{ data.season }}</p>
  </div>
  <div class="header-meta">
    {% if logo_base64 %}
    <img src="data:image/png;base64,{{ logo_base64 }}" class="header-logo" alt="Logo">
    {% endif %}
    <div>Généré le {{ data.generated_at }}</div>
  </div>
</div>

<div class="kpi-row">
  <div class="kpi-box">
    <div class="kpi-value">{{ data.stats.active_skaters }}</div>
    <div class="kpi-label">Patineurs actifs</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-value">{{ data.stats.competitions_tracked }}</div>
    <div class="kpi-label">Compétitions</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-value">{{ data.stats.total_programs }}</div>
    <div class="kpi-label">Programmes</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-value">{{ data.stats.total_podiums }}</div>
    <div class="kpi-label">Podiums</div>
  </div>
</div>

{% if data.skaters_summary %}
<div class="section">
  <h2>Tableau des patineurs</h2>
  <table>
    <thead>
      <tr>
        <th>Nom</th>
        <th>Catégorie</th>
        <th class="num">Comp.</th>
        <th class="num">Meilleur TSS</th>
        <th class="num">Meilleur TES</th>
        <th class="num">Meilleur PCS</th>
      </tr>
    </thead>
    <tbody>
      {% for s in data.skaters_summary %}
      <tr>
        <td>{{ s.name }}</td>
        <td>{{ s.category or "—" }}</td>
        <td class="num">{{ s.competitions_entered }}</td>
        <td class="num">{{ "%.2f"|format(s.best_tss) if s.best_tss else "—" }}</td>
        <td class="num">{{ "%.2f"|format(s.best_tes) if s.best_tes else "—" }}</td>
        <td class="num">{{ "%.2f"|format(s.best_pcs) if s.best_pcs else "—" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% if data.medals %}
<div class="section">
  <h2>Podiums et médailles</h2>
  <table>
    <thead>
      <tr>
        <th>Patineur</th>
        <th>Compétition</th>
        <th>Date</th>
        <th>Catégorie</th>
        <th class="num">Rang</th>
      </tr>
    </thead>
    <tbody>
      {% for m in data.medals %}
      <tr>
        <td>{{ m.skater_name }}</td>
        <td>{{ m.competition_name }}</td>
        <td>{{ m.competition_date.strftime("%d/%m/%Y") if m.competition_date else "—" }}</td>
        <td>{{ m.category }}</td>
        <td class="num medal-{{ m.rank }}">#{{ m.rank }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% if data.most_improved %}
<div class="section">
  <h2>Progression</h2>
  <table>
    <thead>
      <tr>
        <th>Patineur</th>
        <th>Catégorie</th>
        <th class="num">Premier TSS</th>
        <th class="num">Dernier TSS</th>
        <th class="num">Progression</th>
      </tr>
    </thead>
    <tbody>
      {% for m in data.most_improved %}
      <tr>
        <td>{{ m.name }}</td>
        <td>{{ m.category or "—" }}</td>
        <td class="num">{{ "%.2f"|format(m.first_tss) }}</td>
        <td class="num">{{ "%.2f"|format(m.last_tss) }}</td>
        <td class="num {{ 'improvement-positive' if m.delta >= 0 else 'improvement-negative' }}">
          {{ "%+.2f"|format(m.delta) }}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/templates/
git commit -m "feat: add Jinja2 HTML templates for skater and club PDF reports"
```

---

### Task 5: Report route endpoints

**Files:**
- Create: `backend/app/routes/reports.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write endpoint integration test**

Add to `backend/tests/test_reports.py`:

```python
from app.models.app_settings import AppSettings


@pytest.mark.asyncio
async def test_skater_pdf_endpoint(client, admin_token, db_session):
    skater = await _seed_skater_data(db_session)
    resp = await client.get(
        f"/api/reports/skater/{skater.id}/pdf?season=2025-2026",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_skater_pdf_no_data(client, admin_token, db_session):
    skater = await _seed_skater_data(db_session)
    resp = await client.get(
        f"/api/reports/skater/{skater.id}/pdf?season=2030-2031",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_club_pdf_endpoint(client, admin_token, db_session):
    await _seed_club_data(db_session)
    resp = await client.get(
        "/api/reports/club/pdf?season=2025-2026",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_report_requires_auth(client):
    resp = await client.get("/api/reports/club/pdf?season=2025-2026")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py::test_skater_pdf_endpoint -v
```

Expected: 404 or error — route doesn't exist yet.

- [ ] **Step 3: Create `reports.py` route file**

Create `backend/app/routes/reports.py`:

```python
from __future__ import annotations

import base64
from pathlib import Path

from litestar import Router, get
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader
import weasyprint

from app.database import get_session
from app.services.report_data import get_skater_report_data, get_club_report_data

# Jinja2 setup — templates live next to the app package
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


def _load_logo_base64(logo_path: str | None) -> str | None:
    """Load club logo as base64 for embedding in PDF HTML."""
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.is_file():
        return None
    return base64.b64encode(p.read_bytes()).decode()


@get("/skater/{skater_id:int}/pdf")
async def skater_report_pdf(
    skater_id: int,
    season: str,
    session: AsyncSession,
) -> Response:
    data = await get_skater_report_data(skater_id, season, session)
    if not data.results:
        raise NotFoundException(detail="Aucun résultat pour cette saison")

    logo_b64 = _load_logo_base64(None)  # Skater report: logo loaded from settings if needed
    template = _jinja_env.get_template("reports/skater_season.html")
    html = template.render(data=data, logo_base64=logo_b64)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    safe_name = data.skater_name.replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-{safe_name}-{season}.pdf"'
        },
    )


@get("/club/pdf")
async def club_report_pdf(
    season: str,
    session: AsyncSession,
) -> Response:
    data = await get_club_report_data(season, session)
    if not data.skaters_summary:
        raise NotFoundException(detail="Aucun résultat pour cette saison")

    logo_b64 = _load_logo_base64(data.club_logo_path)
    template = _jinja_env.get_template("reports/club_season.html")
    html = template.render(data=data, logo_base64=logo_b64)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-club-{season}.pdf"'
        },
    )


router = Router(
    path="/api/reports",
    route_handlers=[skater_report_pdf, club_report_pdf],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Register the router in `main.py`**

Add import at top of `backend/app/main.py`:
```python
from app.routes.reports import router as reports_router
```

Add `reports_router` to the `route_handlers` list in the `Litestar()` constructor.

- [ ] **Step 5: Run all report tests**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_reports.py -v
```

Expected: All tests PASS (data tests + endpoint tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/reports.py backend/app/main.py backend/tests/test_reports.py
git commit -m "feat: add PDF report endpoints for skater and club season reports"
```

---

### Task 6: Frontend export buttons

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (around line 480)
- Modify: `frontend/src/pages/HomePage.tsx` (around line 229)

- [ ] **Step 1: Add export button to SkaterAnalyticsPage**

In `frontend/src/pages/SkaterAnalyticsPage.tsx`, inside the `<div className="flex flex-wrap gap-3 shrink-0 items-center">` block (line 480), after the season `<select>` (after the closing `)}` on line 492), add:

```tsx
{selectedSeason && (
  <a
    href={`/api/reports/skater/${skaterId}/pdf?season=${selectedSeason}`}
    className="flex items-center gap-1.5 bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2.5 text-sm text-white font-bold font-headline hover:bg-white/25 transition-colors"
    download
  >
    <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
    Exporter le bilan
  </a>
)}
```

- [ ] **Step 2: Add export button to HomePage**

In `frontend/src/pages/HomePage.tsx`, after the season `<select>` (around line 239), within the same parent container, add:

```tsx
<a
  href={`/api/reports/club/pdf?season=${season}`}
  className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-on-primary rounded-xl text-xs font-bold hover:bg-primary/90 transition-colors"
  download
>
  <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
  Rapport de saison
</a>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx frontend/src/pages/HomePage.tsx
git commit -m "feat: add PDF report export buttons to skater analytics and home pages"
```

---

### Task 7: Dockerfile update

**Files:**
- Modify: `Dockerfile.backend`

- [ ] **Step 1: Add WeasyPrint system dependencies**

In `Dockerfile.backend`, after the `FROM` line and before `COPY --from=...`, add:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.backend
git commit -m "feat: add WeasyPrint system deps to backend Dockerfile"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v
```

Expected: all tests pass, including new report tests.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && PATH="/opt/homebrew/bin:$PATH" npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 3: Manual smoke test (if dev servers running)**

1. Open skater analytics page, select a season, click "Exporter le bilan" — PDF should download
2. Open home page, click "Rapport de saison" — PDF should download
3. Both PDFs should be valid, A4, with tables and correct French text

- [ ] **Step 4: Push**

```bash
git push
```
