"""Diagnostics that association resolution reports."""

from __future__ import annotations

import textwrap
import typing
from typing import ClassVar

import msgspec

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from crates.source_rendering.python import rendering


class OperationExecutionStep(msgspec.Struct, frozen=True):
    """One execution in a stack of executions that a diagnostic shows."""

    executing_name: str
    executed_name: str
    # The executed operation's name in the statement that executes it.
    location: rendering.SourceLocation


class AssociatedEncodingOperationViewDirectionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view of an associated Encoding Operation whose direction differs from the Abstract Operation's view of the same name."""

    view_name: str
    direction: str
    encoding_operation_name: str
    abstract_operation_direction: str
    abstract_operation_name: str
    # Where the association is written.
    association_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"'{self.view_name}' is {self.direction} in"
            + f" '{self.encoding_operation_name}', but"
            + f" {self.abstract_operation_direction} in"
            + f" '{self.abstract_operation_name}', and they are associated"
            + f" here:\n{sources.render_location(self.association_location)}"
        )


class AssociationAbstractOperationViewCountDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an association that lists a different number of Interface Views than its Abstract Operation has."""

    encoding_operation_name: str
    view_count: int
    abstract_operation_name: str
    abstract_operation_view_count: int
    # Where the Abstract Operation is defined.
    definition_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"this association lists {self.view_count} views for"
            + f" '{self.encoding_operation_name}', but"
            + f" '{self.abstract_operation_name}' has"
            + f" {self.abstract_operation_view_count}, defined"
            + f" here:\n{sources.render_location(self.definition_location)}"
        )


class AssociationAbstractOperationViewNameDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view that an association lists under a different name than its Abstract Operation's view at the same place."""

    view_number: int
    view_name: str
    encoding_operation_name: str
    abstract_operation_name: str
    abstract_operation_view_name: str
    # Where the Abstract Operation's view is defined.
    definition_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"this association lists '{self.view_name}' as view"
            + f" {self.view_number} of '{self.encoding_operation_name}', but view"
            + f" {self.view_number} of '{self.abstract_operation_name}' is"
            + f" '{self.abstract_operation_view_name}', defined"
            + f" here:\n{sources.render_location(self.definition_location)}"
        )


class AssociationViewCountDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an association that lists a different number of Interface Views than its Encoding Operation has."""

    encoding_operation_name: str
    view_count: int
    encoding_operation_view_count: int
    # Where the Encoding Operation is defined.
    definition_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"this association lists {self.view_count} views for"
            + f" '{self.encoding_operation_name}', but it has"
            + f" {self.encoding_operation_view_count} interface views, defined"
            + f" here:\n{sources.render_location(self.definition_location)}"
        )


class AssociationViewEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view that an association lists with a different encoding than its Encoding Operation assigns it."""

    view_name: str
    encoding_name: str
    encoding_operation_name: str
    encoding_operation_encoding_name: str
    # Where the Encoding Operation assigns the view its encoding.
    definition_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"this association says '{self.view_name}' of"
            + f" '{self.encoding_operation_name}' has '{self.encoding_name}', but"
            + f" it has '{self.encoding_operation_encoding_name}', assigned"
            + f" here:\n{sources.render_location(self.definition_location)}"
        )


class AssociationViewNameDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a view that an association lists under a different name than its Encoding Operation's view at the same place."""

    view_number: int
    view_name: str
    encoding_operation_name: str
    encoding_operation_view_name: str
    # Where the Encoding Operation's view is defined.
    definition_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"this association lists '{self.view_name}' as view"
            + f" {self.view_number} of '{self.encoding_operation_name}', but its"
            + f" view {self.view_number} is '{self.encoding_operation_view_name}',"
            + f" defined here:\n{sources.render_location(self.definition_location)}"
        )


class InvalidLiteralContentDiagnostic(diagnostics.Diagnostic):
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


class LiteralCannotBeConvertedDiagnostic(diagnostics.Diagnostic):
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


class LiteralCannotSetValueDiagnostic(diagnostics.Diagnostic):
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


class MissingEncodingOperationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for executing a Value Operation that, for the encodings of what the execution looks at, executes a logical operation that no Encoding Operation is associated with for the encodings of the views it looks at."""

    logical_operation_name: str
    # The encoding of each of the logical operation's views, keyed by the
    # view's name, in the order of its views.
    view_encodings: Mapping[str, str]
    # The executions from the action down to the Logical Operation Execution
    # Statement, in the order they happen.
    execution_stack: Sequence[OperationExecutionStep]

    @property
    def view_encoding_list(self) -> str:
        """Format each view with its encoding as an indented list."""
        lines: list[str] = []
        for view_name, encoding_name in self.view_encodings.items():
            lines.append(f"{view_name}: {encoding_name}")
        return "\n  ".join(lines)

    message_format: ClassVar[str] = (
        "no Encoding Operation is associated with '{self.logical_operation_name}'"
        " for these encodings:\n"
        "  {self.view_encoding_list}\n"
        "so this execution cannot run.\n\n"
        "{execution_stack}"
    )

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        lines = ["This error happens because:"]
        for step in self.execution_stack:
            lines.extend(
                (
                    f"  '{step.executing_name}' executes '{step.executed_name}':",
                    textwrap.indent(sources.render_location(step.location), "    "),
                )
            )
        return self.message_format.format(self=self, execution_stack="\n".join(lines))


class NoProjectRootForAssociationsDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a value quality whose encoding must come from the project's associations, when the program is compiled in a non-filesystem context that has no project config."""

    value_quality: str
    config_path: str
    message_format: ClassVar[str] = (
        "'{self.value_quality}' gets its encoding from the project's "
        + "associations, so the compiler tried to load them from the project. "
        + "However, {self.config_path} was not found."
    )


class UnknownComputerOperationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an Encoding Operation that executes a computer operation that the compiler does not know how to perform."""

    encoding_operation_name: str
    message_format: ClassVar[str] = (
        "{self.encoding_operation_name} executes the computer operation, but"
        + " the compiler does not know how to perform a computer operation for"
        + " {self.encoding_operation_name}. To fix this, do one of these:\n"
        + "  1. Use an Encoding Operation from the standard universe instead of"
        + " {self.encoding_operation_name}.\n"
        + "  2. In {self.encoding_operation_name}, replace 'execute the computer"
        + " operation.' with statements that execute Encoding Operations that the"
        + " compiler knows how to perform."
    )


class ValueHasNoEncodingDiagnostic(diagnostics.Diagnostic):
    """A value quality is not associated with any encoding."""

    value_quality: str
    message_format: ClassVar[str] = (
        "{self.value_quality} is not associated with any encoding in"
        " .define/encodings/encodings.defcl"
    )
