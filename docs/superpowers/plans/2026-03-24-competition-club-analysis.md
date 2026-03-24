# Competition Club Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-competition club analysis page with club challenge ranking, medals, PBs, category coverage, and detailed results — as a second tab alongside the existing season analytics.

**Architecture:** New backend service (`competition_analysis.py`) computes all analysis from `CategoryResult` data. Single API endpoint returns the full analysis response. Frontend adds a tab system to the existing `/club` route, with the new page as `/club/competition`.

**Tech Stack:** Python/Litestar + SQLAlchemy (backend), React/TypeScript + Tailwind CSS (frontend), pytest with async fixtures (tests)

**Spec:** `docs/superpowers/specs/2026-03-24-competition-club-analysis-design.md`

---

### Task 1: Club Challenge Scoring Service — Pure Logic

**Files:**
- Create: `backend/app/services/competition_analysis.py`
- Create: `backend/tests/test_competition_analysis.py`

This task implements the pure scoring algorithm as a standalone function with no DB dependency, making it easy to test.

- [ ] **Step 1: Write failing tests for the scoring algorithm**

```python
# backend/tests/test_competition_analysis.py
import pytest
from app.services.competition_analysis import compute_club_challenge_points


def test_single_skater_in_category():
    """1 skater: gets 1 base + 3 podium = 4."""
    result = compute_club_challenge_points(rank=1, total_in_category=1)
    assert result == {"base": 1, "podium": 3, "total": 4}


def test_two_skaters():
    """2 skaters: rank 1 gets 2+3=5, rank 2 gets 1+2=3."""
    r1 = compute_club_challenge_points(rank=1, total_in_category=2)
    assert r1 == {"base": 2, "podium": 3, "total": 5}
    r2 = compute_club_challenge_points(rank=2, total_in_category=2)
    assert r2 == {"base": 1, "podium": 2, "total": 3}


def test_four_skaters():
    """4 skaters: rank 1=7, rank 2=5, rank 3=3, rank 4=1."""
    assert compute_club_challenge_points(1, 4) == {"base": 4, "podium": 3, "total": 7}
    assert compute_club_challenge_points(2, 4) == {"base": 3, "podium": 2, "total": 5}
    assert compute_club_challenge_points(3, 4) == {"base": 2, "podium": 1, "total": 3}
    assert compute_club_challenge_points(4, 4) == {"base": 1, "podium": 0, "total": 1}


def test_ten_skaters_cap():
    """10 skaters: rank 1 gets 10+3=13, rank 10 gets 1."""
    assert compute_club_challenge_points(1, 10) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 10) == {"base": 1, "podium": 0, "total": 1}


def test_eleven_skaters_capped_at_ten():
    """11 skaters: rank 1 still gets 10+3=13, ranks 10 and 11 both get 1."""
    assert compute_club_challenge_points(1, 11) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 11) == {"base": 1, "podium": 0, "total": 1}
    assert compute_club_challenge_points(11, 11) == {"base": 1, "podium": 0, "total": 1}


def test_fifteen_skaters_beyond_tenth():
    """15 skaters: ranks 11-15 all get 1 base, 0 podium."""
    for rank in range(11, 16):
        assert compute_club_challenge_points(rank, 15) == {"base": 1, "podium": 0, "total": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_club_challenge_points'`

- [ ] **Step 3: Implement the scoring function**

```python
# backend/app/services/competition_analysis.py
"""Competition club analysis service."""


def compute_club_challenge_points(rank: int, total_in_category: int) -> dict:
    """Compute club challenge points for a skater at a given rank.

    Base points: max(min(N - rank + 1, 10), 1) where N = total_in_category.
    Podium bonus: rank 1 → +3, rank 2 → +2, rank 3 → +1.
    """
    base = max(min(total_in_category - rank + 1, 10), 1)
    podium = {1: 3, 2: 2, 3: 1}.get(rank, 0)
    return {"base": base, "podium": podium, "total": base + podium}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/competition_analysis.py backend/tests/test_competition_analysis.py
git commit -m "feat: add club challenge scoring algorithm with tests"
```

---

### Task 2: Competition Analysis Service — DB Logic

**Files:**
- Modify: `backend/app/services/competition_analysis.py`
- Modify: `backend/tests/test_competition_analysis.py`

Adds the async service function that queries the DB and computes the full analysis response.

- [ ] **Step 1: Write the integration test with seed data**

Add to `backend/tests/test_competition_analysis.py`:

```python
import pytest_asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.skater import Skater
from app.models.category_result import CategoryResult
from app.models.app_settings import AppSettings
from app.services.competition_analysis import compute_competition_club_analysis


@pytest_asyncio.fixture
async def seed_club_analysis(db_session: AsyncSession):
    """Seed data for competition club analysis.

    Competition 'Comp A' with 2 categories:
    - 'R2 Minime Femme': 4 skaters (2 from TC, 2 from OC)
    - 'R1 Junior Homme': 2 skaters (1 from TC, 1 from OC)

    Prior competition 'Comp Prior' for PB detection.
    """
    settings = AppSettings(club_name="Test Club", club_short="TC", current_season="2025-2026")
    db_session.add(settings)

    comp_prior = Competition(name="Comp Prior", url="http://test/prior", date=date(2025, 9, 1), season="2025-2026")
    comp_a = Competition(name="Comp A", url="http://test/compa", date=date(2025, 11, 1), season="2025-2026")
    db_session.add_all([comp_prior, comp_a])
    await db_session.flush()

    # Skaters
    s1 = Skater(first_name="Marie", last_name="Dupont", club="TC")
    s2 = Skater(first_name="Julie", last_name="Moreau", club="TC")
    s3 = Skater(first_name="Jean", last_name="Martin", club="TC")
    s4 = Skater(first_name="Other", last_name="One", club="OC")
    s5 = Skater(first_name="Other", last_name="Two", club="OC")
    s6 = Skater(first_name="Other", last_name="Three", club="OC")
    db_session.add_all([s1, s2, s3, s4, s5, s6])
    await db_session.flush()

    # Prior results (for PB detection): Marie had 28.0 in R2 Minime Femme
    db_session.add(CategoryResult(
        competition_id=comp_prior.id, skater_id=s1.id,
        category="R2 Minime Femme", overall_rank=2, combined_total=28.0,
        segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
    ))

    # Comp A — R2 Minime Femme (4 skaters)
    for skater, rank, total in [
        (s1, 1, 35.0),   # Marie TC — rank 1, PB (prev 28.0)
        (s4, 2, 32.0),   # Other1 OC — rank 2
        (s2, 3, 30.0),   # Julie TC — rank 3, first-timer (no PB)
        (s5, 4, 25.0),   # Other2 OC — rank 4
    ]:
        db_session.add(CategoryResult(
            competition_id=comp_a.id, skater_id=skater.id,
            category="R2 Minime Femme", overall_rank=rank, combined_total=total,
            segment_count=1, skating_level="R2", age_group="Minime", gender="Femme",
        ))

    # Comp A — R1 Junior Homme (2 skaters)
    for skater, rank, total in [
        (s6, 1, 60.0),  # Other3 OC — rank 1
        (s3, 2, 55.0),  # Jean TC — rank 2, first-timer (no PB)
    ]:
        db_session.add(CategoryResult(
            competition_id=comp_a.id, skater_id=skater.id,
            category="R1 Junior Homme", overall_rank=rank, combined_total=total,
            segment_count=1, skating_level="R1", age_group="Junior", gender="Homme",
        ))

    await db_session.commit()
    return {"comp_a": comp_a, "comp_prior": comp_prior}


@pytest.mark.asyncio
async def test_competition_club_analysis(db_session: AsyncSession, seed_club_analysis):
    comp_a = seed_club_analysis["comp_a"]
    result = await compute_competition_club_analysis(db_session, comp_a.id, "TC")

    # KPIs
    assert result["kpis"]["skaters_entered"] == 3  # Marie, Julie, Jean
    assert result["kpis"]["total_medals"] == 2  # Marie rank 1, Julie rank 3
    assert result["kpis"]["personal_bests"] == 1  # Only Marie (Julie & Jean are first-timers)
    assert result["kpis"]["categories_entered"] == 2
    assert result["kpis"]["categories_total"] == 2

    # Club challenge ranking
    ranking = result["club_challenge"]["ranking"]
    assert len(ranking) == 2  # TC and OC
    # TC: R2MF(Marie r1: 4+3=7, Julie r3: 2+1=3) + R1JH(Jean r2: 1+2=3) = 13
    # OC: R2MF(Other1 r2: 3+2=5, Other2 r4: 1+0=1) + R1JH(Other3 r1: 2+3=5) = 11
    tc_entry = next(e for e in ranking if e["is_my_club"])
    assert tc_entry["total_points"] == 13
    assert tc_entry["rank"] == 1

    oc_entry = next(e for e in ranking if not e["is_my_club"])
    assert oc_entry["total_points"] == 11
    assert oc_entry["rank"] == 2

    # Medals (club only)
    assert len(result["medals"]) == 2
    medal_names = {m["skater_name"] for m in result["medals"]}
    assert "Marie Dupont" in medal_names  # rank 1
    assert "Julie Moreau" in medal_names  # rank 3

    # Results
    assert len(result["results"]) == 3
    marie_result = next(r for r in result["results"] if r["skater_name"] == "Marie Dupont")
    assert marie_result["is_pb"] is True
    assert marie_result["medal"] == 1

    julie_result = next(r for r in result["results"] if r["skater_name"] == "Julie Moreau")
    assert julie_result["is_pb"] is False  # first-timer
    assert julie_result["medal"] == 3

    jean_result = next(r for r in result["results"] if r["skater_name"] == "Jean Martin")
    assert jean_result["is_pb"] is False  # first-timer
    assert jean_result["medal"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py::test_competition_club_analysis -v`
Expected: FAIL — `ImportError: cannot import name 'compute_competition_club_analysis'`

- [ ] **Step 3: Implement the async analysis function**

Add to `backend/app/services/competition_analysis.py`:

```python
from collections import defaultdict
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category_result import CategoryResult
from app.models.competition import Competition
from app.models.skater import Skater


async def compute_competition_club_analysis(
    session: AsyncSession,
    competition_id: int,
    club: str,
) -> dict:
    """Compute full club analysis for a given competition."""
    # Load competition
    comp_result = await session.execute(
        select(Competition).where(Competition.id == competition_id)
    )
    competition = comp_result.scalar_one()

    # Load all category results for this competition with skaters
    stmt = (
        select(CategoryResult)
        .where(CategoryResult.competition_id == competition_id)
        .options(selectinload(CategoryResult.skater))
        .join(CategoryResult.skater)
    )
    result = await session.execute(stmt)
    all_results = result.scalars().all()

    # Group by category
    by_category: dict[str, list[CategoryResult]] = defaultdict(list)
    for cr in all_results:
        by_category[cr.category].append(cr)

    # Sort each category by overall_rank
    for cat_results in by_category.values():
        cat_results.sort(key=lambda cr: cr.overall_rank or 999)

    club_upper = club.upper()

    # --- Club Challenge ---
    club_points: dict[str, dict] = defaultdict(lambda: {"total": 0, "podium": 0})
    category_breakdown = []

    for category, cat_results in sorted(by_category.items()):
        n = len(cat_results)
        cat_clubs: dict[str, dict] = defaultdict(lambda: {"points": 0, "podium_points": 0})
        club_skaters_detail = []

        for cr in cat_results:
            skater_club = (cr.skater.club or "").upper()
            pts = compute_club_challenge_points(cr.overall_rank, n)
            cat_clubs[skater_club]["points"] += pts["total"]
            cat_clubs[skater_club]["podium_points"] += pts["podium"]
            club_points[skater_club]["total"] += pts["total"]
            club_points[skater_club]["podium"] += pts["podium"]

            if skater_club == club_upper:
                club_skaters_detail.append({
                    "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
                    "rank": cr.overall_rank,
                    "base_points": pts["base"],
                    "podium_points": pts["podium"],
                    "total_points": pts["total"],
                })

        category_breakdown.append({
            "category": category,
            "clubs": [
                {"club": c, "points": v["points"], "podium_points": v["podium_points"]}
                for c, v in sorted(cat_clubs.items())
            ],
            "club_skaters": club_skaters_detail,
        })

    # Build ranking sorted by total desc, then podium desc
    ranking = []
    for c, pts in club_points.items():
        ranking.append({
            "club": c,
            "total_points": pts["total"],
            "podium_points": pts["podium"],
            "is_my_club": c == club_upper,
        })
    ranking.sort(key=lambda x: (-x["total_points"], -x["podium_points"]))
    for i, entry in enumerate(ranking):
        entry["rank"] = i + 1

    # --- Club skaters ---
    club_results = [cr for cr in all_results if (cr.skater.club or "").upper() == club_upper]
    club_skater_ids = {cr.skater_id for cr in club_results}

    # --- PB detection ---
    pb_skater_ids: set[int] = set()
    for cr in club_results:
        prior_stmt = (
            select(func.max(CategoryResult.combined_total))
            .join(CategoryResult.competition)
            .where(
                CategoryResult.skater_id == cr.skater_id,
                CategoryResult.category == cr.category,
                CategoryResult.competition_id != competition_id,
                Competition.date < competition.date,
                CategoryResult.combined_total.isnot(None),
            )
        )
        prior_result = await session.execute(prior_stmt)
        prev_best = prior_result.scalar()
        if prev_best is not None and cr.combined_total is not None and cr.combined_total > prev_best:
            pb_skater_ids.add(cr.skater_id)

    # --- Medals ---
    medals = []
    for cr in club_results:
        if cr.overall_rank and cr.overall_rank <= 3:
            medals.append({
                "skater_id": cr.skater_id,
                "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
                "category": cr.category,
                "rank": cr.overall_rank,
                "combined_total": cr.combined_total,
            })
    medals.sort(key=lambda m: (m["rank"], m["category"]))

    # --- Category coverage ---
    categories = []
    for category, cat_results in sorted(by_category.items()):
        club_count = sum(1 for cr in cat_results if (cr.skater.club or "").upper() == club_upper)
        categories.append({
            "category": category,
            "club_skaters": club_count,
            "total_skaters": len(cat_results),
        })

    # --- Detailed results ---
    results = []
    for cr in club_results:
        total_in_cat = len(by_category.get(cr.category, []))
        results.append({
            "skater_id": cr.skater_id,
            "skater_name": f"{cr.skater.first_name} {cr.skater.last_name}",
            "category": cr.category,
            "overall_rank": cr.overall_rank,
            "total_skaters": total_in_cat,
            "combined_total": cr.combined_total,
            "is_pb": cr.skater_id in pb_skater_ids,
            "medal": cr.overall_rank if cr.overall_rank and cr.overall_rank <= 3 else None,
        })
    results.sort(key=lambda r: (r["category"], r["overall_rank"] or 999))

    # --- KPIs ---
    kpis = {
        "skaters_entered": len(club_skater_ids),
        "total_medals": len(medals),
        "personal_bests": len(pb_skater_ids),
        "categories_entered": sum(1 for c in categories if c["club_skaters"] > 0),
        "categories_total": len(by_category),
    }

    return {
        "competition": {
            "id": competition.id,
            "name": competition.name,
            "date": competition.date.isoformat() if competition.date else None,
            "season": competition.season,
        },
        "club_name": club,
        "kpis": kpis,
        "club_challenge": {
            "ranking": ranking,
            "category_breakdown": category_breakdown,
        },
        "medals": medals,
        "categories": categories,
        "results": results,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py -v`
Expected: All tests PASS (7 scoring + 1 integration)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/competition_analysis.py backend/tests/test_competition_analysis.py
git commit -m "feat: add competition club analysis service with DB integration"
```

---

### Task 3: API Endpoint + Competition Filtering

**Files:**
- Modify: `backend/app/routes/stats.py`
- Modify: `backend/app/routes/competitions.py`
- Modify: `backend/tests/test_competition_analysis.py`

- [ ] **Step 1: Write route-level integration tests**

Add to `backend/tests/test_competition_analysis.py`:

```python
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_competition_club_analysis_endpoint(client: AsyncClient, admin_token: str, seed_club_analysis):
    comp_a = seed_club_analysis["comp_a"]
    resp = await client.get(
        f"/api/stats/competition-club-analysis?competition_id={comp_a.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["club_name"] == "TC"
    assert data["kpis"]["skaters_entered"] == 3
    assert len(data["club_challenge"]["ranking"]) == 2


@pytest.mark.asyncio
async def test_competition_club_analysis_missing_id(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/stats/competition-club-analysis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # competition_id is required — should get 400 or validation error
    assert resp.status_code in (400, 500)


@pytest.mark.asyncio
async def test_competitions_filter_by_club(client: AsyncClient, admin_token: str, seed_club_analysis):
    resp = await client.get(
        "/api/competitions/?club=TC",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Only Comp A and Comp Prior have TC skaters
    names = {c["name"] for c in data}
    assert "Comp A" in names
    assert "Comp Prior" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py::test_competition_club_analysis_endpoint tests/test_competition_analysis.py::test_competitions_filter_by_club -v`
Expected: FAIL — 404 (route not found)

- [ ] **Step 3: Add the endpoint to stats.py**

Add to `backend/app/routes/stats.py` (before the `router = Router(...)` line). Note: the `_get_club_short` helper already exists in this file (line 22-27) — it reads from AppSettings if no explicit club is passed.

```python
from app.services.competition_analysis import compute_competition_club_analysis


@get("/competition-club-analysis")
async def competition_club_analysis(
    session: AsyncSession,
    competition_id: int,
    club: Optional[str] = None,
) -> dict:
    club_short = await _get_club_short(session, club)
    if not club_short:
        return {"error": "No club configured"}
    return await compute_competition_club_analysis(session, competition_id, club_short)
```

Update the router registration to include the new handler:

```python
router = Router(
    path="/api/stats",
    route_handlers=[progression_ranking, benchmarks, element_mastery, competition_club_analysis],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 4: Add club filter to competitions list**

Modify `backend/app/routes/competitions.py` — update the `list_competitions` function:

```python
from sqlalchemy.orm import selectinload
from app.models.category_result import CategoryResult
from app.models.skater import Skater
from sqlalchemy import func

@get("/")
async def list_competitions(
    session: AsyncSession,
    club: str | None = None,
    season: str | None = None,
) -> list[dict]:
    stmt = select(Competition).order_by(Competition.date.desc())
    if season:
        stmt = stmt.where(Competition.season == season)
    if club:
        stmt = (
            stmt
            .join(CategoryResult, CategoryResult.competition_id == Competition.id)
            .join(Skater, Skater.id == CategoryResult.skater_id)
            .where(func.upper(Skater.club) == club.upper())
            .distinct()
        )
    result = await session.execute(stmt)
    return [competition_to_dict(c) for c in result.scalars()]
```

Add imports at top of file: `from sqlalchemy import select, distinct, func` (update existing import), and add:
```python
from app.models.category_result import CategoryResult
from app.models.skater import Skater
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/stats.py backend/app/routes/competitions.py backend/tests/test_competition_analysis.py
git commit -m "feat: add competition-club-analysis endpoint and club filter on competitions list"
```

---

### Task 4: Frontend API Types & Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add TypeScript interfaces**

Add to `frontend/src/api/client.ts` after the existing type definitions:

```typescript
// --- Competition Club Analysis ---

export interface ClubChallengeEntry {
  club: string;
  total_points: number;
  podium_points: number;
  rank: number;
  is_my_club: boolean;
}

export interface CategoryBreakdownClub {
  club: string;
  points: number;
  podium_points: number;
}

export interface CategoryBreakdownSkater {
  skater_name: string;
  rank: number;
  base_points: number;
  podium_points: number;
  total_points: number;
}

export interface CategoryBreakdown {
  category: string;
  clubs: CategoryBreakdownClub[];
  club_skaters: CategoryBreakdownSkater[];
}

export interface MedalEntry {
  skater_id: number;
  skater_name: string;
  category: string;
  rank: 1 | 2 | 3;
  combined_total: number;
}

export interface CategoryCoverageEntry {
  category: string;
  club_skaters: number;
  total_skaters: number;
}

export interface ClubSkaterResult {
  skater_id: number;
  skater_name: string;
  category: string;
  overall_rank: number | null;
  total_skaters: number;
  combined_total: number | null;
  is_pb: boolean;
  medal: 1 | 2 | 3 | null;
}

export interface CompetitionClubAnalysis {
  competition: { id: number; name: string; date: string; season: string };
  club_name: string;
  kpis: {
    skaters_entered: number;
    total_medals: number;
    personal_bests: number;
    categories_entered: number;
    categories_total: number;
  };
  club_challenge: {
    ranking: ClubChallengeEntry[];
    category_breakdown: CategoryBreakdown[];
  };
  medals: MedalEntry[];
  categories: CategoryCoverageEntry[];
  results: ClubSkaterResult[];
}
```

- [ ] **Step 2: Add API functions**

Add to the `api.stats` object in `client.ts`:

```typescript
competitionClubAnalysis: (params: { competition_id: number; club?: string }) => {
  const qs = new URLSearchParams();
  qs.set("competition_id", String(params.competition_id));
  if (params.club) qs.set("club", params.club);
  const query = qs.toString() ? `?${qs}` : "";
  return request<CompetitionClubAnalysis>(`/stats/competition-club-analysis${query}`);
},
```

Update the `api.competitions.list` function to accept optional `club` and `season` params. Find the existing `list` function and update it:

```typescript
list: (params?: { club?: string; season?: string }) => {
  const qs = new URLSearchParams();
  if (params?.club) qs.set("club", params.club);
  if (params?.season) qs.set("season", params.season);
  const query = qs.toString() ? `?${qs}` : "";
  return request<Competition[]>(`/competitions/${query}`);
},
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add competition club analysis types and API functions"
```

---

### Task 5: Routing & Tab System

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/ClubTabBar.tsx`

- [ ] **Step 1: Create the ClubTabBar component**

```typescript
// frontend/src/components/ClubTabBar.tsx
import { Link, useLocation } from "react-router-dom";

const tabs = [
  { to: "/club/saison", label: "Saison" },
  { to: "/club/competition", label: "Compétition" },
];

export default function ClubTabBar() {
  const { pathname } = useLocation();
  return (
    <div className="flex gap-0 mb-6">
      {tabs.map((tab) => {
        const active = pathname.startsWith(tab.to);
        return (
          <Link
            key={tab.to}
            to={tab.to}
            className={`px-5 py-2 text-sm font-semibold transition-colors border-b-2 ${
              active
                ? "text-primary border-primary"
                : "text-on-surface-variant border-transparent hover:text-on-surface"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx routing and nav**

In `frontend/src/App.tsx`:

1. Update the navLinks array — change the stats entry:
```typescript
{ to: "/club", label: "CLUB", icon: "bar_chart", end: false },
```

2. Replace the `/stats` route with:
```typescript
<Route path="/club/saison" element={<StatsPage />} />
<Route path="/club/competition" element={<ClubCompetitionPage />} />
<Route path="/club" element={<Navigate to="/club/saison" replace />} />
<Route path="/stats" element={<Navigate to="/club/saison" replace />} />
```

Add imports:
```typescript
import { Navigate } from "react-router-dom";
import ClubCompetitionPage from "./pages/ClubCompetitionPage";
```

- [ ] **Step 3: Add ClubTabBar to StatsPage**

In `frontend/src/pages/StatsPage.tsx`, add the tab bar at the top of the returned JSX, right after the opening `<div>`:

```typescript
import ClubTabBar from "../components/ClubTabBar";

// Inside the return, at the very top:
<ClubTabBar />
```

- [ ] **Step 4: Create a minimal ClubCompetitionPage placeholder**

```typescript
// frontend/src/pages/ClubCompetitionPage.tsx
import ClubTabBar from "../components/ClubTabBar";

export default function ClubCompetitionPage() {
  return (
    <div>
      <ClubTabBar />
      <h1 className="font-headline text-2xl font-bold text-on-surface">
        Analyse compétition
      </h1>
      <p className="text-sm text-on-surface-variant mt-1">
        Page en construction...
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Verify in browser**

Run the dev server and verify:
- `/club` redirects to `/club/saison`
- `/stats` redirects to `/club/saison`
- Tab bar appears on both pages
- Clicking "Compétition" tab navigates to `/club/competition`
- Sidebar "CLUB" link works

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ClubTabBar.tsx frontend/src/pages/ClubCompetitionPage.tsx frontend/src/pages/StatsPage.tsx frontend/src/App.tsx
git commit -m "feat: add club tab system with saison/competition tabs and routing"
```

---

### Task 6: ClubCompetitionPage — Filters & KPIs

**Files:**
- Modify: `frontend/src/pages/ClubCompetitionPage.tsx`

- [ ] **Step 1: Implement the filter dropdowns and KPI cards**

Replace the placeholder in `ClubCompetitionPage.tsx`:

```typescript
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ClubTabBar from "../components/ClubTabBar";
import { api, Competition, CompetitionClubAnalysis } from "../api/client";

export default function ClubCompetitionPage() {
  const [selectedSeason, setSelectedSeason] = useState<string>("");
  const [selectedCompId, setSelectedCompId] = useState<number | null>(null);

  // Fetch seasons
  const { data: seasons = [] } = useQuery({
    queryKey: ["seasons"],
    queryFn: api.competitions.seasons,
  });

  // Auto-select latest season
  const season = selectedSeason || seasons[0] || "";

  // Fetch all competitions for the season (Task 10 refines this to my_club filtering)
  const { data: competitions = [] } = useQuery({
    queryKey: ["club-competitions", season],
    queryFn: () => api.competitions.list({ season }),
    enabled: !!season,
  });

  const { data: analysis, isLoading } = useQuery({
    queryKey: ["competition-club-analysis", selectedCompId],
    queryFn: () => api.stats.competitionClubAnalysis({ competition_id: selectedCompId! }),
    enabled: !!selectedCompId,
  });

  return (
    <div>
      <ClubTabBar />

      {/* Page header */}
      <div className="mb-6">
        <h1 className="font-headline text-2xl font-bold text-on-surface">
          Analyse compétition
        </h1>
        <p className="text-sm text-on-surface-variant mt-0.5">
          Performance du club sur une compétition
        </p>
      </div>

      {/* Filter row */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">
            Saison
          </span>
          <select
            value={season}
            onChange={(e) => {
              setSelectedSeason(e.target.value);
              setSelectedCompId(null);
            }}
            className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
          >
            {seasons.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">
            Compétition
          </span>
          <select
            value={selectedCompId ?? ""}
            onChange={(e) => setSelectedCompId(e.target.value ? Number(e.target.value) : null)}
            className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary min-w-[300px]"
          >
            <option value="">Sélectionner...</option>
            {competitions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}{c.city ? ` — ${c.city}` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Content */}
      {!selectedCompId && (
        <p className="text-sm text-on-surface-variant">
          Sélectionnez une compétition pour voir l'analyse.
        </p>
      )}

      {isLoading && (
        <p className="text-sm text-on-surface-variant">Chargement...</p>
      )}

      {analysis && (
        <>
          {/* KPI Hero Row */}
          <div className="grid grid-cols-4 gap-3 mb-6">
            {[
              { value: analysis.kpis.skaters_entered, label: "Patineurs engagés" },
              { value: analysis.kpis.total_medals, label: "Médailles" },
              { value: analysis.kpis.personal_bests, label: "Records personnels" },
              {
                value: `${analysis.kpis.categories_entered}/${analysis.kpis.categories_total}`,
                label: "Catégories couvertes",
              },
            ].map((kpi) => (
              <div
                key={kpi.label}
                className="bg-surface-container-lowest rounded-xl shadow-sm p-4 text-center"
              >
                <div className="font-mono text-2xl font-bold text-primary">
                  {kpi.value}
                </div>
                <div className="text-[10px] text-on-surface-variant mt-1">
                  {kpi.label}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

**Important:** The `api.competitions.list` call needs to work with the `club` and `season` params added in Task 4. For the club filter on the dropdown, we need the backend to resolve `CLUB_SHORT` from settings. Update the `list_competitions` handler in `competitions.py` to accept a `my_club: bool = False` flag that auto-resolves the club from AppSettings. OR simply fetch all competitions for the season and let the user pick — the analysis endpoint returns empty data if no club skaters.

For simplicity, use `api.competitions.list({ season })` without the club filter for the dropdown. The dropdown shows all competitions in the season.

- [ ] **Step 2: Verify in browser**

Run dev server. Navigate to `/club/competition`. Verify:
- Season dropdown populates and auto-selects latest
- Competition dropdown shows competitions for selected season
- Selecting a competition shows KPI cards with real data

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ClubCompetitionPage.tsx
git commit -m "feat: add filters and KPI hero row to ClubCompetitionPage"
```

---

### Task 7: ClubCompetitionPage — Club Challenge & Medals Panels

**Files:**
- Modify: `frontend/src/pages/ClubCompetitionPage.tsx`

- [ ] **Step 1: Add the two-column section after the KPI row**

Inside the `{analysis && (<>...</>)}` block, after the KPI grid, add:

```typescript
{/* Two-column: Club Challenge + Medals */}
<div className="grid grid-cols-[3fr_2fr] gap-4 mb-6">
  {/* Club Challenge Ranking */}
  <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
    <div className="flex items-center justify-between mb-4">
      <h2 className="font-headline font-bold text-on-surface text-sm flex items-center gap-2">
        <span className="material-symbols-outlined text-lg">emoji_events</span>
        Classement Club Challenge
      </h2>
      <button
        onClick={() => setShowCategoryModal(true)}
        className="text-xs text-primary hover:underline underline-offset-2"
      >
        Voir le détail par catégorie ›
      </button>
    </div>
    <table className="w-full text-xs">
      <thead>
        <tr className="text-on-surface-variant text-left">
          <th className="py-1 px-2 w-8">#</th>
          <th className="py-1 px-2">Club</th>
          <th className="py-1 px-2 text-right">Points</th>
          <th className="py-1 px-2 text-right text-[10px]">Podium</th>
        </tr>
      </thead>
      <tbody>
        {analysis.club_challenge.ranking.map((entry) => (
          <tr
            key={entry.club}
            className={entry.is_my_club
              ? "bg-primary/10 font-semibold"
              : "text-on-surface-variant"
            }
          >
            <td className="py-1.5 px-2 font-mono">{entry.rank}</td>
            <td className={`py-1.5 px-2 ${entry.is_my_club ? "text-primary" : ""}`}>
              {entry.club}
            </td>
            <td className="py-1.5 px-2 text-right font-mono">{entry.total_points}</td>
            <td className="py-1.5 px-2 text-right font-mono text-on-surface-variant">
              {entry.podium_points}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>

  {/* Medals */}
  <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
    <h2 className="font-headline font-bold text-on-surface text-sm mb-4">
      Podiums du club
    </h2>
    {analysis.medals.length === 0 ? (
      <p className="text-xs text-on-surface-variant">Aucun podium</p>
    ) : (
      <div className="flex flex-col gap-2">
        {analysis.medals.map((m, i) => {
          const bg = m.rank === 1 ? "bg-[#fff8e1]" : m.rank === 2 ? "bg-[#f5f5f5]" : "bg-[#fdf0ef]";
          const icon = m.rank === 1 ? "🥇" : m.rank === 2 ? "🥈" : "🥉";
          return (
            <div key={i} className={`flex items-center gap-2 p-2 rounded-lg ${bg}`}>
              <span className="text-lg">{icon}</span>
              <div>
                <div className="font-semibold text-xs text-on-surface">{m.skater_name}</div>
                <div className="text-[10px] text-on-surface-variant">
                  {m.category} — {m.combined_total?.toFixed(2)} pts
                </div>
              </div>
            </div>
          );
        })}
      </div>
    )}
  </div>
</div>
```

Add state for the modal at the top of the component:
```typescript
const [showCategoryModal, setShowCategoryModal] = useState(false);
```

- [ ] **Step 2: Verify in browser**

Check that the two-column layout renders correctly with real data.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ClubCompetitionPage.tsx
git commit -m "feat: add club challenge ranking and medals panels"
```

---

### Task 8: ClubCompetitionPage — Detailed Results Table

**Files:**
- Modify: `frontend/src/pages/ClubCompetitionPage.tsx`

- [ ] **Step 1: Add the detailed results table**

After the two-column section, add:

```typescript
{/* Detailed Results */}
<div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
  <h2 className="font-headline font-bold text-on-surface text-sm mb-4">
    Résultats détaillés
  </h2>
  <table className="w-full text-xs">
    <thead>
      <tr className="text-on-surface-variant text-left">
        <th className="py-1 px-2">Patineur</th>
        <th className="py-1 px-2">Catégorie</th>
        <th className="py-1 px-2 text-center">Rang</th>
        <th className="py-1 px-2 text-right">Score</th>
        <th className="py-1 px-2 text-center w-12"></th>
      </tr>
    </thead>
    <tbody>
      {analysis.results.map((r, i) => (
        <tr
          key={i}
          className={r.medal ? "" : "text-on-surface-variant"}
        >
          <td className="py-1.5 px-2 font-medium">{r.skater_name}</td>
          <td className="py-1.5 px-2">{r.category}</td>
          <td className="py-1.5 px-2 text-center font-mono">
            {r.overall_rank} / {r.total_skaters}
          </td>
          <td className="py-1.5 px-2 text-right font-mono">
            {r.combined_total?.toFixed(2)}
          </td>
          <td className="py-1.5 px-2 text-center">
            {r.medal === 1 && "🥇"}
            {r.medal === 2 && "🥈"}
            {r.medal === 3 && "🥉"}
            {r.is_pb && " ⭐"}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
  <div className="mt-2 text-[10px] text-on-surface-variant">
    ⭐ = Record personnel
  </div>
</div>
```

- [ ] **Step 2: Verify in browser**

Check table renders with real data, medals and PB stars show correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ClubCompetitionPage.tsx
git commit -m "feat: add detailed results table to ClubCompetitionPage"
```

---

### Task 9: Category Breakdown Modal

**Files:**
- Create: `frontend/src/components/CategoryBreakdownModal.tsx`
- Modify: `frontend/src/pages/ClubCompetitionPage.tsx`

- [ ] **Step 1: Create the modal component**

```typescript
// frontend/src/components/CategoryBreakdownModal.tsx
import { useState, useEffect } from "react";
import { CategoryBreakdown } from "../api/client";

interface Props {
  breakdowns: CategoryBreakdown[];
  onClose: () => void;
}

export default function CategoryBreakdownModal({ breakdowns, onClose }: Props) {
  const [expanded, setExpanded] = useState<string | null>(
    breakdowns[0]?.category ?? null
  );

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-on-surface/40" />
      <div
        className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-headline font-bold text-on-surface text-base">
            Détail par catégorie
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Accordion */}
        <div className="space-y-2">
          {breakdowns.map((bd) => {
            const isOpen = expanded === bd.category;
            const clubTotal = bd.club_skaters.reduce((s, sk) => s + sk.total_points, 0);
            return (
              <div key={bd.category}>
                <button
                  onClick={() => setExpanded(isOpen ? null : bd.category)}
                  className="w-full flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg text-left hover:bg-surface-container-high transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">
                    {isOpen ? "expand_more" : "chevron_right"}
                  </span>
                  <span className="font-semibold text-xs text-on-surface">
                    {bd.category}
                  </span>
                  <span className="text-[10px] text-on-surface-variant ml-auto">
                    {bd.club_skaters.length} patineur{bd.club_skaters.length > 1 ? "s" : ""}
                    {" · "}
                    {clubTotal} pts club
                  </span>
                </button>
                {isOpen && bd.club_skaters.length > 0 && (
                  <table className="w-[calc(100%-20px)] ml-5 mt-1 text-xs">
                    <thead>
                      <tr className="text-on-surface-variant text-[10px]">
                        <td className="py-1 px-2">Rang</td>
                        <td className="py-1 px-2">Patineur</td>
                        <td className="py-1 px-2 text-right">Base</td>
                        <td className="py-1 px-2 text-right">Podium</td>
                        <td className="py-1 px-2 text-right font-semibold">Total</td>
                      </tr>
                    </thead>
                    <tbody>
                      {bd.club_skaters.map((sk) => (
                        <tr key={sk.skater_name}>
                          <td className="py-1 px-2 font-mono">{sk.rank}</td>
                          <td className="py-1 px-2 font-medium">{sk.skater_name}</td>
                          <td className="py-1 px-2 text-right font-mono">{sk.base_points}</td>
                          <td className="py-1 px-2 text-right font-mono text-primary">
                            {sk.podium_points > 0 ? `+${sk.podium_points}` : "—"}
                          </td>
                          <td className="py-1 px-2 text-right font-mono font-bold">
                            {sk.total_points}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {isOpen && bd.club_skaters.length === 0 && (
                  <p className="ml-5 mt-1 text-[10px] text-on-surface-variant">
                    Aucun patineur du club dans cette catégorie
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire modal into ClubCompetitionPage**

In `ClubCompetitionPage.tsx`, add at the bottom of the component (before the closing `</div>`):

```typescript
import CategoryBreakdownModal from "../components/CategoryBreakdownModal";

// Inside the JSX, at the end:
{showCategoryModal && analysis && (
  <CategoryBreakdownModal
    breakdowns={analysis.club_challenge.category_breakdown}
    onClose={() => setShowCategoryModal(false)}
  />
)}
```

- [ ] **Step 3: Verify in browser**

Click "Voir le détail par catégorie" and verify:
- Modal opens with overlay
- Categories are listed as accordion
- First category is expanded by default
- Point breakdown table shows correctly
- Escape key and overlay click close the modal

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CategoryBreakdownModal.tsx frontend/src/pages/ClubCompetitionPage.tsx
git commit -m "feat: add category breakdown modal for club challenge details"
```

---

### Task 10: Competition Dropdown Club Filtering

**Files:**
- Modify: `frontend/src/pages/ClubCompetitionPage.tsx`
- Modify: `backend/app/routes/competitions.py`

The competition dropdown should only show competitions where the club had at least one skater. This requires the backend `list_competitions` to support filtering by the configured club.

- [ ] **Step 1: Add `my_club` flag to the competitions list endpoint**

In `backend/app/routes/competitions.py`, update `list_competitions`:

```python
from app.models.app_settings import AppSettings

@get("/")
async def list_competitions(
    session: AsyncSession,
    club: str | None = None,
    season: str | None = None,
    my_club: bool = False,
) -> list[dict]:
    # Resolve club from settings if my_club flag is set
    effective_club = club
    if my_club and not club:
        settings_result = await session.execute(select(AppSettings).limit(1))
        settings = settings_result.scalar_one_or_none()
        if settings:
            effective_club = settings.club_short

    stmt = select(Competition).order_by(Competition.date.desc())
    if season:
        stmt = stmt.where(Competition.season == season)
    if effective_club:
        stmt = (
            stmt
            .join(CategoryResult, CategoryResult.competition_id == Competition.id)
            .join(Skater, Skater.id == CategoryResult.skater_id)
            .where(func.upper(Skater.club) == effective_club.upper())
            .distinct()
        )
    result = await session.execute(stmt)
    return [competition_to_dict(c) for c in result.scalars()]
```

- [ ] **Step 2: Update frontend API client**

Update `api.competitions.list` in `client.ts` to support `my_club`:

```typescript
list: (params?: { club?: string; season?: string; my_club?: boolean }) => {
  const qs = new URLSearchParams();
  if (params?.club) qs.set("club", params.club);
  if (params?.season) qs.set("season", params.season);
  if (params?.my_club) qs.set("my_club", "true");
  const query = qs.toString() ? `?${qs}` : "";
  return request<Competition[]>(`/competitions/${query}`);
},
```

- [ ] **Step 3: Update ClubCompetitionPage to use my_club filter**

Change the competitions query in `ClubCompetitionPage.tsx`:

```typescript
const { data: competitions = [] } = useQuery({
  queryKey: ["club-competitions", season],
  queryFn: () => api.competitions.list({ season, my_club: true }),
  enabled: !!season,
});
```

- [ ] **Step 4: Verify existing competitions list still works**

Make sure `CompetitionsPage.tsx` still calls `api.competitions.list()` without params and works as before.

- [ ] **Step 5: Add test for my_club flag**

Add to `backend/tests/test_competition_analysis.py`:

```python
@pytest.mark.asyncio
async def test_competitions_filter_my_club(client: AsyncClient, admin_token: str, seed_club_analysis):
    resp = await client.get(
        "/api/competitions/?my_club=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    names = {c["name"] for c in data}
    assert "Comp A" in names
    assert "Comp Prior" in names
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && python -m pytest tests/test_competition_analysis.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/competitions.py frontend/src/api/client.ts frontend/src/pages/ClubCompetitionPage.tsx backend/tests/test_competition_analysis.py
git commit -m "feat: add my_club flag for competition filtering in dropdown"
```

---

### Task 11: Final Polish & Verification

**Files:**
- Various — cleanup and edge cases

- [ ] **Step 1: Handle empty state gracefully**

In `ClubCompetitionPage.tsx`, after the analysis loads, if `analysis.results.length === 0`, show:
```typescript
{analysis && analysis.results.length === 0 && (
  <p className="text-sm text-on-surface-variant">
    Aucun patineur du club dans cette compétition.
  </p>
)}
```

- [ ] **Step 2: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests pass, no regressions

- [ ] **Step 3: Manual browser verification**

Verify the complete flow:
1. Navigate to `/club` → redirects to `/club/saison`
2. Click "Compétition" tab → shows `/club/competition`
3. Select a season and competition
4. KPI cards show correct counts
5. Club challenge table ranks clubs correctly
6. Medals panel shows podium finishers
7. Results table shows all club skaters with medals and PB stars
8. "Voir le détail par catégorie" opens modal with accordion
9. `/stats` redirects to `/club/saison`

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "feat: polish ClubCompetitionPage edge cases and empty states"
```
