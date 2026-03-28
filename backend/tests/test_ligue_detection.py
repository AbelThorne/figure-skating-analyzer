from app.services.competition_metadata import detect_ligue


class TestLigueDetection:
    def test_csnpa_in_url_returns_ffsg(self):
        result = detect_ligue(
            "https://ligue-des-alpes-patinage.org/CSNPA/Saison20252026/CSNPA_AUTOMNE_2025/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_occitanie_domain_with_csnpa_in_path_returns_occitanie(self):
        """Occitanie domain should return Occitanie even if CSNPA appears in sub-path."""
        result = detect_ligue(
            "https://ligue-occitanie-sg.com/Resultats/2025-2026/CSNPA-2025-TF-Nimes/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Occitanie"

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

    def test_csnpa_x10_domain_returns_ffsg(self):
        result = detect_ligue(
            "https://csnpa.x10.mx/CSNPA/cdf_adults_2026/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_isujs_free_fr_returns_occitanie(self):
        result = detect_ligue(
            "https://isujs.so.free.fr/Resultats/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Occitanie"

    def test_lna_sportsdeglace_returns_aquitaine(self):
        result = detect_ligue(
            "https://lna-sportsdeglace.fr/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Aquitaine"

    def test_paca_domain_returns_region_sud(self):
        result = detect_ligue(
            "https://lchampionpaca.sos-ordi91.fr/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Région Sud"

    def test_centre_val_de_loire_domain(self):
        result = detect_ligue(
            "https://resultatscmpt.great-site.net/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Centre Val de Loire"

    def test_unknown_domain_with_csnpa_returns_ffsg(self):
        """Unknown domain but CSNPA in URL should still return FFSG."""
        result = detect_ligue(
            "https://unknown-host.com/CSNPA/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "FFSG"

    def test_unknown_domain_returns_autres(self):
        result = detect_ligue(
            "https://example.com/event/index.htm",
            "<html><title>Test</title></html>",
        )
        assert result == "Autres"
