"""Resolution of global name references to the files that hold their definitions."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import constants
from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.validator.structural import (
    file_validation_context,
)
from define.compiler.validator.structural.resolver import path_tracker

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.config import project_roots
    from define.compiler.data_structures import define_path
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result
    from define.compiler.validator.structural import (
        file_validator,
    )


class ResolvedDefinition(msgspec.Struct, frozen=True):
    """A definition that a reference resolved to, and the file that holds it."""

    loaded_file: file_validator.LoadedFile
    definition: ast.GlobalDefinition


class LoadFile(msgspec.Struct, frozen=True):
    """A file that the caller must load before the reference can resolve."""

    context: file_validation_context.FileValidationContext


class AwaitingFile(msgspec.Struct, frozen=True):
    """A reference that waits for a file that is already loading, and resolves when add_loaded_file records it."""


class Unresolved(msgspec.Struct, frozen=True):
    """A reference that cannot resolve, whose diagnostic, if any, is already recorded."""


# Neither outcome has data, so every reference shares one of each.
AWAITING_FILE = AwaitingFile()
UNRESOLVED = Unresolved()

# What validating a reference found: the definition it names, a file to load
# first, or why there is neither.
type ReferenceOutcome = ResolvedDefinition | LoadFile | AwaitingFile | Unresolved


class _DeferredReferenceEdge(msgspec.Struct):
    """An edge waiting for its target file to finish loading."""

    edge: reference_graph.ReferenceEdge
    source_definition: validation_result.DefinitionValidationResult


class ReferenceResolver:
    """Finds the files and definitions that references lead to.

    Decides which files to load, so that no file loads twice, and loads the
    project roots that references lead into. Reports the diagnostics for
    references that cannot resolve to a definition. Only the coordinator thread
    may use it.
    """

    _project_roots: project_roots.ProjectRoots
    _path_tracker: path_tracker.PathTracker[file_validator.LoadedFile]
    _deferred_edges: dict[define_path.DefinePath, list[_DeferredReferenceEdge]]
    _program_diagnostics: list[diagnostics.FormattableDiagnostic]

    def __init__(self, roots: project_roots.ProjectRoots):
        """Initialize with the program's project roots, and no files loaded."""
        self._project_roots = roots
        self._path_tracker = path_tracker.PathTracker()
        self._deferred_edges = {}
        self._program_diagnostics = []

    def completed_files(self) -> list[file_validator.LoadedFile]:
        """Return every file that finished loading."""
        return self._path_tracker.completed_results()

    def program_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return the diagnostics about the program rather than one of its files, including the ones that loading its project configs found."""
        return [*self._project_roots.diagnostics(), *self._program_diagnostics]

    def validate_reference(
        self,
        referencing_root: define_path.DefinePath,
        referencing_file: file_validator.LoadedFile | None,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> ReferenceOutcome:
        """Validate an edge from the project root referencing_root, and return what it found.

        referencing_file is the file that holds the edge, which must not name
        an earlier definition in it, or None for an edge from an association,
        which the project's config holds. Diagnostics about the edge are added
        to source_definition.

        If the target file is not loaded yet, the rest of the validation
        happens when it loads, and add_loaded_file returns the definition
        instead.
        """
        target = self._validate_target_file(referencing_root, edge, source_definition)
        if target is None:
            return UNRESOLVED
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
                in_source_file=target_loaded_file is referencing_file,
            )
        self._deferred_edges.setdefault(target_file, []).append(
            _DeferredReferenceEdge(edge, source_definition)
        )
        if self._path_tracker.is_tracked(target_file):
            return AWAITING_FILE
        self._path_tracker.mark_in_progress(target_file)
        return LoadFile(target)

    def _validate_target_file(
        self,
        referencing_root: define_path.DefinePath,
        edge: reference_graph.ReferenceEdge,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> file_validation_context.FileValidationContext | None:
        """Validate the file an edge names, and return it, or None if the edge cannot resolve in it.

        Reports why the edge cannot resolve in the file, unless that was
        already reported elsewhere.
        """
        # Edges with an explicit FQUN only exist when file validation found the
        # FQUN in the enclosing root's local deps, or when the universe needs
        # no configuration.
        target = self._project_roots.load_sub_root_config(
            edge.global_name_reference.name_content.source_fqun, referencing_root
        )
        # Why the universe cannot be used was already reported.
        if target is None:
            return None
        target_root, target_root_config = target
        target_file_path = edge.global_name_reference.name_content.path.file_path()
        target_file = target_root / target_file_path
        if self._check_target_in_sub_root(
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
    ) -> list[ResolvedDefinition]:
        """Record a file that finished loading, and return the definitions that the edges waiting on it resolve to."""
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
        resolved_definitions: list[ResolvedDefinition] = []
        for deferred_edge in self._deferred_edges.pop(completed_file, []):
            outcome = self._validate_reference_against_target(
                deferred_edge.edge,
                loaded_file,
                deferred_edge.source_definition,
                # A file is recorded as loaded before any of its definitions
                # are validated, so no edge ever waits for its own file.
                in_source_file=False,
            )
            if isinstance(outcome, ResolvedDefinition):
                resolved_definitions.append(outcome)
        return resolved_definitions

    def _check_target_in_sub_root(
        self,
        edge: reference_graph.ReferenceEdge,
        target_root: define_path.DefinePath,
        target_file: define_path.DefinePath,
        source_definition: validation_result.DefinitionValidationResult,
    ) -> bool:
        """Check if a reference leads into a sub-root that the target universe's project lists.

        Returns True (and appends a diagnostic) when the edge should be skipped.
        """
        sub_root = self._project_roots.find_sub_root_between(target_root, target_file)
        if sub_root is None:
            return False
        sub_root_path, entry = sub_root
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
    ) -> ResolvedDefinition | Unresolved:
        """Validate a reference edge against a loaded target file, and return the definition it names, if it can resolve.

        in_source_file is whether the target file holds the edge.
        """
        target_file = target_loaded_file.context.full_path
        target_load_failure = target_loaded_file.load_failure
        target_definition = target_loaded_file.definitions.get(
            edge.global_name_reference.full_typed_name
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
        if target_loaded_file.context.root_prefix == constants.STANDARD_LIBRARY_ROOT:
            if isinstance(target_load_failure, syntax_errors.SourceFileNotFound):
                self._path_tracker.mark_not_found(target_file)
            elif target_definition is not None:
                return ResolvedDefinition(target_loaded_file, target_definition)
            source_definition.diagnostics.append(
                diagnostics.StandardDefinitionNotFoundDiagnostic(
                    location=edge.global_name_reference.location,
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return UNRESOLVED

        if isinstance(target_load_failure, syntax_errors.SourceFileNotFound):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileNotFoundDiagnostic(
                    location=edge.global_name_reference.name_content.path.location,
                    file_path=str(target_file),
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return UNRESOLVED

        # Reported at the reference, like a missing file, rather than as the
        # file's own load failure, which has no location.
        if isinstance(target_load_failure, syntax_errors.SourceFileUnreadable):
            source_definition.diagnostics.append(
                diagnostics.ReferencedFileUnreadableDiagnostic(
                    location=edge.global_name_reference.name_content.path.location,
                    file_path=str(target_file),
                    reason=target_load_failure.reason,
                )
            )
            self._path_tracker.mark_not_found(target_file)
            return UNRESOLVED

        if target_definition is None:
            source_definition.diagnostics.append(
                diagnostics.ReferencedDefinitionNotFoundDiagnostic(
                    location=edge.global_name_reference.location,
                    file_path=str(target_file),
                    definition_name=edge.global_name_reference.full_typed_name,
                )
            )
            return UNRESOLVED
        return ResolvedDefinition(target_loaded_file, target_definition)
