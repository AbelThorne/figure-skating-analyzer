"""
Parser service: extracts element-by-element details from PDF score sheets.

Used for enrichment — the main scores come from HTML scraping.

Each element dict contains:
    number      int             Element order in the program (1–12)
    name        str             Clean element code (all markers stripped)
    markers     list[str]       ISU markers present: "<", "<<", "q", "e", "!", "*", "x"
    base_value  float           Base value (already ×1.10 when "x" marker present)
    judge_goe   list[int]       Per-judge GOE scores (−5 to +5), length 3–9
    goe         float           Panel GOE (trimmed mean of judge GOEs)
    score       float           Final element score (base_value + goe)
    info_flag   str | None      Reserved for future Info-column data
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------

def _extract_markers(raw_name: str) -> tuple[str, list[str]]:
    """Split an element name string into (clean_name, list_of_markers).

    ISU markers are suffix characters that may appear after element codes:
        <<   Downgrade (≥½ rotation short)
        <    Under-rotation (¼–½ rotation short)
        q    Quarter short (exactly ¼, no BV reduction, GOE capped at −1)
        e    Incorrect edge takeoff (Flip/Lutz)
        !    Unclear/warning edge
        *    Nullified element (over program limit, BV=0 GOE=0)
        x    Second-half bonus (BV already ×1.10 in base_value)

    Examples:
        "3Lz<"      -> ("3Lz",    ["<"])
        "3Lo<<"     -> ("3Lo",    ["<<"])
        "3F+2Te"    -> ("3F+2T",  ["e"])
        "StSq3*"    -> ("StSq3",  ["*"])
        "3Lzx"      -> ("3Lz",    ["x"])
        "2Aq"       -> ("2A",     ["q"])
        "3Lz+2T"    -> ("3Lz+2T", [])
    """
    markers: list[str] = []
    name = raw_name.strip()

    # Strip trailing markers repeatedly (longest first to avoid << being parsed as < + <)
    while True:
        changed = False
        for marker in ("<<", "<", "q", "e", "!", "*", "x"):
            if name.endswith(marker):
                markers.insert(0, marker)
                name = name[: -len(marker)]
                changed = True
                break
        if not changed:
            break

    return name, markers


# ---------------------------------------------------------------------------
# Element row parsing
# ---------------------------------------------------------------------------

def _parse_element_row(line: str) -> dict | None:
    """Parse one element row from extracted protocol text.

    Line format (space-separated tokens):
        N  ElementCode  base_value  j1 j2 ... jN  panel_goe  element_score

    Where N is 1–12, ElementCode may carry marker suffixes, and
    judge count is 3–9 (local competitions may have fewer than 9).

    Returns a dict with enriched element data, or None if the line
    does not match the expected element row format.
    """
    tokens = line.split()

    # Minimum: num + code + base_val + 3 judges + goe + score = 8 tokens
    if len(tokens) < 8:
        return None

    # First token must be a 1-or-2-digit element number (1–12)
    if not re.match(r"^\d{1,2}$", tokens[0]):
        return None
    number = int(tokens[0])
    if not (1 <= number <= 12):
        return None

    # Second token is the raw element code (may include markers as suffixes)
    raw_name = tokens[1]

    # ISU marker tokens that may appear standalone in the token stream
    _STANDALONE_MARKERS = {"<<", "<", "q", "e", "!", "*", "x"}

    # Collect any standalone marker tokens that appear between name and base_value
    # e.g. "4 2Lz+2T< < 3.14 ..." — the lone "<" at tokens[2] is a duplicate marker
    idx = 2
    pre_base_markers: list[str] = []
    while idx < len(tokens) and tokens[idx] in _STANDALONE_MARKERS:
        pre_base_markers.append(tokens[idx])
        idx += 1

    # Next token after optional pre-base markers must be a float (base value)
    if idx >= len(tokens):
        return None
    try:
        base_value = float(tokens[idx])
    except ValueError:
        return None
    idx += 1

    # Remaining tokens after base_value may contain more standalone ISU marker tokens
    # (e.g. "x" for second-half bonus) before the numeric GOE/score values.
    remaining = list(tokens[idx:])
    inline_markers: list[str] = pre_base_markers
    while remaining and remaining[0] in _STANDALONE_MARKERS:
        inline_markers.append(remaining.pop(0))

    if len(remaining) < 3:  # need ≥1 judge + goe + score
        return None

    try:
        score = float(remaining[-1])
        goe = float(remaining[-2])
        judge_tokens = remaining[:-2]
    except ValueError:
        return None

    # Enforce judge count range (3–9)
    if not (3 <= len(judge_tokens) <= 9):
        return None

    try:
        judge_goe = [int(float(t)) for t in judge_tokens]
    except ValueError:
        return None

    clean_name, name_markers = _extract_markers(raw_name)
    # Merge: name-embedded markers first, then standalone inline markers
    # Deduplicate while preserving order
    seen: set[str] = set()
    markers: list[str] = []
    for m in name_markers + inline_markers:
        if m not in seen:
            seen.add(m)
            markers.append(m)

    return {
        "number": number,
        "name": clean_name,
        "markers": markers,
        "base_value": base_value,
        "judge_goe": judge_goe,
        "goe": goe,
        "score": score,
        "info_flag": None,
    }


# ---------------------------------------------------------------------------
# Skater header pattern
# ---------------------------------------------------------------------------

# Matches the rank/name/nation/score header line for each skater:
# "1  MARTIN Emma  FRA  3  28.14  12.50  15.64  0.00"
_SKATER_HEADER_RE = re.compile(
    r"^(\d{1,3})\s+(.+?)\s+([A-Z]{2,3})\s+\d{1,3}\s+\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+\s+-?\d+\.\d+",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_elements_from_text(text: str) -> list[dict]:
    """Parse protocol text (as extracted by pdfplumber) into per-skater element data.

    Returns a list of dicts, one per skater:
        {
            "skater_name":      str,
            "category_segment": str | None,
            "elements":         list[dict],
        }

    Each element dict contains: number, name, markers, base_value,
    judge_goe, goe, score, info_flag.
    """
    results = []
    category_segment = _extract_category_segment(text)

    skater_matches = list(_SKATER_HEADER_RE.finditer(text))
    for i, sm in enumerate(skater_matches):
        skater_name = sm.group(2).strip()
        block_start = sm.end()
        block_end = skater_matches[i + 1].start() if i + 1 < len(skater_matches) else len(text)
        block = text[block_start:block_end]

        elements = []
        for line in block.splitlines():
            elem = _parse_element_row(line)
            if elem is not None:
                elements.append(elem)

        if elements:
            results.append({
                "skater_name": skater_name,
                "category_segment": category_segment,
                "elements": elements,
            })

    return results


def parse_elements(pdf_path: Path) -> list[dict]:
    """Parse a PDF score sheet and return per-skater element details.

    Thin wrapper: extracts text via pdfplumber, then delegates to
    parse_elements_from_text for all parsing logic.
    """
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return parse_elements_from_text(full_text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_category_segment(text: str) -> str | None:
    """Extract the category/segment line from near the top of the protocol text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:10]:
        if "JUDGES DETAILS" in line.upper():
            continue
        if re.search(r"\b(FREE SKATING|SHORT PROGRAM|RHYTHM DANCE|FREE DANCE)\b", line, re.IGNORECASE):
            return line
    return None
