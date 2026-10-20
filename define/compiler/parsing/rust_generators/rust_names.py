"""Rust names for Python classes."""

from __future__ import annotations

import re

_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def snake_case_name(class_name: str) -> str:
    """Return the snake_case form of the CamelCase `class_name`."""
    return _WORD_BOUNDARY.sub("_", class_name).lower()
