"""
Parser service: extracts element-by-element details from PDF score sheets.

Used for enrichment — the main scores come from HTML scraping.

Each element dict contains:
    number      int             Element order in the program (1–12)
    name        str             Clean element code (all markers stripped)
    markers     list[str]       ISU markers present: "<", "<<", "q", "e", "!", "*", "x", "F"
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

# ISU marker tokens that may appear standalone in the token stream
_STANDALONE_MARKERS = {"<<", "<", "q", "e", "!", "*", "x"}


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------

def _strip_trailing_markers(part: str) -> tuple[str, list[str]]:
    """Strip all trailing ISU markers from a single element part.

    Returns (clean_part, markers_list). Strips longest match first to
    avoid "<<" being parsed as two "<" markers.
    """
    markers: list[str] = []
    while True:
        changed = False
        for marker in ("<<", "<", "q", "e", "!", "*", "x"):
            if part.endswith(marker):
                markers.insert(0, marker)
                part = part[: -len(marker)]
                changed = True
                break
        if not changed:
            break
    return part, markers


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

    For non-combo elements the marker list is flat:
        "3Lz<"      -> ("3Lz",      ["<"])
        "3Lo<<"     -> ("3Lo",      ["<<"])
        "StSq3*"    -> ("StSq3",    ["*"])
        "3Lzx"      -> ("3Lz",      ["x"])
        "2Aq"       -> ("2A",       ["q"])

    For combo elements (containing "+") the returned markers list is
    positional — one entry per jump, aligned by index:
        "+"  means no marker on that jump position
        otherwise the marker string applies to that jump

        "3F+2Te"       -> ("3F+2T",     ["+", "e"])
        "2S<+1T"       -> ("2S+1T",     ["<", "+"])
        "3F!+2T<<"     -> ("3F+2T",     ["!", "<<"])
        "3Lz+2T<+2Lo"  -> ("3Lz+2T+2Lo", ["+", "<", "+"])
        "3Lz+2T"       -> ("3Lz+2T",   [])   # no markers → empty list
    """
    name = raw_name.strip()

    if "+" not in name:
        # Non-combo: strip trailing markers from the whole token
        clean, markers = _strip_trailing_markers(name)
        return clean, markers

    # Combo: split on "+", strip markers from each part
    parts = name.split("+")
    clean_parts: list[str] = []
    part_markers: list[list[str]] = []
    for part in parts:
        clean, ms = _strip_trailing_markers(part)
        clean_parts.append(clean)
        part_markers.append(ms)

    clean_name = "+".join(clean_parts)

    # Check if any part has markers
    any_marked = any(ms for ms in part_markers)
    if not any_marked:
        return clean_name, []

    # Build positional marker list: one entry per jump
    # If a jump has exactly one marker use it; if none use "+"; multi-marker
    # parts collapse to their first marker (rare edge case)
    positional: list[str] = []
    for ms in part_markers:
        if ms:
            positional.append(ms[0])  # primary marker for this jump
        else:
            positional.append("+")

    return clean_name, positional


# ---------------------------------------------------------------------------
# Element row parsing
# ---------------------------------------------------------------------------

def _parse_element_row(line: str) -> dict | None:
    """Parse one element row from extracted ISU Judges Details protocol text.

    Real PDF column order (space-separated tokens after the element number):
        ElementCode  [info_tokens]  BaseValue  [standalone_markers]
        ScoreOfPanel  GOE  J1 J2 ... Jn

    Where:
    - ElementCode may carry embedded marker suffixes (e.g. "3Lz<", "3F+2Te")
    - info_tokens are ISU info-column values: "F" (fall/flag), "<<", "<", "*"
      printed between the element name and the base value; they are skipped
      (ISU markers among them are already embedded in the element code)
    - standalone_markers (e.g. "x") may appear right after the base value
    - ScoreOfPanel is the final element score (second float after base value)
    - GOE is the panel GOE (third float after base value)
    - J1..Jn are per-judge GOE integers; nullified elements use "-" (treated as 0)
    - Judge count is 3–9

    Returns a dict with enriched element data, or None if the line does not
    match the expected element row format.
    """
    tokens = line.split()

    # Minimum: num + code + base_val + score + goe + 3 judges = 8 tokens
    if len(tokens) < 8:
        return None

    # First token must be a 1-or-2-digit element number (1–12)
    if not re.match(r"^\d{1,2}$", tokens[0]):
        return None
    number = int(tokens[0])
    if not (1 <= number <= 12):
        return None

    # Second token is the raw element code (may include marker suffixes)
    raw_name = tokens[1]

    # Skip info-column tokens between name and base value.
    # These are: ISU standalone markers (<<, <, *, q, e, !, x) and the
    # "F" info flag (fall on this element printed by FS Manager).
    # We collect both: ISU markers into pre_base_markers, fall flag separately.
    idx = 2
    pre_base_markers: list[str] = []
    has_fall = False
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in _STANDALONE_MARKERS:
            pre_base_markers.append(tok)
            idx += 1
        elif tok == "F":
            has_fall = True
            idx += 1
        else:
            break

    # Next token must be a float (base value)
    if idx >= len(tokens):
        return None
    try:
        base_value = float(tokens[idx])
    except ValueError:
        return None
    idx += 1

    # Immediately after base value, collect any standalone marker tokens (e.g. "x")
    inline_markers: list[str] = list(pre_base_markers)
    while idx < len(tokens) and tokens[idx] in _STANDALONE_MARKERS:
        inline_markers.append(tokens[idx])
        idx += 1

    # Remaining tokens: GOE  J1 J2 ... Jn  ScoreOfPanel
    # Real PDF column order: BaseValue GOE J1..Jn ScoreOfPanel
    # Layout: remaining[0]=goe, remaining[1:-1]=judges, remaining[-1]=score
    remaining = tokens[idx:]
    if len(remaining) < 5:  # goe + at least 3 judges + score
        return None

    try:
        goe = float(remaining[0])
        judge_tokens = remaining[1:-1]
        score = float(remaining[-1])
    except ValueError:
        return None

    # Enforce judge count range (3–9)
    if not (3 <= len(judge_tokens) <= 9):
        return None

    # Parse judge scores; nullified elements use "-" → treat as 0
    try:
        judge_goe = [0 if t == "-" else int(float(t)) for t in judge_tokens]
    except ValueError:
        return None

    clean_name, name_markers = _extract_markers(raw_name)
    # If name_markers is positional (contains "+" sentinels), use it as-is —
    # the inline standalone tokens are redundant duplicates of what's already
    # embedded in the element code. Merging/deduplicating would corrupt the
    # positional structure (e.g. turn ["e", "+", "+"] into ["e", "+"]).
    if "+" in name_markers:
        markers = name_markers
    else:
        # Flat format: merge name-embedded markers with standalone inline markers,
        # deduplicating while preserving order.
        seen: set[str] = set()
        markers = []
        for m in name_markers + inline_markers:
            if m not in seen:
                seen.add(m)
                markers.append(m)

    # "F" (fall) is an element-level flag — always appended last, never positional.
    if has_fall:
        markers.append("F")

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


_SEGMENT_CODE_MAP = {
    "free skating": "FS",
    "short program": "SP",
    "rhythm dance": "RD",
    "free dance": "FD",
}


def extract_segment_code(category_segment: str | None) -> str | None:
    """Extract a short segment code (SP, FS, …) from a category/segment line."""
    if not category_segment:
        return None
    low = category_segment.lower()
    for pattern, code in _SEGMENT_CODE_MAP.items():
        if pattern in low:
            return code
    return None
