"""Parallel coordinator for multi-file Define program validation.

validate_program and validate_program_non_filesystem validate one program each,
using a thread pool. They manage all shared state on the main thread and
delegate pure per-file validation to FileStructuralValidator workers. They
validate only the entry file's definitions and the definitions they reference,
directly or indirectly. A ReferenceResolver decides which files references lead
to and which definitions they resolve to, and the validation loads those files and
validates those definitions.
"""

from __future__ import annotations

import functools
import typing

from crates.source_rendering.python import rendering

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable, Mapping

    from define.compiler.config import config_loader
    from define.compiler.data_structures import define_path


from define.compiler import ast, work_pool
from define.compiler.errors import diagnostics
from define.compiler.graphs import reference_graph, reference_graph_order
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    file_validation_context,
    file_validator,
)
from define.compiler.validator.structural.resolver import (
    filesystem_reference_resolver,
    non_filesystem_reference_resolver,
    reference_resolver,
)


def validate_program(
    path: pathlib.PurePath,
    *,
    max_workers: int | None = None,
    allow_entry_action_interface_positions: bool = False,
) -> StructurallyValidatedProgram:
    """Validate a program starting from the given file path, and return the validation, which can load more of the program.

    allow_entry_action_interface_positions exists only for validation tests
    that specifically require an entry action with interface positions. It
    must remain false when validating a program for code generation.
    """
    source_map = rendering.SourceMap()
    resolver = filesystem_reference_resolver.FilesystemReferenceResolver(source_map)
    run = _ProgramValidationRun(
        resolver,
        source_map,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
    entry_file = resolver.load_entry_file(path)
    if entry_file is not None:
        with work_pool.WorkPool(max_workers=max_workers) as pool:
            for definition in entry_file.definitions.values():
                run.request_definition(entry_file, definition, pool)
            pool.run_until_idle()
    return StructurallyValidatedProgram(run, run.build_program_result())


def validate_program_non_filesystem(
    source: str,
    *,
    max_workers: int | None = None,
    allow_entry_action_interface_positions: bool = False,
) -> StructurallyValidatedProgram:
    """Validate a program from source text, loading config only when needed, and return the validation, which can load more of the program.

    allow_entry_action_interface_positions exists only for validation tests
    that specifically require an entry action with interface positions. It
    must remain false when validating a program for code generation.
    """
    source_map = rendering.SourceMap(in_memory_source=source)
    source_file = file_validator.FileStructuralValidator(source_map).load_source(source)
    resolver = non_filesystem_reference_resolver.NonFilesystemReferenceResolver(
        source_file, source_map
    )
    run = _ProgramValidationRun(
        resolver,
        source_map,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
    if source_file.load_failure is not None:
        return StructurallyValidatedProgram(run, run.build_program_result())

    with work_pool.WorkPool(max_workers=max_workers) as pool:
        for definition in source_file.definitions.values():
            run.request_definition(source_file, definition, pool)
        pool.run_until_idle()
    return StructurallyValidatedProgram(
        run, run.build_program_result(select_last_constructor=True)
    )


@typing.final
class StructurallyValidatedProgram:
    """A structurally validated program, which can load more of the program."""

    def __init__(
        self,
        run: _ProgramValidationRun,
        result: validation_result.ProgramValidationResult,
    ):
        """Initialize with the run that validated the program that the entry file references, directly or indirectly, and its result."""
        self._run = run
        self.result = result

    def load_associated(
        self,
        edges: Iterable[reference_graph.ReferenceEdge],
        *,
        max_workers: int | None = None,
    ):
        """Load and validate what the edges of associations reference, and everything that it references, and add it to the program's result.

        Each edge starts at a validated logical operation or value quality.
        Replaces the result's file results and diagnostics, so later stages
        add their diagnostics after this.
        """
        self._run.load_associated(edges, max_workers=max_workers)
        self.result.file_results = self._run.file_results()
        self.result.diagnostics = self._run.diagnostics()

    def project_roots(
        self,
    ) -> Mapping[str, tuple[define_path.DefinePath, config_loader.Config]]:
        """Return the path and config of each project root whose config loaded, by its universe."""
        return self._run.project_roots()


class _ProgramValidationRun:
    """The state of structurally validating one program.

    Loads files and validates definitions on a thread pool as references
    resolve to them, and registers them and the references between them. All shared state
    is managed on the coordinator thread. After the program that the entry
    file references is validated, it loads what association resolution chooses.
    """

    _resolver: reference_resolver.ReferenceResolver
    _source_map: rendering.SourceMap
    _file_validator: file_validator.FileStructuralValidator
    # The graph of the definitions that the current run validates, which
    # exists only during a run.
    _reference_graph: reference_graph.ReferenceGraph
    # The result of each validated definition, by its full typed name.
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    # Each validated definition, by its full typed name.
    _definitions: dict[str, ast.GlobalDefinition]
    _encoding_operations: list[ast.EncodingOperationDefinition]
    # The full typed names of definitions submitted for validation.
    _requested_definition_names: set[str]
    _allow_entry_action_interface_positions: bool

    def __init__(
        self,
        resolver: reference_resolver.ReferenceResolver,
        source_map: rendering.SourceMap,
        *,
        allow_entry_action_interface_positions: bool,
    ):
        """Initialize with the resolver for the program's references, the source map that its files are registered with, and nothing validated."""
        self._resolver = resolver
        self._source_map = source_map
        self._file_validator = file_validator.FileStructuralValidator(source_map)
        self._reference_graph = reference_graph.ReferenceGraph()
        self._definition_results = {}
        self._definitions = {}
        self._encoding_operations = []
        self._requested_definition_names = set()
        self._allow_entry_action_interface_positions = (
            allow_entry_action_interface_positions
        )

    def build_program_result(
        self,
        *,
        select_last_constructor: bool = False,
    ) -> validation_result.ProgramValidationResult:
        """Validate the entry action and assemble the program result."""
        file_results = self.file_results()
        entry_action = None
        entry_file_definitions: list[ast.GlobalDefinition] = []
        # The entry file is the first file to load. There is none if it could
        # not be loaded, such as when its path is outside the project root.
        if file_results:
            entry_file_result = file_results[0]
            entry_action_result = _select_entry_action(
                entry_file_result, select_last_constructor=select_last_constructor
            )
            if entry_action_result is not None:
                if not self._allow_entry_action_interface_positions:
                    _validate_entry_action_interface_positions(entry_action_result)
                candidate = typing.cast(
                    "ast.ActionDefinition", entry_action_result.definition
                )
                if candidate.is_constructor:
                    entry_action = candidate
            for definition_result in entry_file_result.definition_results:
                entry_file_definitions.append(definition_result.definition)
        definition_order = reference_graph_order.ReferenceGraphOrder(
            self._reference_graph, entry_file_definitions
        )
        # Later stages need only the compact order, not cycle-detection state.
        del self._reference_graph
        return validation_result.ProgramValidationResult(
            file_results=file_results,
            entry_action=entry_action,
            definition_order=definition_order,
            definitions=self._definitions,
            structural_results=self._definition_results,
            encoding_operations=self._encoding_operations,
            diagnostics=self.diagnostics(),
            source_map=self._source_map,
        )

    def load_associated(
        self,
        edges: Iterable[reference_graph.ReferenceEdge],
        *,
        max_workers: int | None = None,
    ):
        """Load and validate what the edges of associations reference, and everything that it references."""
        # Only definitions that this run validates are in its graph, to find
        # cycles among them. The associations' edges start at definitions
        # that are not, and cannot be part of a cycle, since no encoding or
        # Encoding Operation references a logical operation or value quality.
        self._reference_graph = reference_graph.ReferenceGraph()
        project_roots = self.project_roots()
        with work_pool.WorkPool(max_workers=max_workers) as pool:
            for edge in edges:
                # An association is in the config of the project whose
                # universe its references are written in.
                referencing_root, _ = project_roots[
                    edge.global_name_reference.enclosing_fqun.canonical
                ]
                self._follow_reference(
                    referencing_root,
                    None,
                    self._definition_results[
                        edge.enclosing_definition.typed_name.full_typed_name
                    ],
                    edge,
                    pool,
                )
            pool.run_until_idle()
        del self._reference_graph

    def project_roots(
        self,
    ) -> Mapping[str, tuple[define_path.DefinePath, config_loader.Config]]:
        """Return the path and config of each project root whose config loaded, by its universe."""
        return self._resolver.project_roots()

    def file_results(self) -> list[validation_result.FileValidationResult]:
        """Return the result of each loaded file, without the reference edges that structural validation follows."""
        file_results: list[validation_result.FileValidationResult] = []
        for loaded_file in self._resolver.completed_files():
            file_result = loaded_file.build_file_validation_result(
                self._validated_definition_results(loaded_file)
            )
            # The completed order replaces these structural-only edges;
            # retaining both would duplicate per-reference state during later
            # stages.
            for definition_result in file_result.definition_results:
                definition_result.reference_edges.clear()
            file_results.append(file_result)
        return file_results

    def diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return every diagnostic that structural validation found, about the program, each loaded file, and each validated definition."""
        found = list(self._resolver.program_diagnostics())
        for loaded_file in self._resolver.completed_files():
            if loaded_file.load_failure is not None:
                found.append(loaded_file.load_failure)
            found.extend(loaded_file.file_diagnostics)
            for definition_result in self._validated_definition_results(loaded_file):
                found.extend(definition_result.diagnostics)
        return found

    def _validated_definition_results(
        self, loaded_file: file_validator.LoadedFile
    ) -> list[validation_result.DefinitionValidationResult]:
        """Return the results of a file's validated definitions, in source order."""
        definition_results: list[validation_result.DefinitionValidationResult] = []
        for definition in loaded_file.definitions.values():
            definition_result = self._definition_results.get(
                definition.typed_name.full_typed_name
            )
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
            handle_result=functools.partial(self._register_definition, loaded_file),
        )

    def _process_loaded_file(
        self, loaded_file: file_validator.LoadedFile, pool: work_pool.WorkPool
    ):
        for reached_definition in self._resolver.add_loaded_file(loaded_file):
            self.request_definition(
                reached_definition.loaded_file, reached_definition.definition, pool
            )

    def _register_definition(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Register a validated definition and follow its references."""
        definition = definition_result.definition
        definition_name = definition.typed_name.full_typed_name
        self._definition_results[definition_name] = definition_result
        self._definitions[definition_name] = definition
        if isinstance(definition, ast.EncodingOperationDefinition):
            self._encoding_operations.append(definition)
        self._reference_graph.add_definition(definition_result.definition)
        self._follow_edges(
            loaded_file, definition_result, definition_result.reference_edges, pool
        )

    def _follow_edges(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        edges: Iterable[reference_graph.ReferenceEdge],
        pool: work_pool.WorkPool,
    ):
        """Add a validated definition's edges to the reference graph, and request the definitions that they reference."""
        for edge in edges:
            if self._add_reference_edge(edge, definition_result):
                self._request_reference(loaded_file, definition_result, edge, pool)

    def _request_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        edge: reference_graph.ReferenceEdge,
        pool: work_pool.WorkPool,
    ):
        """Request the definition that a validated definition's edge references, loading its file if needed."""
        # A definition can reference only definitions that come before it in
        # its own file.
        same_file_definition = loaded_file.earlier_definition(
            edge.global_name_reference, definition_result.definition
        )
        if same_file_definition is not None:
            self.request_definition(loaded_file, same_file_definition, pool)
            return
        self._follow_reference(
            loaded_file.context.root_prefix, loaded_file, definition_result, edge, pool
        )

    def _follow_reference(
        self,
        referencing_root: define_path.DefinePath,
        referencing_file: file_validator.LoadedFile | None,
        definition_result: validation_result.DefinitionValidationResult,
        edge: reference_graph.ReferenceEdge,
        pool: work_pool.WorkPool,
    ):
        """Request the definition that an edge from referencing_root references, loading its file if needed.

        referencing_file is the file that holds the edge, or None for an edge
        from an association.
        """
        match self._resolver.validate_reference(
            referencing_root, referencing_file, edge, definition_result
        ):
            case reference_resolver.ReachedDefinition() as reached_definition:
                self.request_definition(
                    reached_definition.loaded_file,
                    reached_definition.definition,
                    pool,
                )
            case file_validation_context.FileValidationContext() as file_to_load:
                pool.submit(
                    self._file_validator.load_file,
                    file_to_load,
                    handle_result=self._process_loaded_file,
                )
            case None:
                # Nothing to do for this reference now: it waits for a file
                # that is already loading, or it was reported or skipped.
                pass

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
