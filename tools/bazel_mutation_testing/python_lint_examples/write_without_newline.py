# Rejected: ast-grep:text-write-explicit-newline
# Rejected in mutation runs: ast-grep:text-write-explicit-newline
"""A deleted newline, which makes Python write the platform's line endings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib


def save(path: pathlib.Path, text: str):
    """Write `text` to `path`."""
    _ = path.write_text(text, encoding="utf-8")
