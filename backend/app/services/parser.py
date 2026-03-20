"""
Parser service: extracts element-by-element details from PDF score sheets.

Used for enrichment — the main scores come from HTML scraping.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


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


def _parse_element_row(line: str) -> dict | None:
    """Parse a single element row from a protocol. (Stub — not yet implemented)."""
    raise NotImplementedError("_parse_element_row not yet implemented")


def parse_elements_from_text(text: str) -> list[dict]:
    """Parse elements from protocol text. (Stub — not yet implemented)."""
    raise NotImplementedError("parse_elements_from_text not yet implemented")


def parse_elements(pdf_path: Path) -> list[dict]:
    """
    Parse a PDF and return per-skater element details.

    Returns a list of dicts:
        {"skater_name": str, "category_segment": str, "elements": [...]}
    """
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # The category/segment line is near the top, e.g. "R3 C BABIES FEMME FREE SKATING"
    category_segment = _extract_category_segment(full_text)

    # Find each skater block: starts with the header data line
    skater_re = re.compile(
        r"^(\d{1,3})\s+(.+?)\s+([A-Z]{2,3})\s+\d{1,3}\s+\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+\s+-?\d+\.\d+",
        re.MULTILINE,
    )
    element_re = re.compile(
        r"^(\d{1,2})\s+(\S+(?:\*|<<)?(?:\s+\*)?)\s+(\d+\.\d+)\s+.*?(-?\d+\.\d+)\s+",
        re.MULTILINE,
    )

    matches = list(skater_re.finditer(full_text))
    for i, m in enumerate(matches):
        skater_name = m.group(2).strip()
        # Extract elements between this skater header and the next
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        elements = []
        for em in element_re.finditer(block):
            elements.append({
                "number": int(em.group(1)),
                "name": em.group(2).strip(),
                "base_value": float(em.group(3)),
                "goe": float(em.group(4)),
            })

        if elements:
            results.append({
                "skater_name": skater_name,
                "category_segment": category_segment,
                "elements": elements,
            })

    return results


def _extract_category_segment(text: str) -> str | None:
    """Extract the category/segment line from near the top of the PDF."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        if "JUDGES DETAILS" in line.upper():
            continue
        if re.search(r"\b(FREE SKATING|SHORT PROGRAM|RHYTHM DANCE|FREE DANCE)\b", line, re.IGNORECASE):
            return line
    return None
