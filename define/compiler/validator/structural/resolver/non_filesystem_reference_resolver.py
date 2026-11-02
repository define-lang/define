"""Resolution of the references in a program from supplied source text.

The supplied source is not a file in a project, so it loads its project's
config only when one of its references needs it.
"""

from __future__ import annotations

import typing

from define.compiler import config, constants
from define.compiler.errors import diagnostics
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import (
        file_validation_context,
        file_validator,
    )


@typing.final
class NonFilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program from supplied source lead to.

    References can also reach the definitions of the supplied source, which no
    file holds.
    """

    _source_file: file_validator.LoadedFile
    # The universes that the supplied source references but its project config
    # does not configure, each reported once.
    _unknown_universes: set[str]

    def __init__(self, source_file: file_validator.LoadedFile):
        """Initialize with the supplied source as the program's only loaded file."""
        super().__init__()
        self._source_file = source_file
        self._unknown_universes = set()

    @typing.override
    def completed_files(self) -> list[file_validator.LoadedFile]:
        return [self._source_file, *super().completed_files()]

    @typing.override
    def validate_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> (
        reference_resolver.ReachedDefinition
        | file_validation_context.FileValidationContext
        | None
    ):
        if loaded_file is self._source_file:
            if not self._source_reference_resolvable(edge):
                return None
        # A definition from the supplied source has no file path to resolve,
        # and was validated before any other definition.
        elif edge.global_name_reference in self._source_file.definitions:
            return None
        return super().validate_reference(loaded_file, edge, source_definition)

    def _source_reference_resolvable(self, edge: reference_graph.ReferenceEdge) -> bool:
        """Whether a reference from the supplied source can resolve, loading the project config the first time one needs it.

        Reports why a reference cannot resolve the first time that happens.
        """
        if not config.universe_needs_configuration(
            edge.global_name_reference.effective_fqun.canonical
        ):
            return True
        root_config = self._project_root_config(edge)
        if root_config is None:
            return False
        global_name = edge.global_name_reference.name_content
        fqun = global_name.source_fqun
        if fqun is None or fqun in root_config.sub_roots:
            return True
        # In a filesystem context, file validation reports an unknown universe
        # once per file and records no edge for it. The supplied source is one
        # file, so report each unknown universe once here.
        if fqun not in self._unknown_universes:
            self._unknown_universes.add(fqun)
            self._source_file.file_diagnostics.append(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    location=global_name.location,
                    universe=fqun,
                    current_universe_name=root_config.fqun,
                )
            )
        return False

    def _project_root_config(
        self, edge: reference_graph.ReferenceEdge
    ) -> config.ProjectRootConfig | None:
        """Return the project config, loading it for the first reference that needs it.

        If it fails to load, reports why at that reference and returns None,
        then and for every later reference.
        """
        existing = self._path_tracker.config_for_root(constants.PROJECT_ROOT)
        if existing is not None:
            return existing
        if self._path_tracker.is_failed_root(constants.PROJECT_ROOT):
            return None
        global_name = edge.global_name_reference.name_content
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except config.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            self._source_file.file_diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=global_name.location,
                    universe=edge.global_name_reference.effective_fqun.canonical,
                    config_path=str(e.config_path),
                )
            )
            return None
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            self._source_file.file_diagnostics.append(
                diagnostics.ConfigLoadErrorDiagnostic(
                    location=global_name.location,
                    error=e,
                )
            )
            return None
