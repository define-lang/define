# Rejected: ruff:ARG001, pyright:reportGeneralTypeIssues, pyright:reportUnknownVariableType, pyright:reportUnusedParameter
# Rejected in mutation runs: pyright:reportGeneralTypeIssues, pyright:reportUnknownVariableType
"""An assignment whose value became None, which unpacks None."""

from __future__ import annotations


def qualified(name: str) -> str:
    """Return `name` with its package, which is the part before its first dot."""
    package, _, local_name = None
    return f"{package}:{local_name}"
