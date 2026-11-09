"""Names for the invisible characters that diagnostics report."""

from __future__ import annotations

import unicodedata


def describe_invisible_character(character: str) -> str:
    """Return the character's code point and, when Unicode names it, its name."""
    code_point = f"U+{ord(character):04X}"
    name = unicodedata.name(character, "")
    return f"{code_point} {name}" if name else code_point
