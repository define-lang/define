"""Parallel coordinator for multi-file Define program validation.

validate_program and validate_program_non_filesystem validate one program each,
using a thread pool. They manage all shared state on the main thread and
delegate pure per-file validation to workers. They
validate only the entry file's definitions and the definitions they reference,
directly or indirectly. A ReferenceResolver decides which files references lead
to and which definitions they resolve to, and the validation loads those files and
validates those definitions.
"""

from __future__ import annotations

import functools
import typing

from crates.source_rendering.python import rendering
from define.compiler import ast, work_pool
from define.compiler.config import project_roots
from define.compiler.errors import diagnostics
from define.compiler.graphs import reference_graph, reference_graph_order
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    definition_validator,
    file_loader,
)
from define.compiler.validator.structural.resolver import (
    filesystem_reference_resolver,
    non_filesystem_reference_resolver,
    reference_resolver,
)

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable

    from define.compiler.config import config_loader
    from define.compiler.data_structures import define_path
    from define.compiler.validator.structural import structural_result


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
    roots = project_roots.ProjectRoots(source_map)
    resolver = filesystem_reference_resolver.FilesystemReferenceResolver(
        source_map, roots
    )
    entry_file, entry_file_diagnostics = resolver.load_entry_file(path)
    run = _ProgramValidationRun(
        resolver,
        roots,
        source_map,
        entry_file_diagnostics,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
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
    source_file, source_file_diagnostics = file_loader.load_source(source)
    roots = project_roots.ProjectRoots(source_map)
    resolver = non_filesystem_reference_resolver.NonFilesystemReferenceResolver(
        source_file, roots
    )
    run = _ProgramValidationRun(
        resolver,
        roots,
        source_map,
        source_file_diagnostics,
        allow_entry_action_interface_positions=allow_entry_action_interface_positions,
    )
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
        self.project_roots = run.project_roots

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


class _ProgramValidationRun:
    """The state of structurally validating one program.

    Loads files and validates definitions on a thread pool as references
    resolve to them, and registers them and the references between them. All shared state
    is managed on the coordinator thread. After the program that the entry
    file references is validated, it loads what association resolution chooses.
    """

    _resolver: reference_resolver.ReferenceResolver
    project_roots: project_roots.ProjectRoots
    _source_map: rendering.SourceMap
    # The graph of the definitions that the current run validates, which
    # exists only during a run.
    _reference_graph: reference_graph.ReferenceGraph
    # The result of each validated definition, by its full typed name.
    _definition_results: dict[str, structural_result.StructuralDefinitionResult]
    # Each validated definition, by its full typed name.
    _definitions: dict[str, ast.GlobalDefinition]
    _encoding_operations: list[ast.EncodingOperationDefinition]
    # The diagnostics that loading files, validating definitions, and
    # resolving references found.
    _diagnostics: list[diagnostics.FormattableDiagnostic]
    # The full typed names of definitions submitted for validation.
    _requested_definition_names: set[str]
    _allow_entry_action_interface_positions: bool

    def __init__(
        self,
        resolver: reference_resolver.ReferenceResolver,
        roots: project_roots.ProjectRoots,
        source_map: rendering.SourceMap,
        entry_file_diagnostics: Iterable[diagnostics.FormattableDiagnostic],
        *,
        allow_entry_action_interface_positions: bool,
    ):
        """Initialize with the resolver for the program's references, the program's project roots, the source map that its files are registered with, the diagnostics that loading the entry file found, and nothing validated."""
        self._resolver = resolver
        self.project_roots = roots
        self._source_map = source_map
        self._reference_graph = reference_graph.ReferenceGraph()
        self._definition_results = {}
        self._definitions = {}
        self._encoding_operations = []
        self._diagnostics = list(entry_file_diagnostics)
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
                    self._validate_entry_action_interface_positions(entry_action_result)
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
        with work_pool.WorkPool(max_workers=max_workers) as pool:
            for edge in edges:
                # An association is in the config of the project whose
                # universe its references are written in, which is loaded.
                referencing_root, _ = typing.cast(
                    "tuple[define_path.DefinePath, config_loader.Config]",
                    self.project_roots.get_loaded_root_config(
                        edge.global_name_reference.enclosing_fqun.canonical
                    ),
                )
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

    def file_results(self) -> list[structural_result.FileValidationResult]:
        """Return the result of each loaded file, without the reference edges that structural validation follows."""
        file_results: list[structural_result.FileValidationResult] = []
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
        return [*self.project_roots.diagnostics(), *self._diagnostics]

    def _validated_definition_results(
        self, loaded_file: file_loader.LoadedFile
    ) -> list[structural_result.StructuralDefinitionResult]:
        """Return the results of a file's validated definitions, in source order."""
        definition_results: list[structural_result.StructuralDefinitionResult] = []
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
        loaded_file: file_loader.LoadedFile,
        definition: ast.GlobalDefinition,
        pool: work_pool.WorkPool,
    ):
        """Submit a definition for validation unless it was already requested."""
        definition_name = definition.typed_name.full_typed_name
        if definition_name in self._requested_definition_names:
            return
        self._requested_definition_names.add(definition_name)
        pool.submit(
            definition_validator.validate_definition,
            definition,
            loaded_file.context,
            handle_result=functools.partial(self._register_definition, loaded_file),
        )

    def _process_loaded_file(
        self,
        loaded: tuple[file_loader.LoadedFile, list[diagnostics.Diagnostic]],
        pool: work_pool.WorkPool,
    ):
        loaded_file, file_diagnostics = loaded
        self._diagnostics.extend(file_diagnostics)
        for definition_result, outcome in self._resolver.add_loaded_file(loaded_file):
            if isinstance(outcome, reference_resolver.ResolvedDefinition):
                self.request_definition(outcome.loaded_file, outcome.definition, pool)
            else:
                self._report(definition_result, outcome)

    def _register_definition(
        self,
        loaded_file: file_loader.LoadedFile,
        validated: tuple[
            structural_result.StructuralDefinitionResult, list[diagnostics.Diagnostic]
        ],
        pool: work_pool.WorkPool,
    ):
        """Register a validated definition and follow its references."""
        definition_result, definition_diagnostics = validated
        self._diagnostics.extend(definition_diagnostics)
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
        loaded_file: file_loader.LoadedFile,
        definition_result: structural_result.StructuralDefinitionResult,
        edges: Iterable[reference_graph.ReferenceEdge],
        pool: work_pool.WorkPool,
    ):
        """Add a validated definition's edges to the reference graph, and request the definitions that they reference."""
        for edge in edges:
            if self._add_reference_edge(edge, definition_result):
                self._request_reference(loaded_file, definition_result, edge, pool)

    def _request_reference(
        self,
        loaded_file: file_loader.LoadedFile,
        definition_result: structural_result.StructuralDefinitionResult,
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
        referencing_file: file_loader.LoadedFile | None,
        definition_result: structural_result.StructuralDefinitionResult,
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
            case reference_resolver.ResolvedDefinition() as resolved_definition:
                self.request_definition(
                    resolved_definition.loaded_file,
                    resolved_definition.definition,
                    pool,
                )
            case reference_resolver.LoadFile(context=file_to_load):
                pool.submit(
                    file_loader.load_file,
                    file_to_load,
                    self._source_map,
                    handle_result=self._process_loaded_file,
                )
            case (
                reference_resolver.AwaitingFile() | reference_resolver.AlreadyReported()
            ):
                pass
            case reference_resolver.Unresolved(diagnostic=diagnostic):
                self._report(definition_result, diagnostic)

    def _add_reference_edge(
        self,
        edge: reference_graph.ReferenceEdge,
        source_definition: structural_result.StructuralDefinitionResult,
    ) -> bool:
        detected_cycle = self._reference_graph.try_add_edge(edge)
        if detected_cycle is None:
            return True
        self._report(
            source_definition,
            diagnostics.CircularGlobalReferenceDiagnostic(
                location=edge.global_name_reference.location,
                cycle=detected_cycle,
            ),
        )
        return False

    def _report(
        self,
        definition_result: structural_result.StructuralDefinitionResult,
        diagnostic: diagnostics.Diagnostic,
    ):
        """Record a diagnostic about a definition, which makes the definition structurally invalid."""
        self._diagnostics.append(diagnostic)
        definition_result.structurally_valid = False

    def _validate_entry_action_interface_positions(
        self, entry_action_result: structural_result.StructuralDefinitionResult
    ):
        definition = typing.cast("ast.ActionDefinition", entry_action_result.definition)
        for position in definition.interface_positions:
            self._report(
                entry_action_result,
                diagnostics.EntryPointInterfacePositionDiagnostic(
                    location=position.typed_name.location,
                    position_name=position.typed_name.source_typed_name,
                ),
            )


def _select_entry_action(
    entry_file_result: structural_result.FileValidationResult,
    *,
    select_last_constructor: bool = False,
) -> structural_result.StructuralDefinitionResult | None:
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
