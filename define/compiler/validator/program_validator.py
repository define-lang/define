"""Parallel coordinator for multi-file Define program validation.

ProgramValidator orchestrates per-file validation using a thread pool.
It manages all shared state on the main thread and delegates pure
per-file validation to FileValidator workers.
"""

from __future__ import annotations

import time
import typing
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import cached_property

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping

from define.compiler import (
    action_call_graph,
    ast,
    config,
    constants,
    diagnostics,
    exceptions,
    parser,
)
from define.compiler.validator import (
    file_validator,
    path_tracker,
    reference_graph,
    stats,
    validation_result,
)


@dataclass
class _DeferredReferenceEdge:
    """An edge waiting for its target file to complete validation."""

    edge: validation_result.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


@dataclass
class _DeferredChainValidation:
    """A chain element waiting for its parent definition to become resolvable."""

    deferred: validation_result.DeferredChainElements
    source_definition: validation_result.DefinitionValidationResult


@dataclass
class _DeferredMoveConstraint:
    """A move constraint check waiting for a required definition."""

    check: validation_result.DeferredMoveConstraintCheck
    source_definition: validation_result.DefinitionValidationResult


class _FileWorkPool:
    """Manages a thread pool for parallel file validation."""

    _max_workers: int | None
    _submitted: list[Future[validation_result.ValidationResult]]
    _executor: ThreadPoolExecutor
    _fv: file_validator.FileValidator

    def __init__(
        self,
        parser_instance: parser.Parser,
        max_workers: int | None = None,
    ):
        """Initialize with pool configuration only — no side effects."""
        self._max_workers = max_workers
        self._submitted = []
        self._fv = file_validator.FileValidator(parser_instance)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def __enter__(self) -> _FileWorkPool:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True)

    def submit(self, context: file_validator.FileValidationContext):
        """Submit a file for validation. Starts immediately on a worker thread."""
        submitted_at = time.perf_counter_ns()

        def _validate() -> validation_result.ValidationResult:
            started_at = time.perf_counter_ns()
            result = self._fv.validate_file(context)
            result.stats.queue_wait = started_at - submitted_at
            return result

        future = self._executor.submit(_validate)
        self._submitted.append(future)

    def wait_for_next(self) -> validation_result.ValidationResult:
        """Block until the next file completes."""
        for completed in as_completed(self._submitted):
            self._submitted.remove(completed)
            return completed.result()
        raise RuntimeError("wait_for_next called with no pending futures")

    def has_pending(self) -> bool:
        """Return True if there are submitted files not yet collected."""
        return bool(self._submitted)


class ProgramValidator:
    """Coordinates parallel validation of a Define program.

    Runs a single-threaded coordinator loop that submits files to a thread
    pool and processes results as they complete. All shared state is
    managed on the coordinator thread.

    config_loading_time_ns stores program-level config loading time.
    """

    _path_tracker: path_tracker.PathTracker[validation_result.ValidationResult]
    _reference_graph: reference_graph.ReferenceGraph
    action_call_graph: action_call_graph.ActionCallGraph
    _deferred_edges: dict[pathlib.PurePosixPath, list[_DeferredReferenceEdge]]
    _deferred_chain_validations: dict[str, list[_DeferredChainValidation]]
    _deferred_move_constraints: dict[str, list[_DeferredMoveConstraint]]
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    _definition_owners: dict[int, validation_result.ValidationResult]
    config_loading_time_ns: int

    def __init__(self):
        """Initialize coordinator state for one program validation."""
        # TODO: A lot of this is starting to feel like complexity that
        # should be abstracted behind something larger.
        self._path_tracker = path_tracker.PathTracker()
        self._reference_graph = reference_graph.ReferenceGraph()
        self.action_call_graph = action_call_graph.ActionCallGraph()
        self._deferred_edges = {}
        self._deferred_chain_validations = {}
        self._deferred_move_constraints = {}
        self._definition_results = {}
        self._definition_owners = {}
        self.config_loading_time_ns = 0

    @cached_property
    def _parser(self) -> parser.Parser:
        """Lazily construct and cache the parser for this validator instance."""
        # Lark parsers are thread-safe, so we construct one shared instance.
        # Reconstructing repeatedly is slow because it must parse the grammar.
        return parser.Parser()

    def validate_program(
        self,
        path: pathlib.PurePosixPath,
        max_workers: int | None = None,
    ) -> list[validation_result.ValidationResult]:
        """Validate a program starting from the given file path."""
        root_prefix = constants.PROJECT_ROOT
        try:
            fqun, sub_root_mappings = self._load_root_config(root_prefix)
        except exceptions.ConfigError as e:
            return [_make_config_error_result(root_prefix / path, root_prefix, e)]

        initial_context = file_validator.FileValidationContext(
            file_path=path,
            root_prefix=root_prefix,
            expected_fqun=fqun,
            sub_root_mappings=sub_root_mappings,
        )

        with _FileWorkPool(self._parser, max_workers=max_workers) as pool:
            self._path_tracker.mark_in_progress(root_prefix / path)
            pool.submit(initial_context)
            self._run_pool_loop(pool)

        return self._path_tracker.completed_results()

    def validate_program_non_filesystem(
        self,
        source: str,
        max_workers: int | None = None,
    ) -> list[validation_result.ValidationResult]:
        """Validate a program from source text, loading config only when needed."""
        result = file_validator.FileValidator(self._parser).validate_source(source)
        if result.exception is not None:
            return [result]

        self._path_tracker.mark_in_progress(result.file_path)
        self._path_tracker.set_result(result.file_path, result)

        if not self._resolve_non_filesystem_discovered_files(result):
            return self._path_tracker.completed_results()

        with _FileWorkPool(self._parser, max_workers=max_workers) as pool:
            self._process_completed_result(result, pool)
            self._run_pool_loop(pool)
        return self._path_tracker.completed_results()

    def _run_pool_loop(
        self,
        pool: _FileWorkPool,
    ):
        """Run the coordinator loop for queued work."""
        while pool.has_pending():
            result = pool.wait_for_next()
            self._path_tracker.set_result(result.file_path, result)
            self._process_completed_result(result, pool)

    def _process_completed_result(
        self,
        result: validation_result.ValidationResult,
        pool: _FileWorkPool,
    ):
        """Handle a completed file: check edges, submit discovered."""
        started_at = time.perf_counter_ns()
        # We always want to submit discovered files first, to get background
        # work into the queue ASAP.
        for definition_result in result.definition_results:
            self._submit_discovered_files(result, definition_result, pool)
        for definition_result in result.definition_results:
            self._process_completed_definition(result, definition_result)
        # Reference edges are file-scoped, but validating them still depends on
        # this file's definitions already being registered so wrong-type checks
        # don't race ahead of the completed file's real contents.
        self._validate_incoming_reference_edges(result.file_path)
        result.stats.global_validation += time.perf_counter_ns() - started_at

    def _process_completed_definition(
        self,
        result: validation_result.ValidationResult,
        definition_result: validation_result.DefinitionValidationResult,
    ):
        """Handle one completed definition from a file result."""
        self._definition_owners[id(definition_result)] = result
        name = definition_result.definition.typed_name.full_typed_name()
        # FileValidator preserves duplicate definitions in source order so
        # the later ones can still return diagnostics. Originally, I tried
        # to make all the later checks still run on duplicates, but it gets
        # into too much complexity. We do still load DiscoveredFiles from
        # duplicates, above, but that's it.
        if name in self._definition_results:
            return
        self._definition_results[name] = definition_result
        self.action_call_graph.process_definition_result(definition_result)
        self._validate_incoming_chained_names(definition_result)
        self._validate_incoming_move_constraints(definition_result)
        self._validate_outgoing_reference_edges(result.root_prefix, definition_result)
        self._validate_outgoing_chained_names(definition_result)
        self._validate_outgoing_move_constraints(definition_result)

    def _submit_discovered_files(
        self,
        result: validation_result.ValidationResult,
        definition_result: validation_result.DefinitionValidationResult,
        pool: _FileWorkPool,
    ):
        """Submit discovered files if not already tracked."""
        for discovered in definition_result.discovered_files:
            full_path = discovered.root_prefix / discovered.path
            if self._path_tracker.is_tracked(full_path):
                continue
            if self._path_tracker.is_under_failed_root(full_path):
                continue

            self._check_existing_root_conflicts_for_first_subroot_load(
                discovered, result
            )

            try:
                fqun, sub_root_mappings = self._load_root_config(
                    discovered.root_prefix, discovered.expected_fqun
                )
            except exceptions.ConfigError as e:
                self._path_tracker.mark_root_failed(discovered.root_prefix)
                result.add_file_diagnostic(
                    diagnostics.ConfigLoadErrorDiagnostic(
                        position=discovered.position,
                        error=e,
                    )
                )
                continue

            context = file_validator.FileValidationContext(
                file_path=discovered.path,
                root_prefix=discovered.root_prefix,
                expected_fqun=fqun,
                sub_root_mappings=sub_root_mappings,
            )
            self._path_tracker.mark_in_progress(full_path)
            pool.submit(context)

    def _resolve_non_filesystem_discovered_files(
        self,
        result: validation_result.ValidationResult,
    ) -> bool:
        """Load project config if necessary, and resolve FQUNs to sub-roots."""
        if self._first_discovered_file(result) is None:
            return True

        current_fqun, sub_root_mappings = self._load_config_in_non_filesystem_context(
            result
        )
        # We check both of these just for type narrowing.
        if current_fqun is None or sub_root_mappings is None:
            return False
        self._resolve_non_filesystem_discovered_files_with_config(
            result=result,
            current_fqun=current_fqun,
            sub_root_mappings=sub_root_mappings,
        )
        return True

    def _resolve_non_filesystem_discovered_files_with_config(
        self,
        result: validation_result.ValidationResult,
        current_fqun: str,
        sub_root_mappings: Mapping[str, pathlib.PurePosixPath],
    ):
        """Resolve discovered files/edges in non-filesystem mode after config load."""
        unknown_fquns: set[str] = set()
        for definition_result in result.definition_results:
            resolved_discoveries: list[validation_result.DiscoveredFile] = []
            for discovered in definition_result.discovered_files:
                sub_root_rel = sub_root_mappings.get(discovered.expected_fqun)
                if sub_root_rel is None:
                    if discovered.expected_fqun in unknown_fquns:
                        continue
                    unknown_fquns.add(discovered.expected_fqun)
                    result.add_file_diagnostic(
                        diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                            position=discovered.position,
                            universe=discovered.expected_fqun,
                            current_universe_name=current_fqun,
                        )
                    )
                    continue
                discovered.root_prefix = constants.PROJECT_ROOT / sub_root_rel
                resolved_discoveries.append(discovered)
            definition_result.discovered_files = resolved_discoveries

        # In a filesystem context, we don't return reference edges for
        # unknown sub-roots, so we are keeping that behavior consistent
        # in a non-filesystem context.
        for definition_result in result.definition_results:
            definition_result.reference_edges = [
                ref_edge
                for ref_edge in definition_result.reference_edges
                if (
                    ref_edge.global_name_reference.name_content.fqun is None
                    or ref_edge.global_name_reference.name_content.fqun.canonical
                    not in unknown_fquns
                )
            ]

    def _load_config_in_non_filesystem_context(
        self,
        result: validation_result.ValidationResult,
    ) -> tuple[str, Mapping[str, pathlib.PurePosixPath]] | tuple[None, None]:
        """Load root config and map loading errors to non-filesystem diagnostics."""
        first_discovered = self._first_discovered_file(result)
        if first_discovered is None:
            raise ValueError("expected at least one discovered file")
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except exceptions.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.add_file_diagnostic(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    position=first_discovered.position,
                    universe=first_discovered.expected_fqun,
                    config_path=str(e.config_path),
                )
            )
            return (None, None)
        except exceptions.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.add_file_diagnostic(
                diagnostics.ConfigLoadErrorDiagnostic(
                    position=first_discovered.position,
                    error=e,
                )
            )
            return (None, None)

    def _validate_outgoing_reference_edges(
        self,
        enclosing_root: pathlib.PurePosixPath,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Try to add edges to the reference graph, validate targets we already know about, and enqueue those we don't."""
        for ref_edge in source_definition.reference_edges:
            target_file = self._resolve_target_file(
                ref_edge.global_name_reference.name_content, enclosing_root
            )
            if target_file is None:
                continue

            source_key = ref_edge.enclosing_definition.typed_name.full_typed_name()
            target_key = ref_edge.full_typed_name
            detected = self._reference_graph.try_add_edge(source_key, target_key)
            if detected is not None:
                source_definition.add_diagnostic(
                    diagnostics.CircularGlobalReferenceDiagnostic(
                        position=ref_edge.global_name_reference.position,
                        cycle=detected.path,
                    )
                )
                continue
            if self._check_if_current_universe_path_in_a_subroot(
                ref_edge, target_file, enclosing_root, source_definition
            ):
                continue

            # With the thread pool, files complete in arbitrary order. If files
            # A and C both reference file B, and B finishes before A's results
            # are processed, then target_result is already available when
            # processing A's edges.
            target_result = self._path_tracker.try_get_result(target_file)
            if target_result is not None:
                self._validate_reference_against_target(
                    ref_edge,
                    target_file,
                    target_result,
                    source_definition,
                )
            else:
                self._deferred_edges.setdefault(target_file, []).append(
                    _DeferredReferenceEdge(ref_edge, source_definition)
                )

    def _resolve_target_file(
        self,
        global_name: ast.ReferenceGlobalNameContent,
        enclosing_root: pathlib.PurePosixPath,
    ) -> pathlib.PurePosixPath | None:
        """Determine the full file path for a global name reference.

        Returns None if the target is under a failed root.
        """
        if global_name.fqun is not None:
            fqun_string = global_name.fqun.canonical
            sub_root_loc = self._path_tracker.sub_root_location(
                fqun_string, enclosing_root
            )
            sub_root_path = enclosing_root / sub_root_loc
            target_file = global_name.path.file_path(sub_root_path)
            if self._path_tracker.is_under_failed_root(target_file):
                return None
            return target_file

        return global_name.path.file_path(enclosing_root)

    def _check_if_current_universe_path_in_a_subroot(
        self,
        edge: validation_result.ReferenceEdge,
        target_file: pathlib.PurePosixPath,
        enclosing_root: pathlib.PurePosixPath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        """Check if a same-universe reference lands inside another universe's sub-root.

        Returns True (and appends a diagnostic) when the edge should be skipped.
        """
        # This check is only for current-universe references.
        if edge.global_name_reference.name_content.fqun is not None:
            return False

        actual_root = self._path_tracker.find_enclosing_root(target_file)
        if actual_root == enclosing_root:
            return False

        source_definition.add_diagnostic(
            diagnostics.PathInsideOtherUniverseDiagnostic(
                position=edge.global_name_reference.name_content.position,
                path=str(target_file),
                other_universe=self._path_tracker.fqun_for_root(actual_root) or "",
                sub_root_path=str(actual_root),
            )
        )
        return True

    def _validate_reference_against_target(
        self,
        edge: validation_result.ReferenceEdge,
        target_file: pathlib.PurePosixPath,
        target_result: validation_result.ValidationResult,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a reference edge against a completed target file's result."""
        started_at = time.perf_counter_ns()
        self._do_validate_reference_against_target(
            edge=edge,
            target_file=target_file,
            target_result=target_result,
            source_definition=source_definition,
        )
        self._record_deferred_validation_time(source_definition, started_at)

    def _do_validate_reference_against_target(
        self,
        edge: validation_result.ReferenceEdge,
        target_file: pathlib.PurePosixPath,
        target_result: validation_result.ValidationResult,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Apply reference-target validation checks without timing side effects."""
        global_name = edge.global_name_reference.name_content

        if isinstance(target_result.exception, exceptions.SourceFileNotFoundError):
            source_definition.add_diagnostic(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    position=global_name.position,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return

        if edge.full_typed_name not in self._definition_results:
            source_definition.add_diagnostic(
                diagnostics.ReferencedGlobalNameWrongTypeDiagnostic(
                    position=global_name.position,
                    path=global_name.path.name,
                    expected_type=edge.global_name_reference.name_type.value,
                )
            )

    def _validate_incoming_reference_edges(self, completed_file: pathlib.PurePosixPath):
        """Validate deferred reference edges waiting on a completed file."""
        # Reference edges have to wake up by file, not by definition name.
        #
        # Two different files can participate in resolution for the same
        # canonical typed name. One might be the file we actually intended to
        # load, while another might define the same typed name at a different
        # path or might be missing entirely. Since _FileWorkPool completes
        # files in arbitrary order, waking by definition name lets whichever
        # file finishes first drain all waiters for that name.
        #
        # That loses the identity of the file the edge was really waiting on.
        # A completed "wrong" file can consume work that should have been
        # resolved when the real target file completed, which makes missing-file
        # and wrong-file diagnostics depend on completion order. Keying by
        # completed_file preserves the real dependency: an edge is blocked on
        # one exact file finishing validation, and only that file gets to
        # satisfy or fail the deferred edge.
        deferred = self._deferred_edges.pop(completed_file, [])
        target_result = self._path_tracker.get_result(completed_file)
        for deferred_edge in deferred:
            self._validate_reference_against_target(
                deferred_edge.edge,
                completed_file,
                target_result,
                deferred_edge.source_definition,
            )

    def _validate_outgoing_chained_names(
        self,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Queue or immediately validate deferred chain elements referenced within this definition."""
        for deferred in source_definition.deferred_chained_names:
            # Same race as _validate_outgoing_reference_edges: the parent
            # definition may already have been registered (for example, because
            # its file was discovered and completed earlier) before we process
            # this definition's chain elements.
            if deferred.parent_full_typed_name in self._definition_results:
                self._validate_chain_element_against_target(
                    deferred,
                    source_definition,
                )
            else:
                self._deferred_chain_validations.setdefault(
                    deferred.parent_full_typed_name, []
                ).append(_DeferredChainValidation(deferred, source_definition))

    def _validate_incoming_chained_names(
        self, target_definition: validation_result.DefinitionValidationResult
    ):
        """Validate deferred chain elements that were waiting for this definition."""
        name = target_definition.definition.typed_name.full_typed_name()
        for deferred_validation in self._deferred_chain_validations.pop(name, []):
            self._validate_chain_element_against_target(
                deferred_validation.deferred,
                deferred_validation.source_definition,
            )

    def _validate_outgoing_move_constraints(
        self,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Queue or immediately validate deferred move constraint checks referenced in this definition."""
        for check in source_definition.deferred_move_constraint_checks:
            self._try_resolve_move_constraint(check, source_definition)

    def _validate_incoming_move_constraints(
        self, target_definition: validation_result.DefinitionValidationResult
    ):
        """Resolve move constraints waiting on this definition."""
        name = target_definition.definition.typed_name.full_typed_name()
        for deferred_move_constraint in self._deferred_move_constraints.pop(name, []):
            self._try_resolve_move_constraint(
                deferred_move_constraint.check,
                deferred_move_constraint.source_definition,
            )

    def _try_resolve_move_constraint(
        self,
        check: validation_result.DeferredMoveConstraintCheck,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Try to fully resolve a deferred move constraint check."""
        started_at = time.perf_counter_ns()
        self._do_try_resolve_move_constraint(check, source_definition)
        self._record_deferred_validation_time(source_definition, started_at)

    def _do_try_resolve_move_constraint(
        self,
        check: validation_result.DeferredMoveConstraintCheck,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Resolve a deferred move constraint check without timing side effects.

        Eagerly resolves both sides, caching whatever is available. If either
        side is still missing, queues the check on one unresolved definition.
        """
        fqun = check.enclosing_definition.typed_name.name_content.fqun

        from_typed_name: str | None = None
        if check.from_qualities is None:
            qualities, from_typed_name = self._get_required_qualities_for_position(
                check.statement.from_position.chain,
                fqun,
            )
            if qualities is not None:
                check.from_qualities = qualities

        to_typed_name: str | None = None
        if check.to_qualities is None:
            qualities, to_typed_name = self._get_required_qualities_for_position(
                check.statement.to_position.chain,
                fqun,
            )
            if qualities is not None:
                check.to_qualities = qualities

        if check.from_qualities is None or check.to_qualities is None:
            wait_for_definition = (
                from_typed_name if check.from_qualities is None else to_typed_name
            )
            if wait_for_definition is None:
                raise ValueError("wait_for_definition should never be None here")
            self._deferred_move_constraints.setdefault(wait_for_definition, []).append(
                _DeferredMoveConstraint(
                    check=check,
                    source_definition=source_definition,
                )
            )
            return

        missing = check.to_qualities - check.from_qualities
        if missing:
            source_definition.add_diagnostic(
                diagnostics.MoveViolatesConstraintsDiagnostic(
                    position=check.statement.to_position.position,
                    from_position=check.statement.from_position.chain.source_chained_name,
                    to_position=check.statement.to_position.chain.source_chained_name,
                    missing_qualities=sorted(missing),
                )
            )

    def _get_required_qualities_for_position(
        self,
        chain: ast.ChainedName,
        fqun: ast.Fqun,
    ) -> tuple[frozenset[str] | None, str]:
        """Resolve the constraint qualities for the last position in a chain.

        Returns (qualities, typed_name). qualities is None when the target
        definition hasn't been registered yet; typed_name is the definition
        name to wait for.
        """
        # TODO: This uses the last chain element's constraints as a proxy for what
        # qualities a DP has. A DP may actually have more qualities than the last
        # position requires (from its original creation site), and we lose that
        # knowledge by only looking at its current location.
        last_element = chain.typed_names[-1]

        if isinstance(last_element, ast.GlobalTypedNameReference):
            lookup_key = last_element.full_typed_name(in_universe=fqun)
        else:
            # If the last element is a local reference, then per the
            # guarantees provided by file_validator, it _must_ be
            # a chain with more than one item in it, and the parent
            # must be a globally-named action.
            parent = chain.typed_names[-2]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise ValueError("got a local name where a global name was expected")
            lookup_key = parent.full_typed_name(in_universe=fqun)

        definition_result = self._definition_results.get(lookup_key)
        if definition_result is None:
            return (None, lookup_key)

        if isinstance(last_element, ast.GlobalTypedNameReference):
            return (definition_result.position_constraint_names, lookup_key)
        locals_map = definition_result.action_local_position_constraint_names
        return (
            locals_map.get(last_element.name_content.name, frozenset()),
            lookup_key,
        )

    def _validate_chain_element_against_target(
        self,
        deferred: validation_result.DeferredChainElements,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a chain element against a completed target definition."""
        started_at = time.perf_counter_ns()
        self._do_validate_chain_element_against_target(deferred, source_definition)
        self._record_deferred_validation_time(source_definition, started_at)

    def _do_validate_chain_element_against_target(
        self,
        deferred: validation_result.DeferredChainElements,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a chain element against its parent's completed definition."""
        target_result = self._definition_results.get(deferred.parent_full_typed_name)
        if target_result is None:
            return
        match target_result.definition:
            case ast.PositionDefinition():
                self._validate_chain_against_position_def(
                    deferred,
                    target_result,
                    source_definition,
                )
            case ast.ActionDefinition():
                self._validate_chain_against_action_def(
                    deferred,
                    target_result,
                    source_definition,
                )
            case _:
                raise TypeError(
                    f"Unexpected definition type: {type(target_result.definition)}"
                )

    def _validate_chain_against_position_def(
        self,
        deferred: validation_result.DeferredChainElements,
        target_result: validation_result.DefinitionValidationResult,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a chain element against a position definition's constraints."""
        self._check_chain_element_against_constraints(
            deferred.chain_element,
            target_result.position_constraint_names,
            deferred.parent_full_typed_name,
            deferred.source_fqun,
            source_definition,
        )
        self._defer_chain_continuation(
            deferred,
            deferred.chain_element,
            deferred.remaining_chain,
            source_definition,
        )

    def _validate_chain_against_action_def(
        self,
        deferred: validation_result.DeferredChainElements,
        target_result: validation_result.DefinitionValidationResult,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a chain element against an action definition's local positions."""
        element = deferred.chain_element
        if not isinstance(element, ast.LocalTypedNameReference):
            self._emit_not_in_action_diagnostic(deferred, source_definition)
            return
        if element.name_type != ast.NameType.POSITION:
            self._emit_not_in_action_diagnostic(deferred, source_definition)
            return
        locals_map = target_result.action_local_position_constraint_names
        if element.name_content.name not in locals_map:
            self._emit_not_in_action_diagnostic(deferred, source_definition)
            return
        if not deferred.remaining_chain.typed_names:
            return
        next_element = deferred.remaining_chain.typed_names[0]
        del deferred.remaining_chain.typed_names[0]
        self._check_chain_element_against_constraints(
            next_element,
            locals_map[element.name_content.name],
            element.full_typed_name(),
            deferred.source_fqun,
            source_definition,
        )
        self._defer_chain_continuation(
            deferred,
            next_element,
            deferred.remaining_chain,
            source_definition,
        )

    def _emit_not_in_action_diagnostic(
        self,
        deferred: validation_result.DeferredChainElements,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Emit a diagnostic for a chain element not found in an action definition."""
        source_definition.add_diagnostic(
            diagnostics.ChainElementNotInActionDiagnostic(
                position=deferred.chain_element.position,
                element_name=deferred.chain_element.full_typed_name(
                    in_universe=deferred.source_fqun
                ),
                parent_name=deferred.parent_full_typed_name,
            )
        )

    def _defer_chain_continuation(
        self,
        deferred: validation_result.DeferredChainElements,
        validated_element: ast.TypedNameReference,
        remaining: ast.ChainedName,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Submit a deferred chain validation, or validate immediately if ready."""
        if not remaining.typed_names:
            return
        next_deferred = deferred.next_deferred(
            typing.cast("ast.GlobalTypedNameReference", validated_element),
            remaining,
        )
        if next_deferred.parent_full_typed_name in self._definition_results:
            self._validate_chain_element_against_target(
                next_deferred,
                source_definition,
            )
            return
        self._deferred_chain_validations.setdefault(
            next_deferred.parent_full_typed_name, []
        ).append(_DeferredChainValidation(next_deferred, source_definition))

    def _check_chain_element_against_constraints(
        self,
        element: ast.TypedNameReference,
        constraint_names: frozenset[str],
        parent_name: str,
        source_fqun: ast.Fqun,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Check if a chain element matches any constraint, adding a diagnostic if not."""
        element_name = element.full_typed_name(in_universe=source_fqun)
        if element_name not in constraint_names:
            source_definition.add_diagnostic(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    position=element.position,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )

    def _check_existing_root_conflicts_for_first_subroot_load(
        self,
        discovered: validation_result.DiscoveredFile,
        source_result: validation_result.ValidationResult,
    ):
        """Check SubRootAlreadyOccupied for discovered files entering a new sub-root."""
        if self._path_tracker.project_root_loaded(discovered.root_prefix):
            return

        conflicting_path, existing_universe = (
            self._path_tracker.first_tracked_file_under(discovered.root_prefix)
        )
        if conflicting_path is not None:
            source_result.add_file_diagnostic(
                diagnostics.SubRootAlreadyOccupiedDiagnostic(
                    position=discovered.position,
                    universe=discovered.expected_fqun,
                    sub_root_path=str(discovered.root_prefix),
                    existing_file=str(conflicting_path),
                    existing_universe=existing_universe or "",
                )
            )

    def _first_discovered_file(
        self,
        result: validation_result.ValidationResult,
    ) -> validation_result.DiscoveredFile | None:
        """Return the first discovered file in definition iteration order."""
        for definition_result in result.definition_results:
            if definition_result.discovered_files:
                return definition_result.discovered_files[0]
        return None

    def _record_deferred_validation_time(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        started_at: int,
    ):
        """Add deferred-validation time to the file that owns a definition."""
        self._definition_owners[
            id(definition_result)
        ].stats.deferred_validation += (  # pragma: no mutate
            time.perf_counter_ns() - started_at
        )

    # TODO: This should probably return a Config object.
    def _load_root_config(
        self,
        root_prefix: pathlib.PurePosixPath,
        expected_fqun: str | None = None,
    ) -> tuple[str, Mapping[str, pathlib.PurePosixPath]]:
        """Load project config for a root and register it.

        Returns (fqun, sub_root_mappings).
        """
        started_at = time.perf_counter_ns()
        try:
            return self._do_load_root_config(root_prefix, expected_fqun)
        finally:
            self.config_loading_time_ns += time.perf_counter_ns() - started_at

    def _do_load_root_config(
        self,
        root_prefix: pathlib.PurePosixPath,
        expected_fqun: str | None = None,
    ) -> tuple[str, Mapping[str, pathlib.PurePosixPath]]:
        """Load project config for a root and register it without timing side effects."""
        # TODO: When _path_tracker just stores Config objects, this
        # can just return a Config.
        existing = self._path_tracker.fqun_for_root(root_prefix)
        if existing is not None:
            if expected_fqun and existing != expected_fqun:
                raise exceptions.SubRootFqunMismatchError(
                    expected_fqun=expected_fqun,
                    actual_fqun=existing,
                    sub_root_path=str(root_prefix),
                )
            return existing, self._path_tracker.sub_roots_for(root_prefix)

        loader = config.ConfigLoader(root_prefix)
        loader.assert_is_project_root()
        project_config = loader.project_config()
        fqun = project_config.project.universe_name or ""
        if expected_fqun and fqun != expected_fqun:
            raise exceptions.SubRootFqunMismatchError(
                expected_fqun=expected_fqun,
                actual_fqun=fqun,
                sub_root_path=str(root_prefix),
            )
        existing_root = self._path_tracker.root_for_fqun(fqun)
        if existing_root is not None and existing_root != root_prefix:
            raise exceptions.DuplicateFqunError(
                fqun=fqun,
                existing_root=existing_root,
                new_root=root_prefix,
                config_subpath=config.CONFIG_PATH,
            )
        universe_locations = loader.local_deps_config()
        self._path_tracker.register_project_root(
            root_prefix,
            fqun,
            universe_locations,
        )
        return fqun, universe_locations


def _make_config_error_result(
    file_path: pathlib.PurePosixPath,
    root_prefix: pathlib.PurePosixPath,
    error: exceptions.ConfigError,
) -> validation_result.ValidationResult:
    """Create a ValidationResult for a config loading failure."""
    tracker = stats.ValidationStatsTracker()
    return validation_result.ValidationResult(
        exception=error,
        source=None,
        file_path=file_path,
        root_prefix=root_prefix,
        stats=tracker.build(),
        file_diagnostics=[],
        definition_results=[],
    )
