"""Read the Rust lint flags and turned-off lints that bzl:rust_lint_flags writes."""

from __future__ import annotations

import msgspec

from tools import runfiles


class Flags(msgspec.Struct, frozen=True):
    """The lint flags of rustc and of clippy."""

    rustc: list[str]
    clippy: list[str]


class LintFlags(msgspec.Struct, frozen=True):
    """The repository's lint flags, and those of mutation runs."""

    repository: Flags
    mutation_run: Flags
    turned_off: frozenset[str]
    """The lints that mutation runs turn off."""


def load() -> LintFlags:
    """Read the file that the `LINT_FLAGS` environment variable locates."""
    return msgspec.json.decode(
        runfiles.resolve_from_env("LINT_FLAGS").read_bytes(), type=LintFlags
    )
