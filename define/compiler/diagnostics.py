"""Diagnostic types for the Define language validator."""

from __future__ import annotations

from dataclasses import dataclass

from define.compiler import ast  # noqa: TC001


@dataclass
class Diagnostic:
    """Base class for all validation diagnostics."""

    position: ast.SourcePosition
    message: str

    def format(self, source_lines: list[str]) -> str:
        """Format the diagnostic with source context and caret pointer."""
        line_idx = self.position.line - 1
        source_line = (
            source_lines[line_idx] if 0 <= line_idx < len(source_lines) else ""
        )

        column = self.position.column
        caret_line = " " * (column - 1) + "^"

        return (
            f"line {self.position.line}, column {self.position.column}: "
            f"{self.message}\n"
            f"  {source_line}\n"
            f"  {caret_line}"
        )


@dataclass
class ReservedNameDiagnostic(Diagnostic):
    """Base class for reserved name diagnostics."""

    reserved_name: str


@dataclass
class ReservedUniverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved universe name is used."""


@dataclass
class ReservedAuthorityNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority name is used."""


@dataclass
class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""


@dataclass
class PathMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str


@dataclass
class UniverseWithoutAuthorityDiagnostic(Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str


@dataclass
class DuplicateDefinitionDiagnostic(Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int


@dataclass
class LocalNameConflictDiagnostic(Diagnostic):
    """Diagnostic for when a local name conflicts with another local definition."""

    local_name: str
    first_definition_line: int


@dataclass
class FqunMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's FQUN doesn't match the expected project FQUN."""

    expected: str
    actual: str


@dataclass
class InvalidAuthorityDomainDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain has invalid format."""

    domain: str


@dataclass
class InvalidAuthorityPathSegmentDiagnostic(Diagnostic):
    """Diagnostic for when an authority path segment has invalid format."""

    segment: str


@dataclass
class InvalidGlobalNamePathDiagnostic(Diagnostic):
    """Diagnostic for when a global name path segment has invalid format."""

    segment: str


@dataclass
class InvalidLocalNameFormatDiagnostic(Diagnostic):
    """Diagnostic for when a local name has invalid format."""

    local_name: str


@dataclass
class InvalidMultiverseNameDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name has invalid format."""

    multiverse_name: str


@dataclass
class InvalidUniverseNameFormatDiagnostic(Diagnostic):
    """Diagnostic for when a universe name has invalid format."""

    universe_name: str


@dataclass
class GlobalReferenceMustUseShortFormDiagnostic(Diagnostic):
    """Diagnostic for when a same-FQUN global reference uses full form."""

    fqun: str
