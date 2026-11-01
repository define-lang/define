"""Resolution of global name references to the files that hold their definitions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import config, constants
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.errors import diagnostics, exceptions
from define.compiler.validator import validation_result
from define.compiler.validator.structural import file_validator, path_tracker

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Container

    from define.compiler import ast
    from define.compiler.graphs import reference_graph
    from define.compiler.validator.structural import work_pool


class _DeferredReferenceEdge(msgspec.Struct):
    """An edge waiting for its target file to complete validation."""

    edge: reference_graph.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


@typing.final
class ReferenceResolver:
    """Finds the files that hold referenced definitions, loading each file once.

    Owns the project roots and their configs, and reports the diagnostics for
    references that cannot reach a definition. Only the coordinator thread may
    use it.
    """

    _path_tracker: path_tracker.PathTracker[validation_result.FileValidationResult]
    _deferred_edges: dict[define_path.DefinePath, list[_DeferredReferenceEdge]]
    _file_validator: file_validator.FileStructuralValidator
    _handle_validated_file: Callable[[validation_result.FileValidationResult], None]
    # The definitions from the supplied source of a non-filesystem program,
    # which no file holds.
    _source_definitions: typed_name_dict.TypedNameDict[
        ast.GlobalTypedNameInDefinition, None
    ]
    _registered_definitions: Container[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    ]

    def __init__(
        self,
        *,
        handle_validated_file: Callable[[validation_result.FileValidationResult], None],
        registered_definitions: Container[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
        ],
    ):
        """Initialize with the callback for validated files and the names of the definitions registered so far."""
        self._path_tracker = path_tracker.PathTracker()
        self._deferred_edges = {}
        self._file_validator = file_validator.FileStructuralValidator()
        self._handle_validated_file = handle_validated_file
        self._source_definitions = typed_name_dict.TypedNameDict()
        self._registered_definitions = registered_definitions

    def entry_file_context(
        self, path: pathlib.PurePosixPath
    ) -> file_validator.FileValidationContext | None:
        """Return the context for validating the program's entry file.

        If the entry file's project config fails to load, records the failure
        as the entry file's result and returns None.
        """
        root_prefix = constants.PROJECT_ROOT
        full_path = root_prefix / define_path.DefinePathFromPosix(path)
        try:
            root_config = self._load_root_config(root_prefix)
        except config.ConfigError as e:
            self._path_tracker.set_result(
                full_path, _make_config_error_result(full_path, root_prefix, e)
            )
            return None
        return file_validator.FileValidationContext(
            file_path=define_path.DefinePathFromPosix(path),
            root_prefix=root_prefix,
            root_config=root_config,
        )

    def submit_entry_file(
        self, context: file_validator.FileValidationContext, pool: work_pool.WorkPool
    ):
        """Submit the program's entry file for validation."""
        self._path_tracker.mark_in_progress(context.full_path)
        self._submit_file(context, pool)

    def add_source_result(self, result: validation_result.FileValidationResult):
        """Record the result of validating the supplied source of a non-filesystem program."""
        # The non-filesystem entry result lives in _results only — it isn't
        # added to _tracked_files because its file_path is the InvalidDefinePath
        # sentinel, which doesn't have segments. _tracked_files is only used
        # for filesystem-prefix queries, so omitting it is harmless.
        self._path_tracker.set_result(result.file_path, result)
        for definition_result in result.definition_results:
            self._source_definitions[definition_result.definition.typed_name] = None

    def completed_file_results(self) -> list[validation_result.FileValidationResult]:
        """Return the results of every file that completed validation."""
        return self._path_tracker.completed_results()

    def find_referenced_definition(
        self,
        edge: reference_graph.ReferenceEdge,
        target_file: define_path.DefinePath,
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ):
        """Report a diagnostic if an edge's target file cannot have its definition.

        The check waits until the target file completes validation.
        """
        if self._check_if_current_universe_path_in_a_subroot(
            edge, target_file, enclosing_root, source_definition
        ):
            return

        # With the thread pool, files complete in arbitrary order. If files
        # A and C both reference file B, and B finishes before A's results
        # are processed, then target_result is already available when
        # processing A's edges.
        target_result = self._path_tracker.try_get_result(target_file)
        if target_result is not None:
            self._validate_reference_against_target(
                edge,
                target_file,
                target_result,
                source_definition,
            )
        else:
            self._deferred_edges.setdefault(target_file, []).append(
                _DeferredReferenceEdge(edge, source_definition)
            )

    def _submit_file(
        self, context: file_validator.FileValidationContext, pool: work_pool.WorkPool
    ):
        pool.submit(
            self._file_validator.validate_file,
            context,
            handle_result=self._process_validated_file,
        )

    def _process_validated_file(
        self,
        result: validation_result.FileValidationResult,
        pool: work_pool.WorkPool,
    ):
        self._path_tracker.set_result(result.file_path, result)
        # We always want to submit referenced files first, to get background
        # work into the queue ASAP.
        for edge in result.edges_to_other_files():
            if edge.global_name_reference in self._source_definitions:
                continue
            self._submit_referenced_file_from_configured_root(result, edge, pool)
        self._handle_validated_file(result)
        # Reference edges are file-scoped, but validating them still depends on
        # this file's definitions already being registered so wrong-type checks
        # don't race ahead of the completed file's real contents.
        self._validate_incoming_reference_edges(result.file_path)

    def _submit_referenced_file_from_configured_root(
        self,
        result: validation_result.FileValidationResult,
        edge: reference_graph.ReferenceEdge,
        pool: work_pool.WorkPool,
    ):
        """Submit a referenced file using its source project's loaded config."""
        # Edges with an explicit FQUN only exist when file validation found the
        # FQUN in the enclosing root's local deps, or when the universe needs
        # no configuration, so the universe always has a root.
        root_prefix = typing.cast(
            "define_path.DefinePath",
            self._path_tracker.universe_root(
                edge.global_name_reference.name_content.source_fqun,
                result.root_prefix,
            ),
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
        pool: work_pool.WorkPool,
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
            result.file_diagnostics.append(
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
        self._submit_file(context, pool)

    def resolve_non_filesystem_references(
        self,
        result: validation_result.FileValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Load project config if necessary, and submit referenced files."""
        first_edge: reference_graph.ReferenceEdge | None = None
        for edge in result.first_edge_per_referenced_file():
            if _needs_configuration(edge):
                if first_edge is None:
                    first_edge = edge
            else:
                self._submit_referenced_file_from_configured_root(result, edge, pool)
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
        pool: work_pool.WorkPool,
    ):
        """Resolve references in non-filesystem mode after config load."""
        unknown_fquns: set[str] = set()
        for edge in result.first_edge_per_referenced_file():
            # Files in universes that need no configuration were already
            # submitted.
            if not _needs_configuration(edge):
                continue
            global_name = edge.global_name_reference.name_content
            fqun = global_name.source_fqun
            if fqun is not None and fqun not in root_config.sub_roots:
                if fqun in unknown_fquns:
                    continue
                unknown_fquns.add(fqun)
                result.file_diagnostics.append(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        location=global_name.location,
                        universe=fqun,
                        current_universe_name=root_config.fqun,
                    )
                )
                continue
            self._submit_referenced_file_from_configured_root(result, edge, pool)

        # In a filesystem context, we don't return reference edges for
        # unknown sub-roots, so we are keeping that behavior consistent
        # in a non-filesystem context.
        for definition_result in result.definition_results:
            definition_result.reference_edges = [
                ref_edge
                for ref_edge in definition_result.reference_edges
                if ref_edge.global_name_reference.name_content.source_fqun
                not in unknown_fquns
            ]

    @staticmethod
    def _strip_cross_universe_refs(
        result: validation_result.FileValidationResult,
    ):
        """Strip cross-universe edges after total config failure.

        When root config loading fails entirely, every cross-universe FQUN is
        unresolvable. Same-universe edges are kept so that same-file validation
        (e.g. cycle detection) still runs, and so are edges to universes that
        need no configuration.
        """
        for definition_result in result.definition_results:
            definition_result.reference_edges = [
                ref_edge
                for ref_edge in definition_result.reference_edges
                if ref_edge.global_name_reference.name_content.fqun is None
                or not _needs_configuration(ref_edge)
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
            result.file_diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=global_name.location,
                    universe=first_edge.global_name_reference.effective_fqun.canonical,
                    config_path=str(e.config_path),
                )
            )
            return None
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            result.file_diagnostics.append(
                diagnostics.ConfigLoadErrorDiagnostic(
                    location=global_name.location,
                    error=e,
                )
            )
            return None

    def resolve_target_file(
        self,
        global_name: ast.ReferenceGlobalNameContent,
        enclosing_root: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> define_path.DefinePath | None:
        """Determine the full file path for a global name reference.

        Returns None if the target is under a failed or nonexistent root.
        """
        universe_root = self._path_tracker.universe_root(
            global_name.source_fqun, enclosing_root
        )
        if universe_root is None:
            fqun = typing.cast("ast.Fqun", global_name.fqun)
            source_definition.diagnostics.append(
                diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                    location=fqun.location,
                    universe=fqun.canonical,
                    current_universe_name=self._path_tracker.fqun_for_root(
                        enclosing_root
                    )
                    or "",
                )
            )
            return None
        target_file = global_name.path.file_path(universe_root)
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

        source_definition.diagnostics.append(
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

        # A standard universe file is not in the project, so naming it would
        # not help.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if (
            self._path_tracker.find_enclosing_root(target_file)
            == constants.STANDARD_LIBRARY_ROOT
        ):
            if isinstance(target_result.exception, exceptions.SourceFileNotFoundError):
                self._path_tracker.mark_not_found(target_file)
            elif edge.global_name_reference in self._registered_definitions:
                return
            source_definition.diagnostics.append(
                diagnostics.StandardDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return

        if isinstance(target_result.exception, exceptions.SourceFileNotFoundError):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return

        if edge.global_name_reference not in self._registered_definitions:
            source_definition.diagnostics.append(
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
        # path or might be missing entirely. Since the work pool completes
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
            source_result.file_diagnostics.append(
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
        existing = self._path_tracker.config_for_root(root_prefix)
        if existing is not None:
            if expected_fqun and existing.fqun != expected_fqun:
                raise config.SubRootFqunMismatchError(
                    expected_fqun=expected_fqun,
                    actual_fqun=existing.fqun,
                    sub_root_path=str(root_prefix),
                )
            return existing

        # The standard universe ships with the compiler, so its root has no
        # config file.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if root_prefix == constants.STANDARD_LIBRARY_ROOT:
            root_config = config.ProjectRootConfig(
                fqun=constants.STANDARD_UNIVERSE, sub_roots={}
            )
        else:
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


def _needs_configuration(edge: reference_graph.ReferenceEdge) -> bool:
    """Whether a project must configure the referenced universe before resolving the reference."""
    return config.universe_needs_configuration(
        edge.global_name_reference.effective_fqun.canonical
    )


def _make_config_error_result(
    file_path: define_path.DefinePath,
    root_prefix: define_path.DefinePath,
    error: config.ConfigError,
) -> validation_result.FileValidationResult:
    """Create a FileValidationResult for a config loading failure."""
    return validation_result.FileValidationResult(
        exception=error,
        source_digest=None,
        file_path=file_path,
        root_prefix=root_prefix,
        file_diagnostics=[],
        definition_results=[],
    )
