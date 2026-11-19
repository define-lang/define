"""Read the lint flags and turned-off lints that bzl:lint_flags_json writes."""

from __future__ import annotations

import msgspec

from tools import runfiles


class Flags(msgspec.Struct, frozen=True):
    """The lint flags of rustc and of clippy."""

    rustc: list[str]
    clippy: list[str]


class TurnedOff(msgspec.Struct, frozen=True):
    """The lints and rules that mutation runs turn off, for each tool."""

    rust: frozenset[str]
    """The rustc and clippy lints."""
    ruff: frozenset[str]
    ast_grep: frozenset[str]
    pyright: frozenset[str]


class LintFlags(msgspec.Struct, frozen=True):
    """The repository's Rust lint flags, and those of mutation runs."""

    repository: Flags
    mutation_run: Flags
    turned_off: TurnedOff

    def bazel_flags(self) -> list[str]:
        """Return the Bazel flags that turn off the turned-off lints and rules."""
        settings = {
            "allowed_rust_lints": self.turned_off.rust,
            "turned_off_ast_grep_rules": self.turned_off.ast_grep,
            "turned_off_pyright_rules": self.turned_off.pyright,
            "turned_off_ruff_rules": self.turned_off.ruff,
        }
        flags: list[str] = []
        for setting, names in settings.items():
            # A list flag set to an empty string holds one empty name.
            if names:
                flags.append(f"--//tools/bzl:{setting}={','.join(sorted(names))}")
        return flags


def load() -> LintFlags:
    """Read the file that the `LINT_FLAGS` environment variable locates."""
    return msgspec.json.decode(
        runfiles.resolve_from_env("LINT_FLAGS").read_bytes(), type=LintFlags
    )
