"""Resolution of global name references to the files that hold their definitions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import config, constants
from define.compiler.errors import diagnostics, exceptions
from define.compiler.validator.structural import (
    file_validation_context,
)
from define.compiler.validator.structural.resolver import path_tracker

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import define_path
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import (
        file_validator,
    )
    from source_rendering.python import rendering


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
    # The project roots and universes whose local dependency declares a
    # sub-root path that another one already declared, so the project cannot
    # use that universe.
    _disabled_universes: set[tuple[define_path.DefinePath, str]]
    _config_diagnostics: list[diagnostics.FormattableDiagnostic]
    _source_map: rendering.SourceMap

    def __init__(self, source_map: rendering.SourceMap):
        """Initialize with the source map to register the program's files with, and no files loaded."""
        self._source_map = source_map
        self._path_tracker = path_tracker.PathTracker()
        self._deferred_edges = {}
        self._disabled_universes = set()
        self._config_diagnostics = []

    def completed_files(self) -> list[file_validator.LoadedFile]:
        """Return every file that finished loading."""
        return self._path_tracker.completed_results()

    def config_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return the diagnostics of every project config that was loaded."""
        return self._config_diagnostics

    def validate_reference(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> ReachedDefinition | file_validation_context.FileValidationContext | None:
        """Validate an edge, and return the definition it names if its file is loaded.

        The edge must not name an earlier definition in its own file.

        If the target file is not loaded yet, the rest of the validation
        happens when it loads, add_loaded_file returns the definition instead,
        and this returns the file if the caller must load it.
        """
        target = self._validate_target_file(loaded_file, edge, source_definition)
        if target is None:
            return None
        target_file = target.full_path

        # With the thread pool, work completes in arbitrary order. If files
        # A and C both reference file B, and B finishes loading before A's
        # definitions are processed, then target_loaded_file is already
        # available when processing A's edges.
        target_loaded_file = self._path_tracker.try_get_result(target_file)
        if target_loaded_file is not None:
            return self._validate_reference_against_target(
                edge,
                target_loaded_file,
                source_definition,
                in_source_file=target_loaded_file is loaded_file,
            )
        self._deferred_edges.setdefault(target_file, []).append(
            _DeferredReferenceEdge(edge, source_definition)
        )
        if self._path_tracker.is_tracked(target_file):
            return None
        self._path_tracker.mark_in_progress(target_file)
        return target

    def _validate_target_file(
        self,
        loaded_file: file_validator.LoadedFile,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> file_validation_context.FileValidationContext | None:
        """Validate the file an edge names, and return it, or None if the edge cannot resolve in it.

        Reports why the edge cannot resolve in the file, unless that was
        already reported elsewhere.
        """
        target_root = self._universe_root(edge, loaded_file.context.root_prefix)
        # The config error for a disabled universe was already reported.
        if target_root is None:
            return None
        target_file_path = edge.global_name_reference.name_content.path.file_path()
        target_file = target_root / target_file_path
        if self._path_tracker.is_under_failed_root(target_file):
            return None
        target_root_config = self._target_root_config(
            edge, target_root, loaded_file.context.root_prefix
        )
        if target_root_config is None:
            return None
        if self._check_target_in_declared_sub_root(
            edge, target_root, target_file, source_definition
        ):
            return None
        return file_validation_context.FileValidationContext(
            file_path=target_file_path,
            root_prefix=target_root,
            root_config=target_root_config,
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
                loaded_file,
                deferred_edge.source_definition,
                # A file is recorded as loaded before any of its definitions
                # are validated, so no edge ever waits for its own file.
                in_source_file=False,
            )
            if reached_definition is not None:
                reached_definitions.append(reached_definition)
        return reached_definitions

    def _target_root_config(
        self,
        edge: reference_graph.ReferenceEdge,
        target_root: define_path.DefinePath,
        referencing_root: define_path.DefinePath,
    ) -> config.ProjectRootConfig | None:
        """Return the config of the project root that an edge from referencing_root leads into, loading it if needed.

        Returns None, after recording the config's diagnostics, if the config
        cannot load.
        """
        existing = self._path_tracker.config_for_root(target_root)
        if existing is not None:
            return existing
        # A short-form reference stays in the referencing root, whose config is
        # loaded, so the reference names its universe.
        fqun = typing.cast("str", edge.global_name_reference.name_content.source_fqun)
        # The standard universe needs no local dependency entry.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if fqun == constants.STANDARD_UNIVERSE:
            return self._load_root_config(target_root)
        return self._load_root_config(
            target_root, self._path_tracker.sub_root_entry(fqun, referencing_root)
        )

    def _universe_root(
        self,
        edge: reference_graph.ReferenceEdge,
        referencing_root: define_path.DefinePath,
    ) -> define_path.DefinePath | None:
        """Return the root of the universe an edge names, or None if the referencing project cannot use it."""
        fqun = edge.global_name_reference.name_content.source_fqun
        if fqun is not None and (referencing_root, fqun) in self._disabled_universes:
            return None
        # Edges with an explicit FQUN only exist when file validation found the
        # FQUN in the enclosing root's local deps, or when the universe needs
        # no configuration, so the universe always has a root.
        return typing.cast(
            "define_path.DefinePath",
            self._path_tracker.universe_root(fqun, referencing_root),
        )

    def _check_target_in_declared_sub_root(
        self,
        edge: reference_graph.ReferenceEdge,
        target_root: define_path.DefinePath,
        target_file: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        """Check if a reference leads into a sub-root that the target universe's project declares.

        Returns True (and appends a diagnostic) when the edge should be skipped.
        """
        declared_sub_root = self._path_tracker.declared_sub_root_containing(
            target_root, target_file
        )
        if declared_sub_root is None:
            return False
        sub_root_path, entry = declared_sub_root
        source_definition.diagnostics.append(
            diagnostics.PathInsideOtherUniverseDiagnostic(
                location=edge.global_name_reference.name_content.path.location,
                path=str(target_file),
                other_universe=entry.universe,
                sub_root_path=str(sub_root_path),
            )
        )
        return True

    def _validate_reference_against_target(
        self,
        edge: reference_graph.ReferenceEdge,
        target_loaded_file: file_validator.LoadedFile,
        source_definition: validation_result.DefinitionValidationResult,
        *,
        in_source_file: bool,
    ) -> ReachedDefinition | None:
        """Validate a reference edge against a loaded target file, and return the definition it names.

        in_source_file is whether the target file holds the edge.
        """
        target_file = target_loaded_file.context.full_path
        target_exception = target_loaded_file.exception
        target_definition = target_loaded_file.definitions.get(
            edge.global_name_reference
        )
        # A definition can reference only definitions that come before it in
        # its own file.
        if target_definition is not None and in_source_file:
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
                    location=edge.global_name_reference.location,
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return None

        if isinstance(target_exception, exceptions.SourceFileNotFoundError):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=edge.global_name_reference.name_content.path.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return None

        if target_definition is None:
            source_definition.diagnostics.append(
                diagnostics.ReferencedDefinitionNotFoundDiagnostic(
                    location=edge.global_name_reference.location,
                    file_path=str(target_file),
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return None
        return ReachedDefinition(target_loaded_file, target_definition)

    def _load_root_config(
        self,
        root_prefix: define_path.DefinePath,
        declaring_entry: config.LocalDependencyEntry | None = None,
    ) -> config.ProjectRootConfig | None:
        """Load project config for a root and register it.

        If it cannot load, marks the root failed and returns None after
        recording the config's diagnostics. They are in the config, not at a
        reference, so they are recorded once, however many references lead
        into the root.
        """
        # The standard universe ships with the compiler, so its root has no
        # config file.
        # TODO: Remove this special case once the Define Standard Library
        # exists.
        if root_prefix == constants.STANDARD_LIBRARY_ROOT:
            root_config = config.ProjectRootConfig(
                fqun=constants.STANDARD_UNIVERSE, sub_roots={}
            )
        else:
            result = config.ConfigLoader(
                root_prefix, self._source_map
            ).load_project_root_config(declaring_entry)
            if result.root_config is None:
                self._path_tracker.mark_root_failed(root_prefix)
                self._config_diagnostics.extend(result.diagnostics)
                return None
            root_config = result.root_config
        existing_root = self._path_tracker.root_for_fqun(root_config.fqun)
        if existing_root is not None and existing_root != root_prefix:
            self._path_tracker.mark_root_failed(root_prefix)
            self._config_diagnostics.append(
                diagnostics.DuplicateFqunDiagnostic(
                    config_path=str(root_prefix / config.CONFIG_PATH),
                    field_path=("project", "universe_name"),
                    fqun=root_config.fqun,
                    existing_config=str(existing_root / config.CONFIG_PATH),
                )
            )
            return None
        self._path_tracker.register_project_root(root_prefix, root_config)
        self._declare_sub_roots(root_prefix, root_config)
        return root_config

    def _declare_sub_roots(
        self, root_prefix: define_path.DefinePath, root_config: config.ProjectRootConfig
    ):
        """Record the sub-roots that a loaded project's local dependencies declare."""
        for entry in root_config.sub_roots.values():
            sub_root_path = root_prefix / entry.path
            if entry.universe == root_config.fqun:
                self._disabled_universes.add((root_prefix, entry.universe))
                self._config_diagnostics.append(
                    diagnostics.LocalDependencyOnOwnUniverseDiagnostic(
                        config_path=entry.deps_path,
                        field_path=("deps", "local", entry.index, "universe_name"),
                        universe=entry.universe,
                    )
                )
                continue
            existing_entry = self._path_tracker.declare_sub_root(sub_root_path, entry)
            if existing_entry is None:
                continue
            self._disabled_universes.add((root_prefix, entry.universe))
            self._config_diagnostics.append(
                diagnostics.SubRootPathAlreadyDeclaredDiagnostic(
                    config_path=entry.deps_path,
                    field_path=("deps", "local", entry.index, "path"),
                    sub_root_path=str(sub_root_path),
                    first_config_path=existing_entry.deps_path,
                    first_field_path=("deps", "local", existing_entry.index, "path"),
                )
            )
