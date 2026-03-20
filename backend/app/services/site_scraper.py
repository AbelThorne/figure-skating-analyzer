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
class ScrapedCategory:
    """A category discovered on the competition index page with its CAT result URL."""
    category: str          # e.g. "National Novice Femme"
    cat_url: str | None = None   # URL to CATxxxRS.htm overall result page
    segments: list[str] | None = None  # segment names discovered (e.g. ["Short Program", "Free Skating"])

@dataclass
class ScrapedCategoryResult:
    """An overall category result from a CATxxxRS.htm page."""
    name: str
    club: str | None = None
    nationality: str | None = None
    category: str | None = None
    overall_rank: int | None = None
    combined_total: float | None = None
    sp_rank: int | None = None
    fs_rank: int | None = None
    segment_count: int = 1

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
    """Scraper for FS Manager (Swiss Timing) competition result sites.

    Implements the BaseScraper interface (duck-typed to avoid circular imports).
    """

    def parse_index(self, html: str, base_url: str) -> tuple[list[ScrapedEvent], list[ScrapedCategory]]:
        """Parse the competition index page and return discovered events and categories.

        Returns:
            A tuple of (events, categories) where events are individual segments
            and categories group segments together with their CATxxxRS.htm URL.
        """
        soup = BeautifulSoup(html, "html.parser")
        base_dir = base_url.rsplit("/", 1)[0] + "/"
        events: list[ScrapedEvent] = []
        categories: list[ScrapedCategory] = []

        # Find the main event table — it has a TabHeadWhite header row.
        # Use only the innermost qualifying table (avoid processing nested tables multiple times).
        all_tables = soup.find_all("table")
        qualifying = [t for t in all_tables if t.find("tr", class_=re.compile(r"TabHead"))]
        # Keep only innermost: skip tables that contain another qualifying table as descendant
        qualifying_set = set(id(t) for t in qualifying)
        tables_to_process = [
            t for t in qualifying
            if not any(
                id(child) in qualifying_set
                for child in t.find_all("table")
                if id(child) != id(t)
            )
        ]

        for table in tables_to_process:
            header_row = table.find("tr", class_=re.compile(r"TabHead"))
            if not header_row:
                continue

            current_category: str | None = None
            current_cat_url: str | None = None
            current_segments: list[str] = []

            for row in table.find_all("tr"):
                row_classes = " ".join(row.get("class") or [])
                if "TabHead" in row_classes:
                    continue

                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                first_cell_text = _clean_text(cells[0].get_text())
                second_cell_text = _clean_text(cells[1].get_text()) if len(cells) > 1 else ""

                if first_cell_text:
                    # Save previous category before starting a new one
                    if current_category:
                        categories.append(ScrapedCategory(
                            category=current_category,
                            cat_url=current_cat_url,
                            segments=current_segments if current_segments else None,
                        ))

                    # Category row — store category name, but skip schedule rows (date like "07.02.2026")
                    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_cell_text):
                        current_category = None  # reset so segment rows under this are skipped
                        current_cat_url = None
                        current_segments = []
                    else:
                        current_category = first_cell_text
                        current_cat_url = None
                        current_segments = []

                        # Extract CATxxxRS.htm URL from the category row
                        for a in row.find_all("a", href=True):
                            href = a["href"]
                            if re.search(r"CAT\d+RS\.htm$", href, re.IGNORECASE):
                                current_cat_url = urljoin(base_dir, href)
                elif second_cell_text and current_category:
                    # Segment row — extract SEG URL and PDF URL
                    segment_name = second_cell_text
                    current_segments.append(segment_name)
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

            # Don't forget the last category
            if current_category:
                categories.append(ScrapedCategory(
                    category=current_category,
                    cat_url=current_cat_url,
                    segments=current_segments if current_segments else None,
                ))

        return events, categories

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
            if not any(
                id(child) in qualifying_set
                for child in t.find_all("table")
                if id(child) != id(t)
            )
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

        # Reject rows that look like section headers (e.g. "Technical Element Score")
        # A valid skater row must have a numeric total score
        tss_raw = cell_text("tss")
        if not tss_raw or _parse_float(tss_raw) is None:
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

    def parse_cat_page(self, html: str, category: str, segment_count: int) -> list[ScrapedCategoryResult]:
        """Parse a CATxxxRS.htm page and return overall category results.

        The CAT result page has columns like: FPl. | Name | Club | Nation | Points | SP | FS
        For single-segment categories: FPl. | Name | Club | Nation | Points | FS
        """
        soup = BeautifulSoup(html, "html.parser")
        results: list[ScrapedCategoryResult] = []

        all_tables = soup.find_all("table")
        qualifying = [t for t in all_tables if t.find("tr", class_=re.compile(r"TabHead"))]
        qualifying_set = set(id(t) for t in qualifying)
        tables_to_process = [
            t for t in qualifying
            if not any(
                id(child) in qualifying_set
                for child in t.find_all("table")
                if id(child) != id(t)
            )
        ]

        for table in tables_to_process:
            header_row = table.find("tr", class_=re.compile(r"TabHead"))
            if not header_row:
                continue

            headers = [_clean_text(th.get_text()).lower() for th in header_row.find_all(["th", "td"], recursive=False)]
            col_map = self._map_cat_columns(headers)
            if "name" not in col_map:
                continue

            for row in table.find_all("tr"):
                css = " ".join(row.get("class") or [])
                if "TabHead" in css:
                    continue
                if not re.search(r"Line\d", css):
                    continue

                cells = row.find_all(["td", "th"], recursive=False)
                result = self._parse_cat_row(cells, col_map, category, segment_count)
                if result:
                    results.append(result)

        return results

    def _map_cat_columns(self, headers: list[str]) -> dict[str, int]:
        """Map CAT result page column headers to indices."""
        col_map: dict[str, int] = {}
        for i, h in enumerate(headers):
            h = h.strip().rstrip(".=+- ").strip()
            if h in ("fpl", "pl"):
                col_map["rank"] = i
            elif h == "name":
                col_map["name"] = i
            elif h == "club":
                col_map["club"] = i
            elif h == "nation":
                col_map["nation"] = i
            elif h == "points":
                col_map["points"] = i
            elif h == "sp":
                col_map["sp"] = i
            elif h == "fs":
                col_map["fs"] = i
        return col_map

    def _parse_cat_row(
        self,
        cells: list[Tag],
        col_map: dict[str, int],
        category: str,
        segment_count: int,
    ) -> ScrapedCategoryResult | None:
        def cell_text(key: str) -> str | None:
            idx = col_map.get(key)
            if idx is None or idx >= len(cells):
                return None
            return _clean_text(cells[idx].get_text()) or None

        name_text = cell_text("name")
        if not name_text or len(name_text) < 2:
            return None

        # Skip withdrawn / disqualified rows (Points will be empty or "WD")
        points_raw = cell_text("points")
        combined_total = _parse_float(points_raw)
        if combined_total is None:
            return None

        # Extract nation
        nationality: str | None = None
        nat_idx = col_map.get("nation")
        if nat_idx is not None and nat_idx < len(cells):
            nat_text = _clean_text(cells[nat_idx].get_text())
            m = re.search(r"\b([A-Z]{2,3})\b", nat_text)
            if m:
                nationality = m.group(1)

        return ScrapedCategoryResult(
            name=name_text,
            club=cell_text("club"),
            nationality=nationality,
            category=category,
            overall_rank=_parse_int(cell_text("rank")),
            combined_total=combined_total,
            sp_rank=_parse_int(cell_text("sp")),
            fs_rank=_parse_int(cell_text("fs")),
            segment_count=segment_count,
        )

    async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult], list[ScrapedCategoryResult]]:
        """Full scrape: fetch index, discover events, fetch all SEG and CAT pages.

        Returns:
            A tuple of (events, segment_results, category_results).
        """
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
        ) as client:
            index_html = await _fetch(url, client)
            if not index_html:
                return [], [], []

            events, categories = self.parse_index(index_html, url)
            all_results: list[ScrapedResult] = []
            all_cat_results: list[ScrapedCategoryResult] = []

            for event in events:
                if not event.seg_url:
                    continue
                seg_html = await _fetch(event.seg_url, client)
                if not seg_html:
                    logger.warning("Failed to fetch %s", event.seg_url)
                    continue
                results = self.parse_seg_page(seg_html, event.category, event.segment)
                all_results.extend(results)

            for cat in categories:
                if not cat.cat_url:
                    continue
                cat_html = await _fetch(cat.cat_url, client)
                if not cat_html:
                    logger.warning("Failed to fetch %s", cat.cat_url)
                    continue
                segment_count = len(cat.segments) if cat.segments else 1
                cat_results = self.parse_cat_page(cat_html, cat.category, segment_count)
                all_cat_results.extend(cat_results)

            return events, all_results, all_cat_results


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
