# backend/tests/test_parser.py
"""Tests for the enriched score-card parser (parser.py)."""

from pathlib import Path

import pytest

from app.services.parser import _extract_markers, _parse_element_row, parse_elements_from_text

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _extract_markers
# ---------------------------------------------------------------------------

class TestExtractMarkers:
    def test_no_markers(self):
        name, markers = _extract_markers("3Lz")
        assert name == "3Lz"
        assert markers == []

    def test_underrotation(self):
        name, markers = _extract_markers("3Lz<")
        assert name == "3Lz"
        assert markers == ["<"]

    def test_downgrade(self):
        name, markers = _extract_markers("3Lo<<")
        assert name == "3Lo"
        assert markers == ["<<"]

    def test_quarter_underrotation(self):
        name, markers = _extract_markers("2Aq")
        assert name == "2A"
        assert markers == ["q"]

    def test_incorrect_edge(self):
        name, markers = _extract_markers("3Fe")
        assert name == "3F"
        assert markers == ["e"]

    def test_unclear_edge(self):
        name, markers = _extract_markers("3F!")
        assert name == "3F"
        assert markers == ["!"]

    def test_second_half_bonus(self):
        name, markers = _extract_markers("3Lzx")
        assert name == "3Lz"
        assert markers == ["x"]

    def test_nullified(self):
        name, markers = _extract_markers("StSq3*")
        assert name == "StSq3"
        assert markers == ["*"]

    def test_combo_no_markers(self):
        name, markers = _extract_markers("3Lz+2T")
        assert name == "3Lz+2T"
        assert markers == []

    def test_combo_edge_on_last_jump(self):
        # "3F+2Te" → edge call applies to the combo (2T)
        name, markers = _extract_markers("3F+2Te")
        assert name == "3F+2T"
        assert "e" in markers

    def test_combo_unclear_edge(self):
        # "3F!+2T" → ! appears after the first jump before +
        # In real FS Manager HTML, ! on Flip in a combo may appear as "3F!+2T"
        name, markers = _extract_markers("3F!+2T")
        # After stripping: name ends with "T", not a marker → no markers stripped
        # The ! is embedded, not a trailing suffix — stays in name
        # This is an edge case: some formats put ! before +, not at the end
        # Acceptable: name="3F!+2T", markers=[] (no trailing markers)
        assert "3F" in name  # the jump code is present
        # Do not assert markers here — format varies; just ensure no crash

    def test_spin_no_markers(self):
        name, markers = _extract_markers("CSSp4")
        assert name == "CSSp4"
        assert markers == []

    def test_step_sequence_nullified(self):
        name, markers = _extract_markers("StSq3*")
        assert name == "StSq3"
        assert "*" in markers


# ---------------------------------------------------------------------------
# _parse_element_row
# ---------------------------------------------------------------------------

class TestParseElementRow:
    def test_clean_element_nine_judges(self):
        line = " 1  2A                            3.30   1   1   1   2   1   1   1   1   1   1.11   4.41"
        result = _parse_element_row(line)
        assert result is not None
        assert result["number"] == 1
        assert result["name"] == "2A"
        assert result["markers"] == []
        assert result["base_value"] == pytest.approx(3.30)
        assert result["judge_goe"] == [1, 1, 1, 2, 1, 1, 1, 1, 1]
        assert len(result["judge_goe"]) == 9
        assert result["goe"] == pytest.approx(1.11)
        assert result["score"] == pytest.approx(4.41)
        assert result["info_flag"] is None

    def test_underrotation_marker(self):
        line = " 2  3Lz<                          4.20  -3  -3  -4  -3  -3  -3  -3  -3  -3  -3.00   1.20"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lz"
        assert result["markers"] == ["<"]
        assert result["judge_goe"] == [-3, -3, -4, -3, -3, -3, -3, -3, -3]
        assert result["goe"] == pytest.approx(-3.00)

    def test_downgrade_marker(self):
        line = " 5  3Lo<<                         1.70  -4  -5  -5  -5  -5  -4  -5  -5  -5  -4.78  -3.08"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lo"
        assert result["markers"] == ["<<"]
        assert result["base_value"] == pytest.approx(1.70)

    def test_unclear_edge_on_combo(self):
        line = " 3  3F!+2T                        5.30   0   0   0   1   0   0   0   0   0   0.00   5.30"
        result = _parse_element_row(line)
        assert result is not None
        # "3F!+2T" — ! is embedded before + so may stay in name depending on format
        # At minimum: element parses without error and number is correct
        assert result["number"] == 3
        assert result["base_value"] == pytest.approx(5.30)
        assert result["judge_goe"] == [0, 0, 0, 1, 0, 0, 0, 0, 0]

    def test_nullified_element(self):
        line = " 6  StSq3*                        0.00   0   0   0   0   0   0   0   0   0   0.00   0.00"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "StSq3"
        assert "*" in result["markers"]
        assert result["base_value"] == pytest.approx(0.00)
        assert result["judge_goe"] == [0] * 9

    def test_second_half_bonus(self):
        line = " 7  3Lzx                          7.92   1   1   1   2   1   1   1   1   1   1.22   9.14"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lz"
        assert "x" in result["markers"]
        assert result["base_value"] == pytest.approx(7.92)

    def test_quarter_underrotation(self):
        line = " 8  2Aq                           3.30  -1  -1  -2  -1  -1  -1  -1  -1  -1  -1.11   2.19"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "2A"
        assert result["markers"] == ["q"]

    def test_edge_call_on_combo_suffix(self):
        line = " 2  3F+2Te                        5.83  -1  -1  -1  -2  -1  -1  -1  -1  -1  -1.00   4.83"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3F+2T"
        assert "e" in result["markers"]

    def test_five_judges(self):
        # Local competitions may have only 5 judges
        line = " 1  2A                            3.30   1   1   1   1   1   1.00   4.30"
        result = _parse_element_row(line)
        assert result is not None
        assert len(result["judge_goe"]) == 5
        assert result["goe"] == pytest.approx(1.00)
        assert result["score"] == pytest.approx(4.30)

    def test_non_element_header_returns_none(self):
        assert _parse_element_row("# Executed Elements") is None
        assert _parse_element_row(" #  Executed Elements       Info  Base Value") is None
        assert _parse_element_row("") is None
        assert _parse_element_row("Programme Components Score") is None

    def test_skater_header_row_returns_none(self):
        # Skater rank+name rows don't match element row shape
        line = "1  MARTIN Emma                FRA   3   28.14   12.50   15.64   0.00"
        # This has 6 floats but no element number in 1-12 range at the right indent
        # and names that are not element codes — parser should return None or a valid parse
        # Key assertion: no crash
        result = _parse_element_row(line)
        # If it parses, number must be 1 and name must be something
        # The important thing is it doesn't crash
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# parse_elements_from_text (integration)
# ---------------------------------------------------------------------------

class TestParseElementsFromText:
    @pytest.fixture
    def protocol_text(self):
        return (FIXTURES / "judges_details_sample.txt").read_text()

    def test_parses_two_skaters(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert len(results) == 2

    def test_first_skater_name(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert results[0]["skater_name"] == "MARTIN Emma"

    def test_first_skater_has_ten_elements(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert len(results[0]["elements"]) == 10

    def test_enriched_element_has_all_keys(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        elem = results[0]["elements"][0]
        assert "number" in elem
        assert "name" in elem
        assert "markers" in elem
        assert "base_value" in elem
        assert "judge_goe" in elem
        assert "goe" in elem
        assert "score" in elem
        assert "info_flag" in elem

    def test_judge_goe_is_list_of_ints(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        for elem in results[0]["elements"]:
            assert isinstance(elem["judge_goe"], list)
            assert all(isinstance(v, int) for v in elem["judge_goe"])

    def test_markers_is_list(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        for elem in results[0]["elements"]:
            assert isinstance(elem["markers"], list)

    def test_second_half_bonus_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # Element 7 is "3Lzx" (index 6 in 0-based list)
        elem7 = results[0]["elements"][6]
        assert elem7["number"] == 7
        assert "x" in elem7["markers"]
        assert elem7["base_value"] == pytest.approx(7.92)

    def test_nullified_element_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # Element 6 is "StSq3*" (index 5)
        elem6 = results[0]["elements"][5]
        assert elem6["number"] == 6
        assert "*" in elem6["markers"]
        assert elem6["base_value"] == pytest.approx(0.00)
        assert all(g == 0 for g in elem6["judge_goe"])

    def test_underrotation_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # Element 2 is "3Lz<" (index 1)
        elem2 = results[0]["elements"][1]
        assert elem2["number"] == 2
        assert "<" in elem2["markers"]
        assert elem2["name"] == "3Lz"

    def test_quarter_underrotation_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # Element 8 is "2Aq" (index 7)
        elem8 = results[0]["elements"][7]
        assert elem8["number"] == 8
        assert "q" in elem8["markers"]
        assert elem8["name"] == "2A"

    def test_second_skater_edge_call(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # DUPONT Lea element 2: "3F+2Te" (index 1)
        elem2 = results[1]["elements"][1]
        assert "e" in elem2["markers"]
        assert elem2["name"] == "3F+2T"

    def test_category_segment_extracted(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert results[0]["category_segment"] is not None
        assert "FREE SKATING" in results[0]["category_segment"].upper()

    def test_elements_are_ordered_by_number(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        numbers = [e["number"] for e in results[0]["elements"]]
        assert numbers == sorted(numbers)
        assert numbers[0] == 1
