"""Parse skater names into (first_name, last_name) using uppercase detection.

Competition result pages use two orderings:
  - "Firstname LASTNAME"    (FS Manager, ISU Worlds 2025)
  - "LASTNAME Firstname"    (ISU OWG 2026)

The reliable signal: family-name words are fully UPPERCASE (allowing
hyphens and apostrophes within a word). Given-name words use mixed case.
"""

from __future__ import annotations

import re


def _is_uppercase_word(word: str) -> bool:
    """Check if a word is an uppercase family-name word.

    Allows hyphens and apostrophes: O'SHEA, PANNEAU-THIERY.
    Must contain at least one letter.
    """
    letters = re.sub(r"['\-]", "", word)
    return len(letters) > 0 and letters == letters.upper() and letters.isalpha()


def parse_skater_name(raw: str) -> tuple[str, str]:
    """Parse a raw skater name into (first_name, last_name).

    Returns:
        A tuple of (first_name, last_name). first_name may be empty
        if only a family name is present.
    """
    raw = " ".join(raw.split())  # normalize whitespace
    if not raw:
        return ("", "")

    words = raw.split()

    # Classify each word as uppercase (family) or not (given)
    upper_indices = [i for i, w in enumerate(words) if _is_uppercase_word(w)]

    if not upper_indices:
        # No uppercase words — treat entire string as last name
        return ("", raw)

    # Uppercase words must be contiguous to form the family name.
    # Find the contiguous block of uppercase words.
    first_upper = upper_indices[0]
    last_upper = upper_indices[-1]

    family_words = words[first_upper : last_upper + 1]
    given_words = words[:first_upper] + words[last_upper + 1 :]

    last_name = " ".join(family_words)
    first_name = " ".join(given_words)

    return (first_name, last_name)
