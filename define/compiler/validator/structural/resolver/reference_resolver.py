"""Resolution of global name references to the files that hold their definitions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import config, constants
from define.compiler.errors import diagnostics, exceptions
from define.compiler.validator.structural import file_validator
from define.compiler.validator.structural.resolver import path_tracker

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import define_path
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result


class ReachedDefinition(msgspec.Struct):
    """A definition that a reference reached, and the file that holds it."""

    loaded_file: file_validator.LoadedFile
    definition: ast.GlobalDefinition


class _DeferredReferenceEdge(msgspec.Struct):
    """An edge waiting for its target file to finish loading."""

    edge: reference_graph.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


class ReferenceResolver:
    """Finds the files and definitions that references lead to.

    Decides which files to load, so that no file loads twice, and owns the
    project roots and their configs. Reports the diagnostics for references
    that cannot reach a definition. Only the coordinator thread may use it.
    """

    _path_tracker: path_tracker.PathTracker[file_validator.LoadedFile]
    _deferred_edges: dict[define_path.DefinePath, list[_DeferredReferenceEdge]]

    def __init__(self):
        """Initialize with no files loaded."""
        self._path_tracker = path_tracker.PathTracker()
        self._deferred_edges = {}

    def completed_files(self) -> list[file_validator.LoadedFile]:
        """Return every file that finished loading."""
        return self._path_tracker.completed_results()

    def files_to_load(
        self,
        loaded_file: file_validator.LoadedFile,
        definition_result: validation_result.DefinitionValidationResult,
    ) -> list[file_validator.FileValidationContext]:
        """Return the files that a validated definition's edges lead to and that are not loaded yet."""
        contexts: list[file_validator.FileValidationContext] = []
        for edge in definition_result.reference_edges:
            context = self._file_to_load(loaded_file, edge, definition_result)
            if context is not None:
                contexts.append(context)
        return contexts

    def _file_to_load(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        definition_result: validation_result.DefinitionValidationResult,
    ) -> file_validator.FileValidationContext | None:
        """Return the file that one of a validated definition's edges leads to, if it is not loaded yet."""
        if (
            loaded_file.earlier_definition(
                edge.global_name_reference, definition_result.definition
            )
            is not None
        ):
            return None
        return self._referenced_file_to_load(loaded_file, edge)

    def follow_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> ReachedDefinition | None:
        """Return the definition that an edge names, or report why it cannot be found.

        If the target file has not finished loading, the edge waits for it, and
        add_loaded_file returns the definition instead.
        """
        enclosing_root = loaded_file.context.root_prefix
        target_file = edge.global_name_reference.name_content.path.file_path(
            self._universe_root(edge, enclosing_root)
        )
        if self._path_tracker.is_under_failed_root(target_file):
            return None
        if self._check_if_current_universe_path_in_a_subroot(
            edge, target_file, enclosing_root, source_definition
        ):
            return None

        # With the thread pool, work completes in arbitrary order. If files
        # A and C both reference file B, and B finishes loading before A's
        # definitions are processed, then target_loaded_file is already
        # available when processing A's edges.
        target_loaded_file = self._path_tracker.try_get_result(target_file)
        if target_loaded_file is None:
            self._deferred_edges.setdefault(target_file, []).append(
                _DeferredReferenceEdge(edge, source_definition)
            )
            return None
        return self._validate_reference_against_target(
            edge, target_file, target_loaded_file, source_definition
        )

    def add_loaded_file(
        self, loaded_file: file_validator.LoadedFile
    ) -> list[ReachedDefinition]:
        """Record a file that finished loading, and return the definitions that the edges waiting on it reach."""
        completed_file = loaded_file.context.full_path
        self._path_tracker.set_result(completed_file, loaded_file)
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
        # one exact file finishing loading, and only that file gets to
        # satisfy or fail the deferred edge.
        reached_definitions: list[ReachedDefinition] = []
        for deferred_edge in self._deferred_edges.pop(completed_file, []):
            reached_definition = self._validate_reference_against_target(
                deferred_edge.edge,
                completed_file,
                loaded_file,
                deferred_edge.source_definition,
            )
            if reached_definition is not None:
                reached_definitions.append(reached_definition)
        return reached_definitions

    def _referenced_file_to_load(
        self,
        referencing_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
    ) -> file_validator.FileValidationContext | None:
        """Return the file that an edge leads to, if it is not loaded or loading yet.

        Marks the file as loading, so the caller must load it.
        """
        root_prefix = self._universe_root(edge, referencing_file.context.root_prefix)
        global_name = edge.global_name_reference.name_content
        file_path = global_name.path.file_path()
        full_path = root_prefix / file_path
        if self._path_tracker.is_tracked(full_path):
            return None
        if self._path_tracker.is_under_failed_root(full_path):
            return None

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
            return None

        self._path_tracker.mark_in_progress(full_path)
        return file_validator.FileValidationContext(
            file_path=file_path,
            root_prefix=root_prefix,
            root_config=root_config,
        )

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
    ) -> ReachedDefinition | None:
        """Validate a reference edge against a loaded target file, and return the definition it names."""
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
                return ReachedDefinition(target_loaded_file, target_definition)
            source_definition.diagnostics.append(
                diagnostics.StandardDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return None

        if isinstance(target_exception, exceptions.SourceFileNotFoundError):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return None

        if target_definition is None:
            source_definition.diagnostics.append(
                diagnostics.ReferencedDefinitionNotFoundDiagnostic(
                    location=global_name.location,
                    file_path=str(target_file),
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return None
        return ReachedDefinition(target_loaded_file, target_definition)

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
