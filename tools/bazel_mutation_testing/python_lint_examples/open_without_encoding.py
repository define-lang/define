# Rejected: ast-grep:text-io-explicit-encoding, ruff:PLW1514
# Rejected in mutation runs: ast-grep:text-io-explicit-encoding, ruff:PLW1514
"""A deleted encoding, which makes Python use the locale's."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib


def save(path: pathlib.Path, text: str):
    """Write `text` to `path`."""
    _ = path.write_text(text, newline="\n")
