from app.services.french_ranking.url import normalize_french_ranking_url


def test_reecrit_pubhtml_en_export_csv():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv"
    )


def test_preserve_le_gid_en_query_string():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml?gid=42")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=42"
    )


def test_preserve_le_gid_en_fragment():
    assert (
        normalize_french_ranking_url("https://docs.google.com/spreadsheets/d/e/ABC/pubhtml#gid=42")
        == "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=42"
    )


def test_laisse_inchangee_une_url_deja_au_format_export():
    url = "https://docs.google.com/spreadsheets/d/e/ABC/pub?output=csv&gid=7"
    assert normalize_french_ranking_url(url) == url


def test_laisse_inchangee_une_source_non_google():
    assert normalize_french_ranking_url("https://exemple.fr/ranking.csv") == "https://exemple.fr/ranking.csv"


def test_supprime_les_espaces_autour():
    assert normalize_french_ranking_url("  https://exemple.fr/a.csv  ") == "https://exemple.fr/a.csv"
