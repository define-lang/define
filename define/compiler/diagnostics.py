"""Diagnostic types for the Define language validator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar

from define.compiler import ast  # noqa: TC001


@dataclass
class Diagnostic:
    """Base class for all validation diagnostics."""

    position: ast.SourcePosition
    message_format: ClassVar[str] = ""

    @property
    def message(self) -> str:
        """Render the diagnostic message from the format template."""
        fields: dict[str, object] = asdict(self)
        return self.message_format.format(**fields)

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

    message_format: ClassVar[str] = "'{reserved_name}' is a reserved universe name"


@dataclass
class ReservedAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority domain is used."""

    message_format: ClassVar[str] = "'{reserved_name}' is a reserved authority domain"


@dataclass
class DotlessAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a dotless authority domain is used in a restricted multiverse."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "'{reserved_name}' is reserved: "
        "authority domains without '.' are reserved "
        "in the '{multiverse_name}' multiverse"
    )


@dataclass
class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""

    message_format: ClassVar[str] = "'{reserved_name}' is a reserved multiverse name"


@dataclass
class PathMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str
    message_format: ClassVar[str] = (
        "definition path '{actual_path}' does not match file path '{expected_path}'"
    )


@dataclass
class UniverseWithoutAuthorityDiagnostic(Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe '{universe_name}' requires an authority; "
        "only 'standard' may be used without an authority"
    )


@dataclass
class DuplicateDefinitionDiagnostic(Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate {definition_type} definition for path '{path}'; "
        "first defined on line {first_definition_line}"
    )


@dataclass
class LocalNameConflictDiagnostic(Diagnostic):
    """Diagnostic for when a local name conflicts with another local definition."""

    local_name: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate local definition '{local_name}'; "
        "first defined on line {first_definition_line}"
    )


@dataclass
class FqunMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's FQUN doesn't match the expected project FQUN."""

    expected: str
    actual: str
    message_format: ClassVar[str] = (
        "Fully-qualified universe name '{actual}' does not match "
        "project universe name '{expected}'"
    )


@dataclass
class AuthorityDomainTooShortDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain is too short."""

    domain: str
    message_format: ClassVar[str] = (
        "authority domain '{domain}' must be at least 2 characters"
    )


@dataclass
class AuthorityDomainInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain has an invalid character."""

    domain: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in authority domain '{domain}'"
    )


@dataclass
class InvalidAuthorityPathSegmentDiagnostic(Diagnostic):
    """Diagnostic for when an authority path segment has invalid format."""

    segment: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in authority path segment '{segment}'"
    )


@dataclass
class InvalidGlobalNamePathDiagnostic(Diagnostic):
    """Diagnostic for when a global name path segment has invalid format."""

    segment: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in path segment '{segment}'"
    )


@dataclass
class InvalidLocalNameFormatDiagnostic(Diagnostic):
    """Diagnostic for when a local name has invalid format."""

    local_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in local name '{local_name}'"
    )


@dataclass
class MultiverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name is too short."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "multiverse name '{multiverse_name}' must be at least 2 characters"
    )


@dataclass
class MultiverseNameInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name has an invalid character."""

    multiverse_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in multiverse name '{multiverse_name}'"
    )


@dataclass
class UniverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a universe name is too short."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe name '{universe_name}' must be at least 2 characters"
    )


@dataclass
class UniverseNameInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when a universe name has an invalid character."""

    universe_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{char}' in universe name '{universe_name}'"
    )


@dataclass
class GlobalReferenceMustUseShortFormDiagnostic(Diagnostic):
    """Diagnostic for when a same-FQUN global reference uses full form."""

    fqun: str
    message_format: ClassVar[str] = (
        "global name references with the same fully-qualified universe name "
        "as the enclosing definition must use the short form; "
        "delete '{fqun}:' from this reference"
    )
