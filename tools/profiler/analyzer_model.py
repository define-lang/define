"""Shared models and filters for wall and CPU profile analysis."""

from __future__ import annotations

import dataclasses
import itertools
import pathlib
import typing

if typing.TYPE_CHECKING:
    from tools.profiler import schema


@dataclasses.dataclass(frozen=True, slots=True)
class AnalysisFilters:
    """Dimensions selected for one analyzer report."""

    # PRF-018: Focused analysis.
    thread_ids: frozenset[int] = frozenset()
    filename: str | None = None
    function: str | None = None
    caller: str | None = None
    callee: str | None = None
    compiler_only: bool = False


DEFAULT_FILTERS = AnalysisFilters()


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionIdentity:
    """Stable function identity independent of the sampled source line."""

    filename: str
    function: str


def is_compiler_filename(filename: str) -> bool:
    """Return whether a filename belongs to Define compiler source."""
    path_parts = pathlib.PurePath(filename).parts
    for index, path_part in enumerate(path_parts):
        if path_part.endswith(".runfiles"):
            # Bazel paths can contain package names before the runfiles source path.
            return path_parts[index + 1 : index + 4] == (
                "_main",
                "define",
                "compiler",
            )
    return any(
        parent == "define" and child == "compiler"
        for parent, child in itertools.pairwise(path_parts)
    )


def matches_frame(frame: schema.Frame, filters: AnalysisFilters) -> bool:
    """Return whether a source frame satisfies the report filters."""
    # PRF-018: Focused analysis.
    if filters.filename is not None and filters.filename not in frame["filename"]:
        return False
    if filters.function is not None and filters.function not in frame["function"]:
        return False
    return not filters.compiler_only or is_compiler_filename(frame["filename"])


def function_identity(frame: schema.Frame) -> FunctionIdentity:
    """Return the function identity for a source-identified frame."""
    return FunctionIdentity(
        filename=frame["filename"],
        function=frame["function"],
    )


def matches_function(identity: FunctionIdentity, filters: AnalysisFilters) -> bool:
    """Return whether a function satisfies the report filters."""
    # PRF-018: Focused analysis.
    if filters.filename is not None and filters.filename not in identity.filename:
        return False
    if filters.function is not None and filters.function not in identity.function:
        return False
    return not filters.compiler_only or is_compiler_filename(identity.filename)
