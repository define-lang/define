"""Shared data types for Define language validation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler import (
    ast,
    diagnostics,
    exceptions,
)
from define.compiler.lark import lark_standalone

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from define.compiler.data_structures import define_path, typed_name_dict
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import stats

type AnyValidationException = exceptions.DefineError | lark_standalone.UnexpectedInput


@dataclass(frozen=True)
class ParticleStatementValidity:
    """Name validation results for a create or move statement."""

    target_ok: bool
    source_ok: bool = True
    from_is_prefix_of_to: bool = False


# TODO: We should probably have a more minimal output from the reference
# graph validator that provides codegen only what it needs (instead of
# modifying this data structure).
@dataclass
class DefinitionValidationResult:
    """Validation output for one definition within a file."""

    definition: ast.QualityDefinition
    _diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)

    reference_edges: list[reference_graph.ReferenceEdge] = field(default_factory=list)
    particle_statement_validity: list[ParticleStatementValidity] = field(
        default_factory=list
    )

    def add_diagnostic(self, diagnostic: diagnostics.Diagnostic):
        """Append a diagnostic to this definition's results."""
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return diagnostics sorted by source location (line, then column)."""
        return sorted(
            self._diagnostics,
            key=lambda d: (d.location.line, d.location.column),
        )


@dataclass
class FileValidationResult:
    """Validation output for one source file."""

    exception: AnyValidationException | None
    source_lines: list[str] | None
    file_path: define_path.DefinePath  # Full path: root_prefix / relative file path.
    root_prefix: define_path.DefinePath
    stats: stats.ValidationTimingStats
    file_diagnostics: list[diagnostics.Diagnostic]
    _post_definition_diagnostics: list[diagnostics.Diagnostic] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    # This preserves source order, including duplicate definitions that were
    # diagnosed during file validation.
    definition_results: list[DefinitionValidationResult]

    def add_file_diagnostic(self, diagnostic: diagnostics.Diagnostic):
        """Append a non-definition diagnostic after per-definition diagnostics."""
        self._post_definition_diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> Sequence[diagnostics.Diagnostic]:
        """Return file-level and per-definition diagnostics as a read-only view."""
        return (
            list(self.file_diagnostics)
            + [
                diagnostic
                for result in self.definition_results
                for diagnostic in result.diagnostics
            ]
            + list(self._post_definition_diagnostics)
        )

    def edges_to_other_files(self) -> Iterator[reference_graph.ReferenceEdge]:
        """Yield the edges that lead to other files.

        An edge leads to another file unless its target is the enclosing
        definition or a definition that appeared earlier in the same file.
        """
        seen_targets: set[str] = set()
        for definition_result in self.definition_results:
            seen_targets.add(definition_result.definition.typed_name.full_typed_name)
            for edge in definition_result.reference_edges:
                if edge.target_full_typed_name not in seen_targets:
                    yield edge

    def first_edge_to_other_file(self) -> reference_graph.ReferenceEdge | None:
        """Return the first edge that leads to another file, if any."""
        return next(self.edges_to_other_files(), None)

    def first_edge_per_referenced_file(
        self,
    ) -> Iterator[reference_graph.ReferenceEdge]:
        """Yield each definition's first edge per referenced file.

        Within one definition, only the first reference to a given file drives
        file loading and its diagnostics, no matter which definition type the
        references name.
        """
        seen_targets: set[str] = set()
        for definition_result in self.definition_results:
            seen_targets.add(definition_result.definition.typed_name.full_typed_name)
            seen_files: set[tuple[str, str]] = set()
            for edge in definition_result.reference_edges:
                if edge.target_full_typed_name in seen_targets:
                    continue
                referenced_file = (
                    edge.global_name_reference.effective_fqun.canonical,
                    edge.global_name_reference.name_content.path.name,
                )
                if referenced_file in seen_files:
                    continue
                seen_files.add(referenced_file)
                yield edge


@dataclass
class ProgramValidationResult:
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    config_loading_time_ns: int
    reference_graph: reference_graph.ReferenceGraph
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, DefinitionValidationResult
    ]

    @property
    def entry_action(self) -> ast.ActionDefinition | None:
        """Return the entry file's constructor, if it defines one."""
        return next(
            (
                definition_result.definition
                for definition_result in self.file_results[0].definition_results
                if isinstance(definition_result.definition, ast.ActionDefinition)
                and definition_result.definition.is_constructor
            ),
            None,
        )

    @property
    def all_diagnostics(self) -> list[diagnostics.Diagnostic]:
        """All diagnostics from all file results."""
        return [d for r in self.file_results for d in r.diagnostics]

    @property
    def all_exceptions(self) -> list[AnyValidationException]:
        """All exceptions from all file results."""
        return [r.exception for r in self.file_results if r.exception is not None]

    def has_errors(self) -> bool:
        """Whether any file had exceptions or diagnostics."""
        return bool(self.all_exceptions or self.all_diagnostics)
