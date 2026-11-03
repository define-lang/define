"""Tracks file paths and their validation results across a program validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import msgspec

from define.compiler import constants

if TYPE_CHECKING:
    from define.compiler import config
    from define.compiler.data_structures import define_path


@final
class _ProjectRootNode(msgspec.Struct, eq=False):
    children: dict[str, _ProjectRootNode] | None = None
    failed: bool = False
    project_root: tuple[define_path.DefinePath, config.ProjectRootConfig] | None = None
    # The sub-root that a loaded project's local dependency declares at this
    # path, which may not be loaded yet.
    declared_sub_root: (
        tuple[define_path.DefinePath, config.LocalDependencyEntry] | None
    ) = None

    def get_child(self, part: str) -> _ProjectRootNode | None:
        if self.children is None:
            return None
        return self.children.get(part)

    def get_or_create_child(self, part: str) -> _ProjectRootNode:
        if self.children is None:
            self.children = {}
        child = self.children.get(part)
        if child is None:
            child = _ProjectRootNode()
            self.children[part] = child
        return child


class PathTracker[T]:
    """Tracks file paths encountered during validation and their results.

    Manages four concerns:
    - Mapping from file paths to validation results (with an in-progress sentinel).
    - Tracking paths that were referenced but could not be loaded.
    - Mapping project root paths to their resolved config for prefix-based lookups.
    - Recording the sub-root paths that loaded projects' local dependencies
      declare.

    Type parameter T is the result type stored per path (e.g. LoadedFile).
    """

    def __init__(self):
        """Initialize empty path tracking state."""
        self._results: dict[define_path.DefinePath, T | None] = {}
        self._not_found: set[define_path.DefinePath] = set()
        self._project_roots: _ProjectRootNode = _ProjectRootNode()
        self._fqun_to_root: dict[str, define_path.DefinePath] = {}

    def _get_project_root_node(
        self, path: define_path.DefinePath
    ) -> _ProjectRootNode | None:
        node = self._project_roots
        for part in path.parts:
            node = node.get_child(part)
            if node is None:
                return None
        return node

    def _get_or_create_project_root_node(
        self, path: define_path.DefinePath
    ) -> _ProjectRootNode:
        node = self._project_roots
        for part in path.parts:
            node = node.get_or_create_child(part)
        return node

    def _project_root_for_path(
        self, path: define_path.DefinePath
    ) -> tuple[define_path.DefinePath, config.ProjectRootConfig]:
        node = self._project_roots
        project_root = node.project_root
        parts = path.parts
        del parts[-1]
        for part in parts:
            children = node.children
            if children is None:
                break
            child = children.get(part)
            if child is None:
                break
            node = child
            if node.project_root is not None:
                project_root = node.project_root
        return cast(
            "tuple[define_path.DefinePath, config.ProjectRootConfig]", project_root
        )

    def is_tracked(self, path: define_path.DefinePath) -> bool:
        """Return True if this path has been started or completed."""
        return path in self._results

    def mark_in_progress(self, path: define_path.DefinePath):
        """Record that validation of this path has begun."""
        self._results[path] = None

    def set_result(self, path: define_path.DefinePath, result: T):
        """Store the completed result for a path."""
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
        self._get_or_create_project_root_node(root).failed = True

    def is_failed_root(self, root: define_path.DefinePath) -> bool:
        """Return True if this exact project root has a known-bad config."""
        node = self._get_project_root_node(root)
        return node is not None and node.failed

    def is_under_failed_root(self, path: define_path.DefinePath) -> bool:
        """Return True if path is under a root with a known-bad config."""
        node = self._project_roots
        parts = path.parts
        del parts[-1]
        for part in parts:
            children = node.children
            if children is None:
                return False
            child = children.get(part)
            if child is None:
                return False
            node = child
            if node.failed:
                return True
        return False

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
        node = self._get_or_create_project_root_node(root)
        if node.project_root is not None:
            raise ValueError(f"sub_root already registered: {root}")
        node.project_root = (root, root_config)
        self._fqun_to_root[root_config.fqun] = root

    def declare_sub_root(
        self,
        sub_root_path: define_path.DefinePath,
        entry: config.LocalDependencyEntry,
    ) -> config.LocalDependencyEntry | None:
        """Record that a local dependency declares a sub-root at a path, unless one already does.

        The first declaration of a path wins. Returns the entry that already
        declares the path, if one does.
        """
        node = self._get_or_create_project_root_node(sub_root_path)
        if node.declared_sub_root is not None:
            return node.declared_sub_root[1]
        node.declared_sub_root = (sub_root_path, entry)
        return None

    def declared_sub_root_containing(
        self, root: define_path.DefinePath, path: define_path.DefinePath
    ) -> tuple[define_path.DefinePath, config.LocalDependencyEntry] | None:
        """Return the sub-root declared between a loaded project root and a path in it, if there is one.

        A path in a more deeply declared sub-root is also in this one.
        """
        # The root's config is loaded, so the root has a node.
        node = cast("_ProjectRootNode", self._get_project_root_node(root))
        parts = path.parts
        del parts[-1]
        for part in parts[len(root.parts) :]:
            child = node.get_child(part)
            if child is None:
                return None
            node = child
            if node.declared_sub_root is not None:
                return node.declared_sub_root
        return None

    def root_for_fqun(self, fqun: str) -> define_path.DefinePath | None:
        """Return the root path registered for a given FQUN, or None."""
        return self._fqun_to_root.get(fqun)

    def config_for_root(
        self, root: define_path.DefinePath
    ) -> config.ProjectRootConfig | None:
        """Return the resolved config registered for an exact project root path, or None."""
        node = self._get_project_root_node(root)
        if node is None or node.project_root is None:
            return None
        return node.project_root[1]

    def universe_root(
        self, fqun: str | None, referencing_root: define_path.DefinePath
    ) -> define_path.DefinePath | None:
        """Return the root of a referenced universe, if the referencing root can reach it.

        fqun is None for a short-form reference, which is in the referencing
        root's own universe.
        """
        if fqun is None:
            return referencing_root
        # Every project can reference the standard universe without
        # configuring it. Only this universe has an absolute root.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if fqun == constants.STANDARD_UNIVERSE:
            return constants.STANDARD_LIBRARY_ROOT
        if not self.has_sub_root(fqun, referencing_root):
            return None
        return referencing_root / self.sub_root_location(fqun, referencing_root)

    def has_sub_root(self, fqun: str, parent_root: define_path.DefinePath) -> bool:
        """Return True if fqun is a configured sub_root of parent_root."""
        root_config = self.config_for_root(parent_root)
        if root_config is None:
            raise KeyError(parent_root)
        return fqun in root_config.sub_roots

    def sub_root_location(
        self, fqun: str, parent_root: define_path.DefinePath
    ) -> define_path.DefinePath:
        """Return the configured path for fqun relative to parent_root.

        Raises:
            KeyError: If parent_root is not registered or fqun is not a
                configured sub_root under it.
        """
        info = self.config_for_root(parent_root)
        if info is None:
            raise KeyError(parent_root)
        return info.sub_roots[fqun]

    def find_enclosing_root(
        self, path: define_path.DefinePath
    ) -> define_path.DefinePath:
        """Find the innermost project root containing this path.

        At least one project root must be registered.
        """
        return self._project_root_for_path(path)[0]
