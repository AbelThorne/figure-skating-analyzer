"""
Tests for the site scraper service.

These tests run entirely offline using minimal synthetic HTML that mimics the
structure of French IJS competition result pages (ligue-occitanie-sg.com format).
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.services.site_scraper import (
    FrenchIJSScraper,
    GenericTableScraper,
    ScrapedCompetitor,
    ScrapedEvent,
    _title_case_name,
    normalize_name,
    build_lookup,
    _merge_competitor,
)


# ---------------------------------------------------------------------------
# _title_case_name
# ---------------------------------------------------------------------------

class TestTitleCaseName:
    def test_all_caps_simple(self):
        assert _title_case_name("DUPONT MARIE") == "Dupont Marie"

    def test_already_mixed_case(self):
        # Do not touch names that are already mixed-case
        assert _title_case_name("Dupont Marie") == "Dupont Marie"

    def test_particle_lowercased(self):
        # Particles mid-name are lowercased; leading particle is capitalized
        result = _title_case_name("DE LA FONTAINE JEAN")
        assert result == "De la Fontaine Jean"

    def test_single_word(self):
        assert _title_case_name("MARTIN") == "Martin"

    def test_strip_whitespace(self):
        assert _title_case_name("  DUPONT MARIE  ") == "Dupont Marie"

    def test_accented_all_caps(self):
        # Accented letters that happen to be uppercase
        assert _title_case_name("ÉLODIE MARTIN") == "Élodie Martin"


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_removes_accents(self):
        assert normalize_name("Élodie") == "elodie"

    def test_lowercases(self):
        assert normalize_name("DUPONT") == "dupont"

    def test_collapses_spaces(self):
        assert normalize_name("  Marie   Dupont  ") == "marie dupont"

    def test_removes_punctuation(self):
        assert normalize_name("O'Brien") == "obrien"


# ---------------------------------------------------------------------------
# FrenchIJSScraper.can_handle
# ---------------------------------------------------------------------------

class TestFrenchIJSScraperCanHandle:
    scraper = FrenchIJSScraper()

    def test_occitanie_url(self):
        url = "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Montpellier/index.htm"
        assert self.scraper.can_handle(url) is True

    def test_ffsg_url(self):
        assert self.scraper.can_handle("https://www.ffsg.org/resultats/comp/index.htm") is True

    def test_generic_url(self):
        assert self.scraper.can_handle("https://example.com/results/index.htm") is False


# ---------------------------------------------------------------------------
# FrenchIJSScraper index parsing
# ---------------------------------------------------------------------------

INDEX_HTML = """
<html><body>
<h1>CSNPA 2026 - Coupe Régionale Montpellier</h1>
<table>
  <tr>
    <th>Catégorie</th>
    <th>Résultats</th>
    <th>Protocoles</th>
  </tr>
  <tr>
    <td>Espoirs Dames 1</td>
    <td><a href="ESPD1.HTM">Résultats</a></td>
    <td><a href="ESPD1_JD.pdf">PDF</a></td>
  </tr>
  <tr>
    <td>Espoirs Hommes 1</td>
    <td><a href="ESPH1.HTM">Résultats</a></td>
    <td><a href="ESPH1_JD.pdf">PDF</a></td>
  </tr>
</table>
</body></html>
"""

class TestFrenchIJSScraperIndexParsing:
    scraper = FrenchIJSScraper()
    base_url = "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Montpellier/index.htm"

    def test_discovers_two_events(self):
        soup = BeautifulSoup(INDEX_HTML, "html.parser")
        events = self.scraper._parse_index(soup, self.base_url)
        assert len(events) == 2

    def test_event_names(self):
        soup = BeautifulSoup(INDEX_HTML, "html.parser")
        events = self.scraper._parse_index(soup, self.base_url)
        names = [e.name for e in events]
        assert "Espoirs Dames 1" in names
        assert "Espoirs Hommes 1" in names

    def test_event_results_url_absolute(self):
        soup = BeautifulSoup(INDEX_HTML, "html.parser")
        events = self.scraper._parse_index(soup, self.base_url)
        base_dir = "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2026-CR-Montpellier/"
        for event in events:
            assert event.results_url is not None
            assert event.results_url.startswith(base_dir)

    def test_event_pdf_urls(self):
        soup = BeautifulSoup(INDEX_HTML, "html.parser")
        events = self.scraper._parse_index(soup, self.base_url)
        assert all(len(e.pdf_urls) == 1 for e in events)
        assert events[0].pdf_urls[0].endswith(".pdf")


# ---------------------------------------------------------------------------
# FrenchIJSScraper result page parsing
# ---------------------------------------------------------------------------

RESULT_HTML = """
<html><body>
<h2>Espoirs Dames 1 - Résultats</h2>
<table>
  <tr>
    <th>Pl.</th>
    <th>N°</th>
    <th>Patineur</th>
    <th>Club</th>
    <th>Points</th>
  </tr>
  <tr>
    <td>1</td>
    <td>5</td>
    <td>DUPONT MARIE</td>
    <td>Montpellier Skating</td>
    <td>45,23</td>
  </tr>
  <tr>
    <td>2</td>
    <td>3</td>
    <td>DE LA FONTAINE CÉLINE</td>
    <td>Toulouse PSG</td>
    <td>42.10</td>
  </tr>
  <tr>
    <td>3</td>
    <td>1</td>
    <td>MARTIN ÉLODIE</td>
    <td>Nîmes Patinage</td>
    <td>38,50</td>
  </tr>
</table>
</body></html>
"""

class TestFrenchIJSScraperResultPage:
    scraper = FrenchIJSScraper()

    def _competitors(self, category=None) -> list[ScrapedCompetitor]:
        soup = BeautifulSoup(RESULT_HTML, "html.parser")
        return self.scraper._extract_competitors(soup, category=category)

    def test_extracts_three_competitors(self):
        assert len(self._competitors()) == 3

    def test_name_title_cased(self):
        comps = self._competitors()
        names = [c.name for c in comps]
        assert "Dupont Marie" in names

    def test_particle_lowercased_in_name(self):
        comps = self._competitors()
        names = [c.name for c in comps]
        # "DE LA FONTAINE" → "De la Fontaine" (leading word capitalized, inner particles lowercased)
        assert "De la Fontaine Céline" in names

    def test_rank_parsed(self):
        comps = self._competitors()
        ranks = {c.name: c.rank for c in comps}
        assert ranks["Dupont Marie"] == 1

    def test_starting_number_parsed(self):
        comps = self._competitors()
        bibs = {c.name: c.starting_number for c in comps}
        assert bibs["Dupont Marie"] == 5

    def test_club_parsed(self):
        comps = self._competitors()
        clubs = {c.name: c.club for c in comps}
        assert clubs["Dupont Marie"] == "Montpellier Skating"

    def test_score_parsed_comma_decimal(self):
        comps = self._competitors()
        scores = {c.name: c.total_score for c in comps}
        assert scores["Dupont Marie"] == pytest.approx(45.23)

    def test_score_parsed_dot_decimal(self):
        comps = self._competitors()
        scores = {c.name: c.total_score for c in comps}
        assert scores["De la Fontaine Céline"] == pytest.approx(42.10)

    def test_category_from_argument(self):
        comps = self._competitors(category="Espoirs Dames 1")
        assert all(c.category == "Espoirs Dames 1" for c in comps)

    def test_category_inferred_from_heading(self):
        comps = self._competitors(category=None)
        # Heading h2 says "Espoirs Dames 1 - Résultats"
        assert all(c.category is not None for c in comps)


# ---------------------------------------------------------------------------
# FrenchIJSScraper – result page with nationality column
# ---------------------------------------------------------------------------

RESULT_HTML_WITH_NAT = """
<html><body>
<table>
  <tr>
    <th>Rang</th>
    <th>Départ</th>
    <th>Nom</th>
    <th>Club</th>
    <th>Nat</th>
    <th>Points</th>
  </tr>
  <tr>
    <td>1</td>
    <td>2</td>
    <td>LECLERC ANNA</td>
    <td>Bordeaux Patinage</td>
    <td>FRA</td>
    <td>50.00</td>
  </tr>
  <tr>
    <td>2</td>
    <td>4</td>
    <td>GARCIA SOFIA</td>
    <td>Perpignan Glace</td>
    <td>ESP</td>
    <td>47.50</td>
  </tr>
</table>
</body></html>
"""

class TestFrenchIJSScraperWithNationality:
    scraper = FrenchIJSScraper()

    def _competitors(self) -> list[ScrapedCompetitor]:
        soup = BeautifulSoup(RESULT_HTML_WITH_NAT, "html.parser")
        return self.scraper._extract_competitors(soup, category="Senior Dames")

    def test_nationality_parsed(self):
        comps = self._competitors()
        nat_map = {c.name: c.nationality for c in comps}
        assert nat_map["Leclerc Anna"] == "FRA"
        assert nat_map["Garcia Sofia"] == "ESP"


# ---------------------------------------------------------------------------
# GenericTableScraper – basic smoke test
# ---------------------------------------------------------------------------

GENERIC_HTML = """
<html><body>
<table>
  <tr><th>Rank</th><th>Name</th><th>Club</th><th>Score</th></tr>
  <tr><td>1</td><td>Alice Dupont</td><td>Club A</td><td>80.5</td></tr>
  <tr><td>2</td><td>Bob Martin</td><td>Club B</td><td>75.0</td></tr>
</table>
</body></html>
"""

class TestGenericTableScraper:
    scraper = GenericTableScraper()

    def test_can_handle_any_url(self):
        assert self.scraper.can_handle("https://anysite.com/results") is True

    def test_extracts_competitors(self):
        soup = BeautifulSoup(GENERIC_HTML, "html.parser")
        comps = self.scraper._extract_from_page(soup, category_hint="Test Cat")
        assert len(comps) == 2
        names = [c.name for c in comps]
        assert "Alice Dupont" in names

    def test_score_extracted(self):
        soup = BeautifulSoup(GENERIC_HTML, "html.parser")
        comps = self.scraper._extract_from_page(soup, category_hint=None)
        score_map = {c.name: c.total_score for c in comps}
        assert score_map["Alice Dupont"] == pytest.approx(80.5)


# ---------------------------------------------------------------------------
# build_lookup
# ---------------------------------------------------------------------------

class TestBuildLookup:
    def test_lookup_by_normalized_name(self):
        comps = [
            ScrapedCompetitor(name="Dupont Marie", club="Club A"),
            ScrapedCompetitor(name="Martin Jean", club="Club B"),
        ]
        lookup = build_lookup(comps)
        assert "dupont marie" in lookup
        assert lookup["dupont marie"].club == "Club A"

    def test_lookup_case_insensitive(self):
        comps = [ScrapedCompetitor(name="DUPONT MARIE")]
        lookup = build_lookup(comps)
        # normalize_name lowercases
        assert "dupont marie" in lookup


# ---------------------------------------------------------------------------
# _merge_competitor
# ---------------------------------------------------------------------------

class TestMergeCompetitor:
    def test_fills_missing_fields(self):
        target = ScrapedCompetitor(name="Dupont Marie", club=None, rank=None)
        source = ScrapedCompetitor(name="DUPONT MARIE", club="Club A", rank=1)
        _merge_competitor(target, source)
        assert target.club == "Club A"
        assert target.rank == 1

    def test_does_not_overwrite_existing(self):
        target = ScrapedCompetitor(name="Dupont Marie", club="Original Club")
        source = ScrapedCompetitor(name="DUPONT MARIE", club="New Club")
        _merge_competitor(target, source)
        assert target.club == "Original Club"
