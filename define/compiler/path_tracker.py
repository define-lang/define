"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

import pathlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import pygtrie

if TYPE_CHECKING:
    from collections.abc import Mapping


class _PathTrie[V](pygtrie.Trie[pathlib.PurePosixPath, V]):
    """A trie keyed by PurePosixPath, with slash-separated path components."""

    @override
    def _path_from_key(self, key: pathlib.PurePosixPath) -> list[str]:
        posix = key.as_posix()
        if posix == ".":
            return [""]
        return ["", *posix.split("/")]

    @override
    def _key_from_path(self, path: tuple[str, ...]) -> pathlib.PurePosixPath:
        if len(path) <= 1:
            return pathlib.PurePosixPath(".")
        return pathlib.PurePosixPath("/".join(path[1:]))


@dataclass
class _UniverseInfo:
    fqun: str
    sub_roots: Mapping[str, pathlib.PurePosixPath]


class PathTracker[T]:
    """Tracks file paths encountered during validation and their results.

    Manages three concerns:
    - Mapping from file paths to validation results (with an in-progress sentinel).
    - Tracking paths that were referenced but could not be loaded.
    - Mapping sub_root paths to universe info for prefix-based lookups.

    Type parameter T is the result type stored per path (e.g. ValidationResult).
    """

    def __init__(self):
        """Initialize empty path tracking state."""
        self._results: OrderedDict[pathlib.PurePosixPath, T | None] = OrderedDict()
        self._not_found: set[pathlib.PurePosixPath] = set()
        self._project_roots: _PathTrie[_UniverseInfo] = _PathTrie()
        self._tracked_files: pygtrie.PrefixSet[pathlib.PurePosixPath] = (
            pygtrie.PrefixSet(factory=_PathTrie)
        )
        self._unknown_universes: set[str] = set()

    def is_tracked(self, path: pathlib.PurePosixPath) -> bool:
        """Return True if this path has been started or completed."""
        return path in self._results

    def mark_in_progress(self, path: pathlib.PurePosixPath):
        """Record that validation of this path has begun."""
        self._results[path] = None
        self._tracked_files.add(path)

    def set_result(self, path: pathlib.PurePosixPath, result: T):
        """Store the completed result for a previously-started path."""
        self._results[path] = result

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

    def register_project_root(
        self,
        root: pathlib.PurePosixPath,
        fqun: str,
        sub_roots: Mapping[str, pathlib.PurePosixPath],
    ):
        """Register a project root as existing at a certain path.

        Args:
            root: The filesystem path for a project root, relative to the
              top-most project root. Can be PurePosixPath(".") for the
              top-most root.
            fqun: The fully qualified universe name configured for the root
              specified in the root arg.
            sub_roots: Mapping of dependency names to their paths.

        Raises:
            ValueError: If root is already registered or fqun was marked unknown.
        """
        if root in self._project_roots:
            raise ValueError(f"sub_root already registered: {root}")
        if fqun in self._unknown_universes:
            raise ValueError(f"fqun was marked unknown: {fqun}")
        self._project_roots[root] = _UniverseInfo(fqun=fqun, sub_roots=sub_roots)

    def project_root_loaded(self, root: pathlib.PurePosixPath) -> bool:
        """Return True if a project root has been registered at this path."""
        return root in self._project_roots

    def fqun_for_root(self, root: pathlib.PurePosixPath) -> str | None:
        """Return the FQUN registered for an exact project root path, or None."""
        if root not in self._project_roots:
            return None
        return self._project_roots[root].fqun

    def universe_has_sub_root_in(
        self, universe: str, root: pathlib.PurePosixPath
    ) -> bool:
        """Return True if the given universe is a configured sub_root under root.

        Raises:
            KeyError: If root is not a registered sub_root.
        """
        info = self._project_roots[root]
        return universe in info.sub_roots

    def mark_unknown_universe(self, fqun: str):
        """Record that this FQUN refers to an unknown universe."""
        self._unknown_universes.add(fqun)

    def is_unknown_universe(self, fqun: str) -> bool:
        """Return True if this FQUN was marked as unknown."""
        return fqun in self._unknown_universes

    def sub_root_location(
        self, fqun: str, parent_root: pathlib.PurePosixPath
    ) -> pathlib.PurePosixPath:
        """Return the configured path for fqun relative to parent_root.

        Raises:
            KeyError: If parent_root is not registered or fqun is not a
                configured sub_root under it.
        """
        info = self._project_roots[parent_root]
        return info.sub_roots[fqun]

    def find_enclosing_root(self, path: pathlib.PurePosixPath) -> pathlib.PurePosixPath:
        """Find the innermost project root containing this path.

        At least one project root must be registered.

        Raises:
            KeyError: If no project root has been registered.
        """
        step = self._project_roots.longest_prefix(path)
        if not step or step.key is None:
            raise KeyError(f"no project root registered for path: {path}")
        return step.key

    def first_tracked_file_under(
        self, sub_root_path: pathlib.PurePosixPath
    ) -> tuple[pathlib.PurePosixPath, str] | tuple[None, None]:
        """Find the first tracked file under sub_root_path and its owning universe.

        Returns (file_path, owner_universe) or None.
        """
        try:
            file_path = next(iter(self._tracked_files.iter(sub_root_path)))
        except StopIteration:
            return (None, None)
        owner_step = self._project_roots.longest_prefix(file_path)
        if owner_step and owner_step.value:
            return (file_path, owner_step.value.fqun)
        return (None, None)
