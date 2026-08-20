"""Parallel coordinator for multi-file Define program validation.

ProgramStructuralValidator orchestrates per-file validation using a thread pool.
It manages all shared state on the main thread and delegates pure
per-file validation to FileStructuralValidator workers.
"""

from __future__ import annotations

import queue
import time
import typing
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    import pathlib

from define.compiler import (
    ast,
    config,
    constants,
    diagnostics,
    exceptions,
    parser,
)
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.graphs import reference_graph
from define.compiler.validator import stats, validation_result
from define.compiler.validator.structural import file_validator, path_tracker


@dataclass
class _DeferredReferenceEdge:
    """An edge waiting for its target file to complete validation."""

    edge: reference_graph.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


class _FileWorkPool:
    """Manages a thread pool for parallel file validation."""

    _pending: int
    _completed: queue.SimpleQueue[Future[validation_result.FileValidationResult]]
    _executor: ThreadPoolExecutor
    _fv: file_validator.FileStructuralValidator

    def __init__(
        self,
        parser_instance: parser.Parser,
        max_workers: int | None = None,
    ):
        """Initialize with pool configuration only — no side effects."""
        self._pending = 0
        self._completed = queue.SimpleQueue()
        self._fv = file_validator.FileStructuralValidator(parser_instance)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object):
        self._executor.shutdown(wait=True)

    def submit(self, context: file_validator.FileValidationContext):
        """Submit a file for validation. Starts immediately on a worker thread."""
        submitted_at = time.perf_counter_ns()

        def _validate() -> validation_result.FileValidationResult:
            started_at = time.perf_counter_ns()
            result = self._fv.validate_file(context)
            result.stats.queue_wait = started_at - submitted_at
            return result

        future = self._executor.submit(_validate)
        self._pending += 1
        # add_done_callback pushes from the worker thread the moment a file
        # finishes, so no completion waits on another one and collecting a
        # completion costs O(1). Scanning every still-pending future instead
        # made the coordinator quadratic in the number of files in the program.
        future.add_done_callback(self._completed.put)

    def wait_for_next(self) -> validation_result.FileValidationResult:
        """Block until the next file completes."""
        if not self._pending:
            raise RuntimeError("wait_for_next called with no pending futures")
        future = self._completed.get()
        self._pending -= 1
        return future.result()

    def has_pending(self) -> bool:
        """Return True if there are submitted files not yet collected."""
        return self._pending > 0


class ProgramStructuralValidator:
    """Coordinates parallel validation of a Define program.

    Runs a single-threaded coordinator loop that submits files to a thread
    pool and processes results as they complete. All shared state is
    managed on the coordinator thread.

    config_loading_time_ns stores program-level config loading time.
    """

    _parser: parser.Parser
    _path_tracker: path_tracker.PathTracker[validation_result.FileValidationResult]
    _reference_graph: reference_graph.ReferenceGraph
    _deferred_edges: dict[define_path.DefinePath, list[_DeferredReferenceEdge]]
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _config_loading_time_ns: int

    def __init__(self, parser_instance: parser.Parser | None = None):
        """Initialize coordinator state for one program validation.

        If parser_instance is provided, it will be used instead of
        constructing a new one. This is only a performance optimization
        that avoids reconstructing the Lark grammar on each validation.
        """
        # Lark parsers are thread-safe, so sharing one instance is safe.
        self._parser = parser_instance or parser.Parser()
        self._path_tracker = path_tracker.PathTracker()
        self._reference_graph = reference_graph.ReferenceGraph()
        self._deferred_edges = {}
        self._definition_results = typed_name_dict.TypedNameDict()
        self._config_loading_time_ns = 0

    def validate_program(
        self,
        path: pathlib.PurePosixPath,
        max_workers: int | None = None,
    ) -> validation_result.ProgramValidationResult:
        """Validate a program starting from the given file path."""
        root_prefix = constants.PROJECT_ROOT
        path_dp = define_path.DefinePathFromPosix(path)
        try:
            root_config = self._load_root_config(root_prefix)
        except config.ConfigError as e:
            return self._build_program_result(
                [_make_config_error_result(root_prefix / path_dp, root_prefix, e)]
            )

        initial_context = file_validator.FileValidationContext(
            file_path=path_dp,
            root_prefix=root_prefix,
            root_config=root_config,
        )

        with _FileWorkPool(self._parser, max_workers=max_workers) as pool:
            self._path_tracker.mark_in_progress(root_prefix / path_dp)
            pool.submit(initial_context)
            self._run_pool_loop(pool)

        return self._build_program_result(self._path_tracker.completed_results())

    def validate_program_non_filesystem(
        self,
        source: str,
        max_workers: int | None = None,
    ) -> validation_result.ProgramValidationResult:
        """Validate a program from source text, loading config only when needed."""
        result = file_validator.FileStructuralValidator(self._parser).validate_source(
            source
        )
        if result.exception is not None:
            return self._build_program_result([result])

        # The non-filesystem entry result lives in _results only — it isn't
        # added to _tracked_files because its file_path is the InvalidDefinePath
        # sentinel, which doesn't have segments. _tracked_files is only used
        # for filesystem-prefix queries, so omitting it is harmless.
        self._path_tracker.set_result(result.file_path, result)

        with _FileWorkPool(self._parser, max_workers=max_workers) as pool:
            self._resolve_non_filesystem_references(result, pool)
            self._process_completed_result(result, pool, submit_referenced_files=False)
            self._run_pool_loop(pool)
        return self._build_program_result(self._path_tracker.completed_results())

    def _build_program_result(
        self,
        file_results: list[validation_result.FileValidationResult],
    ) -> validation_result.ProgramValidationResult:
        """Wrap file results into a ProgramValidationResult."""
        # The completed ReferenceGraph replaces these structural-only edges;
        # retaining both would duplicate per-reference state during later stages.
        for file_result in file_results:
            for definition_result in file_result.definition_results:
                definition_result.reference_edges.clear()
        return validation_result.ProgramValidationResult(
            file_results=file_results,
            config_loading_time_ns=self._config_loading_time_ns,
            reference_graph=self._reference_graph,
            definition_results=self._definition_results,
        )

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
        result: validation_result.FileValidationResult,
        pool: _FileWorkPool,
        *,
        submit_referenced_files: bool = True,
    ):
        """Handle a completed file: check edges, submit referenced files."""
        started_at = time.perf_counter_ns()
        # We always want to submit referenced files first, to get background
        # work into the queue ASAP.
        if submit_referenced_files:
            for edge in result.edges_to_other_files():
                self._submit_filesystem_referenced_file(result, edge, pool)
        for definition_result in result.definition_results:
            self._process_completed_definition(result, definition_result)
        # Reference edges are file-scoped, but validating them still depends on
        # this file's definitions already being registered so wrong-type checks
        # don't race ahead of the completed file's real contents.
        self._validate_incoming_reference_edges(result.file_path)
        result.stats.global_validation += time.perf_counter_ns() - started_at

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

    def _submit_filesystem_referenced_file(
        self,
        result: validation_result.FileValidationResult,
        edge: reference_graph.ReferenceEdge,
        pool: _FileWorkPool,
    ):
        """Submit the file an edge references from a filesystem-context file."""
        global_name = edge.global_name_reference.name_content
        if global_name.fqun is None:
            root_prefix = result.root_prefix
        else:
            # Edges with an explicit FQUN only exist when file validation
            # found the FQUN in the enclosing root's local deps, so this
            # lookup cannot fail.
            root_prefix = result.root_prefix / self._path_tracker.sub_root_location(
                global_name.fqun.canonical, result.root_prefix
            )
        self._submit_referenced_file(
            result=result,
            edge=edge,
            root_prefix=root_prefix,
            pool=pool,
        )

    def _submit_referenced_file(
        self,
        result: validation_result.FileValidationResult,
        edge: reference_graph.ReferenceEdge,
        root_prefix: define_path.DefinePath,
        pool: _FileWorkPool,
    ):
        """Submit an edge's referenced file if not already tracked."""
        global_name = edge.global_name_reference.name_content
        file_path = global_name.path.file_path()
        full_path = root_prefix / file_path
        if self._path_tracker.is_tracked(full_path):
            return
        if self._path_tracker.is_under_failed_root(full_path):
            return

        self._check_existing_root_conflicts_for_first_subroot_load(
            root_prefix=root_prefix,
            global_name_reference=edge.global_name_reference,
            source_result=result,
        )

        try:
            root_config = self._load_root_config(
                root_prefix, edge.global_name_reference.effective_fqun.canonical
            )
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(root_prefix)
            result.add_file_diagnostic(
                diagnostics.ConfigLoadErrorDiagnostic(
                    location=global_name.location,
                    error=e,
                )
            )
            return

        context = file_validator.FileValidationContext(
            file_path=file_path,
            root_prefix=root_prefix,
            root_config=root_config,
        )
        self._path_tracker.mark_in_progress(full_path)
        pool.submit(context)

    def _resolve_non_filesystem_references(
        self,
        result: validation_result.FileValidationResult,
        pool: _FileWorkPool,
    ):
        """Load project config if necessary, and submit referenced files."""
        first_edge = result.first_edge_to_other_file()
        if first_edge is None:
            return

        root_config = self._load_config_in_non_filesystem_context(result, first_edge)
        if root_config is None:
            self._strip_cross_universe_refs(result)
            return
        self._resolve_non_filesystem_references_with_config(
            result=result,
            root_config=root_config,
            pool=pool,
        )

    def _resolve_non_filesystem_references_with_config(
        self,
        result: validation_result.FileValidationResult,
        root_config: config.ProjectRootConfig,
        pool: _FileWorkPool,
    ):
        """Resolve references in non-filesystem mode after config load."""
        unknown_fquns: set[str] = set()
        for edge in result.first_edge_per_referenced_file():
            expected_fqun = edge.global_name_reference.effective_fqun.canonical
            sub_root_rel = root_config.sub_roots.get(expected_fqun)
            if sub_root_rel is None:
                if expected_fqun in unknown_fquns:
                    continue
                unknown_fquns.add(expected_fqun)
                global_name = edge.global_name_reference.name_content
                result.add_file_diagnostic(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        location=global_name.location,
                        universe=expected_fqun,
                        current_universe_name=root_config.fqun,
                    )
                )
                continue
            self._submit_referenced_file(
                result=result,
                edge=edge,
                root_prefix=result.root_prefix / sub_root_rel,
                pool=pool,
            )

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

    def _strip_cross_universe_refs(
        self,
        result: validation_result.FileValidationResult,
    ):
        """Strip cross-universe edges after total config failure.

        When root config loading fails entirely, every cross-universe FQUN is
        unresolvable. Same-universe edges are kept so that same-file validation
        (e.g. cycle detection) still runs.
        """
        for definition_result in result.definition_results:
            definition_result.reference_edges = [
                ref_edge
                for ref_edge in definition_result.reference_edges
                if ref_edge.global_name_reference.name_content.fqun is None
            ]

    def _load_config_in_non_filesystem_context(
        self,
        result: validation_result.FileValidationResult,
        first_edge: reference_graph.ReferenceEdge,
    ) -> config.ProjectRootConfig | None:
        """Load root config and map loading errors to non-filesystem diagnostics."""
        global_name = first_edge.global_name_reference.name_content
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except config.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.add_file_diagnostic(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=global_name.location,
                    universe=first_edge.global_name_reference.effective_fqun.canonical,
                    config_path=str(e.config_path),
                )
            )
            return None
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.add_file_diagnostic(
                diagnostics.ConfigLoadErrorDiagnostic(
                    location=global_name.location,
                    error=e,
                )
            )
            return None

    def _validate_outgoing_reference_edges(
        self,
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Try to add edges to the reference graph, validate targets we already know about, and enqueue those we don't."""
        for ref_edge in source_definition.reference_edges:
            target_file = self._resolve_target_file(
                ref_edge.global_name_reference.name_content,
                enclosing_root,
                source_definition,
            )
            if target_file is None:
                continue

            detected = self._reference_graph.try_add_edge(ref_edge)
            if detected is not None:
                source_definition.add_diagnostic(
                    diagnostics.CircularGlobalReferenceDiagnostic(
                        location=ref_edge.global_name_reference.location,
                        cycle=detected,
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
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> define_path.DefinePath | None:
        """Determine the full file path for a global name reference.

        Returns None if the target is under a failed or nonexistent root.
        """
        if global_name.fqun is None:
            return global_name.path.file_path(enclosing_root)

        fqun_string = global_name.fqun.canonical
        if not self._path_tracker.has_sub_root(fqun_string, enclosing_root):
            source_definition.add_diagnostic(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    location=global_name.fqun.location,
                    universe=fqun_string,
                    current_universe_name=self._path_tracker.fqun_for_root(
                        enclosing_root
                    )
                    or "",
                )
            )
            return None
        sub_root_loc = self._path_tracker.sub_root_location(fqun_string, enclosing_root)
        sub_root_path = enclosing_root / sub_root_loc
        target_file = global_name.path.file_path(sub_root_path)
        if self._path_tracker.is_under_failed_root(target_file):
            return None
        return target_file

    def _check_if_current_universe_path_in_a_subroot(
        self,
        edge: reference_graph.ReferenceEdge,
        target_file: define_path.DefinePath,
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        """Check if a same-universe reference lands inside another universe's sub-root.

        Returns True (and appends a diagnostic) when the edge should be skipped.
        """
        # This check is only for current-universe references.
        if edge.global_name_reference.name_content.fqun is not None:
            return False

        # When config failed to load, we have no sub-root information to check
        # against. This happens in non-filesystem mode when the root project
        # config is missing.
        if not self._path_tracker.project_root_loaded(enclosing_root):
            return False

        actual_root = self._path_tracker.find_enclosing_root(target_file)
        if actual_root == enclosing_root:
            return False

        source_definition.add_diagnostic(
            diagnostics.PathInsideOtherUniverseDiagnostic(
                location=edge.global_name_reference.name_content.location,
                path=str(target_file),
                other_universe=self._path_tracker.fqun_for_root(actual_root) or "",
                sub_root_path=str(actual_root),
            )
        )
        return True

    def _validate_reference_against_target(
        self,
        edge: reference_graph.ReferenceEdge,
        target_file: define_path.DefinePath,
        target_result: validation_result.FileValidationResult,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Validate a reference edge against a completed target file's result."""
        global_name = edge.global_name_reference.name_content

        if isinstance(target_result.exception, exceptions.SourceFileNotFoundError):
            source_definition.add_diagnostic(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return

        if edge.global_name_reference not in self._definition_results:
            source_definition.add_diagnostic(
                diagnostics.ReferencedDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )

    def _validate_incoming_reference_edges(
        self, completed_file: define_path.DefinePath
    ):
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

    def _check_existing_root_conflicts_for_first_subroot_load(
        self,
        root_prefix: define_path.DefinePath,
        global_name_reference: ast.GlobalTypedNameReference,
        source_result: validation_result.FileValidationResult,
    ):
        """Check SubRootAlreadyOccupied for referenced files entering a new sub-root."""
        if self._path_tracker.project_root_loaded(root_prefix):
            return

        conflicting_path, existing_universe = (
            self._path_tracker.first_tracked_file_under(root_prefix)
        )
        if conflicting_path is not None:
            source_result.add_file_diagnostic(
                diagnostics.SubRootAlreadyOccupiedDiagnostic(
                    location=global_name_reference.name_content.location,
                    universe=global_name_reference.effective_fqun.canonical,
                    sub_root_path=str(root_prefix),
                    existing_file=str(conflicting_path),
                    existing_universe=existing_universe or "",
                )
            )

    def _load_root_config(
        self,
        root_prefix: define_path.DefinePath,
        expected_fqun: str | None = None,
    ) -> config.ProjectRootConfig:
        """Load project config for a root and register it."""
        started_at = time.perf_counter_ns()
        try:
            return self._do_load_root_config(root_prefix, expected_fqun)
        finally:
            self._config_loading_time_ns += time.perf_counter_ns() - started_at

    def _do_load_root_config(
        self,
        root_prefix: define_path.DefinePath,
        expected_fqun: str | None = None,
    ) -> config.ProjectRootConfig:
        """Load project config for a root and register it without timing side effects."""
        existing = self._path_tracker.config_for_root(root_prefix)
        if existing is not None:
            if expected_fqun and existing.fqun != expected_fqun:
                raise config.SubRootFqunMismatchError(
                    expected_fqun=expected_fqun,
                    actual_fqun=existing.fqun,
                    sub_root_path=str(root_prefix),
                )
            return existing

        root_config = config.ConfigLoader(root_prefix).load_project_root_config(
            expected_fqun
        )
        existing_root = self._path_tracker.root_for_fqun(root_config.fqun)
        if existing_root is not None and existing_root != root_prefix:
            raise config.DuplicateFqunError(
                fqun=root_config.fqun,
                existing_root=existing_root,
                new_root=root_prefix,
                config_subpath=config.CONFIG_PATH,
            )
        self._path_tracker.register_project_root(root_prefix, root_config)
        return root_config


def _make_config_error_result(
    file_path: define_path.DefinePath,
    root_prefix: define_path.DefinePath,
    error: config.ConfigError,
) -> validation_result.FileValidationResult:
    """Create a FileValidationResult for a config loading failure."""
    tracker = stats.ValidationStatsTracker()
    return validation_result.FileValidationResult(
        exception=error,
        source_lines=None,
        file_path=file_path,
        root_prefix=root_prefix,
        stats=tracker.build(),
        file_diagnostics=[],
        definition_results=[],
    )
