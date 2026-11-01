"""Resolution of global name references to the files that hold their definitions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import config, constants
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.errors import diagnostics, exceptions
from define.compiler.validator.structural import file_validator, path_tracker

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Iterator

    from define.compiler import ast
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import work_pool


class _DeferredReferenceEdge(msgspec.Struct):
    """An edge waiting for its target file to finish loading."""

    edge: reference_graph.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


@typing.final
class ReferenceResolver:
    """Finds the files that hold referenced definitions, loading each file once.

    Owns the project roots and their configs, and reports the diagnostics for
    references that cannot reach a definition. Only the coordinator thread may
    use it.
    """

    _path_tracker: path_tracker.PathTracker[file_validator.LoadedFile]
    _deferred_edges: dict[define_path.DefinePath, list[_DeferredReferenceEdge]]
    _file_validator: file_validator.FileStructuralValidator
    _handle_referenced_definition: Callable[
        [file_validator.LoadedFile, ast.GlobalDefinition, work_pool.WorkPool], None
    ]
    # The supplied source of a non-filesystem program, which no file holds.
    _source_file: file_validator.LoadedFile | None

    def __init__(
        self,
        *,
        handle_referenced_definition: Callable[
            [file_validator.LoadedFile, ast.GlobalDefinition, work_pool.WorkPool],
            None,
        ],
    ):
        """Initialize with the callback that receives each definition a reference reaches."""
        self._path_tracker = path_tracker.PathTracker()
        self._deferred_edges = {}
        self._file_validator = file_validator.FileStructuralValidator()
        self._handle_referenced_definition = handle_referenced_definition
        self._source_file = None

    def load_entry_file(
        self, path: pathlib.PurePosixPath
    ) -> file_validator.LoadedFile | None:
        """Load the program's entry file.

        If the entry file's project config fails to load, records the failure
        as the entry file's result and returns None.
        """
        root_prefix = constants.PROJECT_ROOT
        file_path = define_path.DefinePathFromPosix(path)
        full_path = root_prefix / file_path
        try:
            root_config = self._load_root_config(root_prefix)
        except config.ConfigError as e:
            self._path_tracker.set_result(
                full_path, _make_config_error_file(file_path, root_prefix, e)
            )
            return None
        entry_file = self._file_validator.load_file(
            file_validator.FileValidationContext(
                file_path=file_path,
                root_prefix=root_prefix,
                root_config=root_config,
            )
        )
        self._path_tracker.mark_in_progress(full_path)
        self._path_tracker.set_result(full_path, entry_file)
        return entry_file

    def add_source_file(self, source_file: file_validator.LoadedFile):
        """Record the supplied source of a non-filesystem program."""
        # The non-filesystem entry result lives in _results only — it isn't
        # added to _tracked_files because its file_path is the InvalidDefinePath
        # sentinel, which doesn't have segments. _tracked_files is only used
        # for filesystem-prefix queries, so omitting it is harmless.
        self._path_tracker.set_result(source_file.context.full_path, source_file)
        self._source_file = source_file

    def completed_files(self) -> list[file_validator.LoadedFile]:
        """Return every file that finished loading."""
        return self._path_tracker.completed_results()

    def submit_referenced_files(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Submit the files that a validated definition's edges lead to."""
        for edge in definition_result.reference_edges:
            if self._references_source_definition(loaded_file, edge, definition_result):
                continue
            if (
                loaded_file.earlier_definition(
                    edge.global_name_reference, definition_result.definition
                )
                is not None
            ):
                continue
            self._submit_referenced_file_from_configured_root(loaded_file, edge, pool)

    def follow_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Hand over the definition that an edge names, or report why it cannot be found.

        Waits until the target file finishes loading.
        """
        # A definition from the supplied source has no file path to resolve,
        # and was validated before any other definition.
        if self._references_source_definition(loaded_file, edge, source_definition):
            return
        enclosing_root = loaded_file.context.root_prefix
        target_file = edge.global_name_reference.name_content.path.file_path(
            self._universe_root(edge, enclosing_root)
        )
        if self._path_tracker.is_under_failed_root(target_file):
            return
        if self._check_if_current_universe_path_in_a_subroot(
            edge, target_file, enclosing_root, source_definition
        ):
            return

        # With the thread pool, work completes in arbitrary order. If files
        # A and C both reference file B, and B finishes loading before A's
        # definitions are processed, then target_loaded_file is already
        # available when processing A's edges.
        target_loaded_file = self._path_tracker.try_get_result(target_file)
        if target_loaded_file is not None:
            self._validate_reference_against_target(
                edge,
                target_file,
                target_loaded_file,
                source_definition,
                pool,
            )
        else:
            self._deferred_edges.setdefault(target_file, []).append(
                _DeferredReferenceEdge(edge, source_definition)
            )

    def _references_source_definition(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        referencing_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        if self._source_file is None:
            return False
        if loaded_file is self._source_file:
            return (
                self._source_file.earlier_definition(
                    edge.global_name_reference, referencing_definition.definition
                )
                is not None
            )
        return edge.global_name_reference in self._source_file.definitions

    def _submit_file(
        self, context: file_validator.FileValidationContext, pool: work_pool.WorkPool
    ):
        pool.submit(
            self._file_validator.load_file,
            context,
            handle_result=self._process_loaded_file,
        )

    def _process_loaded_file(
        self,
        loaded_file: file_validator.LoadedFile,
        pool: work_pool.WorkPool,
    ):
        self._path_tracker.set_result(loaded_file.context.full_path, loaded_file)
        self._validate_incoming_reference_edges(loaded_file.context.full_path, pool)

    def _submit_referenced_file_from_configured_root(
        self,
        referencing_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        pool: work_pool.WorkPool,
    ):
        """Submit a referenced file using its source project's loaded config."""
        self._submit_referenced_file(
            referencing_file=referencing_file,
            edge=edge,
            root_prefix=self._universe_root(edge, referencing_file.context.root_prefix),
            pool=pool,
        )

    def _submit_referenced_file(
        self,
        referencing_file: file_validator.LoadedFile,
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
            referencing_file=referencing_file,
        )

        try:
            root_config = self._load_root_config(
                root_prefix, edge.global_name_reference.effective_fqun.canonical
            )
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(root_prefix)
            referencing_file.file_diagnostics.append(
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
        source_file: file_validator.LoadedFile,
        source_definition_results: list[validation_result.DefinitionValidationResult],
        pool: work_pool.WorkPool,
    ):
        """Load project config if necessary, and submit the supplied source's referenced files."""
        first_edge: reference_graph.ReferenceEdge | None = None
        for edge in _edges_leaving_source_definitions(source_definition_results):
            if _needs_configuration(edge):
                if first_edge is None:
                    first_edge = edge
            else:
                self._submit_referenced_file_from_configured_root(
                    source_file, edge, pool
                )
        if first_edge is None:
            return

        root_config = self._load_config_in_non_filesystem_context(
            source_file, first_edge
        )
        if root_config is None:
            _strip_cross_universe_refs(source_definition_results)
            return
        self._resolve_non_filesystem_references_with_config(
            source_file=source_file,
            source_definition_results=source_definition_results,
            root_config=root_config,
            pool=pool,
        )

    def _resolve_non_filesystem_references_with_config(
        self,
        source_file: file_validator.LoadedFile,
        source_definition_results: list[validation_result.DefinitionValidationResult],
        root_config: config.ProjectRootConfig,
        pool: work_pool.WorkPool,
    ):
        """Resolve references in non-filesystem mode after config load."""
        unknown_fquns: set[str] = set()
        for edge in _edges_leaving_source_definitions(source_definition_results):
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
                source_file.file_diagnostics.append(
                    diagnostics.ExternalUniverseNotConfiguredDiagnostic(
                        location=global_name.location,
                        universe=fqun,
                        current_universe_name=root_config.fqun,
                    )
                )
                continue
            self._submit_referenced_file_from_configured_root(source_file, edge, pool)

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

    def _load_config_in_non_filesystem_context(
        self,
        source_file: file_validator.LoadedFile,
        first_edge: reference_graph.ReferenceEdge,
    ) -> config.ProjectRootConfig | None:
        """Load root config and map loading errors to non-filesystem diagnostics."""
        global_name = first_edge.global_name_reference.name_content
        try:
            return self._load_root_config(constants.PROJECT_ROOT)
        except config.NotProjectRootError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            source_file.file_diagnostics.append(
                diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
                    location=global_name.location,
                    universe=first_edge.global_name_reference.effective_fqun.canonical,
                    config_path=str(e.config_path),
                )
            )
            return None
        except config.ConfigError as e:
            self._path_tracker.mark_root_failed(constants.PROJECT_ROOT)
            source_file.file_diagnostics.append(
                diagnostics.ConfigLoadErrorDiagnostic(
                    location=global_name.location,
                    error=e,
                )
            )
            return None

    def _universe_root(
        self,
        edge: reference_graph.ReferenceEdge,
        referencing_root: define_path.DefinePath,
    ) -> define_path.DefinePath:
        # Edges with an explicit FQUN only exist when file validation found the
        # FQUN in the enclosing root's local deps, or when the universe needs
        # no configuration, so the universe always has a root.
        return typing.cast(
            "define_path.DefinePath",
            self._path_tracker.universe_root(
                edge.global_name_reference.name_content.source_fqun,
                referencing_root,
            ),
        )

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
        target_loaded_file: file_validator.LoadedFile,
        source_definition: validation_result.DefinitionValidationResult,
        pool: work_pool.WorkPool,
    ):
        """Validate a reference edge against a loaded target file, and hand over the definition it names."""
        global_name = edge.global_name_reference.name_content
        target_exception = target_loaded_file.exception
        target_definition = target_loaded_file.definitions.get(
            edge.global_name_reference
        )
        # A definition can reference only definitions that come before it in
        # its own file.
        if (
            target_definition is not None
            and target_definition.location.file_path
            == source_definition.definition.location.file_path
        ):
            target_definition = target_loaded_file.earlier_definition(
                edge.global_name_reference, source_definition.definition
            )

        # A standard universe file is not in the project, so naming it would
        # not help.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if (
            self._path_tracker.find_enclosing_root(target_file)
            == constants.STANDARD_LIBRARY_ROOT
        ):
            if isinstance(target_exception, exceptions.SourceFileNotFoundError):
                self._path_tracker.mark_not_found(target_file)
            elif target_definition is not None:
                self._handle_referenced_definition(
                    target_loaded_file, target_definition, pool
                )
                return
            source_definition.diagnostics.append(
                diagnostics.StandardDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return

        if isinstance(target_exception, exceptions.SourceFileNotFoundError):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return

        if target_definition is None:
            source_definition.diagnostics.append(
                diagnostics.ReferencedDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return
        self._handle_referenced_definition(target_loaded_file, target_definition, pool)

    def _validate_incoming_reference_edges(
        self, completed_file: define_path.DefinePath, pool: work_pool.WorkPool
    ):
        """Validate deferred reference edges waiting on a loaded file."""
        # Reference edges have to wake up by file, not by definition name.
        #
        # Two different files can participate in resolution for the same
        # canonical typed name. One might be the file we actually intended to
        # load, while another might define the same typed name at a different
        # path or might be missing entirely. Since the work pool loads
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
        target_loaded_file = self._path_tracker.get_result(completed_file)
        for deferred_edge in deferred:
            self._validate_reference_against_target(
                deferred_edge.edge,
                completed_file,
                target_loaded_file,
                deferred_edge.source_definition,
                pool,
            )

    def _check_existing_root_conflicts_for_first_subroot_load(
        self,
        root_prefix: define_path.DefinePath,
        global_name_reference: ast.GlobalTypedNameReference,
        referencing_file: file_validator.LoadedFile,
    ):
        """Check SubRootAlreadyOccupied for referenced files entering a new sub-root."""
        if self._path_tracker.project_root_loaded(root_prefix):
            return

        conflicting_path, existing_universe = (
            self._path_tracker.first_tracked_file_under(root_prefix)
        )
        if conflicting_path is not None:
            referencing_file.file_diagnostics.append(
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


def _make_config_error_file(
    file_path: define_path.DefinePath,
    root_prefix: define_path.DefinePath,
    error: config.ConfigError,
) -> file_validator.LoadedFile:
    """Create a LoadedFile for a file whose project config failed to load."""
    return file_validator.LoadedFile(
        context=file_validator.FileValidationContext(
            file_path=file_path, root_prefix=root_prefix
        ),
        exception=error,
        source_digest=None,
        file_diagnostics=[],
        definitions=typed_name_dict.TypedNameDict(),
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
