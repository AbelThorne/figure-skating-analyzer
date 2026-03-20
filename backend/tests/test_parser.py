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
        # "3F+2Te" → edge call on 2T (last jump): positional ["+", "e"]
        name, markers = _extract_markers("3F+2Te")
        assert name == "3F+2T"
        assert markers == ["+", "e"]

    def test_combo_marker_on_first_jump(self):
        # "2S<+1T" → under-rotation on 2S (first jump): positional ["<", "+"]
        name, markers = _extract_markers("2S<+1T")
        assert name == "2S+1T"
        assert markers == ["<", "+"]

    def test_combo_markers_on_both_jumps(self):
        # "3F!+2T<<" → ! on 3F, << on 2T: positional ["!", "<<"]
        name, markers = _extract_markers("3F!+2T<<")
        assert name == "3F+2T"
        assert markers == ["!", "<<"]

    def test_combo_three_parts_middle_marker(self):
        # "3Lz+2T<+2Lo" → < on 2T (middle jump): ["+", "<", "+"]
        name, markers = _extract_markers("3Lz+2T<+2Lo")
        assert name == "3Lz+2T+2Lo"
        assert markers == ["+", "<", "+"]

    def test_combo_x_on_last_jump(self):
        # "3Lzx+2T" → x bonus applies to whole combo via last jump notation
        name, markers = _extract_markers("3Lzx+2T")
        assert name == "3Lz+2T"
        assert markers == ["x", "+"]

    def test_combo_unclear_edge_on_first(self):
        # "3F!+2T" → ! on 3F (first jump), nothing on 2T
        name, markers = _extract_markers("3F!+2T")
        assert name == "3F+2T"
        assert markers == ["!", "+"]

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
# Real PDF format: # Name [info_tokens] BaseValue GOE J1..Jn ScoreOfPanel
# ---------------------------------------------------------------------------

class TestParseElementRow:
    def test_clean_element_nine_judges(self):
        # Format: num name base goe j1..j9 score
        line = " 1  2A                            3.30   1.11   1   1   1   2   1   1   1   1   1   4.41"
        result = _parse_element_row(line)
        assert result is not None
        assert result["number"] == 1
        assert result["name"] == "2A"
        assert result["markers"] == []
        assert result["base_value"] == pytest.approx(3.30)
        assert result["goe"] == pytest.approx(1.11)
        assert result["score"] == pytest.approx(4.41)
        assert result["judge_goe"] == [1, 1, 1, 2, 1, 1, 1, 1, 1]
        assert len(result["judge_goe"]) == 9

    def test_underrotation_marker(self):
        line = " 2  3Lz<                          4.20  -3.00  -3  -3  -4  -3  -3  -3  -3  -3  -3   1.20"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lz"
        assert result["markers"] == ["<"]
        assert result["goe"] == pytest.approx(-3.00)
        assert result["judge_goe"] == [-3, -3, -4, -3, -3, -3, -3, -3, -3]

    def test_downgrade_marker(self):
        line = " 5  3Lo<<                         1.70  -4.78  -4  -5  -5  -5  -5  -4  -5  -5  -5  -3.08"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lo"
        assert result["markers"] == ["<<"]
        assert result["base_value"] == pytest.approx(1.70)
        assert result["goe"] == pytest.approx(-4.78)

    def test_nullified_element(self):
        line = " 6  StSq3*              *         0.00   0.00   0   0   0   0   0   0   0   0   0   0.00"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "StSq3"
        assert "*" in result["markers"]
        assert result["base_value"] == pytest.approx(0.00)
        assert result["judge_goe"] == [0] * 9

    def test_second_half_bonus_standalone_x(self):
        # x appears as standalone token between name and base value
        line = " 7  3Lz              x            7.92   1.22   1   1   1   2   1   1   1   1   1   9.14"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3Lz"
        assert "x" in result["markers"]
        assert result["base_value"] == pytest.approx(7.92)
        assert result["goe"] == pytest.approx(1.22)

    def test_quarter_underrotation(self):
        line = " 8  2Aq                           3.30  -1.11  -1  -1  -2  -1  -1  -1  -1  -1  -1   2.19"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "2A"
        assert result["markers"] == ["q"]
        assert result["goe"] == pytest.approx(-1.11)

    def test_edge_call_on_combo_suffix(self):
        line = " 2  3F+2Te                        5.83  -1.00  -1  -1  -1  -2  -1  -1  -1  -1  -1   4.83"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3F+2T"
        assert "e" in result["markers"]
        assert result["goe"] == pytest.approx(-1.00)

    def test_five_judges(self):
        # Local competitions may have only 5 judges
        line = " 1  2A                            3.30   1.00   1   1   1   1   1   4.30"
        result = _parse_element_row(line)
        assert result is not None
        assert len(result["judge_goe"]) == 5
        assert result["goe"] == pytest.approx(1.00)
        assert result["score"] == pytest.approx(4.30)

    def test_info_flag_F_before_base_value(self):
        # "F" fall flag appears between element name and base value — must appear in markers
        line = " 9  2S                F  x        1.30  -0.65  -5  -5  -5  -5  -5   0.65"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "2S"
        assert "x" in result["markers"]
        assert "F" in result["markers"]
        assert result["base_value"] == pytest.approx(1.30)
        assert result["goe"] == pytest.approx(-0.65)
        assert result["judge_goe"] == [-5, -5, -5, -5, -5]

    def test_info_flag_with_downgrade_marker(self):
        # "2Lo<< F <<" — element name has <<, then fall flag F and standalone <<
        line = " 2  2Lo<<             F  <<       0.50  -0.25  -5  -5  -5  -5  -5   0.25"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "2Lo"
        assert "<<" in result["markers"]
        assert "F" in result["markers"]
        assert result["base_value"] == pytest.approx(0.50)
        assert result["goe"] == pytest.approx(-0.25)

    def test_nullified_with_dash_judges(self):
        # Nullified element has "-" as judge scores
        line = " 3  FCUSpB*                *      0.00   0.00   -   -   -   -   -   0.00"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "FCUSpB"
        assert "*" in result["markers"]
        assert result["base_value"] == pytest.approx(0.00)
        assert result["goe"] == pytest.approx(0.00)
        assert result["judge_goe"] == [0, 0, 0, 0, 0]

    def test_underrotation_on_first_jump_of_combo(self):
        line = " 3  2S<+1T                        2.84  -2.11  -2  -2  -3  -2  -2  -2  -2  -2  -2   0.73"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "2S+1T"
        assert result["markers"] == ["<", "+"]
        assert result["base_value"] == pytest.approx(2.84)
        assert result["goe"] == pytest.approx(-2.11)

    def test_unclear_edge_on_first_jump_of_combo(self):
        line = " 3  3F!+2T                        5.30   0.00   0   0   0   1   0   0   0   0   0   5.30"
        result = _parse_element_row(line)
        assert result is not None
        assert result["name"] == "3F+2T"
        assert result["markers"] == ["!", "+"]
        assert result["goe"] == pytest.approx(0.00)

    def test_non_element_header_returns_none(self):
        assert _parse_element_row("# Executed Elements") is None
        assert _parse_element_row(" #  Executed Elements       Info  Base Value") is None
        assert _parse_element_row("") is None
        assert _parse_element_row("Programme Components Score") is None

    def test_skater_header_row_returns_none(self):
        line = "1  MARTIN Emma                FRA   3   28.14   12.50   15.64   0.00"
        result = _parse_element_row(line)
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# parse_elements_from_text (integration)
# ---------------------------------------------------------------------------

class TestParseElementsFromText:
    @pytest.fixture
    def protocol_text(self):
        return (FIXTURES / "judges_details_sample.txt").read_text()

    def test_parses_three_skaters(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert len(results) == 3

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

    def test_goe_is_before_judges_in_output(self, protocol_text):
        # Element 1: 2A, goe=1.11, judges=[1,1,1,2,1,1,1,1,1]
        results = parse_elements_from_text(protocol_text)
        elem1 = results[0]["elements"][0]
        assert elem1["number"] == 1
        assert elem1["name"] == "2A"
        assert elem1["goe"] == pytest.approx(1.11)
        assert elem1["score"] == pytest.approx(4.41)
        assert elem1["judge_goe"] == [1, 1, 1, 2, 1, 1, 1, 1, 1]

    def test_second_half_bonus_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # Element 7 is "3Lz x" (index 6)
        elem7 = results[0]["elements"][6]
        assert elem7["number"] == 7
        assert "x" in elem7["markers"]
        assert elem7["base_value"] == pytest.approx(7.92)
        assert elem7["goe"] == pytest.approx(1.22)

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
        assert elem2["goe"] == pytest.approx(-3.00)

    def test_combo_marker_on_first_jump_detected(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # MARTIN Emma element 3: "2S<+1T" (index 2)
        elem3 = results[0]["elements"][2]
        assert elem3["number"] == 3
        assert elem3["name"] == "2S+1T"
        assert elem3["markers"] == ["<", "+"]
        assert elem3["goe"] == pytest.approx(-2.11)

    def test_second_skater_edge_call_on_last_jump(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # DUPONT Lea element 2: "3F+2Te" (index 1)
        elem2 = results[1]["elements"][1]
        assert elem2["name"] == "3F+2T"
        assert elem2["markers"] == ["+", "e"]
        assert elem2["goe"] == pytest.approx(-1.00)

    def test_third_skater_parsed(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert results[2]["skater_name"] == "ERNY Saskia"

    def test_third_skater_nine_elements(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert len(results[2]["elements"]) == 9

    def test_info_flag_F_captured(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # ERNY element 2: "2Lo<< F <<" → name=2Lo, markers contain both << and F
        elem2 = results[2]["elements"][1]
        assert elem2["number"] == 2
        assert elem2["name"] == "2Lo"
        assert "<<" in elem2["markers"]
        assert "F" in elem2["markers"]
        assert elem2["base_value"] == pytest.approx(0.50)
        assert elem2["goe"] == pytest.approx(-0.25)

    def test_nullified_with_dash_judges(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # ERNY element 3: "FCUSpB* *" — dashes as judge scores
        elem3 = results[2]["elements"][2]
        assert elem3["number"] == 3
        assert "*" in elem3["markers"]
        assert elem3["judge_goe"] == [0, 0, 0, 0, 0]

    def test_info_flag_F_with_underrotation(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # ERNY element 4: "1A+2T< F <" → name=1A+2T, positional markers + F appended
        elem4 = results[2]["elements"][3]
        assert elem4["number"] == 4
        assert elem4["name"] == "1A+2T"
        assert "<" in elem4["markers"]
        assert "F" in elem4["markers"]
        assert elem4["goe"] == pytest.approx(-0.55)

    def test_info_flag_x_standalone(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        # ERNY element 9: "2S F x" → name=2S, markers contain both x and F
        elem9 = results[2]["elements"][8]
        assert elem9["number"] == 9
        assert elem9["name"] == "2S"
        assert "x" in elem9["markers"]
        assert "F" in elem9["markers"]
        assert elem9["goe"] == pytest.approx(-0.65)
        assert elem9["judge_goe"] == [-5, -5, -5, -5, -5]

    def test_category_segment_extracted(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        assert results[0]["category_segment"] is not None
        assert "FREE SKATING" in results[0]["category_segment"].upper()

    def test_elements_are_ordered_by_number(self, protocol_text):
        results = parse_elements_from_text(protocol_text)
        numbers = [e["number"] for e in results[0]["elements"]]
        assert numbers == sorted(numbers)
        assert numbers[0] == 1
