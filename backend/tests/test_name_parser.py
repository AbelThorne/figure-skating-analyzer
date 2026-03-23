import pytest
from app.services.name_parser import parse_skater_name


@pytest.mark.parametrize(
    "raw, expected_first, expected_last",
    [
        # FS Manager format: Firstname LASTNAME
        ("Fanny Sofia LIISANANTTI", "Fanny Sofia", "LIISANANTTI"),
        ("Lilou MORLON", "Lilou", "MORLON"),
        ("Emma WARIN", "Emma", "WARIN"),
        ("Lola PANNEAU-THIERY", "Lola", "PANNEAU-THIERY"),
        # ISU OWG 2026 format: LASTNAME Firstname
        ("MALININ Ilia", "Ilia", "MALININ"),
        ("KAGIYAMA Yuma", "Yuma", "KAGIYAMA"),
        ("SIAO HIM FA Adam", "Adam", "SIAO HIM FA"),
        ("GUTMANN Lara Naki", "Lara Naki", "GUTMANN"),
        ("O'SHEA Danny", "Danny", "O'SHEA"),
        ("GIOTOPOULOS MOORE Hektor", "Hektor", "GIOTOPOULOS MOORE"),
        # ISU Worlds 2025 format: Firstname LASTNAME (same as FS Manager)
        ("Adam SIAO HIM FA", "Adam", "SIAO HIM FA"),
        ("Kevin AYMOZ", "Kevin", "AYMOZ"),
        # Edge cases
        ("STELLATO-DUDEK Deanna", "Deanna", "STELLATO-DUDEK"),
        ("Mathys BUE-HUBERT", "Mathys", "BUE-HUBERT"),
        # Pair / ice dance teams (ISU format: LASTNAME Firstname / LASTNAME Firstname)
        ("FOURNIER BEAUDRY Laurence / CIZERON Guillaume", "", "Laurence FOURNIER BEAUDRY / Guillaume CIZERON"),
        ("CHOCK Madison / BATES Evan", "", "Madison CHOCK / Evan BATES"),
        ("STELLATO-DUDEK Deanna / DESCHAMPS Maxime", "", "Deanna STELLATO-DUDEK / Maxime DESCHAMPS"),
        # Pair / ice dance teams (FS Manager format: Firstname LASTNAME / Firstname LASTNAME)
        ("Laurence FOURNIER BEAUDRY / Guillaume CIZERON", "", "Laurence FOURNIER BEAUDRY / Guillaume CIZERON"),
    ],
)
def test_parse_skater_name(raw, expected_first, expected_last):
    first, last = parse_skater_name(raw)
    assert first == expected_first
    assert last == expected_last


def test_parse_single_uppercase_word():
    """A single uppercase word → last name only."""
    first, last = parse_skater_name("MALININ")
    assert first == ""
    assert last == "MALININ"


def test_parse_all_lowercase_fallback():
    """No uppercase words → entire string is last name."""
    first, last = parse_skater_name("unknown name")
    assert first == ""
    assert last == "unknown name"


def test_parse_empty_string():
    first, last = parse_skater_name("")
    assert first == ""
    assert last == ""


def test_parse_extra_whitespace():
    first, last = parse_skater_name("  Fanny   LIISANANTTI  ")
    assert first == "Fanny"
    assert last == "LIISANANTTI"
