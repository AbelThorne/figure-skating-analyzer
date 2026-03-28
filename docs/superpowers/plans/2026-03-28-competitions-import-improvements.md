# Competitions Import Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ligue field with detection/filtering, auto-polling for competition updates, and status labels ("Prochainement"/"En cours") based on competition dates.

**Architecture:** Extend the Competition model with 4 new columns (`ligue`, `date_end`, `polling_enabled`, `polling_activated_at`). Ligue detection happens in `competition_metadata.py`, date_end extraction in the scraper. A background async polling loop in `main.py` lifespan submits import+enrich jobs hourly. Status labels are computed client-side from dates.

**Tech Stack:** Python/Litestar/SQLAlchemy (backend), React/TypeScript/TanStack Query (frontend), pytest (tests)

---

## File Structure

### Files to modify

| File | Changes |
|------|---------|
| `backend/app/models/competition.py` | Add `ligue`, `date_end`, `polling_enabled`, `polling_activated_at` columns |
| `backend/app/database.py` | Add 4 migration entries to `_MIGRATIONS` |
| `backend/app/services/site_scraper.py` | Add `date_end` to `ScrapedCompetitionInfo`, extract both dates |
| `backend/app/services/competition_metadata.py` | Add `detect_ligue()` function, include in `detect_metadata()` |
| `backend/app/services/import_service.py` | Store `ligue` and `date_end` during import |
| `backend/app/routes/competitions.py` | Update DTO, add polling endpoint, add ligue filter/edit support |
| `backend/app/main.py` | Add polling loop in lifespan |
| `frontend/src/api/client.ts` | Update `Competition` type, add `LIGUES` constant, add `togglePolling` API |
| `frontend/src/pages/CompetitionsPage.tsx` | Add ligue filter, polling toggle, status badges |
| `frontend/src/pages/CompetitionPage.tsx` | Add status badge in header |

### Files to create

| File | Purpose |
|------|---------|
| `backend/tests/test_ligue_detection.py` | Tests for ligue detection logic |
| `backend/tests/test_polling.py` | Tests for polling auto-disable logic |

### Existing test files to modify

| File | Changes |
|------|---------|
| `backend/tests/test_fs_manager_scraper.py` | Add `date_end` assertions to existing tests |

---

### Task 1: Add new columns to Competition model + migration

**Files:**
- Modify: `backend/app/models/competition.py:1-31`
- Modify: `backend/app/database.py:41-67`

- [ ] **Step 1: Add columns to Competition model**

In `backend/app/models/competition.py`, add 4 new columns after `last_import_log`:

```python
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Date, Text, JSON, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    season: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    discipline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rink: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ligue: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    competition_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    polling_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    polling_activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_import_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="competition", cascade="all, delete-orphan"
    )
    category_results: Mapped[list["CategoryResult"]] = relationship(  # noqa: F821
        "CategoryResult", back_populates="competition", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Add migration entries in database.py**

In `backend/app/database.py`, add these 4 entries to the `_MIGRATIONS` list (after the existing entries around line 53):

```python
        ("competitions", "ligue", "VARCHAR(50)"),
        ("competitions", "date_end", "DATE"),
        ("competitions", "polling_enabled", "BOOLEAN DEFAULT 0"),
        ("competitions", "polling_activated_at", "DATETIME"),
```

- [ ] **Step 3: Run tests to verify no regressions**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: All existing tests pass (new columns are nullable with defaults, so no breakage).

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/competition.py backend/app/database.py
git commit -m "feat: add ligue, date_end, polling_enabled, polling_activated_at columns to Competition"
```

---

### Task 2: Extract date_end from scraper

**Files:**
- Modify: `backend/app/services/site_scraper.py:41-47` (ScrapedCompetitionInfo dataclass)
- Modify: `backend/app/services/site_scraper.py:98-132` (parse_competition_info method)
- Modify: `backend/tests/test_fs_manager_scraper.py`

- [ ] **Step 1: Write failing tests for date_end extraction**

Add these tests to `backend/tests/test_fs_manager_scraper.py`:

```python
def test_parse_competition_info_extracts_date_end():
    html = """<html>
    <head><title>Test Event 2025</title></head>
    <body>
    <table class="MainTab">
    <tr><td><img src="evt_header.jpg"></td></tr>
    <tr><td>
        <table width="100%" cellspacing="1" align="center">
            <tr>
                <td class="caption3" width="50%">TOULOUSE / FRA</td>
                <td class="caption3" width="50%">Alex JANY</td>
            </tr>
        </table>
    </td></tr>
    <tr class="caption3"><td>20.03.2026 - 22.03.2026</td></tr>
    </table>
    </body></html>"""
    scraper = FSManagerScraper()
    info = scraper.parse_competition_info(html)
    assert info.date == "2026-03-20"
    assert info.date_end == "2026-03-22"


def test_parse_competition_info_single_date_sets_date_end():
    html = """<html>
    <head><title>Test Event</title></head>
    <body>15.11.2025</body></html>"""
    scraper = FSManagerScraper()
    info = scraper.parse_competition_info(html)
    assert info.date == "2025-11-15"
    assert info.date_end == "2025-11-15"


def test_parse_competition_info_no_date_no_date_end():
    html = "<html><head><title>Test</title></head><body>No dates here</body></html>"
    scraper = FSManagerScraper()
    info = scraper.parse_competition_info(html)
    assert info.date is None
    assert info.date_end is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_fs_manager_scraper.py::test_parse_competition_info_extracts_date_end tests/test_fs_manager_scraper.py::test_parse_competition_info_single_date_sets_date_end tests/test_fs_manager_scraper.py::test_parse_competition_info_no_date_no_date_end -v`
Expected: FAIL — `ScrapedCompetitionInfo` has no `date_end` attribute.

- [ ] **Step 3: Add date_end to ScrapedCompetitionInfo**

In `backend/app/services/site_scraper.py`, modify the `ScrapedCompetitionInfo` dataclass (around line 41):

```python
@dataclass
class ScrapedCompetitionInfo:
    """Competition metadata extracted from the index page."""
    name: str | None = None
    date: str | None = None  # ISO format YYYY-MM-DD (first day of competition)
    date_end: str | None = None  # ISO format YYYY-MM-DD (last day of competition)
    city: str | None = None
    country: str | None = None
    rink: str | None = None
```

- [ ] **Step 4: Extract date_end in parse_competition_info**

In `backend/app/services/site_scraper.py`, replace the date extraction block in `parse_competition_info` (around lines 108-113) with:

```python
        # Dates from DD.MM.YYYY patterns (typically a date range like "20.03.2026 - 22.03.2026")
        text = soup.get_text()
        date_matches = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if date_matches:
            day, month, year = date_matches[0]
            info.date = f"{year}-{month}-{day}"
            if len(date_matches) >= 2:
                day2, month2, year2 = date_matches[-1]
                info.date_end = f"{year2}-{month2}-{day2}"
            else:
                info.date_end = info.date
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_fs_manager_scraper.py -v`
Expected: All tests pass, including the 3 new ones.

- [ ] **Step 6: Update existing test assertion**

The existing `test_parse_competition_info_extracts_city_country_rink` test has a date range "04.10.2025 - 05.10.2025". Add `date_end` assertion to it:

```python
    assert info.date_end == "2025-10-05"
```

- [ ] **Step 7: Run all tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_fs_manager_scraper.py -v`
Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/site_scraper.py backend/tests/test_fs_manager_scraper.py
git commit -m "feat: extract date_end from competition banner date range"
```

---

### Task 3: Implement ligue detection

**Files:**
- Modify: `backend/app/services/competition_metadata.py`
- Create: `backend/tests/test_ligue_detection.py`

- [ ] **Step 1: Write failing tests for ligue detection**

Create `backend/tests/test_ligue_detection.py`:

```python
from app.services.competition_metadata import detect_ligue


class TestLigueDetection:
    def test_csnpa_in_url_returns_ffsg(self):
        result = detect_ligue(
            "https://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/CSNPA_AUTOMNE_2025/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_csnpa_in_url_path_segment_returns_ffsg(self):
        result = detect_ligue(
            "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2025-TF-Nimes/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_csnpa_in_html_returns_ffsg(self):
        result = detect_ligue(
            "https://example.com/event/index.htm",
            "<html><title>CSNPA Automne 2025</title><body>text</body></html>",
        )
        assert result == "FFSG"

    def test_csnpa_case_insensitive(self):
        result = detect_ligue(
            "https://example.com/csnpa_event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_isu_domain_returns_isu(self):
        result = detect_ligue(
            "https://results.isu.org/results/season2526/ec2026/",
            "<html><title>Test</title></html>",
        )
        assert result == "ISU"

    def test_isuresults_domain_returns_isu(self):
        result = detect_ligue(
            "https://www.isuresults.com/results/season2526/wc2026/",
            "<html><title>Test</title></html>",
        )
        assert result == "ISU"

    def test_alpes_domain_without_csnpa_returns_aura(self):
        result = detect_ligue(
            "https://ligue-des-alpes-patinage.org/Results/TDF_Grenoble/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "AURA"

    def test_occitanie_domain_without_csnpa_returns_occitanie(self):
        result = detect_ligue(
            "https://ligue-occitanie-sg.com/Resultats/2025-2026/CR-Castres/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Occitanie"

    def test_unknown_domain_returns_autres(self):
        result = detect_ligue(
            "https://example.com/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Autres"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_ligue_detection.py -v`
Expected: FAIL — `detect_ligue` not defined.

- [ ] **Step 3: Implement detect_ligue**

Add to `backend/app/services/competition_metadata.py`, after the existing imports:

```python
# Domain → ligue mapping (when CSNPA is NOT present)
_DOMAIN_TO_LIGUE: dict[str, str] = {
    "ligue-des-alpes-patinage.org": "AURA",
    "ligue-occitanie-sg.com": "Occitanie",
}


def detect_ligue(url: str, html: str) -> str:
    """Detect the ligue (regional league) from URL and HTML content.

    Priority:
    1. CSNPA mention in URL or HTML → FFSG (national)
    2. ISU domains → ISU
    3. Domain mapping → regional ligue
    4. Fallback → Autres
    """
    from urllib.parse import urlparse

    # 1. CSNPA in URL or HTML → FFSG
    if re.search(r"csnpa", url, re.IGNORECASE) or re.search(r"csnpa", html[:3000], re.IGNORECASE):
        return "FFSG"

    # 2. ISU domains
    domain = urlparse(url).hostname or ""
    if any(domain.endswith(d) for d in _ISU_DOMAINS):
        return "ISU"

    # 3. Domain mapping
    for domain_pattern, ligue in _DOMAIN_TO_LIGUE.items():
        if domain.endswith(domain_pattern):
            return ligue

    # 4. Fallback
    return "Autres"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_ligue_detection.py -v`
Expected: All 9 tests pass.

- [ ] **Step 5: Include ligue in detect_metadata return**

Modify `detect_metadata()` in `backend/app/services/competition_metadata.py` to also return `ligue`:

```python
def detect_metadata(url: str, html: str, *, scraped_city: str | None = None, scraped_country: str | None = None) -> dict:
    comp_type = _detect_type(url, html)
    season = _detect_season(url, html)
    city = scraped_city or _detect_city(url, html)
    country = _map_country_code(scraped_country) if scraped_country else _detect_country(url)
    ligue = detect_ligue(url, html)
    return {
        "competition_type": comp_type,
        "city": city,
        "country": country,
        "season": season,
        "ligue": ligue,
    }
```

- [ ] **Step 6: Run all metadata tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_competition_metadata.py tests/test_ligue_detection.py -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/competition_metadata.py backend/tests/test_ligue_detection.py
git commit -m "feat: add ligue detection from URL/HTML with CSNPA priority"
```

---

### Task 4: Store ligue and date_end during import

**Files:**
- Modify: `backend/app/services/import_service.py:94-136`
- Modify: `backend/app/routes/competitions.py:160-204` (backfill-metadata)

- [ ] **Step 1: Store date_end and ligue in run_import**

In `backend/app/services/import_service.py`, after line 115 (`comp.date = date_type.fromisoformat(comp_info.date)`), add date_end storage:

```python
    if comp_info.date_end and not comp.date_end:
        comp.date_end = date_type.fromisoformat(comp_info.date_end)
```

Then inside the `if not comp.metadata_confirmed:` block (after line 135 `comp.rink = comp_info.rink`), add ligue storage:

```python
        if meta.get("ligue"):
            comp.ligue = meta["ligue"]
```

- [ ] **Step 2: Update backfill-metadata to store ligue**

In `backend/app/routes/competitions.py`, in the `backfill_metadata` handler, after the existing metadata updates (around line 198), add:

```python
                if meta.get("ligue") and not comp.ligue:
                    comp.ligue = meta["ligue"]
```

Also add date_end extraction in backfill. After `comp_info = scraper.parse_competition_info(html)` (line 183), add:

```python
                if comp_info.date_end and not comp.date_end:
                    comp.date_end = date_type.fromisoformat(comp_info.date_end)
```

Add the import at the top of the file:

```python
from datetime import date as date_type, datetime, timezone
```

- [ ] **Step 3: Run all tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/import_service.py backend/app/routes/competitions.py
git commit -m "feat: store ligue and date_end during import and backfill"
```

---

### Task 5: Update backend DTO and routes (ligue filter, polling endpoint, edit support)

**Files:**
- Modify: `backend/app/routes/competitions.py`

- [ ] **Step 1: Update competition_to_dict**

In `backend/app/routes/competitions.py`, update `competition_to_dict()` (around line 19) to include the new fields:

```python
def competition_to_dict(c: Competition) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "url": c.url,
        "date": c.date.isoformat() if c.date else None,
        "date_end": c.date_end.isoformat() if c.date_end else None,
        "season": c.season,
        "discipline": c.discipline,
        "city": c.city,
        "country": c.country,
        "rink": c.rink,
        "ligue": c.ligue,
        "competition_type": c.competition_type,
        "metadata_confirmed": c.metadata_confirmed,
        "polling_enabled": c.polling_enabled,
        "polling_activated_at": c.polling_activated_at.isoformat() if c.polling_activated_at else None,
    }
```

- [ ] **Step 2: Add ligue filter to list_competitions**

Update `list_competitions` handler signature to add `ligue` parameter:

```python
@get("/")
async def list_competitions(
    request: Request,
    session: AsyncSession,
    club: str | None = None,
    season: str | None = None,
    ligue: str | None = None,
    my_club: bool = False,
) -> list[dict]:
```

Add filtering after the existing `season` filter (around line 55):

```python
    if ligue:
        stmt = stmt.where(Competition.ligue == ligue)
```

- [ ] **Step 3: Add ligue to updatable fields**

In `update_competition` handler, update the field list (around line 98):

```python
    for field in ("city", "country", "competition_type", "season", "ligue"):
```

- [ ] **Step 4: Add polling toggle endpoint**

Add a new route handler before the `router` definition:

```python
@post("/{competition_id:int}/polling")
async def toggle_polling(competition_id: int, data: dict, request: Request, session: AsyncSession) -> dict:
    require_admin(request)
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    enabled = data.get("enabled", False)
    comp.polling_enabled = enabled
    if enabled:
        comp.polling_activated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(comp)
    return competition_to_dict(comp)
```

Add the import at the top:

```python
from datetime import datetime, timezone
```

- [ ] **Step 5: Register toggle_polling in router**

Add `toggle_polling` to the `route_handlers` list in the `Router()` call:

```python
router = Router(
    path="/api/competitions",
    route_handlers=[
        list_competitions,
        list_seasons,
        get_competition,
        create_competition,
        update_competition,
        delete_competition,
        import_competition,
        get_import_status,
        enrich_competition,
        confirm_metadata,
        backfill_metadata,
        bulk_import,
        toggle_polling,
    ],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/competitions.py
git commit -m "feat: update DTO, add ligue filter, polling endpoint, and ligue edit support"
```

---

### Task 6: Add polling loop in lifespan

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_polling.py`

- [ ] **Step 1: Write test for polling auto-disable logic**

Create `backend/tests/test_polling.py`:

```python
import pytest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition


@pytest.mark.asyncio
async def test_polling_auto_disable_after_week(db_session: AsyncSession):
    """Competitions with date_end > 7 days ago should have polling disabled."""
    comp = Competition(
        name="Old Event",
        url="https://example.com/old-event/index.htm",
        date=date(2026, 3, 1),
        date_end=date(2026, 3, 2),
        polling_enabled=True,
        polling_activated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    # Simulate the polling check logic
    from app.main import _should_disable_polling
    assert _should_disable_polling(comp, today=date(2026, 3, 15)) is True
    assert _should_disable_polling(comp, today=date(2026, 3, 8)) is False
    assert _should_disable_polling(comp, today=date(2026, 3, 9)) is False
    assert _should_disable_polling(comp, today=date(2026, 3, 10)) is True


@pytest.mark.asyncio
async def test_polling_not_disabled_without_date_end(db_session: AsyncSession):
    """Competitions without date_end should keep polling active."""
    comp = Competition(
        name="No End Date",
        url="https://example.com/no-end/index.htm",
        polling_enabled=True,
        polling_activated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    from app.main import _should_disable_polling
    assert _should_disable_polling(comp, today=date(2026, 12, 31)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_polling.py -v`
Expected: FAIL — `_should_disable_polling` not defined.

- [ ] **Step 3: Implement _should_disable_polling and polling loop**

In `backend/app/main.py`, add the imports and helper function:

```python
import asyncio
import logging
from datetime import date as date_type, timedelta

from sqlalchemy import select

logger = logging.getLogger(__name__)
```

Add the helper function before the `lifespan` function:

```python
def _should_disable_polling(comp: "Competition", today: date_type | None = None) -> bool:
    """Return True if polling should be auto-disabled for this competition."""
    if today is None:
        today = date_type.today()
    if not comp.date_end:
        return False
    return (comp.date_end + timedelta(days=7)) < today
```

Add the polling loop function:

```python
async def _polling_loop() -> None:
    """Background loop that polls enabled competitions every hour."""
    from app.models.competition import Competition

    while True:
        await asyncio.sleep(3600)
        try:
            async with async_session_factory() as session:
                stmt = select(Competition).where(Competition.polling_enabled == True)  # noqa: E712
                comps = (await session.execute(stmt)).scalars().all()
                today = date_type.today()
                for comp in comps:
                    if _should_disable_polling(comp, today):
                        comp.polling_enabled = False
                        logger.info("Auto-disabled polling for competition %d (%s)", comp.id, comp.name)
                        continue
                    job_queue.create_job("import", comp.id)
                    job_queue.create_job("enrich", comp.id)
                    logger.info("Polling: submitted import+enrich for competition %d (%s)", comp.id, comp.name)
                await session.commit()
        except Exception:
            logger.exception("Error in polling loop")
```

- [ ] **Step 4: Start and stop polling loop in lifespan**

Update the `lifespan` function in `backend/app/main.py`:

```python
@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncGenerator[None, None]:
    await init_db()

    async def _handle_job(job: dict) -> dict:
        async with async_session_factory() as session:
            if job["type"] == "import":
                return await run_import(session, job["competition_id"], force=False)
            elif job["type"] == "reimport":
                return await run_import(session, job["competition_id"], force=True)
            elif job["type"] == "enrich":
                return await run_enrich(session, job["competition_id"], force=False)
            else:
                raise ValueError(f"Unknown job type: {job['type']}")

    job_queue.set_handler(_handle_job)
    await job_queue.start_worker()
    polling_task = asyncio.create_task(_polling_loop())
    try:
        yield
    finally:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        await job_queue.stop_worker()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_polling.py -v`
Expected: All pass.

- [ ] **Step 6: Run all tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/test_polling.py
git commit -m "feat: add hourly polling loop with auto-disable after 1 week"
```

---

### Task 7: Update frontend types, constants, and API

**Files:**
- Modify: `frontend/src/api/client.ts:107-135` (Competition interface + constants)
- Modify: `frontend/src/api/client.ts:730-762` (API functions)

- [ ] **Step 1: Update Competition interface**

In `frontend/src/api/client.ts`, update the `Competition` interface (around line 107):

```typescript
export interface Competition {
  id: number;
  name: string;
  url: string;
  date: string | null;
  date_end: string | null;
  season: string | null;
  discipline: string | null;
  city: string | null;
  country: string | null;
  rink: string | null;
  ligue: string | null;
  competition_type: string | null;
  metadata_confirmed: boolean;
  polling_enabled: boolean;
  polling_activated_at: string | null;
}
```

- [ ] **Step 2: Add LIGUES constant**

Add after the `COMPETITION_TYPES` constant (around line 135):

```typescript
export const LIGUES: Record<string, string> = {
  ISU: "ISU",
  FFSG: "FFSG",
  Occitanie: "Occitanie",
  Aquitaine: "Aquitaine",
  "Ile-de-France": "Ile-de-France",
  AURA: "AURA",
  "Grand Est": "Grand Est",
  "Pays de Loire": "Pays de Loire",
  Bretagne: "Bretagne",
  "Bourgogne Franche-Comte": "Bourgogne Franche-Comte",
  "Centre Val de Loire": "Centre Val de Loire",
  "Hauts de France": "Hauts de France",
  Normandie: "Normandie",
  Autres: "Autres",
};
```

- [ ] **Step 3: Add togglePolling API function and update update type**

In the `competitions` section of the `api` object, add the `togglePolling` function (after `backfillMetadata`):

```typescript
    togglePolling: (id: number, enabled: boolean) =>
      request<Competition>(`/competitions/${id}/polling`, {
        method: "POST",
        body: JSON.stringify({ enabled }),
      }),
```

Also update the `update` function to include `ligue`:

```typescript
    update: (id: number, data: Partial<Pick<Competition, "city" | "country" | "competition_type" | "season" | "ligue">>) =>
      request<Competition>(`/competitions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: update Competition type with ligue, date_end, polling fields + API"
```

---

### Task 8: Add ligue filter, polling toggle, and status badges to CompetitionsPage

**Files:**
- Modify: `frontend/src/pages/CompetitionsPage.tsx`

- [ ] **Step 1: Add imports and state**

Update the imports at the top of `frontend/src/pages/CompetitionsPage.tsx`:

```typescript
import { api, Competition, JobInfo, COMPETITION_TYPES, LIGUES } from "../api/client";
```

Add new state variables after the existing filter state (around line 43):

```typescript
  const [filterLigue, setFilterLigue] = useState<string>("all");
  const [showPolledOnly, setShowPolledOnly] = useState(false);
```

- [ ] **Step 2: Add polling toggle mutation**

Add after the existing `confirmMutation` (around line 102):

```typescript
  const pollingMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api.competitions.togglePolling(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["competitions"] }),
  });
```

- [ ] **Step 3: Update filtering logic**

Update `filteredCompetitions` (around line 119) to add ligue and polling filters:

```typescript
  const filteredCompetitions = (competitions ?? [])
    .filter((c) => filterSeason === "all" || c.season === filterSeason)
    .filter((c) => filterType === "all" || c.competition_type === filterType)
    .filter((c) => filterLigue === "all" || c.ligue === filterLigue)
    .filter((c) => !showUnconfirmedOnly || !c.metadata_confirmed)
    .filter((c) => !showPolledOnly || c.polling_enabled)
    .sort((a, b) => {
      // ... existing sort logic unchanged
    });
```

- [ ] **Step 4: Add ligue filter dropdown to filter bar**

Add after the "Type" filter dropdown (around line 237), before the "Trier par" dropdown:

```tsx
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Ligue</span>
            <select
              value={filterLigue}
              onChange={(e) => setFilterLigue(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">Toutes</option>
              {Object.entries(LIGUES).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
```

- [ ] **Step 5: Add "Suivi auto" checkbox**

Add after the existing "A verifier uniquement" checkbox (around line 261):

```tsx
          <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer">
            <input
              type="checkbox"
              checked={showPolledOnly}
              onChange={(e) => setShowPolledOnly(e.target.checked)}
              className="accent-primary"
            />
            Suivi auto
          </label>
```

- [ ] **Step 6: Add competition status badge helper**

Add this helper function before the `return` statement of `CompetitionsPage` (around line 140):

```typescript
  function getCompetitionStatus(c: Competition): { label: string; className: string } | null {
    if (!c.date) return null;
    const today = new Date().toISOString().split("T")[0];
    const endDate = c.date_end ?? c.date;
    if (c.date > today) {
      return { label: "Prochainement", className: "bg-surface-container text-on-surface-variant" };
    }
    if (c.date <= today && endDate >= today) {
      return { label: "En cours", className: "bg-primary/10 text-primary" };
    }
    return null;
  }
```

- [ ] **Step 7: Add status badge and polling toggle in competition row**

In the competition row JSX, after the existing `!c.metadata_confirmed` badge (around line 331), add the status badge:

```tsx
                    {(() => {
                      const status = getCompetitionStatus(c);
                      return status ? (
                        <span className={`${status.className} text-[10px] font-semibold px-2 py-0.5 rounded-full`}>
                          {status.label}
                        </span>
                      ) : null;
                    })()}
```

Add the polling toggle button in the admin action buttons area (at the beginning of the admin buttons div, around line 344), before the "Valider" button:

```tsx
                    <button
                      onClick={() => pollingMutation.mutate({ id: c.id, enabled: !c.polling_enabled })}
                      disabled={pollingMutation.isPending}
                      className={`rounded-lg py-1.5 px-2 text-xs font-bold active:scale-95 transition-all flex items-center gap-1 ${
                        c.polling_enabled
                          ? "bg-primary/10 text-primary"
                          : "bg-surface-container text-on-surface-variant"
                      }`}
                      title={c.polling_enabled ? "Suivi automatique actif" : "Activer le suivi automatique"}
                    >
                      <span className="material-symbols-outlined text-base leading-none">sync</span>
                    </button>
```

- [ ] **Step 8: Add ligue to the edit form**

In the inline metadata editor section (around line 461), add a ligue dropdown. Insert it after the "Saison" input field:

```tsx
                    <div className="flex-1 min-w-[150px]">
                      <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Ligue</label>
                      <select
                        value={editForm.ligue}
                        onChange={(e) => setEditForm((f) => ({ ...f, ligue: e.target.value }))}
                        className={inputClass}
                      >
                        <option value="">—</option>
                        {Object.entries(LIGUES).map(([code, label]) => (
                          <option key={code} value={code}>{label}</option>
                        ))}
                      </select>
                    </div>
```

Also update the `editForm` state type and initialization (around line 83):

```typescript
  const [editForm, setEditForm] = useState<{
    city: string;
    country: string;
    competition_type: string;
    season: string;
    ligue: string;
  }>({ city: "", country: "", competition_type: "", season: "", ligue: "" });
```

And update where `editForm` is populated when clicking "Modifier" (around line 357):

```typescript
                        setEditForm({
                          city: c.city ?? "",
                          country: c.country ?? "",
                          competition_type: c.competition_type ?? "",
                          season: c.season ?? "",
                          ligue: c.ligue ?? "",
                        });
```

- [ ] **Step 9: Add ligue to the competition meta line**

Update the meta line (around line 333) to include ligue:

```tsx
                  <p className="text-xs text-on-surface-variant mt-1">
                    {[
                      c.city && c.country ? `${c.city}, ${c.country}` : c.city || c.country,
                      c.date ? new Date(c.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }) : null,
                      c.season,
                      c.ligue,
                    ].filter(Boolean).join(" · ")}
                  </p>
```

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/CompetitionsPage.tsx
git commit -m "feat: add ligue filter, polling toggle, and status badges to CompetitionsPage"
```

---

### Task 9: Add status badge to CompetitionPage detail header

**Files:**
- Modify: `frontend/src/pages/CompetitionPage.tsx:232-259`

- [ ] **Step 1: Import Competition type**

Update the import at the top of `frontend/src/pages/CompetitionPage.tsx`:

```typescript
import { api, Score, CategoryResult, Competition } from "../api/client";
```

- [ ] **Step 2: Add status badge helper and badge in header**

Add a status helper function before the component's return statement (inside the component, after the `groups` computation around line 230):

```typescript
  function getCompetitionStatus(c: Competition): { label: string; className: string } | null {
    if (!c.date) return null;
    const today = new Date().toISOString().split("T")[0];
    const endDate = c.date_end ?? c.date;
    if (c.date > today) {
      return { label: "Prochainement", className: "bg-surface-container text-on-surface-variant" };
    }
    if (c.date <= today && endDate >= today) {
      return { label: "En cours", className: "bg-primary/10 text-primary" };
    }
    return null;
  }

  const competitionStatus = getCompetitionStatus(competition);
```

Then add the badge in the header, inside the `<h1>` tag after the external link icon (around line 254):

```tsx
        {competitionStatus && (
          <span className={`${competitionStatus.className} text-xs font-semibold px-2.5 py-0.5 rounded-full`}>
            {competitionStatus.label}
          </span>
        )}
```

- [ ] **Step 3: Update the meta line to show date range and ligue**

Update the meta line (around line 255) to show date range and ligue:

```tsx
      <div className="text-sm text-gray-500 mb-4">
        {[
          competition.discipline,
          competition.season,
          competition.date && competition.date_end && competition.date !== competition.date_end
            ? `${new Date(competition.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} - ${new Date(competition.date_end).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}`
            : competition.date
              ? new Date(competition.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })
              : null,
          competition.ligue,
        ]
          .filter(Boolean)
          .join(" · ")}
      </div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/CompetitionPage.tsx
git commit -m "feat: add status badge and ligue to CompetitionPage detail header"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 2: Check frontend compiles**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build 2>&1 | tail -10`
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Verify Docker build**

Run: `docker compose build 2>&1 | tail -5`
Expected: Build succeeds.
