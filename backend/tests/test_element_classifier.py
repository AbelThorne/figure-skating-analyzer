import pytest
from app.services.element_classifier import classify_element, extract_jump_type, extract_level


class TestClassifyElement:
    def test_single_axel(self):
        assert classify_element("1A") == "jump"
    def test_double_toe(self):
        assert classify_element("2T") == "jump"
    def test_double_salchow(self):
        assert classify_element("2S") == "jump"
    def test_double_loop(self):
        assert classify_element("2Lo") == "jump"
    def test_double_flip(self):
        assert classify_element("2F") == "jump"
    def test_double_lutz(self):
        assert classify_element("2Lz") == "jump"
    def test_triple_toe(self):
        assert classify_element("3T") == "jump"
    def test_triple_axel(self):
        assert classify_element("3A") == "jump"
    def test_combo_spin(self):
        assert classify_element("CCoSp4") == "spin"
    def test_flying_combo_spin(self):
        assert classify_element("FCSp3") == "spin"
    def test_flying_sit_spin(self):
        assert classify_element("FSSp4") == "spin"
    def test_camel_spin_no_level(self):
        assert classify_element("CCSp") == "spin"
    def test_layback_spin(self):
        assert classify_element("LSp4") == "spin"
    def test_step_sequence(self):
        assert classify_element("StSq3") == "step"
    def test_choreo_sequence(self):
        assert classify_element("ChSq1") == "step"
    def test_spin_not_jump(self):
        assert classify_element("FCSp3") != "jump"
    def test_step_not_jump(self):
        assert classify_element("StSq3") != "jump"
    def test_unknown_element(self):
        assert classify_element("BoDs3") is None


class TestExtractJumpType:
    def test_double_axel(self):
        assert extract_jump_type("2A") == "2A"
    def test_triple_toe(self):
        assert extract_jump_type("3T") == "3T"
    def test_single_loop(self):
        assert extract_jump_type("1Lo") == "1Lo"
    def test_quad_salchow(self):
        assert extract_jump_type("4S") == "4S"
    def test_non_jump_returns_none(self):
        assert extract_jump_type("CCoSp4") is None


class TestExtractLevel:
    def test_level_4(self):
        assert extract_level("CCoSp4") == 4
    def test_level_3(self):
        assert extract_level("StSq3") == 3
    def test_level_1(self):
        assert extract_level("ChSq1") == 1
    def test_no_level(self):
        assert extract_level("CCSp") == 0
    def test_b_suffix(self):
        assert extract_level("CCoSpB") == 0.5
