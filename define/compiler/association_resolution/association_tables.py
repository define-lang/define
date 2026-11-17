"""Each project's associations, which association resolution loads from the project's config files the first time it reads them."""

from __future__ import annotations

import threading
import types
import typing

from define.compiler.config import association_config

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from crates.source_rendering.python import rendering
    from define.compiler.config import config_loader
    from define.compiler.data_structures import define_path
    from define.compiler.errors import diagnostics

_NO_ASSOCIATIONS = association_config.AssociationTable(
    value_encodings=types.MappingProxyType({}),
    encoding_operations=types.MappingProxyType({}),
)


@typing.final
class _ProjectAssociations:
    """A project root's associations, loaded the first time they are read."""

    def __init__(self, root: define_path.DefinePath, config: config_loader.Config):
        """Initialize with the project root and its config, and nothing loaded."""
        self._root = root
        self._config = config
        self._lock = threading.Lock()
        # None until loaded.
        self._table: association_config.AssociationTable | None = None

    def table(
        self,
        source_map: rendering.SourceMap,
        config_diagnostics: list[diagnostics.FormattableDiagnostic],
    ) -> association_config.AssociationTable:
        """Return the project's associations, loading them and adding their diagnostics to config_diagnostics if this is the first read."""
        # Once loaded, the table never changes, so reading it needs no lock.
        table = self._table
        if table is not None:
            return table
        with self._lock:
            if self._table is None:
                self._table, table_diagnostics = (
                    association_config.load_association_table(
                        self._root, source_map, self._config
                    )
                )
                config_diagnostics.extend(table_diagnostics)
            return self._table


@typing.final
class AssociationTables:
    """Each project's associations, by the project's universe.

    Resolution reads them concurrently, so each project's are loaded under
    their own lock, and only if resolution reads them.
    """

    def __init__(
        self,
        project_roots: Mapping[
            str, tuple[define_path.DefinePath, config_loader.Config]
        ],
        source_map: rendering.SourceMap,
    ):
        """Initialize with the path and config of each project root, by its universe, the source map to register the config files with, and nothing loaded."""
        self._source_map = source_map
        self._projects: dict[str, _ProjectAssociations] = {}
        for universe, (root, config) in project_roots.items():
            self._projects[universe] = _ProjectAssociations(root, config)
        self._config_diagnostics: list[diagnostics.FormattableDiagnostic] = []

    def table(self, universe: str) -> association_config.AssociationTable:
        """Return the associations of the project whose universe is universe."""
        project = self._projects.get(universe)
        # Source compiled without a project root has no associations.
        # TODO: Decide whether source compiled in a non-filesystem context,
        # such as a REPL, uses the associations of the project root it is
        # compiled in. Today it does only when one of its references happened
        # to load the project config.
        if project is None:
            return _NO_ASSOCIATIONS
        return project.table(self._source_map, self._config_diagnostics)

    def config_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return the diagnostics in the config files of the associations that were read, once resolution is done."""
        return self._config_diagnostics
