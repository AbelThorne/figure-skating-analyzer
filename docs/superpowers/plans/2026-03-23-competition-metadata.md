# Competition Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically detect competition type, city, country, and season during import; let admins review/correct inline; enable filtering and sorting on the Competitions page.

**Architecture:** New `competition_metadata.py` service with URL+HTML heuristics called at end of import. Four new DB columns on `Competition`. Two new API endpoints (PATCH + confirm). Frontend gets filter bar + inline editor.

**Tech Stack:** Python/SQLAlchemy (backend), React/TypeScript/Tailwind (frontend), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-03-23-competition-metadata-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/services/competition_metadata.py` | `detect_metadata(url, html)` — all heuristic logic |
| Create | `backend/tests/test_competition_metadata.py` | Unit tests for metadata detection |
| Modify | `backend/app/models/competition.py` | Add 4 new columns |
| Modify | `backend/app/services/scrapers/base.py` | Update `scrape()` return type to include index HTML |
| Modify | `backend/app/services/site_scraper.py:500-545` | Return index HTML from `scrape()` |
| Modify | `backend/app/services/import_service.py:38-59` | Call `detect_metadata` after scrape |
| Modify | `backend/app/routes/competitions.py` | Add PATCH + confirm endpoints, update DTO |
| Modify | `frontend/src/api/client.ts:73-88` | Add new fields + API functions + COMPETITION_TYPES |
| Modify | `frontend/src/pages/CompetitionsPage.tsx` | Filter bar, badges, inline editor |

---

### Task 1: Add columns to Competition model

**Files:**
- Modify: `backend/app/models/competition.py`

- [ ] **Step 1: Add 4 new columns**

```python
# Add to imports
from sqlalchemy import String, Date, Text, JSON, Boolean

# Add after discipline field:
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    competition_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
```

- [ ] **Step 2: Verify DB creates correctly**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/conftest.py -v --co`
Expected: Collection succeeds (conftest creates all tables from metadata)

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/competition.py
git commit -m "feat: add city, country, competition_type, metadata_confirmed to Competition model"
```

---

### Task 2: Create metadata detection service with tests

**Files:**
- Create: `backend/app/services/competition_metadata.py`
- Create: `backend/tests/test_competition_metadata.py`

- [ ] **Step 1: Write failing tests for URL-based type detection**

```python
# backend/tests/test_competition_metadata.py
from app.services.competition_metadata import detect_metadata


class TestTypeDetectionFromUrl:
    def test_tdf_from_url(self):
        result = detect_metadata("https://example.com/TDF_Colmar_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "tdf"

    def test_cr_from_url(self):
        result = detect_metadata("https://example.com/CR-Castres-2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "cr"

    def test_tf_from_url(self):
        result = detect_metadata("https://example.com/2025-2026/CSNPA-2025-TF-Nimes/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "tf"

    def test_masters_from_url(self):
        result = detect_metadata("https://example.com/FFSG_MASTERS_25/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "masters"

    def test_ouverture_from_url(self):
        result = detect_metadata("https://example.com/Ouverture_2024/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "nationales_autres"

    def test_tmnca_from_url(self):
        result = detect_metadata("https://example.com/TMNCA2024/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "nationales_autres"

    def test_elites_from_url(self):
        result = detect_metadata("https://example.com/FFSG_ELITES_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_france_junior_from_url(self):
        result = detect_metadata("https://example.com/FRANCE_JUNIOR_2026/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_france_novice_from_url(self):
        result = detect_metadata("https://example.com/FRANCE_NOVICE_2026/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_france_minime_from_url(self):
        result = detect_metadata("https://example.com/france_minime_2024/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_cdf_adultes_from_url(self):
        result = detect_metadata("https://example.com/cdf_adultes_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_juniors_from_url(self):
        result = detect_metadata("https://example.com/JUNIORS_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_france_3_from_url(self):
        result = detect_metadata("https://example.com/France_3_Toulouse_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_france"

    def test_sfc_from_url(self):
        result = detect_metadata("https://example.com/SFC_IDF_Cergy_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "france_clubs"

    def test_sel_fr_clubs_from_url(self):
        result = detect_metadata("https://example.com/Sel_Fr_Clubs_SE_2026/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "france_clubs"

    def test_fc_finale_from_url(self):
        result = detect_metadata("https://example.com/FC_Courbevoie_2025/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "france_clubs"

    def test_franceclubs_from_url(self):
        result = detect_metadata("https://example.com/franceclubs_annecy_2024/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "france_clubs"

    def test_gpfra_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/gpfra2025/", "<html><title>Test</title></html>")
        assert result["competition_type"] == "grand_prix"

    def test_gpf_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/gpf2025/", "<html><title>Test</title></html>")
        assert result["competition_type"] == "grand_prix"

    def test_ec_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/ec2026/", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_europe"

    def test_wc_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2425/wc2025/", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_monde"

    def test_wjc_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/wjc2026/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "championnats_monde_junior"

    def test_owg_from_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/owg2026/", "<html><title>Test</title></html>")
        assert result["competition_type"] == "jeux_olympiques"

    def test_unknown_url_defaults_to_autre(self):
        result = detect_metadata("https://example.com/some-event/index.htm", "<html><title>Test</title></html>")
        assert result["competition_type"] == "autre"


class TestSeasonDetection:
    def test_season_from_saison_url(self):
        result = detect_metadata("https://example.com/Saison20252026/TDF_Colmar/index.htm", "<html><title>Test</title></html>")
        assert result["season"] == "2025-2026"

    def test_season_from_isu_url(self):
        result = detect_metadata("https://results.isu.org/results/season2526/ec2026/", "<html><title>Test</title></html>")
        assert result["season"] == "2025-2026"

    def test_season_from_path_segment(self):
        result = detect_metadata("https://example.com/Resultats/2024-2025/CR-Castres/index.htm", "<html><title>Test</title></html>")
        assert result["season"] == "2024-2025"

    def test_season_from_date_fallback_november(self):
        """November 2025 → season 2025-2026"""
        result = detect_metadata(
            "https://example.com/event/index.htm",
            "<html><title>Test</title><body>15.11.2025</body></html>",
        )
        assert result["season"] == "2025-2026"

    def test_season_from_date_fallback_march(self):
        """March 2026 → season 2025-2026"""
        result = detect_metadata(
            "https://example.com/event/index.htm",
            "<html><title>Test</title><body>15.03.2026</body></html>",
        )
        assert result["season"] == "2025-2026"


class TestCityDetection:
    def test_city_from_tdf_url(self):
        result = detect_metadata("https://example.com/TDF_Colmar_2025/index.htm", "<html><title>Test</title></html>")
        assert result["city"] == "Colmar"

    def test_city_from_cr_url(self):
        result = detect_metadata("https://example.com/CR-Castres-2025/index.htm", "<html><title>Test</title></html>")
        assert result["city"] == "Castres"

    def test_city_from_sfc_url(self):
        result = detect_metadata("https://example.com/SFC_IDF_Cergy_2025/index.htm", "<html><title>Test</title></html>")
        assert result["city"] == "Cergy"

    def test_city_from_html_title(self):
        html = '<html><title>Tournoi de France - Lyon 2025</title></html>'
        result = detect_metadata("https://example.com/tdf/index.htm", html)
        # City should be detected from title when not in URL
        assert result["city"] is not None


class TestCountryDetection:
    def test_default_country_france(self):
        result = detect_metadata("https://example.com/TDF_Colmar/index.htm", "<html><title>Test</title></html>")
        assert result["country"] == "France"

    def test_isu_event_still_defaults_france_without_info(self):
        result = detect_metadata("https://results.isu.org/results/season2526/ec2026/", "<html><title>Test</title></html>")
        # ISU events: country should be None when not detectable from HTML (admin will set it)
        assert result["country"] is None


class TestHtmlTitleTypeOverride:
    def test_title_tournoi_de_france(self):
        html = '<html><title>Tournoi de France A3 Neuilly-sur-Marne 2025</title></html>'
        result = detect_metadata("https://example.com/event/index.htm", html)
        assert result["competition_type"] == "tdf"

    def test_title_championnat(self):
        html = '<html><title>Championnats de France Elite 2025</title></html>'
        result = detect_metadata("https://example.com/event/index.htm", html)
        assert result["competition_type"] == "championnats_france"

    def test_title_masters(self):
        html = '<html><title>FFSG Masters de Patinage 2025</title></html>'
        result = detect_metadata("https://example.com/event/index.htm", html)
        assert result["competition_type"] == "masters"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_competition_metadata.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `detect_metadata`**

```python
# backend/app/services/competition_metadata.py
"""Heuristic detection of competition metadata from URL and HTML content."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


# Ordered list of (type_code, url_patterns, title_keywords).
# First match wins — order matters (specific before general).
_TYPE_RULES: list[tuple[str, list[str], list[str]]] = [
    # ISU international
    ("jeux_olympiques", [r"/owg\d{4}"], ["olympic"]),
    ("championnats_monde_junior", [r"/wjc\d{4}"], ["world junior"]),
    ("championnats_monde", [r"/wc\d{4}"], ["world championships", "world figure"]),
    ("championnats_europe", [r"/ec\d{4}"], ["european championships", "european figure"]),
    ("grand_prix", [r"/gpfra\d{4}", r"/gpf\d{4}"], ["grand prix"]),
    # French national — specific before general
    ("france_clubs", [r"/SFC_", r"/Sel_Fr_Clubs", r"/FC_[A-Z]", r"/franceclubs_", r"/FFSG_CSNPA_SFC"], ["france club", "sélection.*club", "finale.*club"]),
    ("championnats_france", [r"/FFSG_ELITES", r"/FRANCE_JUNIOR", r"/FRANCE_NOVICE", r"/[Ff]rance_[Mm]inime", r"/France_3_", r"/cdf_adultes", r"/JUNIORS_", r"/FFSG_JUNIOR", r"/[Ff]rance_[Nn]ovice", r"/FRANCE_MINIME"], ["championnat"]),
    ("masters", [r"/[Mm][Aa][Ss][Tt][Ee][Rr][Ss]"], ["masters"]),
    ("nationales_autres", [r"/[Oo]uverture", r"/[Tt][Mm][Nn][Cc][Aa]"], ["ouverture", "nouveaux champions", "trophée des nouveaux"]),
    # French regional/federal
    ("tdf", [r"/TDF[_\-]", r"/FFSG_CSNPA[\-_]?[Tt][Dd][Ff]", r"/FFSG_CSNPA[\s_\-]tdf"], ["tournoi de france"]),
    ("tf", [r"[\-_]TF[\-_]", r"/TF[\-_]"], ["trophée fédéral"]),
    ("cr", [r"/CR[\-_]"], ["compétition régionale", "critérium régional"]),
]

# Known ISU domains — events on these are international (country ≠ France by default)
_ISU_DOMAINS = ("results.isu.org", "isuresults.com", "www.isuresults.com")


def detect_metadata(url: str, html: str) -> dict:
    """Detect competition type, city, country, and season from URL + HTML.

    Returns dict with keys: competition_type, city, country, season.
    Values are None when not detectable.
    """
    comp_type = _detect_type(url, html)
    season = _detect_season(url, html)
    city = _detect_city(url, html)
    country = _detect_country(url)
    return {
        "competition_type": comp_type,
        "city": city,
        "country": country,
        "season": season,
    }


def _detect_type(url: str, html: str) -> str:
    """Detect competition type. Returns type code or 'autre'."""
    # Pass 1: URL patterns
    for type_code, url_patterns, _title_kw in _TYPE_RULES:
        for pattern in url_patterns:
            if re.search(pattern, url):
                return type_code

    # Pass 2: HTML title keywords
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text().lower()
    body_text = soup.get_text().lower()[:2000]  # first 2000 chars
    combined = title + " " + body_text

    for type_code, _url_pat, title_keywords in _TYPE_RULES:
        for keyword in title_keywords:
            if keyword.lower() in combined:
                return type_code

    return "autre"


def _detect_season(url: str, html: str) -> str | None:
    """Detect season from URL or HTML date."""
    # Pattern: Saison20252026
    m = re.search(r"[Ss]aison(\d{4})(\d{4})", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Pattern: season2526 (ISU)
    m = re.search(r"season(\d{2})(\d{2})", url)
    if m:
        y1 = int(m.group(1))
        y2 = int(m.group(2))
        return f"20{y1:02d}-20{y2:02d}"

    # Pattern: 2024-2025 or 2025-2026 in path
    m = re.search(r"(\d{4})-(\d{4})", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Fallback: infer from date in HTML
    text = BeautifulSoup(html, "html.parser").get_text()
    date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if date_match:
        day, month_str, year_str = date_match.groups()
        month = int(month_str)
        year = int(year_str)
        if month >= 7:  # July onwards → season year/(year+1)
            return f"{year}-{year + 1}"
        else:  # Before July → season (year-1)/year
            return f"{year - 1}-{year}"

    return None


def _detect_city(url: str, html: str) -> str | None:
    """Extract city name from URL path or HTML title."""
    # Try URL path patterns
    city = _city_from_url(url)
    if city:
        return city

    # Try HTML title
    city = _city_from_title(html)
    return city


def _city_from_url(url: str) -> str | None:
    """Extract city from known URL patterns."""
    from urllib.parse import urlparse, unquote
    path = unquote(urlparse(url).path)

    # TDF_CityName_Year or TDF_X9_CityName_Year
    m = re.search(r"/TDF[_\-](?:[A-Z]\d[_\-])?([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path)
    if m:
        return _clean_city_name(m.group(1))

    # CR-CityName-Year
    m = re.search(r"/CR[_\-]([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path)
    if m:
        return _clean_city_name(m.group(1))

    # SFC_ZONE_CityName_Year
    m = re.search(r"/SFC_[A-Z]{2,3}_([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path)
    if m:
        return _clean_city_name(m.group(1))

    # FC_CityName_Year
    m = re.search(r"/FC_([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path)
    if m:
        return _clean_city_name(m.group(1))

    # franceclubs_CityName_Year
    m = re.search(r"/franceclubs_([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path, re.IGNORECASE)
    if m:
        return _clean_city_name(m.group(1))

    # France_Novice_CityName_Year / France_Minime_CityName_Year / France_3_CityName_Year
    m = re.search(r"/[Ff]rance_(?:Novice|Minime|3)_([A-Za-z\-]+)(?:[_\-]\d{4})?(?:/|$)", path)
    if m:
        return _clean_city_name(m.group(1))

    # Sel_Fr_Clubs_ZONE_Year — no city in this pattern
    # JUNIORS_Year / FFSG_ELITES_Year — no city in these patterns

    return None


def _city_from_title(html: str) -> str | None:
    """Try to extract city from HTML <title>."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if not title_tag:
        return None
    title = title_tag.get_text().strip()

    # Pattern: "Something - CityName Year"
    m = re.search(r"[\-–]\s*([A-ZÀ-Ÿ][a-zà-ÿ\-]+(?:\s+[a-zà-ÿ]+)*(?:[\-\s][a-zà-ÿA-ZÀ-Ÿ]+)*)\s+\d{4}", title)
    if m:
        return m.group(1).strip()

    return None


def _clean_city_name(raw: str) -> str:
    """Clean extracted city name: replace separators, title-case."""
    name = raw.replace("_", " ")
    # Title case each word, preserving hyphens (e.g., Charleville-Mézières)
    parts = name.split("-")
    cleaned_parts = []
    for part in parts:
        words = part.strip().split()
        cleaned_parts.append(" ".join(w.capitalize() for w in words))
    return "-".join(p for p in cleaned_parts if p)


def _detect_country(url: str) -> str | None:
    """Detect country. Default France unless ISU domain."""
    from urllib.parse import urlparse
    domain = urlparse(url).hostname or ""
    if any(domain.endswith(d) for d in _ISU_DOMAINS):
        return None  # ISU events: admin sets country
    return "France"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_competition_metadata.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/competition_metadata.py backend/tests/test_competition_metadata.py
git commit -m "feat: add competition metadata detection service with tests"
```

---

### Task 3: Update scraper to return index HTML

**Files:**
- Modify: `backend/app/services/scrapers/base.py`
- Modify: `backend/app/services/site_scraper.py:500-545`

- [ ] **Step 1: Update BaseScraper return type**

In `backend/app/services/scrapers/base.py`, change `scrape` signature:

```python
@abstractmethod
async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult], list[ScrapedCategoryResult], ScrapedCompetitionInfo, str]: ...
```

The 5th element is the index HTML string.

- [ ] **Step 2: Update FSManagerScraper.scrape() to return index_html**

In `backend/app/services/site_scraper.py`, modify `scrape()`:

Change line 500:
```python
async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult], list[ScrapedCategoryResult], ScrapedCompetitionInfo, str]:
```

Change line 512 (empty return):
```python
return [], [], [], ScrapedCompetitionInfo(), ""
```

Change line 545 (final return):
```python
return events, all_results, all_cat_results, comp_info, index_html
```

- [ ] **Step 3: Update run_enrich to unpack 5-tuple**

In `backend/app/services/import_service.py` line 154, change:
```python
events, _, _, _, _ = await scraper.scrape(comp.url)
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scrapers/base.py backend/app/services/site_scraper.py backend/app/services/import_service.py
git commit -m "refactor: return index HTML from scraper.scrape() for metadata detection"
```

---

### Task 4: Integrate metadata detection into import service

**Files:**
- Modify: `backend/app/services/import_service.py:38-59`

- [ ] **Step 1: Add detect_metadata call after scraping**

In `run_import()`, after the scrape call and before the name/date assignment, add metadata detection. The modified section (lines 53-59) becomes:

```python
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
```

- [ ] **Step 2: Run existing tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/import_service.py
git commit -m "feat: detect competition metadata during import"
```

---

### Task 5: Update API — DTO, PATCH, confirm endpoints

**Files:**
- Modify: `backend/app/routes/competitions.py`

- [ ] **Step 1: Update competition_to_dict**

Add new fields to the DTO function:

```python
def competition_to_dict(c: Competition) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "url": c.url,
        "date": c.date.isoformat() if c.date else None,
        "season": c.season,
        "discipline": c.discipline,
        "city": c.city,
        "country": c.country,
        "competition_type": c.competition_type,
        "metadata_confirmed": c.metadata_confirmed,
    }
```

- [ ] **Step 2: Update imports at top of file**

Add `patch` and `Request` to the litestar import, and add the auth guard import:

```python
from litestar import Router, get, post, delete, patch, Request
from app.auth.guards import require_admin
```

- [ ] **Step 3: Add PATCH endpoint**

```python

@patch("/{competition_id:int}")
async def update_competition(competition_id: int, data: dict, request: Request, session: AsyncSession) -> dict:
    require_admin(request)
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    for field in ("city", "country", "competition_type", "season"):
        if field in data:
            setattr(comp, field, data[field])
    comp.metadata_confirmed = True
    await session.commit()
    await session.refresh(comp)
    return competition_to_dict(comp)
```

- [ ] **Step 4: Add confirm-metadata endpoint**

```python
@post("/{competition_id:int}/confirm-metadata")
async def confirm_metadata(competition_id: int, request: Request, session: AsyncSession) -> dict:
    require_admin(request)
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")
    comp.metadata_confirmed = True
    await session.commit()
    await session.refresh(comp)
    return competition_to_dict(comp)
```

- [ ] **Step 5: Add backfill-metadata endpoint**

```python
@post("/backfill-metadata")
async def backfill_metadata(request: Request, session: AsyncSession) -> dict:
    """Re-fetch index pages and detect metadata for all unconfirmed competitions."""
    require_admin(request)
    import httpx
    from app.services.competition_metadata import detect_metadata
    from datetime import date as date_type

    result_stmt = select(Competition).where(Competition.metadata_confirmed == False)  # noqa: E712
    comps = (await session.execute(result_stmt)).scalars().all()
    updated = 0

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
    ) as client:
        for comp in comps:
            try:
                resp = await client.get(comp.url)
                if resp.status_code != 200:
                    continue
                html = resp.text
                meta = detect_metadata(comp.url, html)
                if meta["competition_type"] and not comp.competition_type:
                    comp.competition_type = meta["competition_type"]
                if meta["city"] and not comp.city:
                    comp.city = meta["city"]
                if meta["country"] and not comp.country:
                    comp.country = meta["country"]
                if meta["season"] and not comp.season:
                    comp.season = meta["season"]
                updated += 1
            except Exception:
                continue

    await session.commit()
    return {"status": "ok", "competitions_updated": updated}
```

- [ ] **Step 6: Register new handlers in the Router**

```python
router = Router(
    path="/api/competitions",
    route_handlers=[
        list_competitions,
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
    ],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 7: Run all tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/routes/competitions.py
git commit -m "feat: add PATCH, confirm-metadata, and backfill-metadata endpoints"
```

---

### Task 6: Update frontend API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add COMPETITION_TYPES constant and update Competition interface**

After the existing `Competition` interface (line 73-80), add new fields and constant:

```typescript
export interface Competition {
  id: number;
  name: string;
  url: string;
  date: string | null;
  season: string | null;
  discipline: string | null;
  city: string | null;
  country: string | null;
  competition_type: string | null;
  metadata_confirmed: boolean;
}

export const COMPETITION_TYPES: Record<string, string> = {
  cr: "Compétition Régionale",
  tf: "Trophée Fédéral",
  tdf: "Tournoi de France",
  masters: "Masters",
  nationales_autres: "Nationales Autres",
  championnats_france: "Championnats de France",
  france_clubs: "France Clubs",
  grand_prix: "Grand Prix",
  championnats_europe: "Championnats d'Europe",
  championnats_monde: "Championnats du Monde",
  championnats_monde_junior: "Championnats du Monde Junior",
  jeux_olympiques: "Jeux Olympiques",
  autre: "Autre",
};
```

- [ ] **Step 2: Add API functions for update and confirm**

In the `competitions` section of `api` object, add:

```typescript
    update: (id: number, data: Partial<Pick<Competition, "city" | "country" | "competition_type" | "season">>) =>
      request<Competition>(`/competitions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    confirmMetadata: (id: number) =>
      request<Competition>(`/competitions/${id}/confirm-metadata`, { method: "POST" }),
    backfillMetadata: () =>
      request<{ status: string; competitions_updated: number }>("/competitions/backfill-metadata", { method: "POST" }),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add competition metadata fields and API functions to frontend client"
```

---

### Task 7: Update CompetitionsPage — filter bar and card layout

**Files:**
- Modify: `frontend/src/pages/CompetitionsPage.tsx`

- [ ] **Step 1: Add filter state and imports**

Add imports and state for filtering/sorting at the top of the component:

```typescript
import { api, Competition, CreateCompetitionPayload, ImportResult, EnrichResult, JobInfo, COMPETITION_TYPES } from "../api/client";

// Inside component, after existing state:
const [filterSeason, setFilterSeason] = useState<string>("all");
const [filterType, setFilterType] = useState<string>("all");
const [sortBy, setSortBy] = useState<string>("date-desc");
const [showUnconfirmedOnly, setShowUnconfirmedOnly] = useState(false);
```

- [ ] **Step 2: Add filtering and sorting logic**

After the state declarations, add computed filtered/sorted list:

```typescript
const seasons = Array.from(
  new Set(competitions?.map((c) => c.season).filter(Boolean) as string[])
).sort().reverse();

const filteredCompetitions = (competitions ?? [])
  .filter((c) => filterSeason === "all" || c.season === filterSeason)
  .filter((c) => filterType === "all" || c.competition_type === filterType)
  .filter((c) => !showUnconfirmedOnly || !c.metadata_confirmed)
  .sort((a, b) => {
    switch (sortBy) {
      case "date-asc":
        return (a.date ?? "").localeCompare(b.date ?? "");
      case "date-desc":
        return (b.date ?? "").localeCompare(a.date ?? "");
      case "city-asc":
        return (a.city ?? "").localeCompare(b.city ?? "");
      case "city-desc":
        return (b.city ?? "").localeCompare(a.city ?? "");
      case "country-asc":
        return (a.country ?? "").localeCompare(b.country ?? "");
      default:
        return (b.date ?? "").localeCompare(a.date ?? "");
    }
  });
```

- [ ] **Step 3: Add filter bar JSX**

Insert filter bar between the page header and the competition list (after `{showForm && ...}` block, before loading/error states):

```tsx
{/* Filter bar */}
{competitions && competitions.length > 0 && (
  <div className="bg-surface-container-lowest rounded-xl shadow-sm p-4 mb-4 flex items-center gap-4 flex-wrap">
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Saison</span>
      <select
        value={filterSeason}
        onChange={(e) => setFilterSeason(e.target.value)}
        className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
      >
        <option value="all">Toutes</option>
        {seasons.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
    </div>
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Type</span>
      <select
        value={filterType}
        onChange={(e) => setFilterType(e.target.value)}
        className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
      >
        <option value="all">Tous</option>
        {Object.entries(COMPETITION_TYPES).map(([code, label]) => (
          <option key={code} value={code}>{label}</option>
        ))}
      </select>
    </div>
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Trier par</span>
      <select
        value={sortBy}
        onChange={(e) => setSortBy(e.target.value)}
        className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
      >
        <option value="date-desc">Date ↓</option>
        <option value="date-asc">Date ↑</option>
        <option value="city-asc">Ville A→Z</option>
        <option value="city-desc">Ville Z→A</option>
        <option value="country-asc">Pays A→Z</option>
      </select>
    </div>
    <label className="ml-auto flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer">
      <input
        type="checkbox"
        checked={showUnconfirmedOnly}
        onChange={(e) => setShowUnconfirmedOnly(e.target.checked)}
        className="accent-error"
      />
      À vérifier uniquement
    </label>
  </div>
)}
```

- [ ] **Step 4: Update competition card layout**

Replace the competition map to use `filteredCompetitions` and update card content to show badges and metadata:

Change `{competitions?.map((c: Competition) => {` to `{filteredCompetitions.map((c: Competition) => {`

Update the card left section (name + meta) to:

```tsx
<div className="min-w-0">
  <div className="flex items-center gap-1.5 flex-wrap">
    <Link
      to={`/competitions/${c.id}`}
      className="font-bold font-headline text-on-surface hover:text-primary transition-colors"
    >
      {c.name}
    </Link>
    <a
      href={c.url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-on-surface-variant hover:text-primary transition-colors"
      title="Ouvrir les résultats"
    >
      <span className="material-symbols-outlined text-[16px] leading-none">open_in_new</span>
    </a>
    {c.competition_type && (
      <span className="bg-surface-container text-on-surface-variant text-[10px] font-semibold px-2 py-0.5 rounded-full">
        {COMPETITION_TYPES[c.competition_type] ?? c.competition_type}
      </span>
    )}
    {!c.metadata_confirmed && (
      <span className="bg-error-container/50 text-on-error-container text-[10px] font-semibold px-2 py-0.5 rounded-full">
        À vérifier
      </span>
    )}
  </div>
  <p className="text-xs text-on-surface-variant mt-1">
    {[
      c.city && c.country ? `${c.city}, ${c.country}` : c.city || c.country,
      c.date ? new Date(c.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }) : null,
      c.season,
    ].filter(Boolean).join(" · ")}
  </p>
</div>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CompetitionsPage.tsx
git commit -m "feat: add filter bar, type badges, and metadata display to CompetitionsPage"
```

---

### Task 8: Add inline editor and confirm/validate buttons

**Files:**
- Modify: `frontend/src/pages/CompetitionsPage.tsx`

- [ ] **Step 1: Add editor state and mutations**

After existing mutations, add:

```typescript
const [editingId, setEditingId] = useState<number | null>(null);
const [editForm, setEditForm] = useState<{
  city: string;
  country: string;
  competition_type: string;
  season: string;
}>({ city: "", country: "", competition_type: "", season: "" });

const updateMutation = useMutation({
  mutationFn: ({ id, data }: { id: number; data: Record<string, string> }) =>
    api.competitions.update(id, data),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["competitions"] });
    setEditingId(null);
  },
});

const confirmMutation = useMutation({
  mutationFn: (id: number) => api.competitions.confirmMetadata(id),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["competitions"] }),
});
```

- [ ] **Step 2: Add Valider/Modifier buttons to admin actions**

In the admin button area (inside `{isAdmin && (...)}`), add before the existing import button:

```tsx
{!c.metadata_confirmed && (
  <button
    onClick={() => confirmMutation.mutate(c.id)}
    className="bg-primary text-on-primary rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all flex items-center gap-1"
  >
    <span className="material-symbols-outlined text-base leading-none">check</span>
    Valider
  </button>
)}
<button
  onClick={() => {
    setEditingId(editingId === c.id ? null : c.id);
    setEditForm({
      city: c.city ?? "",
      country: c.country ?? "",
      competition_type: c.competition_type ?? "",
      season: c.season ?? "",
    });
  }}
  className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all flex items-center gap-1"
>
  <span className="material-symbols-outlined text-base leading-none">edit</span>
  Modifier
</button>
```

- [ ] **Step 3: Add inline editor below the card**

After the card div but before the import/enrich result notifications, add:

```tsx
{/* Inline metadata editor */}
{editingId === c.id && (
  <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 mt-1 border-l-[3px] border-primary">
    <div className="flex gap-3 flex-wrap">
      <div className="flex-1 min-w-[150px]">
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Type</label>
        <select
          value={editForm.competition_type}
          onChange={(e) => setEditForm((f) => ({ ...f, competition_type: e.target.value }))}
          className={inputClass}
        >
          <option value="">—</option>
          {Object.entries(COMPETITION_TYPES).map(([code, label]) => (
            <option key={code} value={code}>{label}</option>
          ))}
        </select>
      </div>
      <div className="flex-1 min-w-[150px]">
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Ville</label>
        <input
          value={editForm.city}
          onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value }))}
          className={inputClass}
          placeholder="Ville"
        />
      </div>
      <div className="flex-1 min-w-[150px]">
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Pays</label>
        <input
          value={editForm.country}
          onChange={(e) => setEditForm((f) => ({ ...f, country: e.target.value }))}
          className={inputClass}
          placeholder="Pays"
        />
      </div>
      <div className="flex-1 min-w-[120px]">
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Saison</label>
        <input
          value={editForm.season}
          onChange={(e) => setEditForm((f) => ({ ...f, season: e.target.value }))}
          className={inputClass}
          placeholder="2025-2026"
        />
      </div>
    </div>
    <div className="flex gap-2 mt-3 justify-end">
      <button
        onClick={() => setEditingId(null)}
        className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-4 text-xs font-bold"
      >
        Annuler
      </button>
      <button
        onClick={() => updateMutation.mutate({ id: c.id, data: editForm })}
        disabled={updateMutation.isPending}
        className="bg-primary text-on-primary rounded-lg py-1.5 px-4 text-xs font-bold active:scale-95 transition-all disabled:opacity-50"
      >
        {updateMutation.isPending ? "Enregistrement..." : "Enregistrer"}
      </button>
    </div>
  </div>
)}
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CompetitionsPage.tsx
git commit -m "feat: add inline metadata editor and confirm button to CompetitionsPage"
```

---

### Task 9: Manual smoke test

- [ ] **Step 1: Start backend and frontend**

Run backend: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run python -m app.main`
Run frontend: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run dev`

- [ ] **Step 2: Test the full flow**

1. Import a competition (e.g. `http://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/CSNPA_AUTOMNE_2025/index.htm`)
2. Verify metadata fields are populated (type, city, season, country)
3. Verify "À vérifier" badge appears
4. Click "Valider" — badge should disappear
5. Click "Modifier" — inline editor should appear with pre-filled values
6. Change a field and save — verify it persists
7. Test filter bar: filter by season, filter by type, sort by date/city
8. Test "À vérifier uniquement" checkbox

- [ ] **Step 3: Run backfill on existing competitions**

If there are existing competitions in the DB, trigger the backfill endpoint to detect their metadata.

- [ ] **Step 4: Final commit if any adjustments needed**

```bash
git add -A && git commit -m "fix: adjustments from smoke testing"
```
