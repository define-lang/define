"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib


class PathTracker[T]:
    """Tracks file paths encountered during validation and their results.

    Manages two concerns:
    - Mapping from file paths to validation results (with an in-progress sentinel).
    - Tracking paths that were referenced but could not be loaded.

    Type parameter T is the result type stored per path (e.g. ValidationResult).
    """

    def __init__(self):
        """Initialize empty path tracking state."""
        self._results: OrderedDict[pathlib.PurePosixPath, T | None] = OrderedDict()
        self._not_found: set[pathlib.PurePosixPath] = set()

    def is_tracked(self, path: pathlib.PurePosixPath) -> bool:
        """Return True if this path has been started or completed."""
        return path in self._results

    def mark_in_progress(self, path: pathlib.PurePosixPath):
        """Record that validation of this path has begun."""
        self._results[path] = None

    def set_result(self, path: pathlib.PurePosixPath, result: T):
        """Store the completed result for a previously-started path."""
        self._results[path] = result

    def has_result(self, path: pathlib.PurePosixPath) -> bool:
        """Return True if this path has a completed result."""
        return self._results.get(path) is not None

    def get_result(self, path: pathlib.PurePosixPath) -> T:
        """Return the completed result for a path.

        Raises KeyError if the path has no completed result.
        """
        result = self._results[path]
        if result is None:
            raise KeyError(f"{path} has no completed result")
        return result

    def mark_not_found(self, path: pathlib.PurePosixPath):
        """Record that this path was referenced but could not be loaded."""
        self._not_found.add(path)

    def completed_results(self) -> list[T]:
        """Return completed results, excluding in-progress and not-found paths.

        Results are returned in the order paths were first encountered.
        """
        return [
            result
            for path, result in self._results.items()
            if result is not None and path not in self._not_found
        ]
