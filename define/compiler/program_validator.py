"""Parallel coordinator for multi-file Define program validation.

ProgramValidator orchestrates per-file validation using a thread pool.
It manages all shared state on the main thread and delegates pure
per-file validation to FileValidator workers.
"""

from __future__ import annotations

import typing
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping

from define.compiler import (
    config,
    constants,
    diagnostics,
    exceptions,
    file_validator,
    parser,
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

    def __init__(self, max_workers: int | None = None):
        """Initialize with pool configuration only — no side effects."""
        self._max_workers = max_workers
        self._submitted = []
        # Lark parsers are thread-safe, so we only need to construct one
        # (which is good because constructing it multiple times is
        #  slow---it has to read and parse the grammar file each time).
        self._fv = file_validator.FileValidator(parser.Parser())
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

        with _FileWorkPool(max_workers=max_workers) as pool:
            self._path_tracker.mark_in_progress(root_prefix / path)
            pool.submit(initial_context)
            while pool.has_pending():
                result = pool.wait_for_next()
                self._path_tracker.set_result(result.file_path, result)
                self._process_completed_result(result, pool)

        return self._path_tracker.completed_results()

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

            source_key, target_key = _edge_keys(ref_edge)
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

        _, target_key = _edge_keys(edge)
        target_has_match = any(
            d.fully_qualified_typed_name == target_key
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
            if expected_fqun is not None and existing != expected_fqun:
                raise exceptions.SubRootFqunMismatchError(
                    expected_fqun=expected_fqun,
                    actual_fqun=existing,
                    sub_root_path=str(root_prefix),
                )
            return existing, self._path_tracker.sub_roots_for(root_prefix)

        loader = config.ConfigLoader(root_prefix)
        loader.assert_is_project_root()
        project_config = loader.project_config()
        universe_locations = loader.local_deps_config()
        fqun = project_config.project.universe_name or ""
        if expected_fqun is not None and fqun != expected_fqun:
            raise exceptions.SubRootFqunMismatchError(
                expected_fqun=expected_fqun,
                actual_fqun=fqun,
                sub_root_path=str(root_prefix),
            )
        self._path_tracker.register_project_root(
            root_prefix,
            fqun,
            universe_locations,
        )
        return fqun, universe_locations


def _edge_keys(edge: validation_result.ReferenceEdge) -> tuple[str, str]:
    """Extract (source_key, target_key) from a reference edge."""
    source_key = edge.enclosing_definition.fully_qualified_typed_name
    ref = edge.global_name_reference
    if ref.global_name.fqun is None:
        target_key = ref.fully_qualified_typed_name(
            with_fqun=edge.enclosing_definition.name.fqun
        )
    else:
        target_key = ref.fully_qualified_typed_name()
    return source_key, target_key


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
