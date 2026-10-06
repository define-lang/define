"""Diagnostic types for the Define language validator."""

from __future__ import annotations

import enum
import textwrap
import typing
from typing import ClassVar, Final

import msgspec

from define.compiler import constants, name_types
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast, config
    from define.compiler.errors import source_map


# The statement that reads every input view and writes every output view of
# each type of operation.
_ALL_VIEWS_STATEMENTS: Final = {
    name_types.NameType.OPERATION: "execute the encoding operation",
    name_types.NameType.ENCODING_OPERATION: "execute the computer operation",
}


class Diagnostic(msgspec.Struct):
    """Base class for all validation diagnostics."""

    location: ast.SourceLocation
    message_format: ClassVar[str] = ""

    def render_message(self, _sources: source_map.SourceMap, /) -> str:
        """Render the diagnostic message, with source lines for other locations it mentions."""
        return self.message_format.format(self=self)

    def format(self, sources: source_map.SourceMap) -> str:
        """Format the diagnostic with the source lines of every location it mentions."""
        return (
            f"{sources.format_location(self.location)}\n{self.render_message(sources)}"
        )


class ReservedNameDiagnostic(Diagnostic):
    """Base class for reserved name diagnostics."""

    reserved_name: str


class ReservedUniverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved universe name is used."""

    message_format: ClassVar[str] = "'{self.reserved_name}' is a reserved universe name"


class ReservedAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority domain is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved authority domain"
    )


class DotlessAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a dotless authority domain is used in a restricted multiverse."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is reserved: "
        "authority domains without '.' are reserved "
        "in the '{self.multiverse_name}' multiverse"
    )


class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved multiverse name"
    )


class PathMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str
    message_format: ClassVar[str] = (
        "definition path '{self.actual_path}' does not match file path "
        "'{self.expected_path}'"
    )


class UniverseWithoutAuthorityDiagnostic(Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe_name}' requires an authority; "
        f"only '{constants.STANDARD_UNIVERSE}' may be used without an authority"
    )


class DuplicateDefinitionDiagnostic(Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate {self.definition_type} definition for path '{self.path}'; "
        "first defined on line {self.first_definition_line}"
    )


class LocalNameConflictDiagnostic(Diagnostic):
    """Diagnostic for when a local name conflicts with another local definition."""

    local_name: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate local definition '{self.local_name}'; "
        "first defined on line {self.first_definition_line}"
    )


class DuplicatePositionConstraintDiagnostic(Diagnostic):
    """Diagnostic for when a quality constraint appears twice in the same Position Constraint Block."""

    constraint_name: str
    first_constraint_line: int
    message_format: ClassVar[str] = (
        "duplicate quality constraint '{self.constraint_name}'; "
        "first declared on line {self.first_constraint_line}"
    )


class MultipleValueConstraintsDiagnostic(Diagnostic):
    """Base class for a Position Constraint Block that specifies more than one value type."""

    first_value_name: str
    first_constraint_line: int


class PositionMultipleValueConstraintsDiagnostic(MultipleValueConstraintsDiagnostic):
    """A position's Position Constraint Block specifies more than one value type."""

    message_format: ClassVar[str] = (
        "a position may only have one value constraint; "
        "'{self.first_value_name}' was already declared on line {self.first_constraint_line}"
    )


class ViewMultipleValueConstraintsDiagnostic(MultipleValueConstraintsDiagnostic):
    """A view's constraints specify more than one value type."""

    message_format: ClassVar[str] = (
        "a view may only have one value constraint; "
        "'{self.first_value_name}' was already declared on line {self.first_constraint_line}"
    )


class DuplicateQualityImplicationDiagnostic(Diagnostic):
    """Diagnostic for when the same quality implication appears twice in the same definition."""

    implication_name: str
    first_implication_line: int
    message_format: ClassVar[str] = (
        "duplicate quality implication '{self.implication_name}'; "
        "first declared on line {self.first_implication_line}"
    )


class UnusedQualityImplicationDiagnostic(Diagnostic):
    """Diagnostic for when a Quality Implication Statement is never used as a chain start in the definition body."""

    implication_name: str
    message_format: ClassVar[str] = (
        "'{self.implication_name}' is implied here, but it is never used as the "
        "first name of a chained name in the executed code of this definition; "
        "either remove the quality implication statement or reference "
        "'{self.implication_name}' in the executed code."
    )


class UnreferencedPositionDiagnostic(Diagnostic):
    """Diagnostic for a position defined but never referenced in its definition."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition or reference "
        "'{self.position_name}'."
    )


class UnreferencedViewDiagnostic(Diagnostic):
    """Diagnostic for an interface view never referenced in its operation."""

    view_name: str
    operation_name_type: name_types.NameType

    @property
    def all_views_statement(self) -> str:
        """The statement that references every view of this operation."""
        return _ALL_VIEWS_STATEMENTS[self.operation_name_type]

    message_format: ClassVar[str] = (
        "'{self.view_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition, reference "
        "'{self.view_name}', or {self.all_views_statement}."
    )


class ViewQualityConstraintDiagnostic(Diagnostic):
    """Diagnostic for a view constraint that names a position or action."""

    constraint_name: str
    message_format: ClassVar[str] = (
        "views may only have value and encoding constraints, "
        "but '{self.constraint_name}' is not a value or an encoding"
    )


class ViewMissingValueConstraintDiagnostic(Diagnostic):
    """Diagnostic for an interface view of a value operation without a value constraint."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have a value constraint, because every "
        "interface view on a value operation must have one"
    )


class ViewMissingEncodingConstraintDiagnostic(Diagnostic):
    """Diagnostic for an interface view of an encoding operation without an encoding constraint."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have an encoding constraint, because every "
        "interface view on an encoding operation must have one"
    )


class EncodingOperationViewValueConstraintDiagnostic(Diagnostic):
    """Diagnostic for a value constraint on an interface view of an encoding operation."""

    constraint_name: str
    message_format: ClassVar[str] = (
        "interface views on an encoding operation may not have value "
        "constraints, but '{self.constraint_name}' is a value"
    )


class ValueOperationViewEncodingConstraintDiagnostic(Diagnostic):
    """Diagnostic for an encoding constraint on an interface view of a value operation."""

    constraint_name: str
    message_format: ClassVar[str] = (
        "interface views on a value operation may not have encoding "
        "constraints, but '{self.constraint_name}' is an encoding"
    )


class OperationArgumentPositionDiagnostic(Diagnostic):
    """Diagnostic for an Operation Argument Statement in an operation definition that looks at a position."""

    position_name: str
    message_format: ClassVar[str] = (
        "within an operation, a view may only look at a view or a "
        "literal, but this is looking at '{self.position_name}'"
    )


class OperationArgumentViewDiagnostic(Diagnostic):
    """Diagnostic for an Operation Argument Statement in an action that looks at a view."""

    view_name: str
    message_format: ClassVar[str] = (
        "within an action, a view may only look at a position or a "
        "literal, but this is looking at '{self.view_name}'"
    )


class AliasedViewDiagnostic(Diagnostic):
    """Diagnostic for more than one view looking at the same view or position in one Operation Arguments Block."""

    looked_at_name: str
    first_argument_line: int
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is already being looked at by another view "
        "on line {self.first_argument_line}; two views in the same execution "
        "may not look at the same particle"
    )


class DuplicateOperationArgumentDiagnostic(Diagnostic):
    """Diagnostic for a view given more than one Operation Argument Statement in one execution."""

    view_name: str
    first_argument_line: int
    message_format: ClassVar[str] = (
        "'{self.view_name}' is already looking at something on line "
        "{self.first_argument_line}; each view can only be specified once in this block"
    )


class UndefinedOperationViewDiagnostic(Diagnostic):
    """Diagnostic for an Operation Argument Statement naming a view the executed operation does not define."""

    view_name: str
    operation_name: str
    interface_view_names: Sequence[str]

    @property
    def interface_view_list(self) -> str:
        """Format the interface views as an indented list."""
        return "\n  ".join(self.interface_view_names)

    message_format: ClassVar[str] = (
        "'{self.view_name}' is not an interface view of '{self.operation_name}'; "
        "its interface views are:\n"
        "  {self.interface_view_list}"
    )


class ArgumentsForOperationWithoutViewsDiagnostic(Diagnostic):
    """Diagnostic for an Operation Arguments Block executing an operation that has no interface views."""

    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' has no interface views, so it must end with "
        "a '.' instead of having a block here"
    )


class OperationArgumentOrderDiagnostic(Diagnostic):
    """Diagnostic for Operation Argument Statements out of the order of the executed operation's interface views."""

    view_name: str
    operation_name: str
    expected_order: Sequence[str]

    @property
    def expected_order_list(self) -> str:
        """Format the expected order as an indented list."""
        return "\n  ".join(self.expected_order)

    message_format: ClassVar[str] = (
        "'{self.view_name}' is out of order; the arguments to "
        "'{self.operation_name}' must be in the same order as its interface "
        "views:\n"
        "  {self.expected_order_list}"
    )


class MissingOperationArgumentDiagnostic(Diagnostic):
    """Diagnostic for an interface view of an executed operation with no Operation Argument Statement."""

    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' requires '{self.view_name}' to look at "
        "something; add a 'with {self.view_name} looking at' line"
    )


class OutputViewLooksAtLiteralDiagnostic(Diagnostic):
    """Diagnostic for an output view of an executed operation looking at a literal."""

    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' writes to '{self.view_name}',"
        " so it cannot look at a literal."
    )


class UnreadInputViewDiagnostic(Diagnostic):
    """Diagnostic for an input view that its operation never reads."""

    view_name: str
    operation_name_type: name_types.NameType

    @property
    def all_views_statement(self) -> str:
        """The statement that reads every input view of this operation."""
        return _ALL_VIEWS_STATEMENTS[self.operation_name_type]

    message_format: ClassVar[str] = (
        "'{self.view_name}' has 'it is read.', but nothing in this operation"
        " reads it. Either have an operation read it,"
        " {self.all_views_statement}, or remove 'it is read.'"
    )


class UnwrittenOutputViewDiagnostic(Diagnostic):
    """Diagnostic for an output view that its operation never writes to."""

    view_name: str
    operation_name_type: name_types.NameType

    @property
    def all_views_statement(self) -> str:
        """The statement that writes to every output view of this operation."""
        return _ALL_VIEWS_STATEMENTS[self.operation_name_type]

    message_format: ClassVar[str] = (
        "'{self.view_name}' has 'it is written.', but nothing in this operation"
        " writes to it. Either have an operation write to it,"
        " {self.all_views_statement}, or remove 'it is written.'"
    )


class WriteToInputOnlyViewDiagnostic(Diagnostic):
    """Diagnostic for an executed operation writing to an input-only view."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is read-only, so it cannot be written to."
        " However, '{self.view_name}' of '{self.operation_name}' writes to it"
        " on this line."
    )


class ReadFromUnwrittenOutputViewDiagnostic(Diagnostic):
    """Diagnostic for an executed operation reading an output-only view before anything writes to it."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is write-only, so it cannot be read until an"
        " earlier statement writes to it. However, '{self.view_name}' of"
        " '{self.operation_name}' reads it on this line before anything writes"
        " to it."
    )


class LookedAtKind(enum.Enum):
    """What an Operation Argument Statement's view is looking at."""

    VIEW = enum.auto()
    POSITION = enum.auto()


class OperationArgumentViolatesConstraintsDiagnostic(Diagnostic):
    """Diagnostic for a view looking at a particle that does not meet the view's constraints."""

    view_name: str
    looked_at_name: str
    looked_at_kind: LookedAtKind
    missing_qualities: Sequence[str]

    @property
    def looked_at_description(self) -> str:
        """Name what is being looked at."""
        match self.looked_at_kind:
            case LookedAtKind.VIEW:
                return f"'{self.looked_at_name}'"
            case LookedAtKind.POSITION:
                return f"the particle in '{self.looked_at_name}'"

    @property
    def missing_list(self) -> str:
        """Format the missing qualities as an indented list."""
        return "\n  ".join(self.missing_qualities)

    message_format: ClassVar[str] = (
        "'{self.view_name}' cannot look at '{self.looked_at_name}' because "
        "{self.looked_at_description} does not have the required qualities:\n"
        "  {self.missing_list}"
    )


class DeadConstraintDiagnostic(Diagnostic):
    """Base class for an unused constraint on a local or interface position."""

    constraint_name: str
    position_name: str


class DeadChildPositionDiagnostic(DeadConstraintDiagnostic):
    """Diagnostic for a position constraint on a local or interface position that is never used."""

    message_format: ClassVar[str] = (
        "'{self.constraint_name}' is a constraint of '{self.position_name}' here, "
        "but the child position it creates is never referenced within this "
        "definition and no move requires it; either reference "
        "'{self.position_name}::{self.constraint_name}' or remove the constraint."
    )


class DeadValueConstraintDiagnostic(DeadConstraintDiagnostic):
    """Diagnostic for a value constraint that is never used."""

    message_format: ClassVar[str] = (
        "'{self.constraint_name}' is a constraint of '{self.position_name}' here, "
        " but the value is never actually used on any particle created in this position. "
        " Either use the value or remove the constraint."
    )


class DeadEncodingConstraintDiagnostic(DeadConstraintDiagnostic):
    """Diagnostic for an encoding constraint that is never used."""

    message_format: ClassVar[str] = (
        "'{self.constraint_name}' is a constraint of '{self.position_name}' here,"
        " but the value of a particle created in this position is never used, so"
        " its encoding never matters. Either use the value or remove the constraint."
    )


class UntriggeredActionDiagnostic(DeadConstraintDiagnostic):
    """Diagnostic for an action constraint on a local or interface position that is never triggered."""

    message_format: ClassVar[str] = (
        "'{self.constraint_name}' is a constraint of '{self.position_name}' here, "
        "but the action it creates is never triggered within this definition and "
        "no move requires it; either trigger it or remove the constraint."
    )


class UntriggeredImpliedActionDiagnostic(Diagnostic):
    """Diagnostic for an implied action that is never triggered by the implying action."""

    implied_action_name: str
    message_format: ClassVar[str] = (
        "'{self.implied_action_name}' is implied here, but it is never triggered "
        "within this action; either trigger it or remove the implication."
    )


class DeadValueWriteDiagnostic(Diagnostic):
    """Diagnostic for a value written to a particle that nothing uses."""

    position_name: str
    message_format: ClassVar[str] = (
        "the value written to '{self.position_name}' here is never used; it needs to be"
        " used before it is written again. To use it, you can do any of these:\n"
        "  - read it in this action"
        "  - trigger an action that uses its value"
        "  - put it into an interface position or implied position and leave it there"
        " at the end of this action"
    )


class UntriggeredActionInterfaceDiagnostic(Diagnostic):
    """Diagnostic for an interface particle not present when its action triggers."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "a particle arrives in '{self.position_name}' here, but "
        "'{self.action_name}' is not triggered with that particle in this position "
        "before the particle moves or is destroyed, or before this action ends."
    )


class UnconsumedActionInterfaceDiagnostic(Diagnostic):
    """Diagnostic for an interface particle that remains after its caller ends."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "after triggering '{self.action_name}', this action must move or destroy every "
        "particle in that action's interface positions, but "
        "'{self.position_name}' still contains a particle when this action ends."
    )


class OccupiedActionInterfaceWhenActionTriggersDiagnostic(Diagnostic):
    """Diagnostic for an occupied action interface passed to another action."""

    action_name: str
    position_name: str
    # Where the particle arrived in the position, so the developer can find
    # the particle that has to move or be destroyed before the trigger.
    arrived_at: ast.SourceLocation

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        """Render the diagnostic message with where the particle arrived."""
        return (
            f"'{self.position_name}' contains a particle when '{self.action_name}' "
            "triggers here; move or destroy the particle before triggering that "
            f"action. The particle arrived at:\n{sources.format_location(self.arrived_at)}"
        )


class FqunMismatchDiagnostic(Diagnostic):
    """Diagnostic for when a definition's FQUN doesn't match the expected project FQUN."""

    expected: str
    actual: str
    message_format: ClassVar[str] = (
        "Fully-qualified universe name '{self.actual}' does not match "
        "project universe name '{self.expected}'"
    )


class AuthorityDomainTooShortDiagnostic(Diagnostic):
    """Diagnostic for when an authority domain is too short."""

    domain: str
    message_format: ClassVar[str] = (
        "authority domain '{self.domain}' must be at least 2 characters"
    )


class InvalidNameCharactersDiagnostic(Diagnostic):
    """Base class for diagnostics about characters that a part of a name may not contain."""

    # Each invalid character once, in the order it first appears.
    chars: tuple[str, ...]

    @property
    def invalid_characters(self) -> str:
        """The invalid characters, quoted, as a phrase for the message."""
        quoted = [f"'{char}'" for char in self.chars]
        if len(quoted) == 1:
            return f"invalid character {quoted[0]}"
        return f"invalid characters {', '.join(quoted[:-1])} and {quoted[-1]}"


class AuthorityDomainInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when an authority domain has invalid characters."""

    domain: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in authority domain '{self.domain}'"
    )


class InvalidAuthorityPathSegmentDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when an authority path segment has invalid characters."""

    segment: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in authority path segment '{self.segment}'"
    )


class AuthorityPathEmptySegmentDiagnostic(Diagnostic):
    """Diagnostic for when an authority path contains an empty segment."""

    authority: str
    message_format: ClassVar[str] = (
        "authority path in '{self.authority}' must not contain '//'"
    )


class InvalidGlobalNamePathCharacterDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a global name path segment has invalid characters."""

    segment: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in path segment '{self.segment}'"
    )


class GlobalNamePathMissingLeadingSlashDiagnostic(Diagnostic):
    """Diagnostic for when a global path does not start with '/'."""

    path: str
    message_format: ClassVar[str] = "global name path '{self.path}' must start with '/'"


class GlobalNamePathTrailingSlashDiagnostic(Diagnostic):
    """Diagnostic for when a global path ends with '/'."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not end with '/'"
    )


class GlobalNamePathEmptySegmentDiagnostic(Diagnostic):
    """Diagnostic for when a global path contains an empty segment."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not contain '//'"
    )


class InvalidLocalNameFormatDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a local name has invalid characters."""

    local_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in local name '{self.local_name}'"
    )


class MultiverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a multiverse name is too short."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "multiverse name '{self.multiverse_name}' must be at least 2 characters"
    )


class MultiverseNameInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a multiverse name has invalid characters."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in multiverse name '{self.multiverse_name}'"
    )


class UniverseNameTooShortDiagnostic(Diagnostic):
    """Diagnostic for when a universe name is too short."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe name '{self.universe_name}' must be at least 2 characters"
    )


class UniverseNameInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a universe name has invalid characters."""

    universe_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in universe name '{self.universe_name}'"
    )


class GlobalReferenceMustUseShortFormDiagnostic(Diagnostic):
    """Diagnostic for when a same-FQUN global reference uses full form."""

    fqun: str
    message_format: ClassVar[str] = (
        "global name references with the same fully-qualified universe name "
        "as the enclosing definition must use the short form; "
        "delete '{self.fqun}:' from this reference"
    )


class ReferencedDefinitionNotFoundDiagnostic(Diagnostic):
    """Diagnostic for when a resolved file does not contain the referenced definition."""

    file_path: str
    definition_name: str
    message_format: ClassVar[str] = (
        "file '{self.file_path}' does not contain a definition for "
        "'{self.definition_name}'"
    )


class StandardDefinitionNotFoundDiagnostic(Diagnostic):
    """Diagnostic for a reference to a name the standard universe does not define."""

    definition_name: str
    message_format: ClassVar[str] = (
        "the standard universe does not define '{self.definition_name}'"
    )


class ReferencedFileNotFoundDiagnostic(Diagnostic):
    """Diagnostic for when a referenced file does not exist."""

    file_path: str
    message_format: ClassVar[str] = (
        "there is no file '{self.file_path}' in this project"
    )


class ExternalUniverseNotConfiguredDiagnostic(Diagnostic):
    """Diagnostic for when a cross-universe reference targets an unconfigured universe."""

    universe: str
    current_universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe}' is not configured as a dependency "
        "of this universe ({self.current_universe_name}); "
        "add it to .define/deps/local.defcl"
    )


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


class ConfigLoadErrorDiagnostic(Diagnostic):
    """Diagnostic for when project configuration fails to load."""

    error: config.ConfigError
    message_format: ClassVar[str] = (
        "an error occurred while loading the project configuration:\n{self.error}"
    )


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


class CircularGlobalReferenceDiagnostic(Diagnostic):
    """Diagnostic for when resolving references would create a cycle."""

    cycle: list[str]

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
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


class UnnecessarySelfReferenceDiagnostic(Diagnostic):
    """Diagnostic for when a definition unnecessarily references itself in a chain."""

    definition_name: str
    message_format: ClassVar[str] = (
        "the reference to '{self.definition_name}' is not necessary"
        " because the code is already inside that definition"
    )


class PositionReferenceChainEndDiagnostic(Diagnostic):
    """Diagnostic for when a position reference chain ends with an action."""

    message_format: ClassVar[str] = "position references must end with a position name"


class UndefinedLocalNameDiagnostic(Diagnostic):
    """Diagnostic for when a local typed name is used but not defined in scope."""

    local_name: str
    message_format: ClassVar[str] = (
        "'{self.local_name}' has not been defined before this line of code"
    )


class UnknownGlobalNameDiagnostic(Diagnostic):
    """Diagnostic for when a global name starts a chain but is not available."""

    source_global_name: str
    full_global_name: str
    message_format: ClassVar[str] = (
        "'{self.source_global_name}' is not available inside of this definition."
        " To make it available, add this line at the top of the definition:\n\n"
        "   it also assigns the '{self.full_global_name}'."
    )


class LocalActionNameDiagnostic(Diagnostic):
    """Diagnostic for when an action uses a local name instead of a global reference."""

    local_name: str
    message_format: ClassVar[str] = (
        "actions cannot have local names, but '{self.local_name}' is a local name"
    )


# TODO: Inform the developer if the creation ocurred due to an inferred requirement
# from the caller. That's also relevant when you have multiple constructors run on
# the same position that do something conflicting to one of the other positions, and
# you need to refer to three things (the create statement that triggered the
# constructors and then the two different constructors that are conflicting).
class CreateInOccupiedPositionDiagnostic(Diagnostic):
    """Diagnostic for when a particle is created in a position that already has one."""

    position_name: str
    populated_at: ast.SourceLocation
    message_format: ClassVar[str] = (
        "a particle already exists in '{self.position_name}';"
        " it was put there at:\n{populated_at}"
    )

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        return self.message_format.format(
            self=self, populated_at=sources.format_location(self.populated_at)
        )


class ParentPositionNotOccupiedDiagnostic(Diagnostic):
    """Diagnostic for when a position is accessed but its parent has no particle."""

    position_name: str
    parent_position_name: str
    message_format: ClassVar[str] = (
        "cannot access '{self.position_name}'"
        " because '{self.parent_position_name}' does not contain a particle.\n"
        "To fix this, either create a particle in '{self.parent_position_name}'"
        " or move an existing particle there."
    )


class MoveToOccupiedPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move's destination position already contains a particle."""

    position_name: str
    occupied_at: ast.SourceLocation
    message_format: ClassVar[str] = (
        "cannot move a particle to '{self.position_name}' because it already"
        " contains one; it was put there at:\n{occupied_at}"
    )

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        return self.message_format.format(
            self=self, occupied_at=sources.format_location(self.occupied_at)
        )


class MoveFromEmptyPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's source position has no particle."""

    position_name: str
    is_action_interface_position: bool = False
    inferred_at: ast.SourceLocation | None = None

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        """Render the diagnostic message, optionally including the inferred-at location."""
        base = (
            f"cannot move a particle from '{self.position_name}'"
            " because it does not contain one"
        )
        if self.inferred_at is not None:
            return f"{base}; it was emptied at:\n{sources.format_location(self.inferred_at)}"
        if self.is_action_interface_position:
            return f"{base}; action interface positions are empty by default"
        return base


class DestroyInEmptyPositionDiagnostic(Diagnostic):
    """Diagnostic for when a destroy statement's target position has no particle."""

    position_name: str
    message_format: ClassVar[str] = (
        "cannot destroy a particle in '{self.position_name}'"
        " because it does not contain one"
    )


class MoveToSamePositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's from and to positions are the same."""

    position_name: str
    message_format: ClassVar[str] = (
        "source and destination cannot be identical when moving particles"
        " ('{self.position_name}' is the name of both"
        " the source and destination here)"
    )


class ValueSettingSamePositionDiagnostic(Diagnostic):
    """Diagnostic for a value setting statement referencing the same position twice."""

    position_name: str
    message_format: ClassVar[str] = (
        "the left and right sides of a value setting statement cannot be"
        " the same position ('{self.position_name}')"
    )


class ValueSettingEmptyPositionDiagnostic(Diagnostic):
    """A Value Setting Statement references an empty position."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' has no particle in it, so it"
        " cannot be used in a value setting statement."
    )


class ValueSettingMissingValueTypeDiagnostic(Diagnostic):
    """A particle in a Value Setting Statement has no assigned value type."""

    position_name: str
    origin_position_name: str
    message_format: ClassVar[str] = (
        "the particle in '{self.position_name}' has no assigned value type."
        " Set a value constraint on the position where it originated:"
        " '{self.origin_position_name}'."
    )


class OperationArgumentEmptyPositionDiagnostic(Diagnostic):
    """An Operation Argument Statement looks at an empty position."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' has no particle in it, so a view cannot look at it."
    )


class UnsetValueDiagnostic(Diagnostic):
    """A Value Setting Statement or an Operation Argument Statement reads a particle whose value is unset."""

    position_name: str
    message_format: ClassVar[str] = (
        "the particle in '{self.position_name}' must have a set value"
        " before its value can be read."
    )


class ValueSettingTypeMismatchDiagnostic(Diagnostic):
    """A Value Setting Statement uses particles with different value types."""

    target_position: str
    source_position: str
    target_value_type: str
    source_value_type: str
    message_format: ClassVar[str] = (
        "this value setting statement has particles with two different value types,"
        " which is not allowed. {self.target_position} has {self.target_value_type}"
        " and {self.source_position} has {self.source_value_type}."
    )


class LiteralCannotSetValueDiagnostic(Diagnostic):
    """A literal's encoding cannot be read as the value type it is setting."""

    potential_literal: str
    literal_encoding: str
    value_type: str
    supported_encodings: Sequence[str]

    @property
    def supported_encodings_advice(self) -> str:
        """Say which literal encodings could set the value type, if any can."""
        if not self.supported_encodings:
            return f"In fact, {self.value_type} cannot be set by a literal at all."
        encoding_list = "\n    ".join(self.supported_encodings)
        return (
            f"To set a {self.value_type}, use a literal with one of these"
            f" encodings:\n    {encoding_list}"
        )

    message_format: ClassVar[str] = (
        "{self.potential_literal} cannot set a {self.value_type}, because literals"
        " with the {self.literal_encoding} cannot be read as {self.value_type}.\n"
        "{self.supported_encodings_advice}"
    )


class LiteralCannotBeConvertedDiagnostic(Diagnostic):
    """A literal's encoding cannot be translated into the encoding a view requires."""

    potential_literal: str
    literal_encoding: str
    encoding: str
    supported_encodings: Sequence[str]

    @property
    def supported_encodings_advice(self) -> str:
        """Say which literal encodings could be translated into the encoding, if any can."""
        if not self.supported_encodings:
            return f"In fact, {self.encoding} cannot be set by a literal at all."
        encoding_list = "\n    ".join(self.supported_encodings)
        return (
            f"To look at a literal as {self.encoding}, use a literal with one of"
            f" these encodings:\n    {encoding_list}"
        )

    message_format: ClassVar[str] = (
        "{self.potential_literal} cannot be looked at as {self.encoding}, because"
        " literals with the {self.literal_encoding} cannot be translated into"
        " {self.encoding}.\n"
        "{self.supported_encodings_advice}"
    )


class ValueHasNoEncodingDiagnostic(Diagnostic):
    """A value type has no encoding, so it can never be set."""

    value_type: str
    message_format: ClassVar[str] = (
        "{self.value_type} has no encoding, so no value of this type can be set."
    )


class InvalidLiteralContentDiagnostic(Diagnostic):
    """A literal's content cannot be represented in the value's encoding."""

    content: str
    potential_literal: str
    value_encoding: str
    reason: str
    message_format: ClassVar[str] = (
        "'{self.content}' is not a valid value for '{self.potential_literal}' here,"
        " because it cannot be represented as '{self.value_encoding}':"
        " {self.reason}."
    )


class MoveViolatesConstraintsDiagnostic(Diagnostic):
    """Diagnostic for when a move's destination constraints are not satisfied."""

    source_position: str
    target_position: str
    missing_qualities: Sequence[str]

    @property
    def missing_list(self) -> str:
        """Format the missing qualities as an indented list."""
        return "\n  ".join(self.missing_qualities)

    message_format: ClassVar[str] = (
        "cannot move a particle\n"
        "  from: {self.source_position}\n"
        "    to: {self.target_position}\n"
        "because the particle being moved does not have the required qualities:\n"
        "  {self.missing_list}"
    )


class MoveIntoDefiningPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement moves a particle into a position it defines."""

    source_position: str
    target_position: str
    message_format: ClassVar[str] = (
        "cannot move a particle\n"
        "  from: {self.source_position}\n"
        "    to: {self.target_position}\n"
        "because the source position defines the destination position"
        " ('{self.source_position}' is the start of both positions)"
    )


class ChainedLocalNameRequiresActionDiagnostic(Diagnostic):
    """Diagnostic for when a local name in a chain is not preceded by a global action."""

    local_name: str
    preceding_name: str
    message_format: ClassVar[str] = (
        "local name '{self.local_name}' in a chain must be preceded by"
        " a globally-named action, but is preceded by '{self.preceding_name}'"
    )


class ChainElementNotInConstraintsDiagnostic(Diagnostic):
    """Diagnostic for when a chain element is not in the first position's constraints."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' must be declared as an explicit 'it has the'"
        " constraint in the definition of '{self.parent_name}'"
    )


class ChainElementNotInterfacePositionDiagnostic(Diagnostic):
    """Diagnostic for when a local name after an action is not an interface position of that action."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is not an interface position of the action"
        " '{self.parent_name}'; only that action's interface positions may follow"
        " it in a chained name"
    )


class ChainGlobalNameAfterActionDiagnostic(Diagnostic):
    """Diagnostic for when a global name follows an action in a chained name."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is a global name, but only the interface positions"
        " of the action '{self.parent_name}' may follow it in a chained name;"
        " interface positions are written as local names"
    )


class EmptyActionStatementsBlockDiagnostic(Diagnostic):
    """Diagnostic for when an action statements block contains no statements."""

    message_format: ClassVar[str] = (
        "action statements block must contain at least one action statement"
    )


class EntryPointNotConstructorDiagnostic(Diagnostic):
    """Diagnostic for when the program entry point is not a constructor."""

    message_format: ClassVar[str] = (
        "the entry point of a Define program must be a constructor"
    )


class EntryPointInterfacePositionDiagnostic(Diagnostic):
    """Diagnostic for an interface position on the program entry point."""

    position_name: str
    message_format: ClassVar[str] = (
        "the entry point action of a Define program must not define interface"
        " positions, but it defines '{self.position_name}'"
    )


class EntryPointOccupiedImpliedPositionRequirementDiagnostic(Diagnostic):
    """Diagnostic for an occupied implied-position requirement on the entry point."""

    position_name: str
    message_format: ClassVar[str] = (
        "the entry point action of a Define program must not infer that implied"
        " position '{self.position_name}' is occupied"
    )


class IncorrectIndentationDiagnostic(Diagnostic):
    """Diagnostic for when a line has incorrect indentation."""

    expected_indent: int
    actual_indent: int
    message_format: ClassVar[str] = (
        "expected {self.expected_indent} spaces of indentation on this line,"
        " but found {self.actual_indent}"
    )


class InferredRequirementViolationDiagnostic(Diagnostic):
    """Diagnostic for when an automatically inferred requirement is violated.

    The same shape serves every case (Action Execution, destructor, Destruction
    Contract): a uniform top sentence naming the runner whose run the requirement
    gates, followed by the causal stack.
    """

    position_name: str
    propagation_chain: list[action_contract.PropagationStep]
    required_empty: bool
    # The action whose Action Statements Block we can't run because the requirement
    # isn't satisfied.
    action_name: str
    required_value: bool = False
    message_format: ClassVar[str] = (
        "'{self.position_name}' must be {self.required_state} before"
        " '{self.action_name}' runs.\n\n"
        "{propagation_chain}"
    )

    @property
    def required_state(self) -> str:
        """The word describing the state the position must be in."""
        if self.required_value:
            return "occupied by a particle with a set value"
        return "empty" if self.required_empty else "occupied"

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        lines = ["This error happens because:"]
        for step in self.propagation_chain:
            lines.extend(
                (
                    f"  {self._format_propagation_step(step)}:",
                    textwrap.indent(sources.format_location(step.location), "    "),
                )
            )
        return self.message_format.format(self=self, propagation_chain="\n".join(lines))

    def _format_propagation_step(self, step: action_contract.PropagationStep) -> str:
        """Render a propagation step as a human-readable label line."""
        match step.kind:
            case action_contract.PropagationKind.DIRECT_INFERENCE:
                return f"'{step.enclosing_quality_name}' infers this requirement"
            case action_contract.PropagationKind.DESTRUCTOR_CASCADE:
                return (
                    f"'{step.enclosing_quality_name}' destroys a particle,"
                    f" triggering the destructor '{step.triggered_quality_name}'"
                )
            case action_contract.PropagationKind.QUALITY_ASSIGNED:
                return (
                    f"'{step.triggered_quality_name}' is assigned to"
                    f" '{step.enclosing_quality_name}'"
                )
            case action_contract.PropagationKind.CONSTRUCTOR_TRIGGER:
                return (
                    f"'{step.enclosing_quality_name}' creates a particle, triggering"
                    f" the constructor '{step.triggered_quality_name}'"
                )
            case action_contract.PropagationKind.ACTION_TRIGGER:
                return (
                    f"'{step.enclosing_quality_name}' triggers"
                    f" '{step.triggered_quality_name}'"
                )
            case action_contract.PropagationKind.PARTICLE_ORIGIN:
                return (
                    f"the particle in '{step.enclosing_quality_name}' comes from here"
                )
            case action_contract.PropagationKind.AUTO_DESTRUCTION:
                return (
                    f"the particle in '{step.enclosing_quality_name}' is automatically"
                    f" destroyed at the end of '{step.triggered_quality_name}'"
                )
            case action_contract.PropagationKind.FILL_SITE:
                return f"'{step.enclosing_quality_name}' is filled here"


class DestructorGuaranteeDiagnostic(Diagnostic):
    """Base class for diagnostics about a destructor changing a contracted position's state."""

    position_name: str


class DestructorProducesEmptyGuaranteeDiagnostic(DestructorGuaranteeDiagnostic):
    """Diagnostic for when a destructor leaves a contracted position empty that started occupied."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line empties '{self.position_name}' and then nothing puts the same"
        " particle back into that position."
    )


class DestructorProducesOccupiedGuaranteeDiagnostic(DestructorGuaranteeDiagnostic):
    """Diagnostic for when a destructor leaves a new particle in a contracted position."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line creates a new particle in '{self.position_name}' and then"
        " nothing removes it from that position."
    )


class DestructorChangesValueDiagnostic(DestructorGuaranteeDiagnostic):
    """A destructor changes a contracted particle's value."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line changes the value of the particle in '{self.position_name}'."
    )


class DestructorProducesOccupiedByExistingGuaranteeDiagnostic(
    DestructorGuaranteeDiagnostic
):
    """Diagnostic for when a destructor moves a particle into a contracted position."""

    origin_name: str
    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line moves a particle from '{self.origin_name}' into"
        " '{self.position_name}' and then nothing moves it back out of that position."
    )


class DestroyInEmptyInterfacePositionDiagnostic(Diagnostic):
    """Diagnostic for destroying from an empty action interface position."""

    position_name: str
    inferred_at: ast.SourceLocation | None

    @typing.override
    def render_message(self, sources: source_map.SourceMap, /) -> str:
        """Render the diagnostic message."""
        base = (
            f"cannot destroy a particle in '{self.position_name}'"
            f" because it does not contain one"
        )
        if self.inferred_at is not None:
            return f"{base}; it was emptied at:\n{sources.format_location(self.inferred_at)}"
        return f"{base}; action interface positions are empty by default"


class ActionSelfTriggerDiagnostic(Diagnostic):
    """Diagnostic for when an action writes to its own trigger position."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "'{self.action_name}' cannot trigger itself"
        " by writing to its own trigger position '{self.position_name}'"
    )
