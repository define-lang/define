"""Project configuration loading and validation."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import constants
from define.compiler.config import (
    encoding_operations_config,
    encodings_config,
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


def universe_needs_configuration(fqun: str) -> bool:
    """Whether a project must configure a universe as a sub-root before referencing it."""
    # TODO: Remove this once the Define Standard Library exists.
    return fqun != constants.STANDARD_UNIVERSE


class Config(msgspec.Struct):
    """Resolved project configuration for a project root."""

    fqun: str
    # The location of the universe_name value in project.defcl, for
    # diagnostics about the universe that are found after the config is loaded.
    fqun_location: rendering.SourceLocation
    # The local dependency entry for each universe that the project configures
    # as a sub-root.
    sub_roots: Mapping[str, local_deps_config.LocalDependencyEntry]
    # The global names of the encodings associated with each of the project's
    # value qualities, located inside encodings.defcl, keyed by the value
    # quality's short global name.
    value_encodings: Mapping[str, list[ast.ReferenceGlobalNameContent]]
    # The global names of the Encoding Operations associated with each of the
    # project's logical operations, located inside encoding_operations.defcl,
    # keyed by the logical operation's short global name.
    logical_operation_encoding_operations: Mapping[
        str, list[ast.ReferenceGlobalNameContent]
    ]


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
        if declaring_entry is not None and project.fqun != declaring_entry.universe:
            fqun_matches = False
            config_diagnostics.append(
                diagnostics.SubRootFqunMismatchDiagnostic(
                    location=project.fqun_location,
                    expected_fqun=declaring_entry.universe,
                    actual_fqun=project.fqun,
                    sub_root_path=str(self._root),
                )
            )
        value_encodings = self._load_encodings(project, config_diagnostics)
        encoding_operations = self._load_encoding_operations(
            project, config_diagnostics
        )
        if (
            not fqun_matches
            or sub_roots is None
            or value_encodings is None
            or encoding_operations is None
        ):
            return ConfigLoadResult(config=None, diagnostics=config_diagnostics)
        return ConfigLoadResult(
            config=Config(
                fqun=project.fqun,
                fqun_location=project.fqun_location,
                sub_roots=sub_roots,
                value_encodings=value_encodings,
                logical_operation_encoding_operations=encoding_operations,
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

    def _load_encodings(
        self,
        project: project_config.ProjectConfig,
        config_diagnostics: list[diagnostics.FormattableDiagnostic],
    ) -> Mapping[str, list[ast.ReferenceGlobalNameContent]] | None:
        """Load the project's Value Encoding Associations, adding their diagnostics to config_diagnostics."""
        value_encodings, encodings_diagnostics = encodings_config.EncodingsConfigReader(
            self._root, self._source_map
        ).load(project)
        config_diagnostics.extend(encodings_diagnostics)
        return value_encodings

    def _load_encoding_operations(
        self,
        project: project_config.ProjectConfig,
        config_diagnostics: list[diagnostics.FormattableDiagnostic],
    ) -> Mapping[str, list[ast.ReferenceGlobalNameContent]] | None:
        """Load the project's Encoding Operation associations with its logical operations, adding their diagnostics to config_diagnostics."""
        encoding_operations, encoding_operations_diagnostics = (
            encoding_operations_config.EncodingOperationsConfigReader(
                self._root, self._source_map
            ).load(project)
        )
        config_diagnostics.extend(encoding_operations_diagnostics)
        return encoding_operations
