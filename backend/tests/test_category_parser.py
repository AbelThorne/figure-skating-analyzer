import pytest
from app.services.category_parser import parse_category


class TestParseLevel:
    def test_national(self):
        assert parse_category("National Novice Femme")["skating_level"] == "National"

    def test_d1_maps_to_national(self):
        assert parse_category("D1 Junior Homme")["skating_level"] == "National"

    def test_federal(self):
        assert parse_category("Fédéral Senior Femme")["skating_level"] == "Fédéral"

    def test_federale_accent_variant(self):
        assert parse_category("Fédérale Junior Femme")["skating_level"] == "Fédéral"

    def test_d2_maps_to_federal(self):
        assert parse_category("D2 Novice Homme")["skating_level"] == "Fédéral"

    def test_r1(self):
        assert parse_category("R1 Minime Femme")["skating_level"] == "R1"

    def test_d3_maps_to_r1(self):
        assert parse_category("D3 Benjamin Homme")["skating_level"] == "R1"

    def test_r2(self):
        assert parse_category("R2 Novice Femme")["skating_level"] == "R2"

    def test_r3_a(self):
        assert parse_category("R3 A Jun-Sen Serie 1 Femme")["skating_level"] == "R3 A"

    def test_r3_b(self):
        assert parse_category("R3 B Poussin Serie 1 Femme")["skating_level"] == "R3 B"

    def test_r3_c(self):
        assert parse_category("R3 C Babies Homme")["skating_level"] == "R3 C"

    def test_adulte_bronze(self):
        assert parse_category("Adulte Bronze Femme")["skating_level"] == "Adulte Bronze"

    def test_adulte_argent(self):
        assert parse_category("Adulte Argent Homme")["skating_level"] == "Adulte Argent"

    def test_adulte_or(self):
        assert parse_category("Adulte Or Femme")["skating_level"] == "Adulte Or"

    def test_no_level_returns_none(self):
        assert parse_category("Novice Femme")["skating_level"] is None


class TestParseAgeGroup:
    def test_babies(self):
        assert parse_category("R3 C Babies Femme")["age_group"] == "Babies"

    def test_poussin(self):
        assert parse_category("R3 B Poussin Serie 1 Femme")["age_group"] == "Poussin"

    def test_benjamin(self):
        assert parse_category("National Benjamin Femme")["age_group"] == "Benjamin"

    def test_minime(self):
        assert parse_category("R1 Minime Homme")["age_group"] == "Minime"

    def test_novice(self):
        assert parse_category("R2 Novice Femme")["age_group"] == "Novice"

    def test_junior(self):
        assert parse_category("Fédéral Junior Femme")["age_group"] == "Junior"

    def test_senior(self):
        assert parse_category("Fédéral Senior Homme")["age_group"] == "Senior"

    def test_junior_senior_compound(self):
        assert parse_category("R1 Junior-Senior Femme")["age_group"] == "Junior-Senior"

    def test_jun_sen_abbreviation(self):
        assert parse_category("R3 A Jun-Sen Serie 1 Femme")["age_group"] == "Junior-Senior"

    def test_min_nov_abbreviation(self):
        assert parse_category("R3 A Min-Nov Serie 1 Femme")["age_group"] == "Minime-Novice"

    def test_adulte_age_group(self):
        assert parse_category("Adulte Bronze Femme")["age_group"] == "Adulte"

    def test_adulte_or_age_group(self):
        assert parse_category("Adulte Or Homme")["age_group"] == "Adulte"


class TestParseGender:
    def test_femme(self):
        assert parse_category("R2 Minime Femme")["gender"] == "Femme"

    def test_homme(self):
        assert parse_category("R1 Minime Homme")["gender"] == "Homme"

    def test_no_gender(self):
        assert parse_category("R2 Minime")["gender"] is None


class TestEdgeCases:
    def test_full_compound_r3(self):
        result = parse_category("R3 A Min-Nov Serie 1 Femme")
        assert result == {
            "skating_level": "R3 A",
            "age_group": "Minime-Novice",
            "gender": "Femme",
        }

    def test_serie_stripped(self):
        result = parse_category("R3 B Benjamin Serie 1 Femme")
        assert result["age_group"] == "Benjamin"

    def test_empty_string(self):
        result = parse_category("")
        assert result == {"skating_level": None, "age_group": None, "gender": None}

    def test_none_input(self):
        result = parse_category(None)
        assert result == {"skating_level": None, "age_group": None, "gender": None}

    def test_case_insensitive(self):
        result = parse_category("national novice femme")
        assert result["skating_level"] == "National"
        assert result["age_group"] == "Novice"
        assert result["gender"] == "Femme"
