"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygtrie

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping


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
        self._sub_root_trie: pygtrie.StringTrie[_UniverseInfo] = pygtrie.StringTrie(
            separator="/"
        )
        self._fqun_to_root: dict[str, pathlib.PurePosixPath] = {}
        self._unknown_universes: set[str] = set()

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

    def _trie_key(self, root: pathlib.PurePosixPath) -> str:
        """Convert a sub_root path to its trie key."""
        posix = root.as_posix()
        if posix == ".":
            return ""
        return "/" + posix

    def _lookup_key(self, path: pathlib.PurePosixPath) -> str:
        """Convert a file path to its trie lookup key."""
        return "/" + path.as_posix()

    def set_sub_root(
        self,
        root: pathlib.PurePosixPath,
        fqun: str,
        sub_roots: Mapping[str, pathlib.PurePosixPath],
    ):
        """Register a sub_root path with its universe info.

        Args:
            root: The filesystem path for this sub_root (empty for project root).
            fqun: The fully qualified universe name.
            sub_roots: Mapping of dependency names to their paths.

        Raises:
            ValueError: If root is already registered, fqun already maps to a
                root, or fqun was marked unknown.
        """
        key = self._trie_key(root)
        if key in self._sub_root_trie:
            raise ValueError(f"sub_root already registered: {root}")
        if fqun in self._fqun_to_root:
            raise ValueError(f"fqun already maps to a root: {fqun}")
        if fqun in self._unknown_universes:
            raise ValueError(f"fqun was marked unknown: {fqun}")
        self._sub_root_trie[key] = _UniverseInfo(fqun=fqun, sub_roots=sub_roots)
        self._fqun_to_root[fqun] = root

    def seen_sub_root(self, root: pathlib.PurePosixPath) -> bool:
        """Return True if this sub_root path has been registered."""
        return self._trie_key(root) in self._sub_root_trie

    def expected_universe(self, path: pathlib.PurePosixPath) -> str:
        """Return the FQUN for the sub_root that owns this file path.

        Uses longest-prefix matching in the trie.

        Raises:
            KeyError: If no sub_root matches the path.
        """
        step = self._sub_root_trie.longest_prefix(self._lookup_key(path))
        if not step:
            raise KeyError(f"no sub_root matches path: {path}")
        info = step.value
        return info.fqun

    def path_to_universe(self, fqun: str) -> pathlib.PurePosixPath:
        """Return the sub_root path for a given FQUN.

        Raises:
            KeyError: If the FQUN is not registered.
        """
        return self._fqun_to_root[fqun]

    def universe_has_sub_root_in(
        self, universe: str, root: pathlib.PurePosixPath
    ) -> bool:
        """Return True if the given universe is a configured sub_root under root.

        Raises:
            KeyError: If root is not a registered sub_root.
        """
        key = self._trie_key(root)
        info = self._sub_root_trie[key]
        return universe in info.sub_roots

    def mark_unknown_universe(self, fqun: str):
        """Record that this FQUN refers to an unknown universe."""
        self._unknown_universes.add(fqun)

    def is_unknown_universe(self, fqun: str) -> bool:
        """Return True if this FQUN was marked as unknown."""
        return fqun in self._unknown_universes
