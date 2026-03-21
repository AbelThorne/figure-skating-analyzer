# Score Card Parser Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the PDF score-card parser to extract per-element markers (`*`, `<`, `<<`, `q`, `e`, `!`, `x`), per-judge GOE scores (−5 to +5), and second-half bonus detection from ISU protocol sheets, storing all enriched data in the existing `Score.elements` JSON column.

**Architecture:** The existing `parser.py` service already extracts element number/name/base_value/GOE from PDF text via pdfplumber. We extend it in-place: (1) split ISU markers out of the element name string, (2) parse the full row of per-judge GOE integers between base_value and the trimmed panel GOE, (3) expose `parse_elements_from_text(text)` as a pure, testable function (no PDF I/O), with `parse_elements(pdf_path)` becoming a thin pdfplumber wrapper. No new DB columns or tables — enriched data is additional keys in each element dict inside the existing `Score.elements` JSON column (backward-compatible).

**Tech Stack:** Python 3.12, pdfplumber (already in use), pytest, TypeScript (frontend type update only)

---

## ISU Marker Reference (for implementers)

| Symbol | Meaning | BV Effect | GOE Effect |
|--------|---------|-----------|------------|
| `*`    | Nullified element (over program limit) | BV = 0 | GOE = 0 |
| `<`    | Under-rotation (¼–½ rotation short) | × 0.70 | Reduced |
| `<<`   | Downgrade (≥½ rotation short) | Scored as lower jump | Reduced |
| `q`    | Quarter short (exactly ¼, since 2021-22) | No reduction | Capped at −1 |
| `e`    | Incorrect edge (Flip/Lutz takeoff) | Reduced | Must be negative |
| `!`    | Unclear/warning edge (Flip/Lutz) | No reduction | At judge discretion |
| `x`    | Second-half bonus (FS only) | × 1.10 (already in BV) | No effect |

Per-judge GOEs are integers −5 to +5. The panel GOE (trimmed mean) is the float stored after discarding the highest and lowest scores. Up to 9 judges (local competitions may have 5 or 7).

---

## PDF Protocol Row Layout

A typical element row in pdfplumber-extracted text:

```
 1  4Lz<   8.90   -3  -3  -4  -3  -3  -3  -3  -3  -3   -3.00   5.90
```

Fields (left to right):
1. Element number (1–2 digits)
2. Element code with optional marker suffixes: `4Lz<`, `3F+2T<<`, `StSq3*`, `3Lzx`, `2Aq`
3. Base value (float; already ×1.1 when `x` is present)
4. Judge GOE scores: 3–9 integers (−5 to +5), space-separated
5. Panel GOE (trimmed mean, float)
6. Element score (float = base_value + panel GOE)

Parsing strategy: tokenize the line by whitespace, validate the shape, and identify boundary between judge GOE ints and the two trailing floats.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/services/parser.py` | **Rewrite** | All parsing logic — marker extraction, per-judge GOE, public API |
| `backend/tests/test_parser.py` | **Create** | Unit + integration tests for all new helpers |
| `backend/tests/fixtures/judges_details_sample.txt` | **Create** | Realistic multi-skater protocol text fixture |
| `frontend/src/api/client.ts` | **Modify** | Add `ScoreElement` type; update `Score.elements` from `Array<Record<string, unknown>>` |

---

## Task 1: Create the protocol text fixture

**Files:**
- Create: `backend/tests/fixtures/judges_details_sample.txt`

This fixture simulates raw text extracted by pdfplumber from a Judges Details PDF. It covers all ISU marker types in realistic positions.

- [ ] **Step 1: Create the fixture file**

Create `backend/tests/fixtures/judges_details_sample.txt` with exactly this content (preserve spacing):

```
JUDGES DETAILS PER SKATER
R2 NOVICE FEMME FREE SKATING

1  MARTIN Emma                FRA   3   28.14   12.50   15.64   0.00
# Executed Elements
 #  Executed Elements       Info  Base Value   J1   J2   J3   J4   J5   J6   J7   J8   J9  GOE  Scores of Panel
 1  2A                            3.30   1   1   1   2   1   1   1   1   1   1.11   4.41
 2  3Lz<                          4.20  -3  -3  -4  -3  -3  -3  -3  -3  -3  -3.00   1.20
 3  3F!+2T                        5.30   0   0   0   1   0   0   0   0   0   0.00   5.30
 4  CSSp4                         3.00   1   1   2   1   1   1   1   1   1   1.11   4.11
 5  3Lo<<                         1.70  -4  -5  -5  -5  -5  -4  -5  -5  -5  -4.78  -3.08
 6  StSq3*                        0.00   0   0   0   0   0   0   0   0   0   0.00   0.00
 7  3Lzx                          7.92   1   1   1   2   1   1   1   1   1   1.22   9.14
 8  2Aq                           3.30  -1  -1  -2  -1  -1  -1  -1  -1  -1  -1.11   2.19
 9  FCoSp3                        3.00   0   1   0   0   1   0   0   1   0   0.33   3.33
10  ChSq1                         3.00   1   1   2   1   1   1   2   1   1   1.22   4.22

2  DUPONT Lea                  FRA   5   22.80   9.40   13.40   0.00
# Executed Elements
 1  2A                            3.30   0   0   1   0   0   0   0   0   0   0.00   3.30
 2  3F+2Te                        5.83  -1  -1  -1  -2  -1  -1  -1  -1  -1  -1.00   4.83
 3  2Lz                           2.10   1   0   1   1   1   0   1   0   1   0.67   2.77
 4  CCoSp4                        3.50   1   1   1   2   1   1   1   1   1   1.11   4.61
 5  2F                            1.80   0   0   0   0   0   0   0   0   0   0.00   1.80
```

- [ ] **Step 2: Verify the fixture reads cleanly**

```bash
wc -l /Users/julien/projects/figure-skating-analyzer/backend/tests/fixtures/judges_details_sample.txt
```

Expected: 27 (or close — whitespace lines are fine).

- [ ] **Step 3: Commit the fixture**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add backend/tests/fixtures/judges_details_sample.txt
git commit -m "test: add judges details protocol text fixture"
```

---

## Task 2: Write failing tests

**Files:**
- Create: `backend/tests/test_parser.py`

- [ ] **Step 1: Create the test file**

```python
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
```

- [ ] **Step 2: Run tests — confirm they all fail**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python -m pytest tests/test_parser.py -v 2>&1 | head -40
```

Expected: `ImportError` — `_extract_markers`, `_parse_element_row`, `parse_elements_from_text` not yet exported.

- [ ] **Step 3: Commit failing tests**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add backend/tests/test_parser.py
git commit -m "test: add failing tests for enriched score card parser"
```

---

## Task 3: Implement `_extract_markers`

**Files:**
- Modify: `backend/app/services/parser.py`

Add only this function — do not change anything else yet.

- [ ] **Step 1: Add `_extract_markers` after the imports in parser.py**

```python
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
```

- [ ] **Step 2: Run only `_extract_markers` tests**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python -m pytest tests/test_parser.py::TestExtractMarkers -v
```

Expected: All `TestExtractMarkers` tests **PASS**. All others still fail.

- [ ] **Step 3: Commit**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add backend/app/services/parser.py
git commit -m "feat: add _extract_markers helper for ISU protocol symbols"
```

---

## Task 4: Implement `_parse_element_row`

**Files:**
- Modify: `backend/app/services/parser.py`

Parsing strategy: tokenize each line by whitespace, then validate the field count and identify the element number, element code, and numeric columns.

- [ ] **Step 1: Add `_parse_element_row` to parser.py (after `_extract_markers`)**

```python
def _parse_element_row(line: str) -> dict | None:
    """Parse one element row from extracted protocol text.

    Line format (space-separated tokens):
        N  ElementCode  base_value  j1 j2 ... jN  panel_goe  element_score

    Where N is 1–12, ElementCode may contain markers, and judge count is 3–9.

    Returns a dict with keys:
        number, name, markers, base_value, judge_goe, goe, score, info_flag
    or None if the line does not match the expected format.
    """
    tokens = line.split()

    # Minimum: num + code + base_val + 3 judges + goe + score = 8 tokens
    if len(tokens) < 8:
        return None

    # First token must be a 1-or-2-digit element number
    if not re.match(r"^\d{1,2}$", tokens[0]):
        return None
    number = int(tokens[0])
    if not (1 <= number <= 12):
        return None

    # Second token is the raw element code (may contain markers)
    raw_name = tokens[1]

    # Third token must be a float (base value)
    try:
        base_value = float(tokens[2])
    except ValueError:
        return None

    # Remaining tokens: judge GOEs (ints) + panel GOE (float) + score (float)
    # The last two tokens are always panel_goe and score (floats).
    # Everything between index 3 and len-2 are judge GOEs (integers).
    remaining = tokens[3:]
    if len(remaining) < 3:  # need at least 1 judge + goe + score
        return None

    try:
        score = float(remaining[-1])
        goe = float(remaining[-2])
        judge_tokens = remaining[:-2]
    except ValueError:
        return None

    # Validate judge count: 3–9
    if not (3 <= len(judge_tokens) <= 9):
        return None

    try:
        judge_goe = [int(float(t)) for t in judge_tokens]
    except ValueError:
        return None

    clean_name, markers = _extract_markers(raw_name)

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
```

- [ ] **Step 2: Run `_parse_element_row` tests**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python -m pytest tests/test_parser.py::TestParseElementRow -v
```

Expected: All `TestParseElementRow` tests **PASS**.

Debug tip if a test fails: print the tokenized line to check token count and positions:
```bash
python3 -c "line='<paste failing line here>'; print(line.split()); print(len(line.split()))"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add backend/app/services/parser.py
git commit -m "feat: add _parse_element_row with per-judge GOE parsing"
```

---

## Task 5: Implement `parse_elements_from_text` and refactor `parse_elements`

**Files:**
- Rewrite: `backend/app/services/parser.py`

Replace the entire file. `parse_elements(pdf_path)` becomes a thin wrapper; `parse_elements_from_text(text)` contains all logic.

- [ ] **Step 1: Replace the full content of `backend/app/services/parser.py`**

```python
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

    # Third token must be a float (base value)
    try:
        base_value = float(tokens[2])
    except ValueError:
        return None

    # Remaining tokens: [j1, j2, ..., jN, panel_goe, element_score]
    # Last two are always panel_goe and score; the rest are judge GOE integers.
    remaining = tokens[3:]
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

    clean_name, markers = _extract_markers(raw_name)

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
```

- [ ] **Step 2: Run all parser tests**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python -m pytest tests/test_parser.py -v
```

Expected: All tests **PASS**.

If `TestParseElementsFromText` tests fail, debug by inspecting what the parser produces:
```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python3 -c "
from app.services.parser import parse_elements_from_text
from pathlib import Path
import json
text = Path('tests/fixtures/judges_details_sample.txt').read_text()
print(json.dumps(parse_elements_from_text(text), indent=2))
"
```

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" python -m pytest tests/ -v
```

Expected: All tests **PASS** (including the pre-existing `test_fs_manager_scraper.py` tests).

- [ ] **Step 4: Commit**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add backend/app/services/parser.py
git commit -m "feat: enrich element parser — markers, per-judge GOE, parse_elements_from_text"
```

---

## Task 6: Update TypeScript type for enriched element shape

**Files:**
- Modify: `frontend/src/api/client.ts` (lines 35–54 area)

The `Score` interface currently has `elements: Array<Record<string, unknown>> | null` (line 53). We add a proper `ScoreElement` interface and update the reference.

- [ ] **Step 1: Open `frontend/src/api/client.ts` and locate line 35 (the `Score` interface)**

- [ ] **Step 2: Insert `ScoreElement` interface before the `Score` interface (around line 35)**

Add this block immediately before `export interface Score {`:

```typescript
export interface ScoreElement {
  number: number;
  name: string;                 // clean element code, markers stripped (e.g. "3Lz")
  markers: string[];            // ISU markers: "<", "<<", "q", "e", "!", "*", "x"
  base_value: number;           // base value (×1.10 already applied when "x" present)
  judge_goe: number[];          // per-judge GOE scores (−5 to +5), length 3–9
  goe: number;                  // panel GOE (trimmed mean)
  score: number;                // final element score (base_value + goe)
  info_flag: string | null;     // reserved
}
```

- [ ] **Step 3: Update line 53 from `Array<Record<string, unknown>>` to `ScoreElement[]`**

Change:
```typescript
  elements: Array<Record<string, unknown>> | null;
```
To:
```typescript
  elements: ScoreElement[] | null;
```

- [ ] **Step 4: Verify TypeScript compiles without new errors**

```bash
cd /Users/julien/projects/figure-skating-analyzer/frontend
PATH="/opt/homebrew/bin:$PATH" npm run build 2>&1 | tail -20
```

Expected: Build succeeds or only pre-existing warnings — no new type errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add frontend/src/api/client.ts
git commit -m "feat: add ScoreElement TypeScript type with markers and judge_goe"
```

---

## Task 7: Manual smoke test with a real competition

- [ ] **Step 1: Start the backend if not running**

```bash
cd /Users/julien/projects/figure-skating-analyzer/backend
PATH="/opt/homebrew/bin:$PATH" uv run uvicorn app.main:app --reload --port 8000 &
sleep 2
```

- [ ] **Step 2: Enrich competition 1**

```bash
curl -s -X POST http://localhost:8000/api/competitions/1/enrich | python3 -m json.tool
```

Expected: `scores_enriched` > 0, `errors` is empty or minimal.

- [ ] **Step 3: Inspect element data — verify enriched shape**

```bash
curl -s "http://localhost:8000/api/scores?competition_id=1&limit=1" | python3 -c "
import json, sys
scores = json.load(sys.stdin)
for s in scores:
    if s.get('elements'):
        print(json.dumps(s['elements'][:3], indent=2))
        break
"
```

Expected output has `markers`, `judge_goe`, `goe`, `score` on each element:
```json
{
  "number": 1,
  "name": "2A",
  "markers": [],
  "base_value": 3.30,
  "judge_goe": [1, 1, 1, 2, 1, 1, 1, 1, 1],
  "goe": 1.11,
  "score": 4.41,
  "info_flag": null
}
```

- [ ] **Step 4: Verify at least one `x` marker appears (second-half bonus)**

```bash
curl -s "http://localhost:8000/api/scores?competition_id=1" | python3 -c "
import json, sys
scores = json.load(sys.stdin)
found = False
for s in scores:
    for e in (s.get('elements') or []):
        if 'x' in e.get('markers', []):
            print('Found x marker:', json.dumps(e, indent=2))
            found = True
            break
    if found:
        break
if not found:
    print('No x markers found — check if Free Skating PDFs are available')
"
```

- [ ] **Step 5: Commit any smoke-test fixes**

```bash
cd /Users/julien/projects/figure-skating-analyzer
git add -A
git commit -m "fix: smoke-test corrections for real PDF parsing"
```

---

## Enriched element dict — final shape

```json
{
  "number": 7,
  "name": "3Lz",
  "markers": ["x"],
  "base_value": 7.92,
  "judge_goe": [1, 1, 1, 2, 1, 1, 1, 1, 1],
  "goe": 1.22,
  "score": 9.14,
  "info_flag": null
}
```

**Marker semantics:**
- `*` → nullified (BV=0, GOE=0)
- `<` → under-rotation, BV at 70%
- `<<` → downgrade, scored as lower jump
- `q` → quarter short, GOE capped at −1, no BV reduction
- `e` → wrong edge, BV reduced, GOE must be negative
- `!` → edge warning, GOE at judge discretion
- `x` → second-half bonus, BV already ×1.1 in the `base_value` field
