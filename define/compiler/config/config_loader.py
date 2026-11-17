"""Project configuration loading and validation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.config import (
    local_deps_config,
    project_config,
)
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import PurePosixPath

    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.data_structures import define_path


class Config(msgspec.Struct):
    """Resolved project configuration for a project root."""

    # The project's universe, located at the universe_name value in its project
    # config, for diagnostics about the universe that are found after the
    # config is loaded.
    fqun: ast.Fqun
    # The local dependency entry for each universe that the project configures
    # as a sub-root.
    sub_roots: Mapping[str, local_deps_config.LocalDependencyEntry]
    # Where the project config says that the project has Value Encoding
    # Associations, or None if it does not say so.
    has_encodings_location: rendering.SourceLocation | None
    # Where the project config says that the project has Encoding Operation
    # associations, or None if it does not say so.
    has_encoding_operations_location: rendering.SourceLocation | None


class ConfigLoadResult(msgspec.Struct, frozen=True):
    """A project root's resolved configuration, if it can be resolved, and the diagnostics in its config files."""

    # None when a diagnostic leaves the configuration's meaning unclear.
    # Otherwise the configuration is used even if it has diagnostics, so that
    # the compiler can go on to find other errors in the program. The compile
    # still fails, since the diagnostics are reported.
    config: Config | None
    diagnostics: list[diagnostics.FormattableDiagnostic]


class ConfigLoader:
    """Loads and validates a project root's configuration files."""

    _root: define_path.DefinePath
    _source_map: rendering.SourceMap
    _project_config: project_config.ProjectConfigReader

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root path and the source map to register config files with."""
        self._root = root
        self._source_map = source_map
        self._project_config = project_config.ProjectConfigReader(root, source_map)

    def config_path(self) -> PurePosixPath:
        """Return the path of the root's project config file."""
        return self._project_config.path()

    def is_project_root(self) -> bool:
        """Whether the root has a project config file."""
        return self._project_config.exists()

    def load_project_root_config(
        self, declaring_entry: local_deps_config.LocalDependencyEntry | None = None
    ) -> ConfigLoadResult:
        """Load and resolve this root's own configuration.

        declaring_entry is the local dependency entry that declares this root
        as a sub-root, or None for the project root. The universe name that a
        sub-root's own config declares must be the entry's.
        """
        config_path = self.config_path()
        if not self.is_project_root():
            if declaring_entry is None:
                return ConfigLoadResult(
                    config=None,
                    diagnostics=[
                        diagnostics.NotRunFromProjectRootDiagnostic(
                            config_path=str(config_path)
                        )
                    ],
                )
            return ConfigLoadResult(
                config=None,
                diagnostics=[
                    diagnostics.SubRootNotProjectRootDiagnostic(
                        location=declaring_entry.path_location,
                        sub_root_path=str(self._root),
                        sub_root_config_path=str(config_path),
                    )
                ],
            )
        # Every config file is loaded even when another has diagnostics that
        # keep the configuration from being used, so that all of their
        # diagnostics are reported at once.
        config_diagnostics: list[diagnostics.FormattableDiagnostic] = []
        project = self._load_project(config_diagnostics)
        sub_roots = self._load_sub_roots(config_diagnostics)
        if project is None:
            return ConfigLoadResult(config=None, diagnostics=config_diagnostics)
        fqun_matches = True
        if (
            declaring_entry is not None
            and project.fqun.canonical != declaring_entry.universe
        ):
            fqun_matches = False
            config_diagnostics.append(
                diagnostics.SubRootFqunMismatchDiagnostic(
                    location=project.fqun.location,
                    expected_fqun=declaring_entry.universe,
                    actual_fqun=project.fqun.canonical,
                    sub_root_path=str(self._root),
                )
            )
        if not fqun_matches or sub_roots is None:
            return ConfigLoadResult(config=None, diagnostics=config_diagnostics)
        return ConfigLoadResult(
            config=Config(
                fqun=project.fqun,
                sub_roots=sub_roots,
                has_encodings_location=project.has_encodings_location,
                has_encoding_operations_location=project.has_encoding_operations_location,
            ),
            diagnostics=config_diagnostics,
        )

    def _load_project(
        self, config_diagnostics: list[diagnostics.FormattableDiagnostic]
    ) -> project_config.ProjectConfig | None:
        """Load the project config, adding its diagnostics to config_diagnostics."""
        project, project_diagnostics = self._project_config.load()
        config_diagnostics.extend(project_diagnostics)
        return project

    def _load_sub_roots(
        self, config_diagnostics: list[diagnostics.FormattableDiagnostic]
    ) -> Mapping[str, local_deps_config.LocalDependencyEntry] | None:
        """Load the sub-roots that the project declares, adding their diagnostics to config_diagnostics."""
        sub_roots, deps_diagnostics = local_deps_config.LocalDepsConfigReader(
            self._root, self._source_map
        ).load()
        config_diagnostics.extend(deps_diagnostics)
        return sub_roots
