"""The project roots of a program, which the compiler loads as it needs them."""

from __future__ import annotations

import threading
import types
import typing

import msgspec

from define.compiler import constants
from define.compiler.config import (
    association_config,
    config_loader,
    encoding_operations_config,
)
from define.compiler.data_structures import define_path
from define.compiler.errors import config_diagnostics

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.config import local_deps_config
    from define.compiler.errors import diagnostics


_NO_ASSOCIATIONS = association_config.AssociationTable(
    value_encodings=types.MappingProxyType({}),
    encoding_operations=encoding_operations_config.NO_ASSOCIATIONS,
)
# The associations of a universe whose project config failed to load, which
# is already reported.
_UNUSABLE_ASSOCIATIONS = association_config.AssociationTable(
    value_encodings=None, encoding_operations=None
)


@typing.final
class NoProjectConfig(msgspec.Struct, frozen=True):
    """The result of looking up the project root's config when the working directory has no project config file."""


@typing.final
class _SubRootTreeNode(msgspec.Struct, eq=False):
    """A directory on the path to a sub-root that a loaded project's config lists."""

    children: dict[str, _SubRootTreeNode] | None = None
    # The local dependency entry of a loaded project whose path is this
    # directory, which makes this directory a sub-root. The sub-root's config
    # may not be loaded yet.
    dependency_entry: local_deps_config.LocalDependencyEntry | None = None

    def get_child(self, part: str) -> _SubRootTreeNode | None:
        if self.children is None:
            return None
        return self.children.get(part)

    def get_or_create_child(self, part: str) -> _SubRootTreeNode:
        if self.children is None:
            self.children = {}
        child = self.children.get(part)
        if child is None:
            child = _SubRootTreeNode()
            self.children[part] = child
        return child


@typing.final
class ProjectRoots:
    """The program's project roots, with their configs, the sub-roots that their configs list, and their associations.

    Loads each project config and each project's associations once, and
    records the diagnostics that loading finds. It is thread-safe.
    """

    def __init__(self, source_map: rendering.SourceMap):
        """Initialize with the source map to register config files with, and no project roots."""
        self._source_map = source_map
        # Held while loading a config or a project's associations, so that
        # each is loaded once. Loading the associations of a universe can load
        # the project root's config, so the lock is reentrant.
        self._lock = threading.RLock()
        self._configs: dict[define_path.DefinePath, config_loader.Config] = {}
        self._by_universe: dict[
            str, tuple[define_path.DefinePath, config_loader.Config]
        ] = {}
        # The associations of each universe whose associations were read, or
        # that the working directory has no project config to have them.
        self._association_tables: dict[
            str, association_config.AssociationTable | NoProjectConfig
        ] = {}
        # The project roots whose config cannot be used.
        self._failed: set[define_path.DefinePath] = set()
        # A tree of directories, because a reference has to find whether any
        # directory between its target root and its target file is a sub-root.
        self._sub_root_tree = _SubRootTreeNode()
        # The project roots and universes whose local dependency lists a
        # sub-root path that another local dependency already listed, so the
        # project cannot use that universe.
        self._disabled_universes: set[tuple[define_path.DefinePath, str]] = set()
        # The diagnostics that loading project configs found. Loading only
        # adds to this list.
        self.diagnostics: list[diagnostics.FormattableDiagnostic] = []

    def load_entry_file_project_config(self) -> config_loader.Config | None:
        """Load the config of the project that holds the program's entry file, which is the project at the working directory.

        Returns None, after recording the config's diagnostics, if the config
        file is missing or cannot be used.
        """
        with self._lock:
            return self._load(constants.PROJECT_ROOT, None)

    def load_project_root_config(self) -> config_loader.Config | NoProjectConfig | None:
        """Return the config of the project root, which is the working directory, loading it if needed.

        Returns NoProjectConfig the first time if the working directory has no
        project config file, so that the caller reports it, and marks the root
        failed. Returns None if the root is failed.
        """
        # A loaded config is never replaced, so reading it needs no lock.
        existing = self._configs.get(constants.PROJECT_ROOT)
        if existing is not None:
            return existing
        with self._lock:
            # Another thread may have loaded the config while this one waited.
            existing = self._configs.get(constants.PROJECT_ROOT)
            if existing is not None:
                return existing
            if constants.PROJECT_ROOT in self._failed:
                return None
            loader = config_loader.ConfigLoader(
                constants.PROJECT_ROOT, self._source_map
            )
            if not loader.is_project_root():
                self._failed.add(constants.PROJECT_ROOT)
                return NoProjectConfig()
            return self._load(constants.PROJECT_ROOT, None)

    def load_sub_root_config(
        self, fqun: str | None, referencing_root: define_path.DefinePath
    ) -> tuple[define_path.DefinePath, config_loader.Config] | None:
        """Return the path and config of the project root of a universe that a loaded project references, loading the config if needed.

        fqun is None for a short-form reference, which is in the referencing
        root's own universe. Otherwise, fqun must be the standard universe or a
        universe that the referencing project configures as a local dependency.

        Returns None if the referencing project cannot use the universe, or if
        the universe's config cannot be used. Either problem is already
        reported.
        """
        if fqun is None:
            return referencing_root, self._configs[referencing_root]
        if (referencing_root, fqun) in self._disabled_universes:
            return None
        # Every project can reference the standard universe without
        # configuring it. Only this universe has an absolute root.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if fqun == constants.STANDARD_UNIVERSE:
            return self._load_root(constants.STANDARD_LIBRARY_ROOT, None)
        entry = self._configs[referencing_root].sub_roots[fqun]
        return self._load_root(referencing_root / entry.path, entry)

    def get_loaded_root_config(
        self, universe: str
    ) -> tuple[define_path.DefinePath, config_loader.Config] | None:
        """Return the path and config of the project root whose universe is universe, if it is loaded."""
        return self._by_universe.get(universe)

    def get_association_table(
        self, universe: str
    ) -> association_config.AssociationTable | NoProjectConfig:
        """Return the associations of the project whose universe is universe, loading them if this is the first read.

        A universe without a loaded project root is in source compiled in a
        non-filesystem context, so its associations come from the project
        root, which is loaded if it has not been. Returns NoProjectConfig for
        every read of a universe if the first read found that the working
        directory has no project config, so that each value quality in the
        universe reports it.
        """
        # A loaded table is never replaced, so reading it needs no lock.
        table = self._association_tables.get(universe)
        if table is not None:
            return table
        with self._lock:
            # Another thread may have loaded the table while this one waited.
            table = self._association_tables.get(universe)
            if table is None:
                table = self._read_association_table(universe)
                self._association_tables[universe] = table
        return table

    def get_referenced_association_table(
        self, reference: ast.GlobalTypedNameReference
    ) -> association_config.AssociationTable | NoProjectConfig | None:
        """Return the associations of the universe that reference names, loading that universe's project root as the project that writes reference sees it.

        Returns None if the project that writes reference does not configure
        the universe, or if the universe's config cannot be used. Either
        problem is reported where reference is used.
        """
        universe = reference.effective_fqun.canonical
        referencing = self._by_universe.get(reference.enclosing_fqun.canonical)
        # Loading the named universe's project root needs the project root of
        # the reference's universe. Source compiled in a non-filesystem
        # context has no loaded project root, so a reference in that source
        # skips the load.
        if universe not in self._by_universe and referencing is not None:
            referencing_root, referencing_config = referencing
            if (
                referencing_config.check_universe_configured(reference.name_content)
                is not None
            ):
                return None
            if self.load_sub_root_config(universe, referencing_root) is None:
                return None
        return self.get_association_table(universe)

    def _read_association_table(
        self, universe: str
    ) -> association_config.AssociationTable | NoProjectConfig:
        """Load the associations of the project whose universe is universe, loading the project root's config first if no loaded root has the universe."""
        loaded_root = self._by_universe.get(universe)
        if loaded_root is None:
            root_config = self.load_project_root_config()
            if isinstance(root_config, NoProjectConfig):
                return root_config
            # Why the project root's config cannot be used is already
            # reported.
            if root_config is None:
                return _UNUSABLE_ASSOCIATIONS
            loaded_root = self._by_universe.get(universe)
            # The project root's universe is not this universe, so no project
            # configures its associations.
            if loaded_root is None:
                return _NO_ASSOCIATIONS
        root, root_config = loaded_root
        table, table_diagnostics = association_config.load_association_table(
            root, self._source_map, root_config
        )
        self.diagnostics.extend(table_diagnostics)
        return table

    def find_sub_root_between(
        self, root: define_path.DefinePath, path: define_path.DefinePath
    ) -> tuple[define_path.DefinePath, local_deps_config.LocalDependencyEntry] | None:
        """Return the first sub-root in the directories between a project root and a path in it, with the local dependency entry that lists it, if there is one.

        A path in a more deeply listed sub-root is also in this one.
        """
        root_depth = len(root.parts)
        node = self._sub_root_tree
        parts = path.parts
        del parts[-1]
        for depth, part in enumerate(parts, start=1):
            child = node.get_child(part)
            if child is None:
                return None
            node = child
            if depth > root_depth and node.dependency_entry is not None:
                sub_root_path = define_path.DefinePath("/".join(parts[:depth]))
                return sub_root_path, node.dependency_entry
        return None

    def _load_root(
        self,
        root: define_path.DefinePath,
        declaring_entry: local_deps_config.LocalDependencyEntry | None,
    ) -> tuple[define_path.DefinePath, config_loader.Config] | None:
        """Return a project root and its config, loading the config if needed, or None if the config cannot be used."""
        # A loaded config is never replaced, so reading it needs no lock.
        root_config = self._configs.get(root)
        if root_config is not None:
            return root, root_config
        with self._lock:
            # Another thread may have loaded the config while this one waited.
            root_config = self._configs.get(root)
            if root_config is None:
                if root in self._failed:
                    return None
                root_config = self._load(root, declaring_entry)
                if root_config is None:
                    return None
        return root, root_config

    def _load(
        self,
        root: define_path.DefinePath,
        declaring_entry: local_deps_config.LocalDependencyEntry | None,
    ) -> config_loader.Config | None:
        """Load the config of a project root, and record the config and the sub-roots that it lists.

        Records the config's diagnostics. The diagnostics are in the config,
        not at a reference, so they are recorded once, however many references
        lead into the root. If the config cannot be used, marks the root failed
        and returns None.
        """
        result = config_loader.ConfigLoader(
            root, self._source_map
        ).load_project_root_config(declaring_entry)
        self.diagnostics.extend(result.diagnostics)
        if result.config is None:
            self._failed.add(root)
            return None
        root_config = result.config
        existing = self._by_universe.get(root_config.fqun.canonical)
        if existing is not None:
            _, existing_config = existing
            self._failed.add(root)
            self.diagnostics.append(
                config_diagnostics.DuplicateFqunDiagnostic(
                    location=root_config.fqun.location,
                    fqun=root_config.fqun.canonical,
                    existing_location=existing_config.fqun.location,
                )
            )
            return None
        self._configs[root] = root_config
        self._by_universe[root_config.fqun.canonical] = (root, root_config)
        for entry in root_config.sub_roots.values():
            self._add_sub_root(root, root_config, entry)
        return root_config

    def _add_sub_root(
        self,
        root: define_path.DefinePath,
        root_config: config_loader.Config,
        entry: local_deps_config.LocalDependencyEntry,
    ):
        """Record the sub-root that a local dependency of a loaded project lists.

        The first local dependency that lists a path wins. A later one that
        lists the same path disables its universe for the project that lists
        it.
        """
        if entry.universe == root_config.fqun.canonical:
            self._disabled_universes.add((root, entry.universe))
            self.diagnostics.append(
                config_diagnostics.LocalDependencyOnOwnUniverseDiagnostic(
                    location=entry.universe_location,
                    universe=entry.universe,
                )
            )
            return
        sub_root_path = root / entry.path
        node = self._sub_root_tree
        for part in sub_root_path.parts:
            node = node.get_or_create_child(part)
        if node.dependency_entry is None:
            node.dependency_entry = entry
            return
        self._disabled_universes.add((root, entry.universe))
        self.diagnostics.append(
            config_diagnostics.SubRootPathAlreadyDeclaredDiagnostic(
                location=entry.path_location,
                sub_root_path=str(sub_root_path),
                first_location=node.dependency_entry.path_location,
            )
        )
