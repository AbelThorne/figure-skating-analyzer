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


class TestScrapedCityCountryOverride:
    def test_scraped_city_takes_priority(self):
        result = detect_metadata(
            "https://example.com/TDF_Colmar_2025/index.htm",
            "<html><title>Test</title></html>",
            scraped_city="Strasbourg",
        )
        assert result["city"] == "Strasbourg"

    def test_scraped_country_mapped(self):
        result = detect_metadata(
            "https://example.com/event/index.htm",
            "<html><title>Test</title></html>",
            scraped_country="FRA",
        )
        assert result["country"] == "France"

    def test_scraped_country_unknown_code_kept(self):
        result = detect_metadata(
            "https://example.com/event/index.htm",
            "<html><title>Test</title></html>",
            scraped_country="XYZ",
        )
        assert result["country"] == "XYZ"


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
        assert result["city"] is not None


class TestCountryDetection:
    def test_default_country_france(self):
        result = detect_metadata("https://example.com/TDF_Colmar/index.htm", "<html><title>Test</title></html>")
        assert result["country"] == "France"

    def test_isu_event_still_defaults_france_without_info(self):
        result = detect_metadata("https://results.isu.org/results/season2526/ec2026/", "<html><title>Test</title></html>")
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
