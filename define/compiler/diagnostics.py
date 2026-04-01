"""Diagnostic types for the Define language validator."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import ClassVar

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast, exceptions

from define.compiler import constants


def _format_position(pos: ast.SourcePosition) -> str:
    """Format a source position as a human-readable location string."""
    if pos.file_path is not None:
        return f'File "{pos.file_path}", line {pos.line}, column {pos.column}'
    return f"line {pos.line}, column {pos.column}"


@dataclass
class Diagnostic:
    """Base class for all validation diagnostics."""

    location: ast.SourcePosition
    message_format: ClassVar[str] = ""

    @property
    def message(self) -> str:
        """Render the diagnostic message from the format template."""
        return self.message_format.format(self=self)

    def format(self, source_lines: Sequence[str]) -> str:
        """Format the diagnostic with source context and caret pointer."""
        line_idx = self.location.line - 1
        source_line = (
            source_lines[line_idx] if 0 <= line_idx < len(source_lines) else ""
        )

        column = self.location.column
        caret_line = " " * (column - 1) + "^"
        header = _format_position(self.location)

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
class UnnecessarySelfReferenceDiagnostic(Diagnostic):
    """Diagnostic for when a definition unnecessarily references itself in a chain."""

    definition_name: str
    message_format: ClassVar[str] = (
        "the reference to '{self.definition_name}' is not necessary"
        " because the code is already inside that definition"
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
class UnknownGlobalNameDiagnostic(Diagnostic):
    """Diagnostic for when a global name starts a chain but is not available."""

    source_global_name: str
    full_global_name: str
    message_format: ClassVar[str] = (
        "'{self.source_global_name}' is not available inside of this definition."
        " To make it available, add this line at the top of the definition:\n\n"
        "   this dimension point must have the '{self.full_global_name}'."
    )


@dataclass
class LocalActionNameDiagnostic(Diagnostic):
    """Diagnostic for when an action uses a local name instead of a global reference."""

    local_name: str
    message_format: ClassVar[str] = (
        "actions cannot have local names, but '{self.local_name}' is a local name"
    )


@dataclass
class CreateInOccupiedPositionDiagnostic(Diagnostic):
    """Diagnostic for when a dimension point is created in a position that already has one."""

    position_name: str
    created_at: ast.SourcePosition
    message_format: ClassVar[str] = (
        "a dimension point already exists in '{self.position_name}';"
        " it was put there at:\n{self.formatted_created_at}"
    )

    @property
    def formatted_created_at(self) -> str:
        """Format the created_at position as a human-readable location string."""
        return _format_position(self.created_at)


@dataclass
class MoveToOccupiedPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move's destination position already contains a dimension point."""

    position_name: str
    occupied_at: ast.SourcePosition | None = None

    @property
    @typing.override
    def message(self) -> str:
        """Render the diagnostic message, optionally including the occupied-at position."""
        base = (
            f"cannot move a dimension point to '{self.position_name}'"
            " because it already contains one"
        )
        if self.occupied_at is not None:
            return f"{base}; it was put there at:\n{_format_position(self.occupied_at)}"
        return base


@dataclass
class MoveFromEmptyPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's source position has no dimension point."""

    position_name: str
    message_format: ClassVar[str] = (
        "cannot move a dimension point from '{self.position_name}'"
        " because it does not contain one"
    )


@dataclass
class MoveToSamePositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's from and to positions are the same."""

    position_name: str
    message_format: ClassVar[str] = (
        "source and destination cannot be identical when moving dimension points"
        " ('{self.position_name}' is the name of both"
        " the source and destination here)"
    )


@dataclass
class MoveViolatesConstraintsDiagnostic(Diagnostic):
    """Diagnostic for when a move's destination constraints are not satisfied."""

    source_position: str
    target_position: str
    # TODO: missing_qualities should use source form, not canonical form.
    missing_qualities: Sequence[str]

    @property
    def missing_list(self) -> str:
        """Format the missing qualities as an indented list."""
        return "\n  ".join(self.missing_qualities)

    message_format: ClassVar[str] = (
        "cannot move a dimension point\n"
        "  from: {self.source_position}\n"
        "    to: {self.target_position}\n"
        "because the dimension point being moved does not have the required qualities:\n"
        "  {self.missing_list}"
    )


@dataclass
class MoveIntoDefiningPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement moves a dimension point into a position it defines."""

    source_position: str
    target_position: str
    message_format: ClassVar[str] = (
        "cannot move a dimension point\n"
        "  from: {self.source_position}\n"
        "    to: {self.target_position}\n"
        "because the source position defines the destination position"
        " ('{self.source_position}' is the start of both positions)"
    )


@dataclass
class ChainedLocalNameRequiresActionDiagnostic(Diagnostic):
    """Diagnostic for when a local name in a chain is not preceded by a global action."""

    local_name: str
    preceding_name: str
    message_format: ClassVar[str] = (
        "local name '{self.local_name}' in a chain must be preceded by"
        " a globally-named action, but is preceded by '{self.preceding_name}'"
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


@dataclass
class EmptyActionStatementsBlockDiagnostic(Diagnostic):
    """Diagnostic for when an action statements block contains no statements."""

    message_format: ClassVar[str] = (
        "action statements block must contain at least one action statement"
    )


@dataclass
class EmptyPositionInitBlockDiagnostic(Diagnostic):
    """Diagnostic for when a position initialization block contains no statements."""

    message_format: ClassVar[str] = (
        "position initialization block must contain at least one action statement"
    )


@dataclass
class EntryPointNotPositionDiagnostic(Diagnostic):
    """Diagnostic for when the program entry point is not a position."""

    message_format: ClassVar[str] = (
        "the entry point of a Define program must be a position"
    )


@dataclass
class IncorrectIndentationDiagnostic(Diagnostic):
    """Diagnostic for when a line has incorrect indentation."""

    expected_indent: int
    actual_indent: int
    message_format: ClassVar[str] = (
        "expected {self.expected_indent} spaces of indentation on this line,"
        " but found {self.actual_indent}"
    )


# TODO: These diagnostics should show source context from inferred_at,
# not just the file/line/column. This requires passing the other file's
# source lines through to the diagnostic's format() method.


@dataclass
class ActionRequirementDiagnostic(Diagnostic):
    """Base class for diagnostics about interface position occupancy state."""

    action_name: str
    position_name: str
    inferred_at: ast.SourcePosition
    propagated_from_locations: list[ast.SourcePosition]

    # TODO: This really needs to be able to show all the relevant
    # source lines. I think we could do that by passing in a
    # source_map to format() and providing some sort of get_context
    # method on the base Diagnostic. The alternative is passing in
    # a source_map on construction of the Diagnostic, but then that
    # means that everything in all of the compiler has to be able
    # to access source_lines for all files.
    @property
    def formatted_inferred_at(self) -> str:
        """Format the inferred_at position and any propagation chain."""
        lines: list[str] = []
        lines.append("This requirement happens because of:")
        lines.append(_format_position(self.inferred_at))
        for i, pos in enumerate(self.propagated_from_locations):
            indent = "  " * (i + 1)
            lines.append(f"{indent}{_format_position(pos)}")
        return "\n".join(lines)


@dataclass
class ActionRequiresEmptyPositionDiagnostic(ActionRequirementDiagnostic):
    """Diagnostic for when an action requires an interface position to be empty but it is not."""

    filled_at: ast.SourcePosition
    message_format: ClassVar[str] = (
        "this line is triggering `{self.action_name}` to run.\n"
        "However, '{self.position_name}' must be empty before that action runs, and it is not empty.\n"
        "It was filled at:\n{self.formatted_filled_at}\n\n"
        "{self.formatted_inferred_at}"
    )

    @property
    def formatted_filled_at(self) -> str:
        """Format the filled_at position as a human-readable location string."""
        return _format_position(self.filled_at)


@dataclass
class ActionRequiresOccupiedPositionDiagnostic(ActionRequirementDiagnostic):
    """Diagnostic for when an action requires an interface position to be occupied but it is not."""

    message_format: ClassVar[str] = (
        "this line is triggering `{self.action_name}` to run.\n"
        "However, '{self.position_name}' must be occupied before that action runs, and it not occupied.\n\n"
        "{self.formatted_inferred_at}"
    )


# TODO: Should perhaps just merge this with the normal MoveFromEmpty diagnostic.
@dataclass
class MoveFromEmptyInterfacePositionDiagnostic(Diagnostic):
    """Diagnostic for moving from an empty action interface position."""

    position_name: str
    inferred_at: ast.SourcePosition | None

    @property
    @typing.override
    def message(self) -> str:
        """Render the diagnostic message."""
        base = (
            f"cannot move a dimension point from '{self.position_name}'"
            f" because it does not contain one"
        )
        if self.inferred_at is not None:
            return f"{base}; it was emptied at:\n{_format_position(self.inferred_at)}"
        return f"{base}; action interface positions are empty by default"
