"""Resolution of the references in a program from supplied source text.

The supplied source is not a file in a project, so it loads its project's
config only when one of its references needs it.
"""

# TODO: Say "non-filesystem context", the spec's term, instead of "supplied
# source" and "non-filesystem mode" throughout the compiler.

from __future__ import annotations

import typing

from define.compiler.config import global_names, project_config, project_roots
from define.compiler.errors import (
    structural_diagnostics,
)
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import define_path
    from define.compiler.errors import (
        diagnostics,
    )
    from define.compiler.graphs import reference_graph
    from define.compiler.validator.structural import (
        file_loader,
        structural_result,
    )


@typing.final
class NonFilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program from supplied source lead to.

    References can also resolve to the definitions of the supplied source, which no
    file holds.
    """

    _source_file: file_loader.LoadedFile
    # The universes that the supplied source references but its project config
    # does not configure, each reported once.
    _unknown_universes: set[str]
    # The universes that the supplied source defines anything in.
    _source_universes: set[str]

    def __init__(
        self,
        source_file: file_loader.LoadedFile,
        roots: project_roots.ProjectRoots,
    ):
        """Initialize with the supplied source as the program's only loaded file, and the program's project roots."""
        super().__init__(roots)
        self._source_file = source_file
        self._unknown_universes = set()
        self._source_universes = {
            definition.typed_name.name_content.fqun.canonical
            for definition in source_file.definitions.values()
        }

    @typing.override
    def completed_files(self) -> list[file_loader.LoadedFile]:
        return [self._source_file, *super().completed_files()]

    @typing.override
    def validate_reference(
        self,
        referencing_root: define_path.DefinePath,
        referencing_file: file_loader.LoadedFile | None,
        edge: reference_graph.ReferenceEdge,
        source_definition: structural_result.StructuralDefinitionResult,
    ) -> reference_resolver.ReferenceOutcome:
        if referencing_file is self._source_file:
            unresolved = self._check_source_reference(edge)
            if unresolved is not None:
                return unresolved
        else:
            # A definition from the supplied source has no file path to
            # resolve.
            definition_in_source = self._source_file.definitions.get(
                edge.global_name_reference.full_typed_name
            )
            if definition_in_source is not None:
                return reference_resolver.ResolvedDefinition(
                    self._source_file, definition_in_source
                )
        return super().validate_reference(
            referencing_root, referencing_file, edge, source_definition
        )

    def _check_source_reference(
        self, edge: reference_graph.ReferenceEdge
    ) -> reference_resolver.Unresolved | reference_resolver.AlreadyReported | None:
        """Return why a reference from the supplied source cannot resolve, or None if it can, loading the project config the first time a reference needs it.

        Returns a diagnostic for why the first time that happens.
        """
        if not global_names.universe_needs_configuration(
            edge.global_name_reference.effective_fqun.canonical
        ):
            return None
        root_config = self._project_roots.load_project_root_config()
        if isinstance(root_config, project_roots.NoProjectConfig):
            return reference_resolver.Unresolved(self._no_project_root_diagnostic(edge))
        # The config's diagnostics are already recorded.
        if root_config is None:
            return reference_resolver.ALREADY_REPORTED
        universe_diagnostic = root_config.check_universe_configured(
            edge.global_name_reference.name_content
        )
        if universe_diagnostic is None:
            return None
        # In a filesystem context, file validation reports an unknown universe
        # once per file and records no edge for it. The supplied source is one
        # file, so report each unknown universe once here.
        if universe_diagnostic.universe in self._unknown_universes:
            return reference_resolver.ALREADY_REPORTED
        self._unknown_universes.add(universe_diagnostic.universe)
        return reference_resolver.Unresolved(universe_diagnostic)

    def _no_project_root_diagnostic(
        self, edge: reference_graph.ReferenceEdge
    ) -> diagnostics.Diagnostic:
        """Return the diagnostic that the working directory has no project config, at the first reference from the supplied source that needs it."""
        reference = edge.global_name_reference
        config_path = str(project_config.CONFIG_FILE.path)
        if reference.effective_fqun.canonical in self._source_universes:
            return structural_diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
                location=reference.location,
                definition_name=reference.source_typed_name,
                config_path=config_path,
            )
        # A short-form reference names the universe of the definition it is
        # in, which the supplied source defines, so a reference to any other
        # universe writes its FQUN.
        return structural_diagnostics.NoProjectRootInNonFilesystemContextDiagnostic(
            location=typing.cast("ast.Fqun", reference.name_content.fqun).location,
            universe=reference.effective_fqun.canonical,
            config_path=config_path,
        )
