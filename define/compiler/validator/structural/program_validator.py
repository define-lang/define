"""Parallel coordinator for multi-file Define program validation.

ProgramStructuralValidator orchestrates per-file validation using a thread pool.
It manages all shared state on the main thread and delegates pure
per-file validation to FileStructuralValidator workers. It registers the
definitions that files hold and the references between them, while its
ReferenceResolver finds and validates the files that references lead to.
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import pathlib

    from define.compiler.data_structures import define_path

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics, source_map
from define.compiler.graphs import reference_graph, reference_graph_order
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    file_validator,
    reference_resolver,
    work_pool,
)


class ProgramStructuralValidator:
    """Coordinates parallel validation of a Define program.

    Registers the definitions of validated files and the references between
    them, as files complete on a thread pool. All shared state is managed on
    the coordinator thread.
    """

    _resolver: reference_resolver.ReferenceResolver
    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _allow_entry_action_interface_positions: bool

    def __init__(
        self,
        *,
        allow_entry_action_interface_positions: bool = False,
    ):
        """Initialize coordinator state for one program validation.

        allow_entry_action_interface_positions exists only for validation tests
        that specifically require an entry action with interface positions. It
        must remain false when validating a program for code generation.
        """
        self._definition_results = typed_name_dict.TypedNameDict()
        self._resolver = reference_resolver.ReferenceResolver(
            handle_validated_file=self._process_completed_result,
            registered_definitions=self._definition_results,
        )
        self._reference_graph = reference_graph.ReferenceGraph()
        self._allow_entry_action_interface_positions = (
            allow_entry_action_interface_positions
        )

    def validate_program(
        self,
        path: pathlib.PurePosixPath,
        max_workers: int | None = None,
    ) -> validation_result.ProgramValidationResult:
        """Validate a program starting from the given file path."""
        entry_context = self._resolver.entry_file_context(path)
        if entry_context is not None:
            with work_pool.WorkPool(max_workers=max_workers) as pool:
                self._resolver.submit_entry_file(entry_context, pool)
                pool.run_until_idle()

        return self._build_program_result(
            self._resolver.completed_file_results(), in_memory_source=None
        )

    def validate_program_non_filesystem(
        self,
        source: str,
        max_workers: int | None = None,
    ) -> validation_result.ProgramValidationResult:
        """Validate a program from source text, loading config only when needed."""
        result = file_validator.FileStructuralValidator().validate_source(source)
        if result.exception is not None:
            return self._build_program_result([result], in_memory_source=source)

        self._resolver.add_source_result(result)

        with work_pool.WorkPool(max_workers=max_workers) as pool:
            self._resolver.resolve_non_filesystem_references(result, pool)
            self._process_completed_result(result)
            pool.run_until_idle()
        return self._build_program_result(
            self._resolver.completed_file_results(),
            in_memory_source=source,
            select_last_constructor=True,
        )

    def _build_program_result(
        self,
        file_results: list[validation_result.FileValidationResult],
        *,
        in_memory_source: str | None,
        select_last_constructor: bool = False,
    ) -> validation_result.ProgramValidationResult:
        """Validate the entry action and assemble the program result."""
        entry_action_result = self._select_entry_action(
            file_results[0], select_last_constructor=select_last_constructor
        )
        entry_action = None
        if entry_action_result is not None:
            if not self._allow_entry_action_interface_positions:
                self._validate_entry_action_interface_positions(entry_action_result)
            candidate = typing.cast(
                "ast.ActionDefinition", entry_action_result.definition
            )
            if candidate.is_constructor:
                entry_action = candidate
        definition_order = reference_graph_order.ReferenceGraphOrder(
            self._reference_graph
        )
        # Later stages need only the compact order, not cycle-detection state.
        del self._reference_graph

        # The completed order replaces these structural-only edges;
        # retaining both would duplicate per-reference state during later stages.
        for file_result in file_results:
            for definition_result in file_result.definition_results:
                definition_result.reference_edges.clear()
        file_digests: dict[pathlib.PurePosixPath, bytes] = {}
        for file_result in file_results:
            if file_result.source_digest is not None:
                file_digests[file_result.file_path.as_posix_path()] = (
                    file_result.source_digest
                )
        return validation_result.ProgramValidationResult(
            file_results=file_results,
            entry_action=entry_action,
            definition_order=definition_order,
            definition_results=self._definition_results,
            source_map=source_map.SourceMap(file_digests, in_memory_source),
        )

    @staticmethod
    def _select_entry_action(
        entry_file_result: validation_result.FileValidationResult,
        *,
        select_last_constructor: bool = False,
    ) -> validation_result.DefinitionValidationResult | None:
        definitions = entry_file_result.definition_results
        candidates = reversed(definitions) if select_last_constructor else definitions
        for definition_result in candidates:
            definition = definition_result.definition
            if not isinstance(definition, ast.ActionDefinition):
                continue
            if select_last_constructor and not definition.is_constructor:
                continue
            return definition_result
        return None

    @staticmethod
    def _validate_entry_action_interface_positions(
        entry_action_result: validation_result.DefinitionValidationResult,
    ):
        definition = typing.cast("ast.ActionDefinition", entry_action_result.definition)
        for position in definition.interface_positions:
            entry_action_result.diagnostics.append(
                diagnostics.EntryPointInterfacePositionDiagnostic(
                    location=position.typed_name.location,
                    position_name=position.typed_name.source_typed_name,
                )
            )

    def _process_completed_result(
        self,
        result: validation_result.FileValidationResult,
    ):
        """Handle a completed file: register its definitions and follow their edges."""
        for definition_result in result.definition_results:
            self._process_completed_definition(result, definition_result)

    def _process_completed_definition(
        self,
        result: validation_result.FileValidationResult,
        definition_result: validation_result.DefinitionValidationResult,
    ):
        """Handle one completed definition from a file result."""
        typed_name = definition_result.definition.typed_name
        # FileStructuralValidator preserves duplicate definitions in source order so
        # the later ones can still return diagnostics. Originally, I tried
        # to make all the later checks still run on duplicates, but it gets
        # into too much complexity. We do still submit referenced files from
        # duplicates, above, but that's it.
        if typed_name in self._definition_results:
            return
        self._definition_results[typed_name] = definition_result
        self._reference_graph.add_definition(definition_result.definition)
        self._validate_outgoing_reference_edges(result.root_prefix, definition_result)

    def _validate_outgoing_reference_edges(
        self,
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Try to add edges to the reference graph, validate targets we already know about, and enqueue those we don't."""
        for ref_edge in source_definition.reference_edges:
            # A definition from the supplied source has no file path to resolve.
            if self._references_non_filesystem_definition(ref_edge):
                _ = self._add_reference_edge(ref_edge, source_definition)
                continue
            target_file = self._resolver.resolve_target_file(
                ref_edge.global_name_reference.name_content,
                enclosing_root,
                source_definition,
            )
            if target_file is None:
                continue

            if not self._add_reference_edge(ref_edge, source_definition):
                continue
            self._resolver.find_referenced_definition(
                ref_edge, target_file, enclosing_root, source_definition
            )

    def _add_reference_edge(
        self,
        ref_edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        detected_cycle = self._reference_graph.try_add_edge(ref_edge)
        if detected_cycle is None:
            return True
        source_definition.diagnostics.append(
            diagnostics.CircularGlobalReferenceDiagnostic(
                location=ref_edge.global_name_reference.location,
                cycle=detected_cycle,
            )
        )
        return False

    def _references_non_filesystem_definition(
        self,
        edge: reference_graph.ReferenceEdge,
    ) -> bool:
        referenced_definition = self._definition_results.get(edge.global_name_reference)
        return (
            referenced_definition is not None
            and referenced_definition.definition.location.file_path is None
        )
