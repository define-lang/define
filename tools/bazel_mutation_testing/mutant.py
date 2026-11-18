"""Mutants: changes to source files that tests should detect."""

from __future__ import annotations

import msgspec


class Mutant(msgspec.Struct, frozen=True):
    """One change to one source file."""

    name: str
    """A description that is unique within a run, starting with the file's
    workspace-relative path and the change's line and column."""
    path: str
    """The workspace-relative path of the changed file."""
    patch: str
    """A patch that `git apply` applies at the workspace's top."""
