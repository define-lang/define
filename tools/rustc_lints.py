"""Find rustc lints that are off by default and that a lint table does not name."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

_ALLOWED_LINT = re.compile(r"^\s+([a-z0-9-]+)\s+allow\s", re.MULTILINE)
_UNKNOWN_LINT = re.compile(r"^unknown lint: `([a-z0-9_]+)`$")


def _allow_by_default_lints(rustc: Path) -> frozenset[str]:
    help_text = subprocess.run(
        [rustc, "-W", "help"], check=True, capture_output=True, text=True
    ).stdout
    # The lint groups follow the lints, and a group is never listed as allow.
    lints = help_text.partition("Lint groups provided by rustc:")[0]
    names = cast("list[str]", _ALLOWED_LINT.findall(lints))
    return frozenset(name.replace("-", "_") for name in names)


def _unknown_lints(rustc: Path, lints: Collection[str]) -> frozenset[str]:
    # Stable rustc lists the lints that only nightly rustc enables, but reports
    # them as unknown once it compiles a crate with them.
    lint_flags: list[str] = []
    for lint in sorted(lints):
        lint_flags.extend(["-A", lint])
    with tempfile.TemporaryDirectory() as output_directory:
        messages = subprocess.run(
            [
                rustc,
                "--crate-type=lib",
                "--emit=metadata",
                "--error-format=json",
                f"--out-dir={output_directory}",
                *lint_flags,
                "-",
            ],
            input="",
            check=True,
            capture_output=True,
            text=True,
        ).stderr
    unknown: set[str] = set()
    for line in messages.splitlines():
        diagnostic = cast("dict[str, object]", json.loads(line))
        match = _UNKNOWN_LINT.match(cast("str", diagnostic["message"]))
        if match is not None:
            unknown.add(match.group(1))
    return frozenset(unknown)


def unnamed_lints(rustc: Path, named_lints: Collection[str]) -> list[str]:
    """Return the stable lints that `rustc` leaves off and `named_lints` omits."""
    allowed = _allow_by_default_lints(rustc)
    unnamed = allowed - set(named_lints)
    return sorted(unnamed - _unknown_lints(rustc, unnamed))
