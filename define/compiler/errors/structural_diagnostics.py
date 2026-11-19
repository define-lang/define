"""Diagnostics that structural validation reports."""

from __future__ import annotations

import typing
from typing import ClassVar

from define.compiler import constants
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering


class InvalidNameCharactersDiagnostic(diagnostics.Diagnostic):
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


class MultipleValueQualitiesDiagnostic(diagnostics.Diagnostic):
    """Base class for a Quality Assignment Block that assigns more than one value quality."""

    first_value_name: str
    first_assignment_line: int


class PathOutsideProjectRootDiagnostic(diagnostics.BaseDiagnostic):
    """Base class for diagnostics about an entry file path, input_path, that is not under the project root."""

    input_path: str
    resolved_path: str
    project_root: str
    label: ClassVar[str] = ""
    message_format: ClassVar[str] = (
        "{self.label}: {self.input_path}\n"
        + "  Resolved to: {self.resolved_path}\n"
        + "  Project root: {self.project_root}\n"
        + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
    )


class ReservedNameDiagnostic(diagnostics.Diagnostic):
    """Base class for reserved name diagnostics."""

    reserved_name: str


class AbsolutePathOutsideProjectRootDiagnostic(PathOutsideProjectRootDiagnostic):
    """Diagnostic for an absolute entry file path that is not under the project root."""

    label: ClassVar[str] = "Absolute path is outside the project root"


class AliasedViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for more than one view looking at the same view or position in one Operation Arguments Block."""

    looked_at_name: str
    first_argument_line: int
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is already being looked at by another view "
        "on line {self.first_argument_line}; two views in the same execution "
        "may not look at the same particle"
    )


class AuthorityDomainInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when an authority domain has invalid characters."""

    domain: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in authority domain '{self.domain}'"
    )


class AuthorityDomainTooShortDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when an authority domain is too short."""

    domain: str
    message_format: ClassVar[str] = (
        "authority domain '{self.domain}' must be at least 2 characters"
    )


class AuthorityPathEmptySegmentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when an authority path contains an empty segment."""

    authority: str
    message_format: ClassVar[str] = (
        "authority path in '{self.authority}' must not contain '//'"
    )


class ChainedLocalNameRequiresActionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a local name in a chain is not preceded by a global action."""

    local_name: str
    preceding_name: str
    message_format: ClassVar[str] = (
        "local name '{self.local_name}' in a chain must be preceded by"
        " a globally-named action, but is preceded by '{self.preceding_name}'"
    )


class CircularGlobalReferenceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when resolving references would create a cycle."""

    cycle: list[str]

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
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


class DotlessAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a dotless authority domain is used in a restricted multiverse."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is reserved: "
        "authority domains without '.' are reserved "
        "in the '{self.multiverse_name}' multiverse"
    )


class DuplicateDefinitionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when the same type is defined twice with the same path."""

    definition_type: str
    path: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate {self.definition_type} definition for path '{self.path}'; "
        "first defined on line {self.first_definition_line}"
    )


class DuplicateLogicalOperationSupportDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a logical operation listed in more than one Logical Operation Support Statement of a value definition."""

    logical_operation_name: str
    first_support_line: int
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' is already supported on line "
        "{self.first_support_line}; each logical operation may be listed only "
        "once in a value definition"
    )


class DuplicateOperationArgumentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view given more than one Operation Argument Statement in one execution."""

    view_name: str
    first_argument_line: int
    message_format: ClassVar[str] = (
        "'{self.view_name}' is already looking at something on line "
        "{self.first_argument_line}; each view can only be specified once in this block"
    )


class DuplicateQualityAssignmentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a Quality Assignment Statement appears twice in the same Quality Assignment Block."""

    quality_name: str
    first_assignment_line: int
    message_format: ClassVar[str] = (
        "duplicate quality assignment '{self.quality_name}'; "
        "first declared on line {self.first_assignment_line}"
    )


class DuplicateQualityImplicationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when the same quality implication appears twice in the same definition."""

    implication_name: str
    first_implication_line: int
    message_format: ClassVar[str] = (
        "duplicate quality implication '{self.implication_name}'; "
        "first declared on line {self.first_implication_line}"
    )


class EmptyActionStatementsBlockDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when an action statements block contains no statements."""

    message_format: ClassVar[str] = (
        "action statements block must contain at least one action statement"
    )


class EncodingOperationViewValueQualityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a value quality on an interface view of an encoding operation."""

    quality_name: str
    message_format: ClassVar[str] = (
        "interface views on an encoding operation may not have value "
        "qualities, but '{self.quality_name}' is a value"
    )


class EntryPointInterfacePositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface position on the program entry point."""

    position_name: str
    message_format: ClassVar[str] = (
        "the entry point action of a Define program must not define interface"
        " positions, but it defines '{self.position_name}'"
    )


class FqunMismatchDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a definition's FQUN doesn't match the expected project FQUN."""

    expected: str
    actual: str
    message_format: ClassVar[str] = (
        "Fully-qualified universe name '{self.actual}' does not match "
        "project universe name '{self.expected}'"
    )


class GlobalNamePathEmptySegmentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a global path contains an empty segment."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not contain '//'"
    )


class GlobalNamePathTrailingSlashDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a global path ends with '/'."""

    path: str
    message_format: ClassVar[str] = (
        "global name path '{self.path}' must not end with '/'"
    )


class GlobalReferenceMustUseShortFormDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a same-FQUN global reference uses full form."""

    fqun: str
    message_format: ClassVar[str] = (
        "global name references with the same fully-qualified universe name "
        "as the enclosing definition must use the short form; "
        "delete '{self.fqun}:' from this reference"
    )


class InvalidAuthorityPathSegmentDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when an authority path segment has invalid characters."""

    segment: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in authority path segment '{self.segment}'"
    )


class InvalidGlobalNamePathCharacterDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a global name path segment has invalid characters."""

    segment: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in path segment '{self.segment}'"
    )


class InvalidLocalNameFormatDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a local name has invalid characters."""

    local_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in local name '{self.local_name}'"
    )


class LocalActionNameDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when an action uses a local name instead of a global reference."""

    local_name: str
    message_format: ClassVar[str] = (
        "actions cannot have local names, but '{self.local_name}' is a local name"
    )


class LocalNameConflictDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a local name conflicts with another local definition."""

    local_name: str
    first_definition_line: int
    message_format: ClassVar[str] = (
        "duplicate local definition '{self.local_name}'; "
        "first defined on line {self.first_definition_line}"
    )


class LocalViewMissingEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view in an Encoding Operation without an encoding."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have an encoding, because every local view "
        "in an encoding operation must have one"
    )


class LocalViewMissingValueQualityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view without a value quality."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have a value quality, because every "
        "local view must have one"
    )


class LocalViewMultipleEncodingsDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view in an Encoding Operation with more than one encoding."""

    first_encoding_name: str
    first_assignment_line: int
    message_format: ClassVar[str] = (
        "a local view in an encoding operation may only have one encoding; "
        "'{self.first_encoding_name}' was already declared on line "
        "{self.first_assignment_line}"
    )


class LocalViewNonEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a Quality Assignment Statement of a local view in an Encoding Operation that names something other than an encoding."""

    quality_name: str
    message_format: ClassVar[str] = (
        "local views in an encoding operation may only be assigned an encoding. "
        "However, '{self.quality_name}' is not an encoding"
    )


class LocalViewNonValueQualityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view Quality Assignment Statement that names something other than a value quality."""

    quality_name: str
    message_format: ClassVar[str] = (
        "local views may only be assigned a value quality. "
        "However, '{self.quality_name}' is not a value quality"
    )


class LogicalOperationSupportOrderDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a Logical Operation Support Statement that is out of alphabetical order."""

    logical_operation_name: str
    logical_operation_name_it_must_precede: str
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' is out of order; Logical Operation "
        "Support Statements must be in alphabetical order by logical operation "
        "name, so it must come before "
        "'{self.logical_operation_name_it_must_precede}'"
    )


class LogicalOperationWithoutOutputViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a logical operation that has no output view."""

    message_format: ClassVar[str] = (
        "a logical operation must have at least one output view; "
        "add 'it is written.' to one of its views"
    )


class MoveIntoDefiningPositionDiagnostic(diagnostics.Diagnostic):
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


class MoveToSamePositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a move statement's from and to positions are the same."""

    position_name: str
    message_format: ClassVar[str] = (
        "source and destination cannot be identical when moving particles"
        " ('{self.position_name}' is the name of both"
        " the source and destination here)"
    )


class MultiverseNameInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a multiverse name has invalid characters."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in multiverse name '{self.multiverse_name}'"
    )


class MultiverseNameTooShortDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a multiverse name is too short."""

    multiverse_name: str
    message_format: ClassVar[str] = (
        "multiverse name '{self.multiverse_name}' must be at least 2 characters"
    )


class NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a reference to a universe the supplied source defines names a definition the supplied source lacks, outside a project root."""

    definition_name: str
    config_path: str
    message_format: ClassVar[str] = (
        "'{self.definition_name}' is not defined in the supplied source, "
        + "so the compiler tried to load it from the project. "
        + "However, {self.config_path} was not found.\n"
        + "For more information, see "
        + constants.DOCS_ROOT
        + "/project-root.md"
    )


class NoProjectRootInNonFilesystemContextDiagnostic(diagnostics.Diagnostic):
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


class OperationWithoutExecutionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a value operation whose Operation Statements Block executes nothing."""

    message_format: ClassVar[str] = (
        "a value operation must execute at least one logical operation "
        "or value operation"
    )


class PathInsideOtherUniverseDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a path being loaded falls inside a different universe's sub-root."""

    path: str
    other_universe: str
    sub_root_path: str
    message_format: ClassVar[str] = (
        "the path '{self.path}' is inside of a different universe from this one "
        "('{self.other_universe}' located at '{self.sub_root_path}') ; "
        "two different universes cannot both occupy '{self.sub_root_path}'"
    )


class PathMismatchDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a definition's path doesn't match the file path."""

    expected_path: str
    actual_path: str
    message_format: ClassVar[str] = (
        "definition path '{self.actual_path}' does not match file path "
        "'{self.expected_path}'"
    )


class PositionMultipleValueQualitiesDiagnostic(MultipleValueQualitiesDiagnostic):
    """A Position Quality Assignment Block assigns more than one value quality."""

    message_format: ClassVar[str] = (
        "a position may only have one value quality; "
        "'{self.first_value_name}' was already declared on line {self.first_assignment_line}"
    )


class PositionReferenceChainEndDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a position reference chain ends with an action."""

    message_format: ClassVar[str] = "position references must end with a position name"


class ReferencedDefinitionNotFoundDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a resolved file does not contain the referenced definition."""

    file_path: str
    definition_name: str
    message_format: ClassVar[str] = (
        "file '{self.file_path}' does not contain a definition for "
        "'{self.definition_name}'"
    )


class ReferencedFileNotFoundDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a referenced file does not exist."""

    file_path: str
    message_format: ClassVar[str] = (
        "there is no file '{self.file_path}' in this project"
    )


class ReferencedFileUnreadableDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a referenced file exists but cannot be read, for the reason that the operating system gives."""

    file_path: str
    reason: str
    message_format: ClassVar[str] = (
        "cannot read the file '{self.file_path}': {self.reason}"
    )


class RelativePathOutsideProjectRootDiagnostic(PathOutsideProjectRootDiagnostic):
    """Diagnostic for a relative entry file path that resolves to outside the project root."""

    label: ClassVar[str] = "Relative path resolves to outside the project root"


class ReservedAuthorityDomainDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved authority domain is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved authority domain"
    )


class ReservedMultiverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved multiverse name is used."""

    message_format: ClassVar[str] = (
        "'{self.reserved_name}' is a reserved multiverse name"
    )


class ReservedUniverseNameDiagnostic(ReservedNameDiagnostic):
    """Diagnostic for when a reserved universe name is used."""

    message_format: ClassVar[str] = "'{self.reserved_name}' is a reserved universe name"


class StandardDefinitionNotFoundDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a reference to a name the standard universe does not define."""

    definition_name: str
    message_format: ClassVar[str] = (
        "the standard universe does not define '{self.definition_name}'"
    )


class UndefinedLocalNameDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a local typed name is used but not defined in scope."""

    local_name: str
    message_format: ClassVar[str] = (
        "'{self.local_name}' has not been defined before this line of code"
    )


class UniverseNameInvalidCharDiagnostic(InvalidNameCharactersDiagnostic):
    """Diagnostic for when a universe name has invalid characters."""

    universe_name: str
    message_format: ClassVar[str] = (
        "{self.invalid_characters} in universe name '{self.universe_name}'"
    )


class UniverseNameTooShortDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a universe name is too short."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe name '{self.universe_name}' must be at least 2 characters"
    )


class UniverseWithoutAuthorityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a universe other than 'standard' is used without an authority."""

    universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe_name}' requires an authority; "
        f"only '{constants.STANDARD_UNIVERSE}' may be used without an authority"
    )


class UnknownGlobalNameDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a global name starts a chain but is not available."""

    source_global_name: str
    full_global_name: str
    message_format: ClassVar[str] = (
        "'{self.source_global_name}' is not available inside of this definition."
        " To make it available, add this line at the top of the definition:\n\n"
        "   it also assigns the '{self.full_global_name}'."
    )


class UnnecessarySelfReferenceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a definition unnecessarily references itself in a chain."""

    definition_name: str
    message_format: ClassVar[str] = (
        "the reference to '{self.definition_name}' is not necessary"
        " because the code is already inside that definition"
    )


class UnreferencedLocalViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view never referenced in its operation."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition or reference "
        "'{self.view_name}'."
    )


class UnreferencedPositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a position defined but never referenced in its definition."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition or reference "
        "'{self.position_name}'."
    )


class UnreferencedViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface view never referenced in its operation."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition or reference "
        "'{self.view_name}'."
    )


class UnusedQualityImplicationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a Quality Implication Statement is never used as a chain start in the definition body."""

    implication_name: str
    message_format: ClassVar[str] = (
        "'{self.implication_name}' is implied here, but it is never used as the "
        "first name of a chained name in the executed code of this definition; "
        "either remove the quality implication statement or reference "
        "'{self.implication_name}' in the executed code."
    )


class ValueOperationViewEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an encoding on an interface view of a value operation."""

    quality_name: str
    message_format: ClassVar[str] = (
        "interface views on a value operation may not have encodings, "
        "but '{self.quality_name}' is an encoding"
    )


class ValueSettingSamePositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a value setting statement referencing the same position twice."""

    position_name: str
    message_format: ClassVar[str] = (
        "the left and right sides of a value setting statement cannot be"
        " the same position ('{self.position_name}')"
    )


class ViewMissingEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface view of an encoding operation without an encoding."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have an encoding, because every "
        "interface view on an encoding operation must have one"
    )


class ViewMissingValueQualityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface view of a value operation without a value quality."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have a value quality, because every "
        "interface view on a value operation must have one"
    )


class ViewMultipleValueQualitiesDiagnostic(MultipleValueQualitiesDiagnostic):
    """A View Quality Assignment Block assigns more than one value quality."""

    message_format: ClassVar[str] = (
        "a view may only have one value quality; "
        "'{self.first_value_name}' was already declared on line {self.first_assignment_line}"
    )


class ViewPositionOrActionQualityDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view Quality Assignment Statement that names a position or action."""

    quality_name: str
    message_format: ClassVar[str] = (
        "views may only be assigned value qualities and encodings, "
        "but '{self.quality_name}' is not a value or an encoding"
    )


class ViewSettingEncodingMismatchDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement in an Encoding Operation has a source and target with different encodings."""

    target_view: str
    source_view: str
    target_encoding: str
    source_encoding: str
    message_format: ClassVar[str] = (
        "this view setting statement has views with two different encodings,"
        " which is not allowed. {self.target_view} has {self.target_encoding}"
        " and {self.source_view} has {self.source_encoding}."
    )


class ViewSettingInputOnlyTargetDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement's target is an input-only interface view."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an input-only interface view, so it cannot be"
        " the target of a view setting statement."
    )


class ViewSettingLocalTargetNotLookedAtDiagnostic(diagnostics.Diagnostic):
    """The statement after a View Setting Statement with a local view target does not look at its source and target."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the next statement after this view setting statement must be either"
        " another view setting statement, or an execution statement that looks"
        " at both '{self.target_name}' and '{self.source_name}', because"
        " '{self.target_name}' is a local view."
    )


class ViewSettingLocalTargetWithoutExecutionDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement with a local view target is not followed by an execution statement."""

    target_name: str
    message_format: ClassVar[str] = (
        "the next statement after this view setting statement must be either"
        " another view setting statement or an execution statement, because"
        " '{self.target_name}' is a local view."
    )


class ViewSettingOutputOnlyTargetDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement's target is an output-only interface view."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an output-only interface view, so it cannot be"
        " the target of a view setting statement. Look at it directly in the"
        " statement that writes it instead."
    )


class ViewSettingReadWriteTargetSourceNotLocalDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement with a read/write interface view target has a source that is not a local view."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the source of this view setting statement must be a local view, not"
        " '{self.source_name}', because '{self.target_name}' is a read/write"
        " interface view."
    )


class ViewSettingSameViewDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement's source and target are the same view."""

    view_name: str
    message_format: ClassVar[str] = (
        "the source and target of a view setting statement cannot be"
        " the same view ('{self.view_name}')"
    )


class ViewSettingSourceWasTargetDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement's source was the target of an earlier View Setting Statement."""

    view_name: str
    target_line: int
    message_format: ClassVar[str] = (
        "'{self.view_name}' is the target of the view setting statement on line"
        " {self.target_line}, so it cannot be the source of another view"
        " setting statement."
    )


class ViewSettingValueQualityMismatchDiagnostic(diagnostics.Diagnostic):
    """A View Setting Statement's source and target have different value qualities."""

    target_view: str
    source_view: str
    target_value_quality: str
    source_value_quality: str
    message_format: ClassVar[str] = (
        "this view setting statement has views with two different value"
        " qualities, which is not allowed. {self.target_view} has"
        " {self.target_value_quality} and {self.source_view} has"
        " {self.source_value_quality}."
    )
