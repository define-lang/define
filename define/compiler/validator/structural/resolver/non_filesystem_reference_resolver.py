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
    from crates.source_rendering.python import rendering
    from define.compiler import ast
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
    # The universes that the supplied source defines anything in.
    _source_universes: set[str]

    def __init__(
        self, source_file: file_validator.LoadedFile, source_map: rendering.SourceMap
    ):
        """Initialize with the supplied source as the program's only loaded file, and the source map to register config files with."""
        super().__init__(source_map)
        self._source_file = source_file
        self._unknown_universes = set()
        self._source_universes = {
            definition.typed_name.name_content.fqun.canonical
            for definition in source_file.definitions.values()
        }

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
        else:
            # A definition from the supplied source has no file path to
            # resolve.
            source_definition_reached = self._source_file.definitions.get(
                edge.global_name_reference
            )
            if source_definition_reached is not None:
                return reference_resolver.ReachedDefinition(
                    self._source_file, source_definition_reached
                )
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
        fqun = edge.global_name_reference.name_content.fqun
        if fqun is None or fqun.canonical in root_config.sub_roots:
            return True
        # In a filesystem context, file validation reports an unknown universe
        # once per file and records no edge for it. The supplied source is one
        # file, so report each unknown universe once here.
        if fqun.canonical not in self._unknown_universes:
            self._unknown_universes.add(fqun.canonical)
            self._source_file.file_diagnostics.append(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    location=fqun.location,
                    universe=fqun.canonical,
                    current_universe_name=root_config.fqun,
                )
            )
        return False

    def _project_root_config(
        self, edge: reference_graph.ReferenceEdge
    ) -> config.ProjectRootConfig | None:
        """Return the project config, loading it for the first reference that needs it.

        If there is no project config, reports that at that reference. If it
        fails to load, records the config's diagnostics. Either way, returns
        None then and for every later reference.
        """
        existing = self._path_tracker.config_for_root(constants.PROJECT_ROOT)
        if existing is not None:
            return existing
        if self._path_tracker.is_failed_root(constants.PROJECT_ROOT):
            return None
        reference = edge.global_name_reference
        names_source_universe = (
            reference.effective_fqun.canonical in self._source_universes
        )
        if names_source_universe:
            location = reference.location
        else:
            # A short-form reference names the universe of the definition it
            # is in, which the supplied source defines, so a reference to any
            # other universe writes its FQUN.
            location = typing.cast("ast.Fqun", reference.name_content.fqun).location
        config_loader = config.ConfigLoader(constants.PROJECT_ROOT, self._source_map)
        if config_loader.is_project_root():
            return self._load_root_config(constants.PROJECT_ROOT)
        self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
        config_path = str(config_loader.config_path())
        if names_source_universe:
            self._source_file.file_diagnostics.append(
                diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
                    location=location,
                    definition_name=reference.source_typed_name,
                    config_path=config_path,
                )
            )
        else:
            self._source_file.file_diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=location,
                    universe=reference.effective_fqun.canonical,
                    config_path=config_path,
                )
            )
        return None
