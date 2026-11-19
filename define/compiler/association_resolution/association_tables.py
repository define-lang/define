"""Each project's associations, which association resolution loads from the project's config files the first time it reads them."""

from __future__ import annotations

import types
import typing

from define.compiler.config import association_config

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler.config import config_loader, project_roots
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
        # None until loaded.
        self._table: association_config.AssociationTable | None = None

    def table(
        self,
        source_map: rendering.SourceMap,
        config_diagnostics: list[diagnostics.FormattableDiagnostic],
    ) -> association_config.AssociationTable:
        """Return the project's associations, loading them and adding their diagnostics to config_diagnostics if this is the first read."""
        if self._table is None:
            self._table, table_diagnostics = association_config.load_association_table(
                self._root, source_map, self._config
            )
            config_diagnostics.extend(table_diagnostics)
        return self._table


@typing.final
class AssociationTables:
    """Each project's associations, by the project's universe.

    A project's associations are loaded only if resolution reads them. Only
    the coordinator thread may read them.
    """

    def __init__(
        self, roots: project_roots.ProjectRoots, source_map: rendering.SourceMap
    ):
        """Initialize with the program's project roots, the source map to register the config files with, and nothing loaded."""
        self._project_roots = roots
        self._source_map = source_map
        # The associations of each universe that resolution read, which has a
        # project root.
        self._projects: dict[str, _ProjectAssociations] = {}
        self._config_diagnostics: list[diagnostics.FormattableDiagnostic] = []

    def table(self, universe: str) -> association_config.AssociationTable:
        """Return the associations of the project whose universe is universe."""
        project = self._projects.get(universe)
        if project is None:
            project_root = self._project_roots.get_loaded_root_config(universe)
            # Source compiled without a project root has no associations.
            # TODO: Decide whether source compiled in a non-filesystem context,
            # such as a REPL, uses the associations of the project root it is
            # compiled in. Today it does only when one of its references
            # happened to load the project config.
            if project_root is None:
                return _NO_ASSOCIATIONS
            project = _ProjectAssociations(*project_root)
            self._projects[universe] = project
        return project.table(self._source_map, self._config_diagnostics)

    def config_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return the diagnostics in the config files of the associations that were read, once resolution is done."""
        return self._config_diagnostics
