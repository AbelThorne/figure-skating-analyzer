"""Classify ISU element codes into jump, spin, or step categories."""

import re

_JUMP_PATTERN = re.compile(r"^([1-4]?)(A|T|S|Lo|Lz|F)\b")
_SPIN_PATTERN = re.compile(r"Sp[B0-4]?$")
_STEP_PATTERN = re.compile(r"^(StSq|ChSq)")
_LEVEL_PATTERN = re.compile(r"(\d)$")


def classify_element(name: str) -> str | None:
    """Classify an element code as 'jump', 'spin', 'step', or None."""
    if _JUMP_PATTERN.match(name):
        return "jump"
    if _SPIN_PATTERN.search(name):
        return "spin"
    if _STEP_PATTERN.match(name):
        return "step"
    return None


def extract_jump_type(name: str) -> str | None:
    """Extract the jump type with rotation count, e.g. '2A', '3Lz'."""
    m = _JUMP_PATTERN.match(name)
    if not m:
        return None
    rotation = m.group(1) or "1"
    jump_code = m.group(2)
    return f"{rotation}{jump_code}"


def extract_level(name: str) -> float:
    """Extract the level number from an element code. B suffix = 0.5, no level = 0."""
    m = _LEVEL_PATTERN.search(name)
    if m:
        return int(m.group(1))
    if name.endswith("B"):
        return 0.5
    return 0
