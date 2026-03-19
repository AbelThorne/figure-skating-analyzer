# HTML-First Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure competition import to use website HTML (SEG pages) as primary data source, with PDFs as optional enrichment for element details.

**Architecture:** Rewrite site scraper to parse FS Manager index + SEG pages. Import endpoint creates skaters/scores from HTML data. New enrich endpoint downloads PDFs and attaches element details to existing scores.

**Tech Stack:** Python, Litestar, SQLAlchemy async, httpx, BeautifulSoup, pdfplumber

**Spec:** `docs/superpowers/specs/2026-03-19-html-first-import-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/models/score.py` | Modify | Add `components`, `elements` JSON fields + unique constraint |
| `backend/app/services/site_scraper.py` | Rewrite | `FSManagerScraper`: parse index page events + SEG page results |
| `backend/app/routes/competitions.py` | Rewrite | HTML-first import endpoint + new enrich endpoint |
| `backend/app/services/parser.py` | Simplify | Extract element details from PDFs only |
| `backend/app/services/downloader.py` | Simplify | Remove adapter pattern, keep download function |
| `backend/app/routes/scores.py` | Modify | Add new fields to score serialization |
| `backend/app/routes/skaters.py` | Modify | Add new fields to skater score serialization |
| `backend/tests/test_site_scraper.py` | Delete | Old tests for removed FrenchIJSScraper |
| `backend/tests/test_parser.py` | Modify | Tests for element extraction |
| `backend/tests/fixtures/` | Create | Sample HTML files for testing |

---

### Task 1: Update Score model

**Files:**
- Modify: `backend/app/models/score.py`

- [ ] **Step 1: Add `components` and `elements` JSON fields and unique constraint**

```python
from typing import Optional

from sqlalchemy import ForeignKey, String, Float, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("competition_id", "skater_id", "category", "segment", name="uq_score_competition_skater_cat_seg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    skater_id: Mapped[int] = mapped_column(ForeignKey("skaters.id"), nullable=False)
    segment: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    starting_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    component_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deductions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    components: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    elements: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="scores"
    )
    skater: Mapped["Skater"] = relationship(  # noqa: F821
        "Skater", back_populates="scores"
    )
```

- [ ] **Step 2: Delete existing database**

```bash
rm -f backend/data/skating.db
```

- [ ] **Step 3: Update score serialization in routes/scores.py and routes/skaters.py**

Add `components` and `elements` to `_score_to_dict` in `backend/app/routes/scores.py:40-58`:

```python
def _score_to_dict(s: Score) -> dict:
    return {
        "id": s.id,
        "competition_id": s.competition_id,
        "competition_name": s.competition.name if s.competition else None,
        "competition_date": s.competition.date.isoformat() if s.competition and s.competition.date else None,
        "skater_id": s.skater_id,
        "skater_name": s.skater.name if s.skater else None,
        "skater_nationality": s.skater.nationality if s.skater else None,
        "skater_club": s.skater.club if s.skater else None,
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
    }
```

Also add `components` and `elements` to the inline score dict in `backend/app/routes/skaters.py:53-68`:

```python
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
        }
        for s in scores
    ]
```

- [ ] **Step 4: Delete old tests that import removed classes**

```bash
rm -f backend/tests/test_site_scraper.py backend/tests/test_parser.py
```

- [ ] **Step 5: Verify app starts**

```bash
cd backend && uv run python -c "from app.models.score import Score; print('Score model OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/score.py backend/app/routes/scores.py backend/app/routes/skaters.py
git rm -f backend/tests/test_site_scraper.py backend/tests/test_parser.py 2>/dev/null; true
git commit -m "feat: add components/elements fields and unique constraint to Score model"
```

---

### Task 2: Rewrite site scraper — index page parsing

**Files:**
- Create: `backend/tests/fixtures/index_sample.html`
- Create: `backend/tests/test_fs_manager_scraper.py`
- Modify: `backend/app/services/site_scraper.py`

- [ ] **Step 1: Create test fixture for index page**

Save a minimal index page HTML to `backend/tests/fixtures/index_sample.html`. Use the actual structure from the FS Manager site:

```html
<html>
<body>
<table class="MainTab">
<tr><td>
<table width="80%" border="0" align="center" cellpadding="0" cellspacing="1" bgcolor="#606060">
<tr><td>
<table width="100%" align="center" border="0" cellspacing="1">
    <tr class="TabHeadWhite">
        <th>Category</th>
        <th>Segment</th>
        <th>&nbsp;</th>
        <th>&nbsp;</th>
        <th>Reports</th>
    </tr>
    <tr class="Line1Red">
        <td class="CellLeft">R1 Junior-Senior Femme</td>
        <td></td>
        <td class="CellLeft"><a href="CAT001EN.htm">Entries</a></td>
        <td class="CellLeft"><a href="CAT001RS.htm">Result</a></td>
        <td>&nbsp;</td>
    </tr>
    <tr class="Line1Red">
        <td class="CellLeft" valign="top"></td>
        <td class="CellLeft">Free Skating</td>
        <td class="CellLeft"><a href="SEG018OF.htm">Panel of Judges</a></td>
        <td class="CellLeft"><a href="SEG018.htm">Starting Order / Detailed Classification</a></td>
        <td><a href="JUDGES001.pdf" target="_blank">Judges Scores (pdf)</a></td>
    </tr>
    <tr class="Line1Blue">
        <td class="CellLeft">R2 Novice Femme</td>
        <td></td>
        <td class="CellLeft"><a href="CAT002EN.htm">Entries</a></td>
        <td class="CellLeft"><a href="CAT002RS.htm">Result</a></td>
        <td>&nbsp;</td>
    </tr>
    <tr class="Line1Blue">
        <td class="CellLeft" valign="top"></td>
        <td class="CellLeft">Short Program</td>
        <td class="CellLeft"><a href="SEG005OF.htm">Panel of Judges</a></td>
        <td class="CellLeft"><a href="SEG005.htm">Starting Order / Detailed Classification</a></td>
        <td><a href="JUDGES002.pdf" target="_blank">Judges Scores (pdf)</a></td>
    </tr>
    <tr class="Line1Blue">
        <td class="CellLeft" valign="top"></td>
        <td class="CellLeft">Free Skating</td>
        <td class="CellLeft"><a href="SEG006OF.htm">Panel of Judges</a></td>
        <td class="CellLeft"><a href="SEG006.htm">Starting Order / Detailed Classification</a></td>
        <td><a href="JUDGES003.pdf" target="_blank">Judges Scores (pdf)</a></td>
    </tr>
</table>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for index parsing**

Create `backend/tests/test_fs_manager_scraper.py`:

```python
from pathlib import Path

from app.services.site_scraper import FSManagerScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_index_finds_events():
    html = (FIXTURES / "index_sample.html").read_text()
    scraper = FSManagerScraper()
    events = scraper.parse_index(html, "http://example.com/results/index.htm")

    assert len(events) == 3  # 2 categories, but R2 Novice has SP + FS = 2 segments + 1 for R1
    # R1 Junior-Senior Femme - Free Skating
    assert events[0].category == "R1 Junior-Senior Femme"
    assert events[0].segment == "Free Skating"
    assert events[0].seg_url == "http://example.com/results/SEG018.htm"
    assert events[0].pdf_url == "http://example.com/results/JUDGES001.pdf"
    # R2 Novice Femme - Short Program
    assert events[1].category == "R2 Novice Femme"
    assert events[1].segment == "Short Program"
    assert events[1].seg_url == "http://example.com/results/SEG005.htm"
    # R2 Novice Femme - Free Skating
    assert events[2].category == "R2 Novice Femme"
    assert events[2].segment == "Free Skating"
    assert events[2].seg_url == "http://example.com/results/SEG006.htm"


def test_parse_index_empty_table():
    html = "<html><body><table></table></body></html>"
    scraper = FSManagerScraper()
    events = scraper.parse_index(html, "http://example.com/index.htm")
    assert events == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_fs_manager_scraper.py -v
```

Expected: FAIL — `FSManagerScraper` does not exist yet.

- [ ] **Step 4: Implement FSManagerScraper index parsing**

Rewrite `backend/app/services/site_scraper.py`. Keep the module-level helpers (`normalize_name`, `_strip_accents`, `_clean_text`, `_title_case_name`) and `GenericTableScraper`. Remove `FrenchIJSScraper`. Add `FSManagerScraper` with a `ScrapedEvent` dataclass and `parse_index` method:

```python
"""
Site scraper for FS Manager (Swiss Timing) competition result websites.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScrapedEvent:
    """An event discovered on the competition index page."""
    category: str          # e.g. "R1 Junior-Senior Femme"
    segment: str           # e.g. "Free Skating"
    seg_url: str | None = None   # URL to SEG detail page
    pdf_url: str | None = None   # URL to judges scores PDF

@dataclass
class ScrapedResult:
    """A competitor result scraped from a SEG detail page."""
    name: str
    club: str | None = None
    nationality: str | None = None
    category: str | None = None
    segment: str | None = None
    rank: int | None = None
    total_score: float | None = None
    technical_score: float | None = None
    component_score: float | None = None
    components: dict | None = None   # e.g. {"CO": 3.42, "PR": 3.25, "SK": 3.25}
    deductions: float | None = None
    starting_number: int | None = None


# ---------------------------------------------------------------------------
# FS Manager Scraper
# ---------------------------------------------------------------------------

_SEGMENT_MAP = {
    "free skating": "FS",
    "short program": "SP",
    "rhythm dance": "RD",
    "free dance": "FD",
}


class FSManagerScraper:
    """Scraper for FS Manager (Swiss Timing) competition result sites."""

    def parse_index(self, html: str, base_url: str) -> list[ScrapedEvent]:
        """Parse the competition index page and return discovered events."""
        soup = BeautifulSoup(html, "html.parser")
        base_dir = base_url.rsplit("/", 1)[0] + "/"
        events: list[ScrapedEvent] = []

        # Find the main event table — it has a TabHeadWhite header row
        for table in soup.find_all("table"):
            header_row = table.find("tr", class_=re.compile(r"TabHead"))
            if not header_row:
                continue

            current_category: str | None = None
            for row in table.find_all("tr"):
                if "TabHead" in (row.get("class") or [""]):
                    continue

                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                first_cell_text = _clean_text(cells[0].get_text())
                second_cell_text = _clean_text(cells[1].get_text()) if len(cells) > 1 else ""

                if first_cell_text:
                    # Category row — store category name
                    current_category = first_cell_text
                elif second_cell_text and current_category:
                    # Segment row — extract SEG URL and PDF URL
                    segment_name = second_cell_text
                    seg_url: str | None = None
                    pdf_url: str | None = None

                    for a in row.find_all("a", href=True):
                        href = a["href"]
                        if re.search(r"SEG\d+\.htm$", href, re.IGNORECASE) and "OF" not in href.upper():
                            seg_url = urljoin(base_dir, href)
                        elif re.search(r"\.pdf$", href, re.IGNORECASE):
                            pdf_url = urljoin(base_dir, href)

                    if seg_url:
                        events.append(ScrapedEvent(
                            category=current_category,
                            segment=segment_name,
                            seg_url=seg_url,
                            pdf_url=pdf_url,
                        ))

        return events

    def parse_seg_page(self, html: str, category: str, segment: str) -> list[ScrapedResult]:
        """Parse a SEG detail page and return competitor results."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[ScrapedResult] = []
        short_segment = _SEGMENT_MAP.get(segment.lower(), segment)

        for table in soup.find_all("table"):
            header_row = table.find("tr", class_=re.compile(r"TabHead"))
            if not header_row:
                continue

            headers = [_clean_text(th.get_text()).lower() for th in header_row.find_all(["th", "td"])]
            col_map = self._map_seg_columns(headers)
            if "name" not in col_map:
                continue

            for row in table.find_all("tr"):
                css = " ".join(row.get("class") or [])
                if "TabHead" in css:
                    continue
                if not re.search(r"Line\d", css):
                    continue

                cells = row.find_all(["td", "th"])
                result = self._parse_seg_row(cells, col_map, category, short_segment)
                if result:
                    results.append(result)

        return results

    def _map_seg_columns(self, headers: list[str]) -> dict[str, int]:
        col_map: dict[str, int] = {}
        component_cols: list[tuple[int, str]] = []
        for i, h in enumerate(headers):
            h = h.strip().rstrip(".=+-")
            if h in ("pl", "fpl"):
                col_map["rank"] = i
            elif h == "name":
                col_map["name"] = i
            elif h == "club":
                col_map["club"] = i
            elif h == "nation":
                col_map["nation"] = i
            elif h == "tss":
                col_map["tss"] = i
            elif h == "tes":
                col_map["tes"] = i
            elif h == "pcs":
                col_map["pcs"] = i
            elif h in ("ded", "ded."):
                col_map["ded"] = i
            elif h in ("stn", "stn."):
                col_map["stn"] = i
            elif h in ("co", "pr", "sk", "in", "ch"):
                component_cols.append((i, h.upper()))
        col_map["_components"] = component_cols  # type: ignore
        return col_map

    def _parse_seg_row(
        self,
        cells: list[Tag],
        col_map: dict,
        category: str,
        segment: str,
    ) -> ScrapedResult | None:
        def cell_text(key: str) -> str | None:
            idx = col_map.get(key)
            if idx is None or idx >= len(cells):
                return None
            return _clean_text(cells[idx].get_text()) or None

        name_text = cell_text("name")
        if not name_text or len(name_text) < 2:
            return None

        # Extract nation from nested flag table if present
        nationality: str | None = None
        nat_idx = col_map.get("nation")
        if nat_idx is not None and nat_idx < len(cells):
            nat_cell = cells[nat_idx]
            # Look for 3-letter code in text nodes
            nat_text = _clean_text(nat_cell.get_text())
            m = re.search(r"\b([A-Z]{2,3})\b", nat_text)
            if m:
                nationality = m.group(1)

        rank = _parse_int(cell_text("rank"))
        tss = _parse_float(cell_text("tss"))
        tes = _parse_float(cell_text("tes"))
        pcs = _parse_float(cell_text("pcs"))
        ded = _parse_float(cell_text("ded"))

        stn_raw = cell_text("stn")
        stn: int | None = None
        if stn_raw:
            m = re.search(r"(\d+)", stn_raw)
            if m:
                stn = int(m.group(1))

        # Components
        components: dict[str, float] = {}
        for idx, comp_name in col_map.get("_components", []):
            if idx < len(cells):
                val = _parse_float(_clean_text(cells[idx].get_text()))
                if val is not None:
                    components[comp_name] = val

        return ScrapedResult(
            name=name_text,
            club=cell_text("club"),
            nationality=nationality,
            category=category,
            segment=segment,
            rank=rank,
            total_score=tss,
            technical_score=tes,
            component_score=pcs,
            components=components if components else None,
            deductions=ded,
            starting_number=stn,
        )

    async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult]]:
        """Full scrape: fetch index, discover events, fetch all SEG pages."""
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
        ) as client:
            index_html = await _fetch(url, client)
            if not index_html:
                return [], []

            events = self.parse_index(index_html, url)
            all_results: list[ScrapedResult] = []
            errors: list[str] = []

            for event in events:
                if not event.seg_url:
                    continue
                seg_html = await _fetch(event.seg_url, client)
                if not seg_html:
                    errors.append(f"Failed to fetch {event.seg_url}")
                    continue
                results = self.parse_seg_page(seg_html, event.category, event.segment)
                all_results.extend(results)

            return events, all_results


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize a skater name for fuzzy matching."""
    name = _strip_accents(name).lower()
    name = re.sub(r"[^a-z\s]", "", name)
    return " ".join(name.split())


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _title_case_name(name: str) -> str:
    stripped = name.strip()
    alpha_chars = [c for c in stripped if c.isalpha()]
    if not alpha_chars or not all(c.isupper() for c in alpha_chars):
        return stripped
    _PARTICLES = {"de", "du", "des", "le", "la", "les", "d", "l", "van", "von", "da"}
    parts = stripped.split()
    result = []
    for i, part in enumerate(parts):
        lower = part.lower()
        if i > 0 and lower in _PARTICLES:
            result.append(lower)
        else:
            result.append(part.capitalize())
    return " ".join(result)


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    text = text.replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    m = re.match(r"(\d+)", text.strip())
    return int(m.group(1)) if m else None


async def _fetch(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning("HTTP %d fetching %s", resp.status_code, url)
            return None
        content_type = resp.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^\s;]+)", content_type, re.IGNORECASE)
        declared = charset_match.group(1) if charset_match else None
        encoding = declared or "windows-1252"
        return resp.content.decode(encoding, errors="replace")
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_fs_manager_scraper.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/site_scraper.py backend/tests/test_fs_manager_scraper.py backend/tests/fixtures/
git commit -m "feat: rewrite site scraper with FSManagerScraper for index + SEG parsing"
```

---

### Task 3: Site scraper — SEG page parsing

**Files:**
- Create: `backend/tests/fixtures/seg_sample.html`
- Modify: `backend/tests/test_fs_manager_scraper.py`

- [ ] **Step 1: Create test fixture for SEG page**

Save to `backend/tests/fixtures/seg_sample.html`:

```html
<html>
<head><title>Competition - R1 Junior-Senior Femme - Free Skating</title></head>
<body>
<table class="MainTab">
<tr class="caption2"><td>R1 Junior-Senior Femme - Free Skating</td></tr>
<tr><td>
<table width="95%" border="0" align="center" cellpadding="0" cellspacing="1" bgcolor="#606060">
<tr><td>
<table width="100%" align="center" border="0" cellspacing="1">
    <tr class="TabHeadRed">
        <th>Pl.</th>
        <th>Name</th>
        <td>Club</td>
        <th>Nation</th>
        <th>TSS<br/>=</th>
        <th>TES<br/>+</th>
        <th>&nbsp;</th>
        <th>PCS<br/>+</th>
        <th>CO</th>
        <th>PR</th>
        <th>SK</th>
        <th>Ded.<br/>-</th>
        <th>StN.</th>
    </tr>
    <tr class="Line1Red">
        <td align="center">1</td>
        <td class="CellLeft"><a href="/bios/skater1.htm" class="disableBiosLink">Maeva BORIES</a></td>
        <td>MONTP</td>
        <td><table><tr class="Line1Red"><td><img src="../flags/FRA.GIF"></td><td></td><td>FRA</td></tr></table></td>
        <td align="right">28.78</td>
        <td align="right">11.91</td>
        <td>&nbsp;</td>
        <td align="right">16.87</td>
        <td align="right">3.42</td>
        <td align="right">3.25</td>
        <td align="right">3.25</td>
        <td align="right">0.00</td>
        <td align="center">#8</td>
    </tr>
    <tr class="Line2Red">
        <td align="center">2</td>
        <td class="CellLeft"><a href="/bios/skater2.htm" class="disableBiosLink">Lou Anne BLACHE</a></td>
        <td>MONTP</td>
        <td><table><tr class="Line2Red"><td><img src="../flags/FRA.GIF"></td><td></td><td>FRA</td></tr></table></td>
        <td align="right">27.55</td>
        <td align="right">10.40</td>
        <td>&nbsp;</td>
        <td align="right">17.15</td>
        <td align="right">3.25</td>
        <td align="right">3.58</td>
        <td align="right">3.25</td>
        <td align="right">0.00</td>
        <td align="center">#4</td>
    </tr>
</table>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for SEG page parsing**

Add to `backend/tests/test_fs_manager_scraper.py`:

```python
def test_parse_seg_page():
    html = (FIXTURES / "seg_sample.html").read_text()
    scraper = FSManagerScraper()
    results = scraper.parse_seg_page(html, "R1 Junior-Senior Femme", "FS")

    assert len(results) == 2

    r1 = results[0]
    assert r1.name == "Maeva BORIES"
    assert r1.club == "MONTP"
    assert r1.nationality == "FRA"
    assert r1.category == "R1 Junior-Senior Femme"
    assert r1.segment == "FS"
    assert r1.rank == 1
    assert r1.total_score == 28.78
    assert r1.technical_score == 11.91
    assert r1.component_score == 16.87
    assert r1.components == {"CO": 3.42, "PR": 3.25, "SK": 3.25}
    assert r1.deductions == 0.00
    assert r1.starting_number == 8

    r2 = results[1]
    assert r2.name == "Lou Anne BLACHE"
    assert r2.rank == 2
    assert r2.total_score == 27.55
    assert r2.starting_number == 4
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_fs_manager_scraper.py -v
```

Expected: PASS (implementation was included in Task 2)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add SEG page parsing tests with fixtures"
```

---

### Task 4: Rewrite import endpoint

**Files:**
- Modify: `backend/app/routes/competitions.py`

- [ ] **Step 1: Rewrite the import endpoint to use HTML-first flow**

Replace the `import_competition` handler in `backend/app/routes/competitions.py`:

```python
from __future__ import annotations

from litestar import Router, get, post, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.services.site_scraper import FSManagerScraper


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


@post("/{competition_id:int}/import")
async def import_competition(competition_id: int, session: AsyncSession) -> dict:
    """Import competition results from website HTML (SEG pages)."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")

    scraper = FSManagerScraper()
    events, results = await scraper.scrape(comp.url)

    imported = 0
    skipped = 0
    errors = []

    for r in results:
        try:
            # Get or create skater
            stmt = select(Skater).where(Skater.name == r.name)
            skater = (await session.execute(stmt)).scalar_one_or_none()
            if not skater:
                skater = Skater(
                    name=r.name,
                    nationality=r.nationality,
                    club=r.club,
                )
                session.add(skater)
                await session.flush()
            else:
                if not skater.nationality and r.nationality:
                    skater.nationality = r.nationality
                if not skater.club and r.club:
                    skater.club = r.club

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
            )
            session.add(score)
            imported += 1
        except Exception as e:
            errors.append({"skater": r.name, "error": str(e)})

    await session.commit()
    return {
        "competition_id": competition_id,
        "events_found": len(events),
        "scores_imported": imported,
        "scores_skipped": skipped,
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
```

- [ ] **Step 2: Verify app starts and import endpoint exists**

```bash
cd backend && uv run python -c "from app.routes.competitions import router; print('Routes OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/competitions.py
git commit -m "feat: rewrite import endpoint to use HTML-first flow"
```

---

### Task 5: Add enrich endpoint

**Files:**
- Modify: `backend/app/routes/competitions.py`
- Modify: `backend/app/services/parser.py`
- Modify: `backend/app/services/downloader.py`

- [ ] **Step 1: Simplify parser to extract elements only**

Replace `backend/app/services/parser.py` with element-focused parser:

```python
"""
Parser service: extracts element-by-element details from PDF score sheets.

Used for enrichment — the main scores come from HTML scraping.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


def parse_elements(pdf_path: Path) -> list[dict]:
    """
    Parse a PDF and return per-skater element details.

    Returns a list of dicts:
        {"skater_name": str, "category_segment": str, "elements": [...]}
    """
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # The category/segment line is near the top, e.g. "R3 C BABIES FEMME FREE SKATING"
    category_segment = _extract_category_segment(full_text)

    # Find each skater block: starts with the header data line
    skater_re = re.compile(
        r"^(\d{1,3})\s+(.+?)\s+([A-Z]{2,3})\s+\d{1,3}\s+\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+\s+-?\d+\.\d+",
        re.MULTILINE,
    )
    element_re = re.compile(
        r"^(\d{1,2})\s+(\S+(?:\*|<<)?(?:\s+\*)?)\s+(\d+\.\d+)\s+.*?(-?\d+\.\d+)\s+",
        re.MULTILINE,
    )

    matches = list(skater_re.finditer(full_text))
    for i, m in enumerate(matches):
        skater_name = m.group(2).strip()
        # Extract elements between this skater header and the next
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        elements = []
        for em in element_re.finditer(block):
            elements.append({
                "number": int(em.group(1)),
                "name": em.group(2).strip(),
                "base_value": float(em.group(3)),
                "goe": float(em.group(4)),
            })

        if elements:
            results.append({
                "skater_name": skater_name,
                "category_segment": category_segment,
                "elements": elements,
            })

    return results


def _extract_category_segment(text: str) -> str | None:
    """Extract the category/segment line from near the top of the PDF."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        if "JUDGES DETAILS" in line.upper():
            continue
        # Category line typically has segment keywords
        if re.search(r"\b(FREE SKATING|SHORT PROGRAM|RHYTHM DANCE|FREE DANCE)\b", line, re.IGNORECASE):
            return line
    return None
```

- [ ] **Step 2: Simplify downloader**

Replace `backend/app/services/downloader.py`:

```python
"""
Downloader service: downloads PDF score sheets from competition result websites.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import PDF_DIR

logger = logging.getLogger(__name__)


async def download_pdfs(pdf_urls: list[str], competition_slug: str) -> list[Path]:
    """Download a list of PDF URLs to local storage. Returns paths of downloaded files."""
    dest_dir = PDF_DIR / competition_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
    ) as client:
        for pdf_url in pdf_urls:
            filename = _pdf_filename(pdf_url)
            dest = dest_dir / filename
            if dest.exists():
                downloaded.append(dest)
                continue
            try:
                resp = await client.get(pdf_url, follow_redirects=True)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                downloaded.append(dest)
            except Exception as exc:
                logger.warning("Failed to download %s: %s", pdf_url, exc)

    return downloaded


def url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    slug = f"{parsed.netloc}{parsed.path}".replace("/", "_").strip("_")
    return re.sub(r"[^a-zA-Z0-9_\-]", "", slug)[:100]


def _pdf_filename(pdf_url: str) -> str:
    path = urlparse(pdf_url).path
    name = path.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name
```

- [ ] **Step 3: Add enrich endpoint to competitions.py**

Add to `backend/app/routes/competitions.py`, before the `router` definition:

```python
from app.services.downloader import download_pdfs, url_to_slug
from app.services.parser import parse_elements
from app.services.site_scraper import normalize_name


@post("/{competition_id:int}/enrich")
async def enrich_competition(competition_id: int, session: AsyncSession) -> dict:
    """Enrich existing scores with element details from PDF score cards."""
    comp = await session.get(Competition, competition_id)
    if not comp:
        raise NotFoundException(f"Competition {competition_id} not found")

    # Discover PDF URLs from site
    scraper = FSManagerScraper()
    events, _ = await scraper.scrape(comp.url)
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
                        if not score.elements:  # don't overwrite
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
```

Add `enrich_competition` to the router's `route_handlers` list.

- [ ] **Step 4: Verify app starts**

```bash
cd backend && uv run python -c "from app.routes.competitions import router; print([r.path for r in router.routes])"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser.py backend/app/services/downloader.py backend/app/routes/competitions.py
git commit -m "feat: add enrich endpoint with PDF element parsing"
```

---

### Task 6: Integration test with real site

**Files:** None (manual test)

- [ ] **Step 1: Delete old database and restart backend**

```bash
rm -f backend/data/skating.db
# Restart the backend server (kill existing, start fresh)
```

- [ ] **Step 2: Create a competition and import via curl**

```bash
# Create competition
curl -s -X POST http://localhost:8000/api/competitions/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Trophee du Soleil 26", "url": "http://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Montpellier/index.htm"}' | python -m json.tool

# Import from HTML
curl -s -X POST http://localhost:8000/api/competitions/1/import | python -m json.tool
```

Verify: `events_found` > 0, `scores_imported` > 0.

- [ ] **Step 3: Verify scores have correct data**

```bash
curl -s 'http://localhost:8000/api/scores/?competition_id=1' | python -m json.tool | head -50
```

Check: names look correct (not "JUDGES DETAILS PER SKATER"), categories present, TES/PCS populated, clubs present.

- [ ] **Step 4: Test enrichment**

```bash
curl -s -X POST http://localhost:8000/api/competitions/1/enrich | python -m json.tool
```

Verify: `pdfs_downloaded` > 0, `scores_enriched` > 0.

- [ ] **Step 5: Verify elements were attached**

```bash
curl -s 'http://localhost:8000/api/scores/?competition_id=1' | python -m json.tool | grep -A5 elements | head -20
```

- [ ] **Step 6: Test idempotency — re-import should skip all**

```bash
curl -s -X POST http://localhost:8000/api/competitions/1/import | python -m json.tool
```

Verify: `scores_imported` = 0, `scores_skipped` > 0.

- [ ] **Step 7: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: HTML-first import flow complete"
```
