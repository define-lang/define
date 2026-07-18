"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, override

import pygtrie

from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from define.compiler import config


class _PathTrie[V](pygtrie.Trie[define_path.DefinePath, V]):
    """A trie keyed by DefinePath, with slash-separated path components."""

    @override
    def _path_from_key(self, key: define_path.DefinePath) -> list[str]:
        return ["", *key.parts]

    @override
    def _key_from_path(self, path: tuple[str, ...]) -> define_path.DefinePath:
        if len(path) <= 1:
            return define_path.EMPTY
        return define_path.DefinePath("/".join(path[1:]))


class PathTracker[T]:
    """Tracks file paths encountered during validation and their results.

    Manages three concerns:
    - Mapping from file paths to validation results (with an in-progress sentinel).
    - Tracking paths that were referenced but could not be loaded.
    - Mapping project root paths to their resolved config for prefix-based lookups.

    Type parameter T is the result type stored per path (e.g. FileValidationResult).
    """

    def __init__(self):
        """Initialize empty path tracking state."""
        self._results: OrderedDict[define_path.DefinePath, T | None] = OrderedDict()
        self._not_found: set[define_path.DefinePath] = set()
        self._project_roots: _PathTrie[config.ProjectRootConfig] = _PathTrie()
        self._fqun_to_root: dict[str, define_path.DefinePath] = {}
        self._tracked_files: pygtrie.PrefixSet[define_path.DefinePath] = (
            pygtrie.PrefixSet(factory=_PathTrie)
        )
        self._failed_roots: pygtrie.PrefixSet[define_path.DefinePath] = (
            pygtrie.PrefixSet(factory=_PathTrie)
        )

    def is_tracked(self, path: define_path.DefinePath) -> bool:
        """Return True if this path has been started or completed."""
        return path in self._results

    def mark_in_progress(self, path: define_path.DefinePath):
        """Record that validation of this path has begun."""
        self._results[path] = None
        self._tracked_files.add(path)

    def set_result(self, path: define_path.DefinePath, result: T):
        """Store the completed result for a previously-started path."""
        self._results[path] = result

    def get_result(self, path: define_path.DefinePath) -> T:
        """Return the completed result for a path.

        Raises KeyError if the path has no completed result.
        """
        result = self._results[path]
        if result is None:
            raise KeyError(f"{path} has no completed result")
        return result

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

    def mark_root_failed(self, root: define_path.DefinePath):
        """Record that a project root's config failed to load."""
        self._failed_roots.add(root)

    def is_under_failed_root(self, path: define_path.DefinePath) -> bool:
        """Return True if path is under a root with a known-bad config."""
        return path in self._failed_roots

    def register_project_root(
        self,
        root: define_path.DefinePath,
        root_config: config.ProjectRootConfig,
    ):
        """Register a project root's resolved configuration at a certain path.

        Args:
            root: The filesystem path for a project root, relative to the
              top-most project root. Can be define_path.EMPTY for the
              top-most root.
            root_config: The resolved project configuration for the root
              specified in the root arg.

        Raises:
            ValueError: If root is already registered.
        """
        if root in self._project_roots:
            raise ValueError(f"sub_root already registered: {root}")
        self._project_roots[root] = root_config
        self._fqun_to_root[root_config.fqun] = root

    def project_root_loaded(self, root: define_path.DefinePath) -> bool:
        """Return True if a project root has been registered at this path."""
        return root in self._project_roots

    def root_for_fqun(self, fqun: str) -> define_path.DefinePath | None:
        """Return the root path registered for a given FQUN, or None."""
        return self._fqun_to_root.get(fqun)

    def config_for_root(
        self, root: define_path.DefinePath
    ) -> config.ProjectRootConfig | None:
        """Return the resolved config registered for an exact project root path, or None."""
        if root not in self._project_roots:
            return None
        return self._project_roots[root]

    def fqun_for_root(self, root: define_path.DefinePath) -> str | None:
        """Return the FQUN registered for an exact project root path, or None."""
        root_config = self.config_for_root(root)
        return None if root_config is None else root_config.fqun

    def has_sub_root(self, fqun: str, parent_root: define_path.DefinePath) -> bool:
        """Return True if fqun is a configured sub_root of parent_root."""
        return fqun in self._project_roots[parent_root].sub_roots

    def sub_root_location(
        self, fqun: str, parent_root: define_path.DefinePath
    ) -> define_path.DefinePath:
        """Return the configured path for fqun relative to parent_root.

        Raises:
            KeyError: If parent_root is not registered or fqun is not a
                configured sub_root under it.
        """
        info = self._project_roots[parent_root]
        return info.sub_roots[fqun]

    def find_enclosing_root(
        self, path: define_path.DefinePath
    ) -> define_path.DefinePath:
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
        self, sub_root_path: define_path.DefinePath
    ) -> tuple[define_path.DefinePath, str] | tuple[None, None]:
        """Find the first tracked file under sub_root_path and its owning universe.

        Returns (file_path, owner_universe) or None.
        """
        try:
            file_path = next(iter(self._tracked_files.iter(sub_root_path)))
        except StopIteration:
            return (None, None)
        owner_step = self._project_roots.longest_prefix(file_path)
        return (file_path, owner_step.value.fqun)
