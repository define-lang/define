"""Parallel coordinator for multi-file Define program validation.

ProgramValidator orchestrates per-file validation using a thread pool.
It manages all shared state on the main thread and delegates pure
per-file validation to FileValidator workers.
"""

from __future__ import annotations

import typing
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import cached_property

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping

from define.compiler import (
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
class _DeferredEdge:
    """An edge waiting for its target file to complete validation."""

    edge: validation_result.ReferenceEdge
    source_result: validation_result.ValidationResult


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
        future = self._executor.submit(self._fv.validate_file, context)
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
    """

    _path_tracker: path_tracker.PathTracker[validation_result.ValidationResult]
    _reference_graph: reference_graph.ReferenceGraph
    _deferred_edges: dict[pathlib.PurePosixPath, list[_DeferredEdge]]

    def __init__(self):
        """Initialize coordinator state for one program validation."""
        self._path_tracker = path_tracker.PathTracker()
        self._reference_graph = reference_graph.ReferenceGraph()
        self._deferred_edges = {}

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
        self._submit_discovered_files(result, pool)
        self._process_reference_edges(result.root_prefix, result)
        self._resolve_deferred_edges_for(result.file_path)

    def _submit_discovered_files(
        self,
        result: validation_result.ValidationResult,
        pool: _FileWorkPool,
    ):
        """Submit discovered files if not already tracked."""
        for discovered in result.discovered_files:
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
                result.diagnostics.append(
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
        if not result.discovered_files:
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
        resolved_discoveries: list[validation_result.DiscoveredFile] = []
        unknown_fquns: set[str] = set()
        for discovered in result.discovered_files:
            sub_root_rel = sub_root_mappings.get(discovered.expected_fqun)
            if sub_root_rel is None:
                if discovered.expected_fqun in unknown_fquns:
                    continue
                unknown_fquns.add(discovered.expected_fqun)
                result.diagnostics.append(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        position=discovered.position,
                        universe=discovered.expected_fqun,
                        current_universe_name=current_fqun,
                    )
                )
                continue
            discovered.root_prefix = constants.PROJECT_ROOT / sub_root_rel
            resolved_discoveries.append(discovered)
        result.discovered_files = resolved_discoveries

        # In a filesystem context, we don't return reference edges for
        # unknown sub-roots, so we are keeping that behavior consistent
        # in a non-filesystem context.
        result.reference_edges = [
            ref_edge
            for ref_edge in result.reference_edges
            if (
                ref_edge.global_name_reference.global_name.fqun is None
                or ref_edge.global_name_reference.global_name.fqun.canonical
                not in unknown_fquns
            )
        ]

    def _load_config_in_non_filesystem_context(
        self,
        result: validation_result.ValidationResult,
    ) -> tuple[str, Mapping[str, pathlib.PurePosixPath]] | tuple[None, None]:
        """Load root config and map loading errors to non-filesystem diagnostics."""
        first_discovered = result.discovered_files[0]
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except exceptions.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    position=first_discovered.position,
                    universe=first_discovered.expected_fqun,
                    config_path=str(e.config_path),
                )
            )
            return (None, None)
        except exceptions.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.diagnostics.append(
                diagnostics.ConfigLoadErrorDiagnostic(
                    position=first_discovered.position,
                    error=e,
                )
            )
            return (None, None)

    def _process_reference_edges(
        self,
        enclosing_root: pathlib.PurePosixPath,
        result: validation_result.ValidationResult,
    ):
        """Try to add edges to the reference graph and validate resolved ones."""
        for ref_edge in result.reference_edges:
            target_file = self._resolve_target_file(ref_edge, enclosing_root)
            if self._path_tracker.is_under_failed_root(target_file):
                continue

            source_key = ref_edge.enclosing_definition.fully_qualified_typed_name
            target_key = ref_edge.fully_qualified_typed_name
            detected = self._reference_graph.try_add_edge(source_key, target_key)
            if detected is not None:
                result.diagnostics.append(
                    diagnostics.CircularGlobalReferenceDiagnostic(
                        position=ref_edge.global_name_reference.position,
                        cycle=detected.path,
                    )
                )
                continue
            if self._check_if_current_universe_path_in_a_subroot(
                ref_edge, target_file, enclosing_root, result
            ):
                continue

            #  With the thread pool, files complete in arbitrary order. If files A
            #  and C both reference file B, and B finishes before A's results are
            #  processed, then target_result is already available when processing
            #  A's edges.
            target_result = self._path_tracker.try_get_result(target_file)
            if target_result is not None:
                self._validate_reference_against_target(
                    ref_edge, target_file, target_result, result
                )
            else:
                self._deferred_edges.setdefault(target_file, []).append(
                    _DeferredEdge(edge=ref_edge, source_result=result)
                )

    def _resolve_target_file(
        self,
        edge: validation_result.ReferenceEdge,
        enclosing_root: pathlib.PurePosixPath,
    ) -> pathlib.PurePosixPath:
        """Determine the full file path for a reference edge's target."""
        global_name = edge.global_name_reference.global_name

        # A reference to another universe, so we need its full sub-root path.
        if global_name.fqun is not None:
            fqun_string = global_name.fqun.canonical
            sub_root_loc = self._path_tracker.sub_root_location(
                fqun_string, enclosing_root
            )
            sub_root_path = enclosing_root / sub_root_loc
            return global_name.path.file_path(sub_root_path)

        return global_name.path.file_path(enclosing_root)

    def _check_if_current_universe_path_in_a_subroot(
        self,
        edge: validation_result.ReferenceEdge,
        target_file: pathlib.PurePosixPath,
        enclosing_root: pathlib.PurePosixPath,
        source_result: validation_result.ValidationResult,
    ) -> bool:
        """Check if a same-universe reference lands inside another universe's sub-root.

        Returns True (and appends a diagnostic) when the edge should be skipped.
        """
        # This check is only for current-universe references.
        if edge.global_name_reference.global_name.fqun is not None:
            return False

        actual_root = self._path_tracker.find_enclosing_root(target_file)
        if actual_root == enclosing_root:
            return False

        source_result.diagnostics.append(
            diagnostics.PathInsideOtherUniverseDiagnostic(
                position=edge.global_name_reference.global_name.position,
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
        source_result: validation_result.ValidationResult,
    ):
        """Validate a reference edge against a completed target file's result."""
        global_name = edge.global_name_reference.global_name

        if isinstance(target_result.exception, exceptions.SourceFileNotFoundError):
            source_result.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    position=global_name.position,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return

        target_has_match = any(
            d.fully_qualified_typed_name == edge.fully_qualified_typed_name
            for d in target_result.definitions
        )
        if not target_has_match:
            source_result.diagnostics.append(
                diagnostics.ReferencedGlobalNameWrongTypeDiagnostic(
                    position=global_name.position,
                    path=global_name.path.name,
                    expected_type=edge.global_name_reference.type_name.value,
                )
            )

    def _resolve_deferred_edges_for(self, completed_file: pathlib.PurePosixPath):
        """Validate deferred edges that were waiting for this file to complete."""
        deferred = self._deferred_edges.pop(completed_file, [])
        target_result = self._path_tracker.get_result(completed_file)
        for deferred_edge in deferred:
            self._validate_reference_against_target(
                deferred_edge.edge,
                completed_file,
                target_result,
                deferred_edge.source_result,
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
            source_result.diagnostics.append(
                diagnostics.SubRootAlreadyOccupiedDiagnostic(
                    position=discovered.position,
                    universe=discovered.expected_fqun,
                    sub_root_path=str(discovered.root_prefix),
                    existing_file=str(conflicting_path),
                    existing_universe=existing_universe or "",
                )
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
        diagnostics=[],
        exception=error,
        source=None,
        file_path=file_path,
        root_prefix=root_prefix,
        stats=tracker.build(),
    )
