"""Diagnostic types for the Define language validator."""

from __future__ import annotations

import enum
import textwrap
import typing
from typing import ClassVar, Final

import msgspec

from defcl.python import validator as dcl_validator
from define.compiler import constants, name_types
from define.compiler.errors import invisible_characters
from define.compiler.validator.reference_graph import propagation_step

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from crates.source_rendering.python import rendering


# The statement that reads every input view and writes every output view of
# each type of operation.
_ALL_VIEWS_STATEMENTS: Final = {
    name_types.NameType.OPERATION: "execute the encoding operation",
    name_types.NameType.ENCODING_OPERATION: "execute the computer operation",
}


class FormattableDiagnostic(typing.Protocol):
    """A diagnostic as the compiler reports it: anything that can show itself."""

    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the source lines of every location it mentions."""
        ...


class BaseDiagnostic(msgspec.Struct):
    """Base class for the compiler's own diagnostics."""

    message_format: ClassVar[str] = ""

    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the source lines of every location it mentions."""
        return self.render_message(sources)

    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message, with source lines for other locations it mentions."""
        return self.message_format.format(self=self)


class Diagnostic(BaseDiagnostic):
    """Base class for diagnostics about a place in a Define file."""

    location: rendering.SourceLocation

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"{sources.render_location(self.location)}\n{self.render_message(sources)}"
        )


class FileLoadFailureDiagnostic(BaseDiagnostic):
    """Base class for diagnostics that keep a Define file from loading or parsing."""


class SourceFileNotFoundDiagnostic(FileLoadFailureDiagnostic):
    """Diagnostic for a Define source file that is not on disk at file_path."""

    file_path: str
    message_format: ClassVar[str] = "Source file not found: {self.file_path}"


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


class DuplicateQualityAssignmentDiagnostic(Diagnostic):
    """Diagnostic for when a Quality Assignment Statement appears twice in the same Quality Assignment Block."""

    quality_name: str
    first_assignment_line: int
    message_format: ClassVar[str] = (
        "duplicate quality assignment '{self.quality_name}'; "
        "first declared on line {self.first_assignment_line}"
    )


class MultipleValueQualitiesDiagnostic(Diagnostic):
    """Base class for a Quality Assignment Block that assigns more than one value quality."""

    first_value_name: str
    first_assignment_line: int


class PositionMultipleValueQualitiesDiagnostic(MultipleValueQualitiesDiagnostic):
    """A Position Quality Assignment Block assigns more than one value quality."""

    message_format: ClassVar[str] = (
        "a position may only have one value quality; "
        "'{self.first_value_name}' was already declared on line {self.first_assignment_line}"
    )


class ViewMultipleValueQualitiesDiagnostic(MultipleValueQualitiesDiagnostic):
    """A View Quality Assignment Block assigns more than one value quality."""

    message_format: ClassVar[str] = (
        "a view may only have one value quality; "
        "'{self.first_value_name}' was already declared on line {self.first_assignment_line}"
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


class OperationWithoutExecutionDiagnostic(Diagnostic):
    """Diagnostic for a value operation whose Operation Statements Block executes nothing."""

    message_format: ClassVar[str] = (
        "a value operation must execute at least one logical operation "
        "or value operation"
    )


class UnreferencedLocalViewDiagnostic(Diagnostic):
    """Diagnostic for a local view never referenced in its operation."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is defined here, but it is never referenced "
        "within this definition; either remove the definition or reference "
        "'{self.view_name}'."
    )


class LogicalOperationWithoutOutputViewDiagnostic(Diagnostic):
    """Diagnostic for a logical operation that has no output view."""

    message_format: ClassVar[str] = (
        "a logical operation must have at least one output view; "
        "add 'it is written.' to one of its views"
    )


class DuplicateLogicalOperationSupportDiagnostic(Diagnostic):
    """Diagnostic for a logical operation listed in more than one Logical Operation Support Statement of a value definition."""

    logical_operation_name: str
    first_support_line: int
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' is already supported on line "
        "{self.first_support_line}; each logical operation may be listed only "
        "once in a value definition"
    )


class LogicalOperationSupportOrderDiagnostic(Diagnostic):
    """Diagnostic for a Logical Operation Support Statement that is out of alphabetical order."""

    logical_operation_name: str
    logical_operation_name_it_must_precede: str
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' is out of order; Logical Operation "
        "Support Statements must be in alphabetical order by logical operation "
        "name, so it must come before "
        "'{self.logical_operation_name_it_must_precede}'"
    )


class LogicalOperationReadNotSupportedDiagnostic(Diagnostic):
    """Diagnostic for a logical operation reading a view whose value quality does not support it with 'it may be read.'."""

    looked_at_name: str
    logical_operation_name: str
    value_name: str
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' cannot read "
        "'{self.looked_at_name}'. '{self.looked_at_name}' holds a "
        "'{self.value_name}'. However, '{self.value_name}' does not "
        "support being read by '{self.logical_operation_name}'."
    )


class LogicalOperationWriteNotSupportedDiagnostic(Diagnostic):
    """Diagnostic for a logical operation writing a view whose value quality does not support it with 'it may be written.'."""

    looked_at_name: str
    logical_operation_name: str
    value_name: str
    message_format: ClassVar[str] = (
        "'{self.logical_operation_name}' cannot write to "
        "'{self.looked_at_name}'. '{self.looked_at_name}' holds a "
        "'{self.value_name}'. However, '{self.value_name}' does not "
        "support being written by '{self.logical_operation_name}'."
    )


class ViewPositionOrActionQualityDiagnostic(Diagnostic):
    """Diagnostic for a view Quality Assignment Statement that names a position or action."""

    quality_name: str
    message_format: ClassVar[str] = (
        "views may only be assigned value qualities and encodings, "
        "but '{self.quality_name}' is not a value or an encoding"
    )


class ViewMissingValueQualityDiagnostic(Diagnostic):
    """Diagnostic for an interface view of a value operation without a value quality."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have a value quality, because every "
        "interface view on a value operation must have one"
    )


class LocalViewNonValueQualityDiagnostic(Diagnostic):
    """Diagnostic for a local view Quality Assignment Statement that names something other than a value quality."""

    quality_name: str
    message_format: ClassVar[str] = (
        "local views may only be assigned a value quality. "
        "However, '{self.quality_name}' is not a value quality"
    )


class LocalViewMissingValueQualityDiagnostic(Diagnostic):
    """Diagnostic for a local view without a value quality."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have a value quality, because every "
        "local view must have one"
    )


class LocalViewNonEncodingDiagnostic(Diagnostic):
    """Diagnostic for a Quality Assignment Statement of a local view in an Encoding Operation that names something other than an encoding."""

    quality_name: str
    message_format: ClassVar[str] = (
        "local views in an encoding operation may only be assigned an encoding. "
        "However, '{self.quality_name}' is not an encoding"
    )


class LocalViewMissingEncodingDiagnostic(Diagnostic):
    """Diagnostic for a local view in an Encoding Operation without an encoding."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have an encoding, because every local view "
        "in an encoding operation must have one"
    )


class LocalViewMultipleEncodingsDiagnostic(Diagnostic):
    """Diagnostic for a local view in an Encoding Operation with more than one encoding."""

    first_encoding_name: str
    first_assignment_line: int
    message_format: ClassVar[str] = (
        "a local view in an encoding operation may only have one encoding; "
        "'{self.first_encoding_name}' was already declared on line "
        "{self.first_assignment_line}"
    )


class ViewMissingEncodingDiagnostic(Diagnostic):
    """Diagnostic for an interface view of an encoding operation without an encoding."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' must have an encoding, because every "
        "interface view on an encoding operation must have one"
    )


class EncodingOperationViewValueQualityDiagnostic(Diagnostic):
    """Diagnostic for a value quality on an interface view of an encoding operation."""

    quality_name: str
    message_format: ClassVar[str] = (
        "interface views on an encoding operation may not have value "
        "qualities, but '{self.quality_name}' is a value"
    )


class ValueOperationViewEncodingDiagnostic(Diagnostic):
    """Diagnostic for an encoding on an interface view of a value operation."""

    quality_name: str
    message_format: ClassVar[str] = (
        "interface views on a value operation may not have encodings, "
        "but '{self.quality_name}' is an encoding"
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
        "'{self.view_name}' is an input interface view, but nothing in this"
        " operation reads it. Either have an operation read it,"
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
        "'{self.view_name}' is an output interface view, but nothing in this"
        " operation writes to it. Either have an operation write to it,"
        " {self.all_views_statement}, or remove 'it is written.'"
    )


class WriteToInputOnlyViewDiagnostic(Diagnostic):
    """Diagnostic for an executed operation writing to an input-only view."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is an input-only interface view, so it cannot be"
        " written to. However, '{self.view_name}' of '{self.operation_name}'"
        " writes to it on this line."
    )


class ReadFromUnwrittenOutputViewDiagnostic(Diagnostic):
    """Diagnostic for an executed operation reading an output-only view before anything writes to it."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is an output-only interface view, so it cannot be"
        " read until an earlier statement writes to it. However, '{self.view_name}' of"
        " '{self.operation_name}' reads it on this line before anything writes"
        " to it."
    )


class ReadFromUnwrittenLocalViewDiagnostic(Diagnostic):
    """Diagnostic for an executed operation reading a local view before anything writes to it."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is a local view, so it cannot be read until an"
        " earlier statement writes to it. However, '{self.view_name}' of"
        " '{self.operation_name}' reads it on this line before anything writes"
        " to it."
    )


class LocalViewWrittenTwiceDiagnostic(Diagnostic):
    """Diagnostic for a local view that more than one statement writes to."""

    looked_at_name: str
    view_name: str
    operation_name: str
    first_write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that first writes the local view."""
        return (
            f"'{self.looked_at_name}' is a local view, so only one statement may"
            f" write to it. However, '{self.view_name}' of '{self.operation_name}'"
            " writes to it again on this line. It was already written here:\n"
            f"{sources.render_location(self.first_write)}"
        )


class InterfaceViewWrittenTwiceDiagnostic(Diagnostic):
    """Diagnostic for an executed definition writing to an interface view that an earlier statement already wrote to."""

    looked_at_name: str
    view_name: str
    operation_name: str
    first_write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that first writes the interface view."""
        return (
            f"'{self.looked_at_name}' is an output interface view, so only one"
            f" statement may write to it. However, '{self.view_name}' of"
            f" '{self.operation_name}' writes to it again on this line. It was"
            " already written here:\n"
            f"{sources.render_location(self.first_write)}"
        )


class InterfaceViewWrittenTwiceByAllViewsStatementDiagnostic(Diagnostic):
    """Diagnostic for a statement that writes to every output view after an earlier statement already wrote to one of them."""

    view_name: str
    operation_name_type: name_types.NameType
    first_write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that first writes the interface view."""
        all_views_statement = _ALL_VIEWS_STATEMENTS[self.operation_name_type]
        return (
            f"'{self.view_name}' is an output interface view, so only one statement"
            f" may write to it. However, '{all_views_statement}.' writes to every"
            f" output view on this line, and '{self.view_name}' was already"
            " written here:\n"
            f"{sources.render_location(self.first_write)}"
        )


class ReadFromWrittenReadWriteViewDiagnostic(Diagnostic):
    """Diagnostic for an executed definition reading a read/write interface view after a statement wrote to it."""

    looked_at_name: str
    view_name: str
    operation_name: str
    write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that writes the interface view."""
        return (
            f"'{self.looked_at_name}' is a read/write interface view, so it may only be"
            " read before the statement that writes to it. However,"
            f" '{self.view_name}' of '{self.operation_name}' reads it on this"
            " line, after it was written here:\n"
            f"{sources.render_location(self.write)}"
        )


class ViewSettingReadFromUnwrittenOutputViewDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement reading an output-only view before anything writes to it."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an output-only interface view, so it cannot be"
        " read until an earlier statement writes to it. However, this view"
        " setting statement reads it before anything writes to it."
    )


class ViewSettingReadFromUnwrittenLocalViewDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement reading a local view before anything writes to it."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is a local view, so it cannot be read until an"
        " earlier statement writes to it. However, this view setting statement"
        " reads it before anything writes to it."
    )


class ViewSettingReadFromWrittenReadWriteViewDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement reading a read/write interface view after a statement wrote to it."""

    view_name: str
    write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that writes the interface view."""
        return (
            f"'{self.view_name}' is a read/write interface view, so it may only be"
            " read before the statement that writes to it. However, this view"
            " setting statement reads it after it was written here:\n"
            f"{sources.render_location(self.write)}"
        )


class ViewSettingLocalViewWrittenTwiceDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement writing to a local view that an earlier statement already wrote to."""

    view_name: str
    first_write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that first writes the local view."""
        return (
            f"'{self.view_name}' is a local view, so only one statement may"
            " write to it. However, this view setting statement writes to it"
            " again. It was already written here:\n"
            f"{sources.render_location(self.first_write)}"
        )


class ViewSettingInterfaceViewWrittenTwiceDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement writing to an interface view that an earlier statement already wrote to."""

    view_name: str
    first_write: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with the statement that first writes the interface view."""
        return (
            f"'{self.view_name}' is an output interface view, so only one"
            " statement may write to it. However, this view setting statement"
            " writes to it again. It was already written here:\n"
            f"{sources.render_location(self.first_write)}"
        )


class ViewSettingReadWriteTargetWithoutExecutionDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement with a read/write interface view target that does not follow an execution statement."""

    target_name: str
    message_format: ClassVar[str] = (
        "the statement before this view setting statement, other than view"
        " setting statements directly before it, must be an execution"
        " statement, because '{self.target_name}' is a read/write interface"
        " view."
    )


class ViewSettingReadWriteTargetNotFromExecutionDiagnostic(Diagnostic):
    """Diagnostic for a View Setting Statement with a read/write interface view target whose source the execution statement before it did not write from the target."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the execution statement before this view setting statement must read"
        " '{self.target_name}' and write '{self.source_name}', because"
        " '{self.target_name}' is a read/write interface view."
    )


# TODO: Name the association's entry in its association configuration file,
# instead of the built-in table, once those files exist (DLP 48). This applies
# to every diagnostic about an associated Encoding Operation, including
# DuplicateAssociatedEncodingOperationDiagnostic.


class AssociatedEncodingOperationViewCountDiagnostic(Diagnostic):
    """Diagnostic for an Encoding Operation associated with a logical operation that has a different number of views."""

    encoding_operation_name: str
    view_count: int
    logical_operation_name: str
    logical_operation_view_count: int
    message_format: ClassVar[str] = (
        "'{self.encoding_operation_name}' has {self.view_count} views, but"
        " '{self.logical_operation_name}',"
        " which the compiler's built-in"
        " BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS entry associates it"
        " with, has {self.logical_operation_view_count}"
    )


class AssociatedEncodingOperationViewNameDiagnostic(Diagnostic):
    """Diagnostic for a view of an associated Encoding Operation whose name differs from the logical operation's view at the same place."""

    view_number: int
    encoding_operation_name: str
    view_name: str
    logical_operation_name: str
    logical_operation_view_name: str
    message_format: ClassVar[str] = (
        "view {self.view_number} of '{self.encoding_operation_name}' is"
        " '{self.view_name}', but view {self.view_number} of"
        " '{self.logical_operation_name}',"
        " which the compiler's built-in"
        " BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS entry associates it"
        " with, is '{self.logical_operation_view_name}'"
    )


class AssociatedEncodingOperationViewDirectionDiagnostic(Diagnostic):
    """Diagnostic for a view of an associated Encoding Operation whose direction differs from the logical operation's view of the same name."""

    view_name: str
    direction: str
    encoding_operation_name: str
    logical_operation_direction: str
    logical_operation_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is {self.direction} in"
        " '{self.encoding_operation_name}', but"
        " {self.logical_operation_direction} in"
        " '{self.logical_operation_name}',"
        " which the compiler's built-in"
        " BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS entry associates it"
        " with"
    )


class DuplicateAssociatedEncodingOperationDiagnostic(Diagnostic):
    """Diagnostic for two Encoding Operations that are associated with the same logical operation and have the same encodings."""

    encoding_operation_name: str
    first_encoding_operation_name: str
    logical_operation_name: str
    message_format: ClassVar[str] = (
        "'{self.encoding_operation_name}' and"
        " '{self.first_encoding_operation_name}' are both associated with"
        " '{self.logical_operation_name}' by the compiler's built-in"
        " BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS entry for"
        " '{self.logical_operation_name}', and their views have the same"
        " encodings, so the compiler cannot choose between them"
    )


class ExecutedOperationHasReadWriteViewDiagnostic(Diagnostic):
    """Diagnostic for an Operation Statements Block executing an operation that has a read/write interface view."""

    operation_name: str
    view_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' has a read/write interface view,"
        " '{self.view_name}', so you cannot execute it inside of another operation."
    )


class UnreadLocalViewDiagnostic(Diagnostic):
    """Diagnostic for a local view that is written but never read."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is written, but nothing in this operation reads it."
        " Either have an operation read it, or remove it."
    )


class LookedAtKind(enum.Enum):
    """What an Operation Argument Statement's view is looking at."""

    VIEW = enum.auto()
    POSITION = enum.auto()


class OperationArgumentMissingQualitiesDiagnostic(Diagnostic):
    """Diagnostic for a view looking at a particle that does not have the qualities the view assigns."""

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


class DeadQualityAssignmentDiagnostic(Diagnostic):
    """Base class for an unused quality assignment on a local or interface position."""

    quality_name: str
    position_name: str


class DeadChildPositionDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a child position assignment on a local or interface position that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        "but the child position it creates is never referenced within this "
        "definition and no move requires it; either reference "
        "'{self.position_name}::{self.quality_name}' or remove the quality assignment."
    )


class DeadValueQualityAssignmentDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a value quality assignment that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        " but the value is never actually used on any particle created in this position. "
        " Either use the value or remove the quality assignment."
    )


class DeadEncodingQualityAssignmentDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for an encoding assignment that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here,"
        " but the value of a particle created in this position is never used, so"
        " its encoding never matters. Either use the value or remove the quality assignment."
    )


class UntriggeredActionDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a child action assignment on a local or interface position that is never triggered."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        "but the action it creates is never triggered within this definition and "
        "no move requires it; either trigger it or remove the quality assignment."
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
    arrived_at: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message with where the particle arrived."""
        return (
            f"'{self.position_name}' contains a particle when '{self.action_name}' "
            "triggers here; move or destroy the particle before triggering that "
            f"action. The particle arrived at:\n{sources.render_location(self.arrived_at)}"
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


class NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(Diagnostic):
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


class ConfigDiagnostic(BaseDiagnostic):
    """Base class for diagnostics about a project's config file, the one at config_path."""

    config_path: str

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the config file that it is about."""
        return f'File "{self.config_path}"\n{self.render_message(sources)}'


# A path to a field of a config file: field names, and the indices of repeated
# fields' elements.
type FieldPath = tuple[str | int, ...]


class ConfigFieldDiagnostic(ConfigDiagnostic):
    """Base class for diagnostics about the field of a config file at field_path."""

    field_path: FieldPath

    @property
    def _field_path_text(self) -> str:
        """The field path as it is written in messages, such as `deps.local[0].path`."""
        text = ""
        for element in self.field_path:
            if isinstance(element, int):
                text += f"[{element}]"
            elif text:
                text += f".{element}"
            else:
                text = element
        return text

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the field that it is about, with its source line."""
        field = self._render_field(sources, self.config_path, self.field_path)
        return f"{field}\n{self.render_message(sources)}"

    @staticmethod
    def _render_field(
        sources: rendering.SourceMap, config_path: str, field_path: FieldPath
    ) -> str:
        """Render where the config file at config_path writes the field at field_path, with its source line."""
        location = dcl_validator.locate_field(sources, config_path, field_path)
        if location is None:
            return sources.render_header_without_position(config_path)
        return sources.render_location(location)


def _project_root_help(config_path: str) -> str:
    return (
        f"A project root is any directory containing {config_path}.\n"
        + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
    )


class NotRunFromProjectRootDiagnostic(ConfigDiagnostic):
    """Diagnostic for a compiler run from a directory that is not a project root, so has no project config at config_path."""

    message_format: ClassVar[str] = (
        "The Define compiler must be run from a project root directory."
    )

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        # The config file does not exist, so showing it as the file that the
        # diagnostic is about would mislead.
        return self.render_message(sources)

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return f"{super().render_message(sources)}\n" + _project_root_help(
            self.config_path
        )


class PathOutsideProjectRootDiagnostic(BaseDiagnostic):
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


class AbsolutePathOutsideProjectRootDiagnostic(PathOutsideProjectRootDiagnostic):
    """Diagnostic for an absolute entry file path that is not under the project root."""

    label: ClassVar[str] = "Absolute path is outside the project root"


class RelativePathOutsideProjectRootDiagnostic(PathOutsideProjectRootDiagnostic):
    """Diagnostic for a relative entry file path that resolves to outside the project root."""

    label: ClassVar[str] = "Relative path resolves to outside the project root"


class SubRootNotProjectRootDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a sub-root that a local dependency names but that is not a project root.

    Its field is the local dependency's path.
    """

    sub_root_path: str
    # The project config that the sub-root does not have.
    sub_root_config_path: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            f"The referenced subroot ({self.sub_root_path}) is not a valid project"
            + f" root: {self.sub_root_config_path} not found.\n"
            + _project_root_help(self.sub_root_config_path)
        )


class ConfigViolationDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a field of a config file whose value breaks a rule of its schema."""

    violation_message: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return f"{self._field_path_text}: {self.violation_message}"


class DuplicateLocalDependencyDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a local dependency whose universe name an earlier local dependency already declares.

    The first declaration of a universe wins, and the later one is not used.
    Its field is the later local dependency's universe_name.
    """

    universe_name: str
    first_field_path: FieldPath

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"Universe '{self.universe_name}' is already declared by an earlier"
            " local dependency, so only that one is used. It is here:\n"
            f"{self._render_field(sources, self.config_path, self.first_field_path)}"
        )


class DuplicateFqunDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for two project roots that declare the same fully-qualified universe name.

    Its field is the universe_name of the later project's config.
    """

    fqun: str
    # The earlier project's config, which declares the universe first.
    existing_config: str

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        existing_universe_name = self._render_field(
            sources, self.existing_config, ("project", "universe_name")
        )
        return (
            f"Universe '{self.fqun}' cannot be defined again here, since it is"
            f" already defined here:\n{existing_universe_name}"
        )


class SubRootFqunMismatchDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a sub-root whose project config declares a different universe than the local dependency that names it.

    Its field is the universe_name of the sub-root's project config.
    """

    expected_fqun: str
    actual_fqun: str
    sub_root_path: str
    message_format: ClassVar[str] = (
        "Sub-root at '{self.sub_root_path}' is configured as a dependency"
        + " with universe '{self.expected_fqun}' but the actual project root"
        + " in that path says it has the universe name '{self.actual_fqun}'"
    )


class SubRootPathAlreadyDeclaredDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a local dependency that declares a sub-root at a path that another local dependency already declared.

    The first declaration of a path wins, and the later one is not used. Its
    field is the later local dependency's path.
    """

    sub_root_path: str
    # The local dependencies config and field of the first local dependency
    # that declares the path.
    first_config_path: str
    first_field_path: FieldPath

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        first_entry = self._render_field(
            sources, self.first_config_path, self.first_field_path
        )
        return (
            f"This local dependency declares the sub-root '{self.sub_root_path}',"
            " but an earlier one already declares it, so only that one is used."
            f" It is here:\n{first_entry}"
        )


class LocalDependencyOnOwnUniverseDiagnostic(ConfigFieldDiagnostic):
    """Diagnostic for a local dependency that names the universe of the project that declares it.

    That universe is already at the project root, so the entry is not used.
    Its field is the local dependency's universe_name.
    """

    universe: str
    message_format: ClassVar[str] = (
        "Universe '{self.universe}' is the project's own universe, so it cannot"
        + " be a dependency of that project."
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


# TODO: Inform the developer if the creation occurred due to an inferred requirement
# from the caller. That's also relevant when you have multiple constructors run on
# the same position that do something conflicting to one of the other positions, and
# you need to refer to three things (the create statement that triggered the
# constructors and then the two different constructors that are conflicting).
class CreateInOccupiedPositionDiagnostic(Diagnostic):
    """Diagnostic for when a particle is created in a position that already has one."""

    position_name: str
    populated_at: rendering.SourceLocation
    message_format: ClassVar[str] = (
        "a particle already exists in '{self.position_name}';"
        " it was put there at:\n{populated_at}"
    )

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return self.message_format.format(
            self=self, populated_at=sources.render_location(self.populated_at)
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
    occupied_at: rendering.SourceLocation
    message_format: ClassVar[str] = (
        "cannot move a particle to '{self.position_name}' because it already"
        " contains one; it was put there at:\n{occupied_at}"
    )

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return self.message_format.format(
            self=self, occupied_at=sources.render_location(self.occupied_at)
        )


class MoveFromEmptyPositionDiagnostic(Diagnostic):
    """Diagnostic for when a move statement's source position has no particle."""

    position_name: str
    is_action_interface_position: bool = False
    inferred_at: rendering.SourceLocation | None = None

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message, optionally including the inferred-at location."""
        base = (
            f"cannot move a particle from '{self.position_name}'"
            " because it does not contain one"
        )
        if self.inferred_at is not None:
            return f"{base}; it was emptied at:\n{sources.render_location(self.inferred_at)}"
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


class ValueSettingMissingValueQualityDiagnostic(Diagnostic):
    """A particle in a Value Setting Statement has no assigned value quality."""

    position_name: str
    origin_position_name: str
    message_format: ClassVar[str] = (
        "the particle in '{self.position_name}' has no assigned value quality."
        " Assign a value quality to the position where it originated:"
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


class ValueSettingValueQualityMismatchDiagnostic(Diagnostic):
    """A Value Setting Statement uses particles with different value qualities."""

    target_position: str
    source_position: str
    target_value_quality: str
    source_value_quality: str
    message_format: ClassVar[str] = (
        "this value setting statement has particles with two different value"
        " qualities, which is not allowed. {self.target_position} has"
        " {self.target_value_quality} and {self.source_position} has"
        " {self.source_value_quality}."
    )


class ViewSettingSameViewDiagnostic(Diagnostic):
    """A View Setting Statement's source and target are the same view."""

    view_name: str
    message_format: ClassVar[str] = (
        "the source and target of a view setting statement cannot be"
        " the same view ('{self.view_name}')"
    )


class ViewSettingValueQualityMismatchDiagnostic(Diagnostic):
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


class ViewSettingEncodingMismatchDiagnostic(Diagnostic):
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


class ViewSettingInputOnlyTargetDiagnostic(Diagnostic):
    """A View Setting Statement's target is an input-only interface view."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an input-only interface view, so it cannot be"
        " the target of a view setting statement."
    )


class ViewSettingOutputOnlyTargetDiagnostic(Diagnostic):
    """A View Setting Statement's target is an output-only interface view."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an output-only interface view, so it cannot be"
        " the target of a view setting statement. Look at it directly in the"
        " statement that writes it instead."
    )


class ViewSettingSourceWasTargetDiagnostic(Diagnostic):
    """A View Setting Statement's source was the target of an earlier View Setting Statement."""

    view_name: str
    target_line: int
    message_format: ClassVar[str] = (
        "'{self.view_name}' is the target of the view setting statement on line"
        " {self.target_line}, so it cannot be the source of another view"
        " setting statement."
    )


class ViewSettingReadWriteTargetSourceNotLocalDiagnostic(Diagnostic):
    """A View Setting Statement with a read/write interface view target has a source that is not a local view."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the source of this view setting statement must be a local view, not"
        " '{self.source_name}', because '{self.target_name}' is a read/write"
        " interface view."
    )


class ViewSettingLocalTargetWithoutExecutionDiagnostic(Diagnostic):
    """A View Setting Statement with a local view target is not followed by an execution statement."""

    target_name: str
    message_format: ClassVar[str] = (
        "the next statement after this view setting statement must be either"
        " another view setting statement or an execution statement, because"
        " '{self.target_name}' is a local view."
    )


class ViewSettingLocalTargetNotLookedAtDiagnostic(Diagnostic):
    """The statement after a View Setting Statement with a local view target does not look at its source and target."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the next statement after this view setting statement must be either"
        " another view setting statement, or an execution statement that looks"
        " at both '{self.target_name}' and '{self.source_name}', because"
        " '{self.target_name}' is a local view."
    )


class LiteralCannotSetValueDiagnostic(Diagnostic):
    """A literal's encoding cannot be read as the value quality it is setting."""

    potential_literal: str
    literal_encoding: str
    value_quality: str
    supported_encodings: Sequence[str]

    @property
    def supported_encodings_advice(self) -> str:
        """Say which literal encodings could set the value quality, if any can."""
        if not self.supported_encodings:
            return f"In fact, {self.value_quality} cannot be set by a literal at all."
        encoding_list = "\n    ".join(self.supported_encodings)
        return (
            f"To set a {self.value_quality}, use a literal with one of these"
            f" encodings:\n    {encoding_list}"
        )

    message_format: ClassVar[str] = (
        "{self.potential_literal} cannot set a {self.value_quality}, because literals"
        " with the {self.literal_encoding} cannot be read as {self.value_quality}.\n"
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
    """A value quality has no encoding, so it can never be set."""

    value_quality: str
    message_format: ClassVar[str] = (
        "{self.value_quality} has no encoding, so it can never be set"
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


class MoveMissingQualitiesDiagnostic(Diagnostic):
    """Diagnostic for when a moved particle lacks qualities its destination assigns."""

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


class ChainElementNotAssignedDiagnostic(Diagnostic):
    """Diagnostic for when a chain element is not explicitly assigned to its parent name."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' must be explicitly assigned with an 'it has the'"
        " statement in the definition of '{self.parent_name}'"
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


class TrailingWhitespaceDiagnostic(Diagnostic):
    """Diagnostic for spaces at the end of a line."""

    message_format: ClassVar[str] = "lines may not end with spaces"


class MissingSpaceBeforeCommentAfterTerminatorDiagnostic(Diagnostic):
    """Diagnostic for a comment directly after a statement's '.'."""

    message_format: ClassVar[str] = (
        "a comment after a statement's '.' must have a space before its '#'"
    )


class MissingSpaceBeforeCommentAfterBraceDiagnostic(Diagnostic):
    """Diagnostic for a comment directly after a '{' or '}'."""

    message_format: ClassVar[str] = (
        "a comment after '{{' or '}}' must have a space before its '#'"
    )


class MissingNewlineAtEndOfFileDiagnostic(Diagnostic):
    """Diagnostic for a source file that does not end with a line feed."""

    message_format: ClassVar[str] = "Define source files must end with a newline"


class MissingTerminatorAtEndOfLineDiagnostic(Diagnostic):
    """Diagnostic for a statement whose line ends where its '.' belongs."""

    message_format: ClassVar[str] = "this statement must end with a '.'"


class SpaceBeforeOpenAngleBracketDiagnostic(Diagnostic):
    """Diagnostic for spaces between a name type and the '<' of its name."""

    message_format: ClassVar[str] = (
        "a name type and the '<' of its name may not have spaces between them"
    )


class ByteOrderMarkInCommentDiagnostic(Diagnostic):
    """Diagnostic for a UTF-8 byte order mark in a comment."""

    message_format: ClassVar[str] = (
        "comments may not have a UTF-8 byte order mark (U+FEFF)"
    )


class ControlCharacterInCommentDiagnostic(Diagnostic):
    """Diagnostic for a control character in a comment."""

    escaped_character: str
    message_format: ClassVar[str] = (
        "comments may not have the control character {self.escaped_character}"
    )


class InvisibleCharacterInCommentDiagnostic(Diagnostic):
    """Diagnostic for an invisible character in a comment that the Invisible Characters rule does not allow there."""

    character: str
    message_format: ClassVar[str] = (
        "comments may not have the invisible character {self.description}"
    )

    @property
    def description(self) -> str:
        """The character's code point and, when Unicode names it, its name."""
        return invisible_characters.describe_invisible_character(self.character)


class InferredRequirementViolationDiagnostic(Diagnostic):
    """Diagnostic for when an automatically inferred requirement is violated.

    The same shape serves every case (Action Execution, destructor, Destruction
    Contract): a uniform top sentence naming the runner whose run the requirement
    gates, followed by the causal stack.
    """

    position_name: str
    propagation_chain: list[propagation_step.PropagationStep]
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
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        lines = ["This error happens because:"]
        for step in self.propagation_chain:
            lines.extend(
                (
                    f"  {self._format_propagation_step(step)}:",
                    textwrap.indent(sources.render_location(step.location), "    "),
                )
            )
        return self.message_format.format(self=self, propagation_chain="\n".join(lines))

    @staticmethod
    def _format_propagation_step(step: propagation_step.PropagationStep) -> str:
        """Render a propagation step as a human-readable label line."""
        match step.kind:
            case propagation_step.PropagationKind.DIRECT_INFERENCE:
                return f"'{step.enclosing_quality_name}' infers this requirement"
            case propagation_step.PropagationKind.DESTRUCTOR_CASCADE:
                return (
                    f"'{step.enclosing_quality_name}' destroys a particle,"
                    f" triggering the destructor '{step.triggered_quality_name}'"
                )
            case propagation_step.PropagationKind.QUALITY_ASSIGNED:
                return (
                    f"'{step.triggered_quality_name}' is assigned to"
                    f" '{step.enclosing_quality_name}'"
                )
            case propagation_step.PropagationKind.CONSTRUCTOR_TRIGGER:
                return (
                    f"'{step.enclosing_quality_name}' creates a particle, triggering"
                    f" the constructor '{step.triggered_quality_name}'"
                )
            case propagation_step.PropagationKind.ACTION_TRIGGER:
                return (
                    f"'{step.enclosing_quality_name}' triggers"
                    f" '{step.triggered_quality_name}'"
                )
            case propagation_step.PropagationKind.PARTICLE_ORIGIN:
                return (
                    f"the particle in '{step.enclosing_quality_name}' comes from here"
                )
            case propagation_step.PropagationKind.AUTO_DESTRUCTION:
                return (
                    f"the particle in '{step.enclosing_quality_name}' is automatically"
                    f" destroyed at the end of '{step.triggered_quality_name}'"
                )
            case propagation_step.PropagationKind.FILL_SITE:
                return f"'{step.enclosing_quality_name}' is filled here"


class DestructorGuaranteeDiagnostic(Diagnostic):
    """Base class for diagnostics about a destructor changing a contracted position's state."""

    position_name: str


class DestructorRequiresEmptyPositionDiagnostic(Diagnostic):
    """A destructor requires one of its contracted positions to be empty."""

    position_name: str

    message_format: ClassVar[str] = (
        "a destructor may not require a position to be empty.\n"
        "However, this line requires '{self.position_name}' to be empty when the"
        " destructor runs."
    )


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
    inferred_at: rendering.SourceLocation | None

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message."""
        base = (
            f"cannot destroy a particle in '{self.position_name}'"
            f" because it does not contain one"
        )
        if self.inferred_at is not None:
            return f"{base}; it was emptied at:\n{sources.render_location(self.inferred_at)}"
        return f"{base}; action interface positions are empty by default"


class ActionSelfTriggerDiagnostic(Diagnostic):
    """Diagnostic for when an action writes to its own trigger position."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "'{self.action_name}' cannot trigger itself"
        " by writing to its own trigger position '{self.position_name}'"
    )
