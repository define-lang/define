"""Parallel coordinator for multi-file Define program validation.

validate_program and validate_program_non_filesystem validate one program each,
using a thread pool. They manage all shared state on the main thread and
delegate pure per-file validation to FileStructuralValidator workers. They
validate only the entry file's definitions and the definitions they reference,
directly or indirectly. A ReferenceResolver decides which files references lead
to and which definitions they reach, and the validation loads those files and
validates those definitions.
"""

from __future__ import annotations

import functools
import typing

if typing.TYPE_CHECKING:
    import pathlib

    from define.compiler.validator.structural.resolver import reference_resolver

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.errors import diagnostics, source_map
from define.compiler.graphs import reference_graph, reference_graph_order
from define.compiler.validator import validation_result
from define.compiler.validator.structural import file_validator, work_pool
from define.compiler.validator.structural.resolver import (
    filesystem_reference_resolver,
    non_filesystem_reference_resolver,
)


def validate_program(
    path: pathlib.PurePosixPath,
    *,
    max_workers: int | None = None,
    allow_entry_action_interface_positions: bool = False,
) -> validation_result.ProgramValidationResult:
    """Validate a program starting from the given file path.

    allow_entry_action_interface_positions exists only for validation tests
    that specifically require an entry action with interface positions. It
    must remain false when validating a program for code generation.
    """
    resolver = filesystem_reference_resolver.FilesystemReferenceResolver()
    program_validation = _ProgramValidationRun(
        resolver,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
    entry_file = resolver.load_entry_file(path)
    if entry_file is not None:
        with work_pool.WorkPool(max_workers=max_workers) as pool:
            for definition in entry_file.definitions.values():
                program_validation.request_definition(entry_file, definition, pool)
            pool.run_until_idle()

    return program_validation.build_program_result(in_memory_source=None)


def validate_program_non_filesystem(
    source: str,
    *,
    max_workers: int | None = None,
    allow_entry_action_interface_positions: bool = False,
) -> validation_result.ProgramValidationResult:
    """Validate a program from source text, loading config only when needed.

    allow_entry_action_interface_positions exists only for validation tests
    that specifically require an entry action with interface positions. It
    must remain false when validating a program for code generation.
    """
    source_file = file_validator.FileStructuralValidator().load_source(source)
    resolver = non_filesystem_reference_resolver.NonFilesystemReferenceResolver(
        source_file
    )
    program_validation = _ProgramValidationRun(
        resolver,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
    if source_file.exception is not None:
        return program_validation.build_program_result(in_memory_source=source)

    # Resolving the source's references needs every one of its reference
    # edges, so its definitions are validated before any other work.
    source_definition_results = program_validation.validate_source_definitions(
        source_file
    )
    with work_pool.WorkPool(max_workers=max_workers) as pool:
        program_validation.load_files(
            resolver.files_referenced_by_source(source_definition_results), pool
        )
        for definition_result in source_definition_results:
            program_validation.register_definition(source_file, definition_result, pool)
        pool.run_until_idle()
    return program_validation.build_program_result(
        in_memory_source=source, select_last_constructor=True
    )


class _ProgramValidationRun:
    """The state of structurally validating one program.

    Loads files and validates definitions on a thread pool as references reach
    them, and registers them and the references between them. All shared state
    is managed on the coordinator thread.
    """

    _resolver: reference_resolver.ReferenceResolver
    _file_validator: file_validator.FileStructuralValidator
    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    # The full typed names of definitions submitted for validation.
    _requested_definition_names: set[str]
    _allow_entry_action_interface_positions: bool

    def __init__(
        self,
        resolver: reference_resolver.ReferenceResolver,
        *,
        allow_entry_action_interface_positions: bool,
    ):
        """Initialize with the resolver for the program's references, and nothing validated."""
        self._resolver = resolver
        self._file_validator = file_validator.FileStructuralValidator()
        self._reference_graph = reference_graph.ReferenceGraph()
        self._definition_results = typed_name_dict.TypedNameDict()
        self._requested_definition_names = set()
        self._allow_entry_action_interface_positions = (
            allow_entry_action_interface_positions
        )

    def validate_source_definitions(
        self, source_file: file_validator.LoadedFile
    ) -> list[validation_result.DefinitionValidationResult]:
        """Validate every definition of the supplied source on this thread."""
        source_definition_results: list[
            validation_result.DefinitionValidationResult
        ] = []
        for definition in source_file.definitions.values():
            self._requested_definition_names.add(definition.typed_name.full_typed_name)
            source_definition_results.append(
                source_file.validate_definition(definition)
            )
        return source_definition_results

    def build_program_result(
        self,
        *,
        in_memory_source: str | None,
        select_last_constructor: bool = False,
    ) -> validation_result.ProgramValidationResult:
        """Validate the entry action and assemble the program result."""
        file_results: list[validation_result.FileValidationResult] = []
        for loaded_file in self._resolver.completed_files():
            file_results.append(
                loaded_file.build_file_validation_result(
                    self._validated_definition_results(loaded_file)
                )
            )
        entry_action_result = _select_entry_action(
            file_results[0], select_last_constructor=select_last_constructor
        )
        entry_action = None
        if entry_action_result is not None:
            if not self._allow_entry_action_interface_positions:
                _validate_entry_action_interface_positions(entry_action_result)
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

    def _validated_definition_results(
        self, loaded_file: file_validator.LoadedFile
    ) -> list[validation_result.DefinitionValidationResult]:
        """Return the results of a file's validated definitions, in source order."""
        definition_results: list[validation_result.DefinitionValidationResult] = []
        for definition in loaded_file.definitions.values():
            definition_result = self._definition_results.get(definition.typed_name)
            # Two files can define the same typed name when a definition's path
            # does not match its file. Only the first of them to be requested
            # is validated, so the result for this typed name may be for a
            # definition in a different file.
            if (
                definition_result is not None
                and definition_result.definition is definition
            ):
                definition_results.append(definition_result)
        return definition_results

    def request_definition(
        self,
        loaded_file: file_validator.LoadedFile,
        definition: ast.GlobalDefinition,
        pool: work_pool.WorkPool,
    ):
        """Submit a definition for validation unless it was already requested."""
        definition_name = definition.typed_name.full_typed_name
        if definition_name in self._requested_definition_names:
            return
        self._requested_definition_names.add(definition_name)
        pool.submit(
            loaded_file.validate_definition,
            definition,
            handle_result=functools.partial(
                self._process_validated_definition, loaded_file
            ),
        )

    def _process_validated_definition(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        # Submitting every referenced file before following any reference gets
        # background work into the queue ASAP, and loads the sub-root configs
        # that each reference is checked against.
        self.load_files(
            self._resolver.files_to_load(loaded_file, definition_result), pool
        )
        self.register_definition(loaded_file, definition_result, pool)

    def load_files(
        self,
        contexts: list[file_validator.FileValidationContext],
        pool: work_pool.WorkPool,
    ):
        """Load files on the pool, and request the definitions that references waiting on them reach."""
        for context in contexts:
            pool.submit(
                self._file_validator.load_file,
                context,
                handle_result=self._process_loaded_file,
            )

    def _process_loaded_file(
        self, loaded_file: file_validator.LoadedFile, pool: work_pool.WorkPool
    ):
        for reached_definition in self._resolver.add_loaded_file(loaded_file):
            self.request_definition(
                reached_definition.loaded_file, reached_definition.definition, pool
            )

    def register_definition(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Register a validated definition and follow its references."""
        self._definition_results[definition_result.definition.typed_name] = (
            definition_result
        )
        self._reference_graph.add_definition(definition_result.definition)
        for edge in definition_result.reference_edges:
            if not self._add_reference_edge(edge, definition_result):
                continue
            reached_definition = self._resolver.follow_reference(
                loaded_file, edge, definition_result
            )
            if reached_definition is not None:
                self.request_definition(
                    reached_definition.loaded_file, reached_definition.definition, pool
                )

    def _add_reference_edge(
        self,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        detected_cycle = self._reference_graph.try_add_edge(edge)
        if detected_cycle is None:
            return True
        source_definition.diagnostics.append(
            diagnostics.CircularGlobalReferenceDiagnostic(
                location=edge.global_name_reference.location,
                cycle=detected_cycle,
            )
        )
        return False


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
