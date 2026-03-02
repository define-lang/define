"""Diagnostic types for the Define language validator."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import ClassVar

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast, exceptions

from define.compiler import constants


@dataclass
class Diagnostic:
    """Base class for all validation diagnostics."""

    position: ast.SourcePosition
    message_format: ClassVar[str] = ""

    @property
    def message(self) -> str:
        """Render the diagnostic message from the format template."""
        return self.message_format.format(self=self)

    def format(self, source_lines: Sequence[str], file_name: str | None = None) -> str:
        """Format the diagnostic with source context and caret pointer."""
        line_idx = self.position.line - 1
        source_line = (
            source_lines[line_idx] if 0 <= line_idx < len(source_lines) else ""
        )

        column = self.position.column
        caret_line = " " * (column - 1) + "^"
        if file_name is not None:
            header = (
                f'File "{file_name}", line {self.position.line}, '
                + f"column {self.position.column}"
            )
        else:
            header = f"line {self.position.line}, column {self.position.column}"

        return f"{header}\n{source_line}\n{caret_line}\n{self.message}"


@dataclass
class ReservedNameDiagnostic(Diagnostic):
    """Base class for reserved name diagnostics."""

    reserved_name: str


@dataclass
class ReservedUniverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved universe name is used."""

    message_format: ClassVar[str] = "'{self.reserved_name}' is a reserved universe name"


@dataclass
class ReservedAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority domain is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved authority domain"
    )


@dataclass
class DotlessAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a dotless authority domain is used in a restricted multiverse."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is reserved: "
        "authority domains without '.' are reserved "
        "in the '{self.multiverse_name}' multiverse"
    )


@dataclass
class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved multiverse name"
    )


@dataclass
class PathMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str
    message_format: ClassVar[str] = (
        "definition path '{self.actual_path}' does not match file path "
        "'{self.expected_path}'"
    )


@dataclass
class UniverseWithoutAuthorityDiagnostic(Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe_name}' requires an authority; "
        "only 'standard' may be used without an authority"
    )


@dataclass
class DuplicateDefinitionDiagnostic(Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate {self.definition_type} definition for path '{self.path}'; "
        "first defined on line {self.first_definition_line}"
    )


@dataclass
class LocalNameConflictDiagnostic(Diagnostic):
    """Diagnostic for when a local name conflicts with another local definition."""

    local_name: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate local definition '{self.local_name}'; "
        "first defined on line {self.first_definition_line}"
    )


@dataclass
class FqunMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's FQUN doesn't match the expected project FQUN."""

    expected: str
    actual: str
    message_format: ClassVar[str] = (
        "Fully-qualified universe name '{self.actual}' does not match "
        "project universe name '{self.expected}'"
    )


@dataclass
class AuthorityDomainTooShortDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain is too short."""

    domain: str
    message_format: ClassVar[str] = (
        "authority domain '{self.domain}' must be at least 2 characters"
    )


@dataclass
class AuthorityDomainInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain has an invalid character."""

    domain: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in authority domain '{self.domain}'"
    )


@dataclass
class InvalidAuthorityPathSegmentDiagnostic(Diagnostic):
    """Diagnostic for when an authority path segment has invalid format."""

    segment: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in authority path segment '{self.segment}'"
    )


@dataclass
class AuthorityPathEmptySegmentDiagnostic(Diagnostic):
    """Diagnostic for when an authority path contains an empty segment."""

    authority: str
    message_format: ClassVar[str] = (
        "authority path in '{self.authority}' must not contain '//'"
    )


@dataclass
class InvalidGlobalNamePathCharacterDiagnostic(Diagnostic):
    """Diagnostic for when a global name path segment has invalid format."""

    segment: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in path segment '{self.segment}'"
    )


@dataclass
class GlobalNamePathMissingLeadingSlashDiagnostic(Diagnostic):
    """Diagnostic for when a global path does not start with '/'."""

    path: str
    message_format: ClassVar[str] = "global name path '{self.path}' must start with '/'"


@dataclass
class GlobalNamePathTrailingSlashDiagnostic(Diagnostic):
    """Diagnostic for when a global path ends with '/'."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not end with '/'"
    )


@dataclass
class GlobalNamePathEmptySegmentDiagnostic(Diagnostic):
    """Diagnostic for when a global path contains an empty segment."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not contain '//'"
    )


@dataclass
class InvalidLocalNameFormatDiagnostic(Diagnostic):
    """Diagnostic for when a local name has invalid format."""

    local_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in local name '{self.local_name}'"
    )


@dataclass
class MultiverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name is too short."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "multiverse name '{self.multiverse_name}' must be at least 2 characters"
    )


@dataclass
class MultiverseNameInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name has an invalid character."""

    multiverse_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in multiverse name '{self.multiverse_name}'"
    )


@dataclass
class UniverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a universe name is too short."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe name '{self.universe_name}' must be at least 2 characters"
    )


@dataclass
class UniverseNameInvalidCharDiagnostic(Diagnostic):
    """Diagnostic for when a universe name has an invalid character."""

    universe_name: str
    char: str
    message_format: ClassVar[str] = (
        "invalid character '{self.char}' in universe name '{self.universe_name}'"
    )


@dataclass
class GlobalReferenceMustUseShortFormDiagnostic(Diagnostic):
    """Diagnostic for when a same-FQUN global reference uses full form."""

    fqun: str
    message_format: ClassVar[str] = (
        "global name references with the same fully-qualified universe name "
        "as the enclosing definition must use the short form; "
        "delete '{self.fqun}:' from this reference"
    )


@dataclass
class ReferencedGlobalNameWrongTypeDiagnostic(Diagnostic):
    """Diagnostic for when a referenced file lacks the referenced type at that path."""

    path: str
    expected_type: str
    message_format: ClassVar[str] = (
        "path '{self.path}' does not define a global name with the type "
        "'{self.expected_type}'"
    )


@dataclass
class ReferencedFileNotFoundDiagnostic(Diagnostic):
    """Diagnostic for when a referenced file does not exist."""

    file_path: str
    message_format: ClassVar[str] = (
        "there is no file '{self.file_path}' in this project"
    )


@dataclass
class ExternalUniverseNotConfiguredDiagnostic(Diagnostic):
    """Diagnostic for when a cross-universe reference targets an unconfigured universe."""

    universe: str
    current_universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe}' is not configured as a dependency "
        "of this universe ({self.current_universe_name}); "
        "add it to .define/deps/local.defcl"
    )


@dataclass
class NoProjectRootInNonFilesystemContextDiagnostic(Diagnostic):
    """Diagnostic for when an external universe reference requires loading from disk outside a project root."""

    universe: str
    config_path: str
    message_format: ClassVar[str] = (
        "universe '{self.universe}' was not previously defined, "
        + "so the compiler tried to load it from the filesystem. "
        + "However, {self.config_path} was not found.\n"
        + "For more information, see "
        + constants.DOCS_ROOT
        + "/project-root.md"
    )


@dataclass
class ConfigLoadErrorDiagnostic(Diagnostic):
    """Diagnostic for when project configuration fails to load."""

    error: exceptions.ConfigError
    message_format: ClassVar[str] = (
        "an error occurred while loading the project configuration:\n{self.error}"
    )


@dataclass
class SubRootAlreadyOccupiedDiagnostic(Diagnostic):
    """Diagnostic for when a sub-root path already has files loaded under a different universe."""

    universe: str
    sub_root_path: str
    existing_file: str
    existing_universe: str
    message_format: ClassVar[str] = (
        "attempted to load the universe '{self.universe}' in "
        "'{self.sub_root_path}' but '{self.existing_file}' was already "
        "registered as having the universe '{self.existing_universe}' ; "
        "two different universes cannot occupy '{self.sub_root_path}'"
    )


@dataclass
class PathInsideOtherUniverseDiagnostic(Diagnostic):
    """Diagnostic for when a path being loaded falls inside a different universe's sub-root."""

    path: str
    other_universe: str
    sub_root_path: str
    message_format: ClassVar[str] = (
        "the path '{self.path}' is inside of a different universe from this one "
        "('{self.other_universe}' located at '{self.sub_root_path}') ; "
        "two different universes cannot both occupy '{self.sub_root_path}'"
    )


@dataclass
class CircularGlobalReferenceDiagnostic(Diagnostic):
    """Diagnostic for when resolving references would create a cycle."""

    cycle: list[str]

    @property
    @typing.override
    def message(self) -> str:
        """Render a multi-line cycle listing with one edge per line."""
        if not self.cycle:
            raise ValueError("cycle must contain at least one typed global name")
        lines = [self.cycle[0]]
        lines.extend(f"  --> {name}" for name in self.cycle[1:])
        cycle_text = "\n".join(lines)
        return (
            "circular references between definitions are not allowed in Define:\n"
            + cycle_text
        )


@dataclass
class PositionReferenceChainEndDiagnostic(Diagnostic):
    """Diagnostic for when a position reference chain ends with an action."""

    message_format: ClassVar[str] = "position references must end with a position name"


@dataclass
class UndefinedLocalNameDiagnostic(Diagnostic):
    """Diagnostic for when a local typed name is used but not defined in scope."""

    local_name: str
    message_format: ClassVar[str] = (
        "'{self.local_name}' has not been defined before this line of code"
    )


@dataclass
class LocalActionNameDiagnostic(Diagnostic):
    """Diagnostic for when an action uses a local name instead of a global reference."""

    local_name: str
    message_format: ClassVar[str] = (
        "actions cannot have local names, but '{self.local_name}' is a local name"
    )


@dataclass
class LocalDuplicateDimensionPointDiagnostic(Diagnostic):
    """Diagnostic for when a dimension point is created in a position that already has one."""

    position_name: str
    first_creation_line: int
    message_format: ClassVar[str] = (
        "a dimension point already exists in '{self.position_name}'; "
        "first created on line {self.first_creation_line}"
    )


@dataclass
class MoveFromEmptyPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's source position has no dimension point."""

    position_name: str
    message_format: ClassVar[str] = (
        "cannot move a dimension point from '{self.position_name}'"
        " because it does not contain one"
    )


@dataclass
class ChainElementNotInConstraintsDiagnostic(Diagnostic):
    """Diagnostic for when a chain element is not in the first position's constraints."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is not declared as one of the"
        " 'it has the' requirements in the definition of '{self.parent_name}'"
    )


@dataclass
class ChainElementNotInActionDiagnostic(Diagnostic):
    """Diagnostic for when a chain element is part of an action's definition definition block."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is not defined inside the definition of '{self.parent_name}'"
    )
