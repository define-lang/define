"""Fails when the greeting is wrong, as a code generator fails on bad input."""

from __future__ import annotations

import sys


def greeting() -> str:
    """Return the greeting."""
    return "hello"


if __name__ == "__main__":
    sys.exit(greeting() != "hello")
