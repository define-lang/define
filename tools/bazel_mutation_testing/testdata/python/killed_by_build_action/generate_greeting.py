"""Fails when the greeting is wrong, as a code generator fails on bad input."""

from __future__ import annotations

import pathlib
import sys


def greeting() -> str:
    """Return the greeting."""
    return "hello"


if __name__ == "__main__":
    if greeting() != "hello":
        sys.exit(1)
    _ = pathlib.Path(sys.argv[1]).write_text("hello\n", encoding="utf-8", newline="\n")
