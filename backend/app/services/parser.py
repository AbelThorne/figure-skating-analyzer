"""
Parser service: extracts structured score data from figure skating PDF score sheets.

Score cards vary by software/format. This module provides:
- A base `BaseParser` class to subclass for specific formats
- A `GenericParser` that uses heuristics with pdfplumber
- A `parse_scorecard(path)` function that selects the right parser

Future format-specific parsers can be registered via `register_parser`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pdfplumber


class ParsedScore:
    """Structured result from parsing one score sheet PDF."""

    def __init__(
        self,
        skater_name: str | None = None,
        nationality: str | None = None,
        segment: str | None = None,
        rank: int | None = None,
        total_score: float | None = None,
        technical_score: float | None = None,
        component_score: float | None = None,
        deductions: float | None = None,
        raw_data: dict[str, Any] | None = None,
    ):
        self.skater_name = skater_name
        self.nationality = nationality
        self.segment = segment
        self.rank = rank
        self.total_score = total_score
        self.technical_score = technical_score
        self.component_score = component_score
        self.deductions = deductions
        self.raw_data = raw_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "skater_name": self.skater_name,
            "nationality": self.nationality,
            "segment": self.segment,
            "rank": self.rank,
            "total_score": self.total_score,
            "technical_score": self.technical_score,
            "component_score": self.component_score,
            "deductions": self.deductions,
            "raw_data": self.raw_data,
        }


class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, text: str) -> bool:
        """Return True if this parser recognises the PDF format."""

    @abstractmethod
    def parse(self, pdf_path: Path) -> list[ParsedScore]:
        """Parse the PDF and return a list of ParsedScore objects (one per skater/segment)."""


class GenericParser(BaseParser):
    """
    Heuristic parser using pdfplumber.

    Attempts to extract:
    - Skater name (first large text block that looks like a name)
    - Segment (SP/FS/RD/FD keywords)
    - Scores from tabular data

    This is a best-effort implementation. Override or subclass for specific formats.
    """

    # Patterns for common score sheet fields
    _SEGMENT_RE = re.compile(r"\b(Short Program|Free Skating|Rhythm Dance|Free Dance|SP|FS|RD|FD)\b", re.IGNORECASE)
    _SCORE_RE = re.compile(r"Total\s+(?:Score|Element\s+Score|Component\s+Score|Segment\s+Score)[^\d]*([\d]+\.[\d]+)", re.IGNORECASE)
    _TES_RE = re.compile(r"Total\s+Element[s]?\s+Score[^\d]*([\d]+\.[\d]+)", re.IGNORECASE)
    _PCS_RE = re.compile(r"(?:Total\s+)?(?:Program\s+)?Component[s]?\s+Score[^\d]*([\d]+\.[\d]+)", re.IGNORECASE)
    _DED_RE = re.compile(r"Deduction[s]?[^\d\-]*([\-]?[\d]+\.[\d]+)", re.IGNORECASE)
    _RANK_RE = re.compile(r"Rank[^\d]*(\d+)", re.IGNORECASE)
    _NAT_RE = re.compile(r"\b([A-Z]{3})\b")

    def can_parse(self, text: str) -> bool:
        return True  # fallback parser

    def parse(self, pdf_path: Path) -> list[ParsedScore]:
        results = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                score = self._parse_page(text, page)
                if score:
                    results.append(score)
        return results

    def _parse_page(self, text: str, page: Any) -> ParsedScore | None:
        if not text.strip():
            return None

        raw: dict[str, Any] = {"text": text}

        segment = self._extract_segment(text)
        total = self._extract_float(self._SCORE_RE, text)
        tes = self._extract_float(self._TES_RE, text)
        pcs = self._extract_float(self._PCS_RE, text)
        ded = self._extract_float(self._DED_RE, text)
        rank = self._extract_int(self._RANK_RE, text)

        # Try tables for more reliable numeric extraction
        tables = page.extract_tables()
        raw["tables"] = tables

        skater_name, nationality = self._extract_skater(text, tables)

        if not skater_name and not total:
            return None

        return ParsedScore(
            skater_name=skater_name,
            nationality=nationality,
            segment=segment,
            rank=rank,
            total_score=total,
            technical_score=tes,
            component_score=pcs,
            deductions=ded,
            raw_data=raw,
        )

    def _extract_segment(self, text: str) -> str | None:
        m = self._SEGMENT_RE.search(text)
        if not m:
            return None
        val = m.group(1).upper()
        mapping = {
            "SHORT PROGRAM": "SP",
            "FREE SKATING": "FS",
            "RHYTHM DANCE": "RD",
            "FREE DANCE": "FD",
        }
        return mapping.get(val, val)

    def _extract_float(self, pattern: re.Pattern, text: str) -> float | None:
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    def _extract_int(self, pattern: re.Pattern, text: str) -> int | None:
        m = pattern.search(text)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
        return None

    def _extract_skater(self, text: str, tables: list) -> tuple[str | None, str | None]:
        """Try to extract skater name and nationality from text and tables."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name = None
        nat = None
        for line in lines[:10]:  # name is usually near the top
            # A name line: 2-4 words, mostly alphabetical, with possible accented chars
            if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ' \-]+$", line) and 2 <= len(line.split()) <= 5:
                if not self._SEGMENT_RE.match(line) and len(line) > 4:
                    name = line
                    break
        # Nationality: 3-letter code near the name line
        if name:
            idx = text.find(name)
            snippet = text[idx : idx + 100]
            m = self._NAT_RE.search(snippet)
            if m:
                nat = m.group(1)
        return name, nat


# --- Registry ---

_parsers: list[BaseParser] = [GenericParser()]


def register_parser(parser: BaseParser, priority: bool = True) -> None:
    if priority:
        _parsers.insert(0, parser)
    else:
        _parsers.append(parser)


def parse_scorecard(pdf_path: Path) -> list[ParsedScore]:
    """
    Parse a figure skating score sheet PDF.
    Returns a list of ParsedScore objects (usually one per page/skater).
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = (pdf.pages[0].extract_text() or "") if pdf.pages else ""

    for parser in _parsers:
        if parser.can_parse(first_page_text):
            return parser.parse(pdf_path)

    return []
