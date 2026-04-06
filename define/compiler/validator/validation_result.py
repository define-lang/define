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
    import pathlib
    from collections.abc import Sequence

    from define.compiler.graphs import reference_graph
    from define.compiler.validator import stats

type AnyValidationException = exceptions.DefineError | lark_standalone.UnexpectedInput


@dataclass
class DiscoveredFile:
    """A file discovered during validation that should be validated next."""

    path: pathlib.PurePosixPath
    root_prefix: pathlib.PurePosixPath
    expected_fqun: str
    location: ast.SourceLocation


@dataclass(frozen=True)
class DimensionPointStatementValidity:
    """Name validation results for a create or move statement."""

    statement: ast.DimensionPointStatement
    target_ok: bool
    source_ok: bool = True


@dataclass
class DefinitionValidationResult:
    """Validation output for one definition within a file."""

    definition: ast.QualityDefinition
    _diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)

    reference_edges: list[reference_graph.ReferenceEdge] = field(default_factory=list)
    discovered_files: list[DiscoveredFile] = field(default_factory=list)
    dp_statement_validity: list[DimensionPointStatementValidity] = field(
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
    # TODO: Should this just be source_lines?
    source: str | None
    file_path: pathlib.PurePosixPath  # Full path: root_prefix / relative file path.
    root_prefix: pathlib.PurePosixPath
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


@dataclass
class ProgramValidationResult:
    """Full result of validating a Define program."""

    file_results: list[FileValidationResult]
    config_loading_time_ns: int
    reference_graph: reference_graph.ReferenceGraph
    definition_results: dict[str, DefinitionValidationResult]

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
