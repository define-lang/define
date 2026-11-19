"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler.data_structures import define_path


class PathTracker[T]:
    """Tracks file paths encountered during validation and their results.

    Manages two concerns:
    - Mapping from file paths to validation results (with an in-progress sentinel).
    - Tracking paths that were referenced but could not be loaded.

    Type parameter T is the result type stored per path (e.g. LoadedFile).
    """

    def __init__(self):
        """Initialize empty path tracking state."""
        self._results: dict[define_path.DefinePath, T | None] = {}
        self._not_found: set[define_path.DefinePath] = set()

    def is_tracked(self, path: define_path.DefinePath) -> bool:
        """Return True if this path has been started or completed."""
        return path in self._results

    def mark_in_progress(self, path: define_path.DefinePath):
        """Record that validation of this path has begun."""
        self._results[path] = None

    def set_result(self, path: define_path.DefinePath, result: T):
        """Store the completed result for a path."""
        self._results[path] = result

    def try_get_result(self, path: define_path.DefinePath) -> T | None:
        """Return the completed result for a path, or None if not yet completed."""
        return self._results.get(path)

    def mark_not_found(self, path: define_path.DefinePath):
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
