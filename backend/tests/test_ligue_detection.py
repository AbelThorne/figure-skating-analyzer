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
