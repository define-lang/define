"""An entry in a project's local dependencies config."""

from __future__ import annotations

from pathlib import PurePosixPath  # noqa: TC003

import msgspec


class LocalDependencyEntry(msgspec.Struct, frozen=True):
    """One entry in a project's local dependencies config."""

    deps_path: PurePosixPath
    universe: str
    # The path as the entry writes it, relative to the project that declares it.
    path: str

    def describe(self) -> str:
        """Describe the entry by its file and the values a developer finds in it."""
        return (
            f"\"{self.deps_path}\" declares universe '{self.universe}' at '{self.path}'"
        )
