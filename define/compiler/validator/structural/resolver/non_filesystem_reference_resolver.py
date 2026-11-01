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
    from collections.abc import Iterator

    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import file_validator


@typing.final
class NonFilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program from supplied source lead to.

    References can also reach the definitions of the supplied source, which no
    file holds.
    """

    _source_file: file_validator.LoadedFile

    def __init__(self, source_file: file_validator.LoadedFile):
        """Initialize with the supplied source as the program's only loaded file."""
        super().__init__()
        self._source_file = source_file

    @typing.override
    def completed_files(self) -> list[file_validator.LoadedFile]:
        return [self._source_file, *super().completed_files()]

    def files_referenced_by_source(
        self,
        source_definition_results: list[validation_result.DefinitionValidationResult],
    ) -> list[file_validator.FileValidationContext]:
        """Load the project config if the supplied source's references need it, and return the files they lead to."""
        contexts: list[file_validator.FileValidationContext] = []
        first_edge: reference_graph.ReferenceEdge | None = None
        for edge in _edges_leaving_source_definitions(source_definition_results):
            if _needs_configuration(edge):
                if first_edge is None:
                    first_edge = edge
            else:
                self._add_file_to_load(edge, contexts)
        if first_edge is None:
            return contexts

        root_config = self._load_project_root_config(first_edge)
        if root_config is None:
            _strip_cross_universe_refs(source_definition_results)
            return contexts
        self._add_files_in_configured_universes(
            source_definition_results, root_config, contexts
        )
        return contexts

    @typing.override
    def follow_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> reference_resolver.ReachedDefinition | None:
        if self._references_supplied_source(loaded_file, edge, source_definition):
            return None
        return super().follow_reference(loaded_file, edge, source_definition)

    @typing.override
    def _file_to_load(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        definition_result: validation_result.DefinitionValidationResult,
    ) -> file_validator.FileValidationContext | None:
        if self._references_supplied_source(loaded_file, edge, definition_result):
            return None
        return super()._file_to_load(loaded_file, edge, definition_result)

    def _references_supplied_source(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        referencing_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        """Whether an edge names a definition in the supplied source."""
        # A definition from the supplied source has no file path to resolve,
        # and was validated before any other definition.
        if loaded_file is self._source_file:
            return (
                self._source_file.earlier_definition(
                    edge.global_name_reference, referencing_definition.definition
                )
                is not None
            )
        return edge.global_name_reference in self._source_file.definitions

    def _add_files_in_configured_universes(
        self,
        source_definition_results: list[validation_result.DefinitionValidationResult],
        root_config: config.ProjectRootConfig,
        contexts: list[file_validator.FileValidationContext],
    ):
        """Add the files that references to configured universes lead to, after the project config loads."""
        unknown_fquns: set[str] = set()
        for edge in _edges_leaving_source_definitions(source_definition_results):
            # Files in universes that need no configuration were already added.
            if not _needs_configuration(edge):
                continue
            global_name = edge.global_name_reference.name_content
            fqun = global_name.source_fqun
            if fqun is not None and fqun not in root_config.sub_roots:
                if fqun in unknown_fquns:
                    continue
                unknown_fquns.add(fqun)
                self._source_file.file_diagnostics.append(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        location=global_name.location,
                        universe=fqun,
                        current_universe_name=root_config.fqun,
                    )
                )
                continue
            self._add_file_to_load(edge, contexts)

        # In a filesystem context, we don't return reference edges for
        # unknown sub-roots, so we are keeping that behavior consistent
        # in a non-filesystem context.
        for definition_result in source_definition_results:
            definition_result.reference_edges = [
                ref_edge
                for ref_edge in definition_result.reference_edges
                if ref_edge.global_name_reference.name_content.source_fqun
                not in unknown_fquns
            ]

    def _add_file_to_load(
        self,
        edge: reference_graph.ReferenceEdge,
        contexts: list[file_validator.FileValidationContext],
    ):
        context = self._referenced_file_to_load(self._source_file, edge)
        if context is not None:
            contexts.append(context)

    def _load_project_root_config(
        self, first_edge: reference_graph.ReferenceEdge
    ) -> config.ProjectRootConfig | None:
        """Load the project config, and map loading errors to non-filesystem diagnostics."""
        global_name = first_edge.global_name_reference.name_content
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except config.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            self._source_file.file_diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=global_name.location,
                    universe=first_edge.global_name_reference.effective_fqun.canonical,
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


def _needs_configuration(edge: reference_graph.ReferenceEdge) -> bool:
    """Whether a project must configure the referenced universe before resolving the reference."""
    return config.universe_needs_configuration(
        edge.global_name_reference.effective_fqun.canonical
    )


def _strip_cross_universe_refs(
    source_definition_results: list[validation_result.DefinitionValidationResult],
):
    """Strip cross-universe edges after total config failure.

    When root config loading fails entirely, every cross-universe FQUN is
    unresolvable. Same-universe edges are kept so that same-file validation
    (e.g. cycle detection) still runs, and so are edges to universes that
    need no configuration.
    """
    for definition_result in source_definition_results:
        definition_result.reference_edges = [
            ref_edge
            for ref_edge in definition_result.reference_edges
            if ref_edge.global_name_reference.name_content.fqun is None
            or not _needs_configuration(ref_edge)
        ]


def _edges_leaving_source_definitions(
    source_definition_results: list[validation_result.DefinitionValidationResult],
) -> Iterator[reference_graph.ReferenceEdge]:
    """Yield the edges of the supplied source's definitions that may lead to a file.

    Skips references to the referencing definition itself and to earlier
    definitions in the supplied source, which have no file to load.
    """
    seen_targets: set[str] = set()
    for definition_result in source_definition_results:
        seen_targets.add(definition_result.definition.typed_name.full_typed_name)
        for edge in definition_result.reference_edges:
            if edge.target_full_typed_name not in seen_targets:
                yield edge
