# Rejected: ruff:TC001
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves an import that only annotations use."""

from __future__ import annotations

from typing import final

from tools.bazel_mutation_testing import lint_flags


@final
class Rules:
    """The rules that a run turns off."""

    def __init__(self, run: str):
        """Read the repository's lint flags for `run`."""
        self._run = run
        self._flags = None

    def describe(self, flags: lint_flags.LintFlags) -> str:
        """Return the Ruff rules that `flags` turn off in the run."""
        return f"{self._run}: {sorted(flags.turned_off.ruff)}"
