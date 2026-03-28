"""Heuristic detection of competition metadata from URL and HTML content."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


# Domain -> ligue mapping
# For domains that host both regional and FFSG (CSNPA) events,
# use a tuple (default_ligue, csnpa_path_pattern) — if the path matches,
# the competition is FFSG; otherwise it's the regional ligue.
_DOMAIN_TO_LIGUE: dict[str, str | tuple[str, str]] = {
    "ligue-des-alpes-patinage.org": ("AURA", r"/CSNPA/"),  # /CSNPA/ path → FFSG, else AURA
    "ligue-occitanie-sg.com": "Occitanie",
    "isujs.so.free.fr": "Occitanie",
    "lna-sportsdeglace.fr": "Aquitaine",
    "lchampionpaca.sos-ordi91.fr": "Région Sud",
    "resultatscmpt.great-site.net": "Centre Val de Loire",
    "csnpa.x10.mx": "FFSG",
}


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
    ("masters", [r"[/_][Mm][Aa][Ss][Tt][Ee][Rr][Ss]"], ["masters"]),
    ("nationales_autres", [r"/[Oo]uverture", r"/[Tt][Mm][Nn][Cc][Aa]"], ["ouverture", "nouveaux champions", "trophée des nouveaux"]),
    # French regional/federal
    ("tdf", [r"/TDF[_\-]", r"/FFSG_CSNPA[\-_]?[Tt][Dd][Ff]", r"/FFSG_CSNPA[\s_\-]tdf"], ["tournoi de france"]),
    ("tf", [r"[\-_]TF[\-_]", r"/TF[\-_]"], ["trophée fédéral"]),
    ("cr", [r"/CR[\-_]"], ["compétition régionale", "critérium régional"]),
]

# Known ISU domains — events on these are international (country ≠ France by default)
_ISU_DOMAINS = ("results.isu.org", "isuresults.com", "www.isuresults.com")


def detect_ligue(url: str, html: str) -> str:
    """Detect the ligue (regional league) from URL and HTML content.

    Priority:
    1. ISU domains -> ISU
    2. Domain mapping (with optional CSNPA path disambiguation)
    3. CSNPA mention in URL or HTML for unknown domains -> FFSG
    4. Fallback -> Autres
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or ""
    path = parsed.path or ""

    # 1. ISU domains
    if any(domain.endswith(d) for d in _ISU_DOMAINS):
        return "ISU"

    # 2. Domain mapping (checked first so known domains are never misclassified)
    for domain_pattern, ligue_value in _DOMAIN_TO_LIGUE.items():
        if domain.endswith(domain_pattern):
            if isinstance(ligue_value, tuple):
                # Tuple: (default_ligue, csnpa_path_pattern)
                default_ligue, csnpa_pattern = ligue_value
                if re.search(csnpa_pattern, path, re.IGNORECASE):
                    return "FFSG"
                return default_ligue
            return ligue_value

    # 3. CSNPA in URL or HTML for unknown domains -> FFSG
    if re.search(r"csnpa", url, re.IGNORECASE) or re.search(r"csnpa", html[:3000], re.IGNORECASE):
        return "FFSG"

    # 4. Fallback
    return "Autres"


def detect_metadata(url: str, html: str, *, scraped_city: str | None = None, scraped_country: str | None = None) -> dict:
    """Detect competition type, city, country, season, and ligue from URL + HTML.

    Returns dict with keys: competition_type, city, country, season, ligue.
    Values are None when not detectable (except ligue which defaults to 'Autres').

    ``scraped_city`` and ``scraped_country`` are values already extracted from
    the FS Manager HTML banner (caption3 row).  When provided they take
    priority over URL/title heuristics.
    """
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
    city = _city_from_url(url)
    if city:
        return city
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
    parts = name.split("-")
    cleaned_parts = []
    for part in parts:
        words = part.strip().split()
        cleaned_parts.append(" ".join(w.capitalize() for w in words))
    return "-".join(p for p in cleaned_parts if p)


_IOC_TO_COUNTRY: dict[str, str] = {
    "FRA": "France",
    "GER": "Germany",
    "ITA": "Italy",
    "ESP": "Spain",
    "GBR": "United Kingdom",
    "USA": "United States",
    "CAN": "Canada",
    "JPN": "Japan",
    "KOR": "South Korea",
    "CHN": "China",
    "RUS": "Russia",
    "SUI": "Switzerland",
    "AUT": "Austria",
    "BEL": "Belgium",
    "NED": "Netherlands",
    "SWE": "Sweden",
    "FIN": "Finland",
    "NOR": "Norway",
    "CZE": "Czech Republic",
    "POL": "Poland",
}


def _map_country_code(code: str) -> str:
    """Map a 3-letter IOC country code to a full country name."""
    return _IOC_TO_COUNTRY.get(code.upper(), code)


def _detect_country(url: str) -> str | None:
    """Detect country. Default France unless ISU domain."""
    from urllib.parse import urlparse
    domain = urlparse(url).hostname or ""
    if any(domain.endswith(d) for d in _ISU_DOMAINS):
        return None  # ISU events: admin sets country
    return "France"
