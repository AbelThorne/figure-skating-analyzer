"""
Site scraper for FS Manager (Swiss Timing) competition result websites.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
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
    components: dict[str, float] | None = None   # e.g. {"CO": 3.42, "PR": 3.25, "SK": 3.25}
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

        # Find the main event table — it has a TabHeadWhite header row.
        # Use only the innermost qualifying table (avoid processing nested tables multiple times).
        all_tables = soup.find_all("table")
        qualifying = [t for t in all_tables if t.find("tr", class_=re.compile(r"TabHead"))]
        # Skip tables that are ancestors of another qualifying table
        qualifying_set = set(id(t) for t in qualifying)
        tables_to_process = [
            t for t in qualifying
            if not any(id(p) in qualifying_set for p in t.parents if p.name == "table")
        ]

        for table in tables_to_process:
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
                        if re.search(r"SEG\d+\.htm$", href, re.IGNORECASE) and "OF" not in href.upper():  # SEG018OF.htm = order of finish page, not results
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

        # Use only the innermost qualifying table (avoid processing nested tables multiple times).
        all_tables = soup.find_all("table")
        qualifying = [t for t in all_tables if t.find("tr", class_=re.compile(r"TabHead"))]
        qualifying_set = set(id(t) for t in qualifying)
        tables_to_process = [
            t for t in qualifying
            if not any(id(p) in qualifying_set for p in t.parents if p.name == "table")
        ]

        for table in tables_to_process:
            header_row = table.find("tr", class_=re.compile(r"TabHead"))
            if not header_row:
                continue

            headers = [_clean_text(th.get_text()).lower() for th in header_row.find_all(["th", "td"], recursive=False)]
            col_map = self._map_seg_columns(headers)
            if "name" not in col_map:
                continue

            for row in table.find_all("tr"):
                css = " ".join(row.get("class") or [])
                if "TabHead" in css:
                    continue
                if not re.search(r"Line\d", css):
                    continue

                cells = row.find_all(["td", "th"], recursive=False)
                result = self._parse_seg_row(cells, col_map, category, short_segment)
                if result:
                    results.append(result)

        return results

    def _map_seg_columns(self, headers: list[str]) -> dict[str, Any]:
        col_map: dict[str, Any] = {}
        component_cols: list[tuple[int, str]] = []
        for i, h in enumerate(headers):
            h = h.strip().rstrip(".=+- ").strip()
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
        col_map["_components"] = component_cols
        return col_map

    def _parse_seg_row(
        self,
        cells: list[Tag],
        col_map: dict[str, Any],
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

            for event in events:
                if not event.seg_url:
                    continue
                seg_html = await _fetch(event.seg_url, client)
                if not seg_html:
                    logger.warning("Failed to fetch %s", event.seg_url)
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
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None
