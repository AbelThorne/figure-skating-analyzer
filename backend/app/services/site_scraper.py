"""
Site scraper: extracts competitor metadata from competition result website HTML pages.

PDFs contain scores (technical, components, elements) but often lack metadata
that is only present on the website: club, birth year, starting number, category, etc.

This module scrapes the HTML site and returns structured competitor info
that can be merged with PDF-parsed scores during import.

The scraper is extensible: register site-specific scrapers via `register_scraper`.
"""

from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag


@dataclass
class ScrapedCompetitor:
    """Competitor metadata extracted from the competition website."""
    name: str
    nationality: str | None = None
    club: str | None = None
    birth_year: int | None = None
    category: str | None = None
    segment: str | None = None
    starting_number: int | None = None
    rank: int | None = None
    # Extra fields that don't fit elsewhere
    extra: dict = field(default_factory=dict)


class BaseSiteScraper(ABC):
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this scraper knows how to handle the given site."""

    @abstractmethod
    async def scrape(self, url: str, client: httpx.AsyncClient) -> list[ScrapedCompetitor]:
        """Scrape the competition site and return competitor metadata."""


class GenericTableScraper(BaseSiteScraper):
    """
    Generic scraper that looks for HTML tables containing competitor data.

    Heuristic approach:
    - Finds tables that likely contain rankings (columns: rank/name/club/nation/score)
    - Follows links to sub-pages (categories) and scrapes those too
    - Best-effort: works reasonably well on statically generated sites
    """

    _NAT_RE = re.compile(r"^[A-Z]{2,3}$")
    _YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
    _RANK_RE = re.compile(r"^\d{1,3}\.?$")
    _NUM_RE = re.compile(r"^\d{1,3}$")

    # Column header keywords → field mapping
    _HEADER_MAP = {
        "rang": "rank", "rank": "rank", "pl": "rank", "place": "rank",
        "num": "starting_number", "n°": "starting_number", "no": "starting_number",
        "bib": "starting_number",
        "nom": "name", "name": "name", "athlete": "name", "patineur": "name",
        "club": "club", "société": "club", "societe": "club",
        "nation": "nationality", "nat": "nationality", "pays": "nationality",
        "né": "birth_year", "naissance": "birth_year", "born": "birth_year",
        "catégorie": "category", "cat": "category", "category": "category",
        "segment": "segment",
    }

    def can_handle(self, url: str) -> bool:
        return True  # fallback

    async def scrape(self, url: str, client: httpx.AsyncClient) -> list[ScrapedCompetitor]:
        pages = await self._collect_pages(url, client)
        competitors: list[ScrapedCompetitor] = []
        seen_names: set[str] = set()

        for page_url, html, category_hint in pages:
            soup = BeautifulSoup(html, "html.parser")
            page_competitors = self._extract_from_page(soup, category_hint)
            for c in page_competitors:
                key = normalize_name(c.name)
                if key not in seen_names:
                    seen_names.add(key)
                    competitors.append(c)
                else:
                    # Merge: update existing entry with any new info
                    existing = next(x for x in competitors if normalize_name(x.name) == key)
                    _merge_competitor(existing, c)

        return competitors

    async def _collect_pages(
        self, url: str, client: httpx.AsyncClient
    ) -> list[tuple[str, str, str | None]]:
        """
        Returns list of (page_url, html_text, category_hint).
        Follows links to sub-pages within the same competition directory.
        """
        pages: list[tuple[str, str, str | None]] = []
        visited: set[str] = set()
        base_path = url.rsplit("/", 1)[0] + "/"

        async def fetch_page(page_url: str, category: str | None):
            if page_url in visited:
                return
            visited.add(page_url)
            try:
                resp = await client.get(page_url, follow_redirects=True)
                if resp.status_code != 200:
                    return
                html = resp.text
                pages.append((page_url, html, category))

                # Follow sub-links within the same competition directory
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if not href or href.startswith("#") or href.startswith("mailto"):
                        continue
                    abs_href = href if href.startswith("http") else urljoin(page_url, href)
                    # Only follow pages within the same competition directory
                    if abs_href.startswith(base_path) and abs_href not in visited:
                        if re.search(r"\.(htm|html)$", abs_href, re.IGNORECASE):
                            # Use link text as category hint
                            hint = a.get_text(strip=True) or category
                            await fetch_page(abs_href, hint)
            except Exception:
                pass

        await fetch_page(url, None)
        return pages

    def _extract_from_page(
        self, soup: BeautifulSoup, category_hint: str | None
    ) -> list[ScrapedCompetitor]:
        competitors: list[ScrapedCompetitor] = []

        # Try to find the category from headings if not hinted
        category = category_hint
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if text and not category:
                category = text
                break

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Parse header row to understand column layout
            header_row = rows[0]
            headers = [
                th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])
            ]
            col_map = self._map_columns(headers)

            if "name" not in col_map:
                continue  # Not a competitor table

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                comp = self._parse_row(cells, col_map, category)
                if comp:
                    competitors.append(comp)

        return competitors

    def _map_columns(self, headers: list[str]) -> dict[str, int]:
        """Return {field_name: column_index} for recognized headers."""
        col_map: dict[str, int] = {}
        for i, h in enumerate(headers):
            normalized = _strip_accents(h).lower().strip(" .:*/")
            for keyword, field_name in self._HEADER_MAP.items():
                if keyword in normalized and field_name not in col_map:
                    col_map[field_name] = i
                    break
        return col_map

    def _parse_row(
        self, cells: list[Tag], col_map: dict[str, int], category: str | None
    ) -> ScrapedCompetitor | None:
        def cell_text(field: str) -> str | None:
            idx = col_map.get(field)
            if idx is None or idx >= len(cells):
                return None
            return cells[idx].get_text(strip=True) or None

        name = cell_text("name")
        if not name or len(name) < 3:
            return None

        club = cell_text("club")
        nationality = cell_text("nationality")
        if nationality and not self._NAT_RE.match(nationality):
            nationality = None

        birth_year = None
        by_raw = cell_text("birth_year")
        if by_raw:
            m = self._YEAR_RE.search(by_raw)
            if m:
                birth_year = int(m.group(1))

        rank = None
        rank_raw = cell_text("rank")
        if rank_raw:
            m = self._RANK_RE.match(rank_raw.strip("."))
            if m:
                rank = int(rank_raw.strip("."))

        starting_number = None
        sn_raw = cell_text("starting_number")
        if sn_raw and self._NUM_RE.match(sn_raw):
            starting_number = int(sn_raw)

        segment = cell_text("segment")

        return ScrapedCompetitor(
            name=name,
            nationality=nationality,
            club=club,
            birth_year=birth_year,
            category=category,
            segment=segment,
            starting_number=starting_number,
            rank=rank,
        )


# --- Name normalization helpers ---

def normalize_name(name: str) -> str:
    """Normalize a skater name for fuzzy matching between HTML and PDF sources."""
    name = _strip_accents(name).lower()
    name = re.sub(r"[^a-z\s]", "", name)
    return " ".join(name.split())


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _merge_competitor(target: ScrapedCompetitor, source: ScrapedCompetitor) -> None:
    """Fill in missing fields in target from source."""
    for f in ("nationality", "club", "birth_year", "category", "segment", "starting_number", "rank"):
        if getattr(target, f) is None and getattr(source, f) is not None:
            setattr(target, f, getattr(source, f))
    target.extra.update({k: v for k, v in source.extra.items() if k not in target.extra})


# --- Registry ---

_scrapers: list[BaseSiteScraper] = [GenericTableScraper()]


def register_scraper(scraper: BaseSiteScraper, priority: bool = True) -> None:
    if priority:
        _scrapers.insert(0, scraper)
    else:
        _scrapers.append(scraper)


async def scrape_competition_site(url: str) -> list[ScrapedCompetitor]:
    """
    Scrape a competition result website and return competitor metadata.
    Results can be merged with PDF-parsed scores during import.
    """
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
    ) as client:
        for scraper in _scrapers:
            if scraper.can_handle(url):
                return await scraper.scrape(url, client)
    return []


def build_lookup(competitors: list[ScrapedCompetitor]) -> dict[str, ScrapedCompetitor]:
    """Build a {normalized_name: ScrapedCompetitor} dict for quick lookup during import."""
    return {normalize_name(c.name): c for c in competitors}
