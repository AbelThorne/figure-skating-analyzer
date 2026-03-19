"""Basic tests for the parser service."""

import pytest
from pathlib import Path
from app.services.parser import GenericParser, ParsedScore


def test_parsed_score_to_dict():
    ps = ParsedScore(
        skater_name="Test Skater",
        nationality="FRA",
        segment="SP",
        rank=1,
        total_score=80.5,
        technical_score=42.0,
        component_score=40.0,
        deductions=1.5,
    )
    d = ps.to_dict()
    assert d["skater_name"] == "Test Skater"
    assert d["segment"] == "SP"
    assert d["total_score"] == 80.5


def test_generic_parser_can_parse():
    parser = GenericParser()
    assert parser.can_parse("any text") is True


def test_extract_segment():
    parser = GenericParser()
    assert parser._extract_segment("Short Program results") == "SP"
    assert parser._extract_segment("Free Skating") == "FS"
    assert parser._extract_segment("no segment here") is None


def test_extract_float():
    import re
    parser = GenericParser()
    pattern = re.compile(r"Total Score[^\d]*([\d]+\.[\d]+)")
    assert parser._extract_float(pattern, "Total Score  75.32") == 75.32
    assert parser._extract_float(pattern, "no match") is None
