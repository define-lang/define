"""Mutants: changes to source files that tests should detect."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import bazel

if TYPE_CHECKING:
    import pathlib


class Mutant(msgspec.Struct, frozen=True):
    """One change to one source file."""

    name: str
    """A description that is unique within a run, starting with the file's
    workspace-relative path and the change's line and column."""
    path: str
    """The workspace-relative path of the changed file."""
    patch: str
    """A patch that `git apply` applies at the workspace's top."""
    lines: tuple[int, int]
    """The first and last lines of the file that a test must run one of, to run
    the change."""

    def apply(self, workspace: pathlib.Path):
        """Change the file in `workspace`, a checkout of the repository."""
        # Text-mode stdin changes LF to CRLF on Windows, even for LF source
        # files.
        _ = subprocess.run(
            [bazel.executable("git"), "apply"],
            cwd=workspace,
            input=self.patch.encode("utf-8"),
            check=True,
        )
