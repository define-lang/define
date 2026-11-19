"""Diagnostics that reference graph validation reports."""

from __future__ import annotations

import enum
import textwrap
import typing
from typing import ClassVar

from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import propagation_step

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from crates.source_rendering.python import rendering


class DeadQualityAssignmentDiagnostic(diagnostics.Diagnostic):
    """Base class for an unused quality assignment on a local or interface position."""

    quality_name: str
    position_name: str


class DestructorGuaranteeDiagnostic(diagnostics.Diagnostic):
    """Base class for diagnostics about a destructor changing a contracted position's state."""

    position_name: str


class LookedAtKind(enum.Enum):
    """What an Operation Argument Statement's view is looking at."""

    VIEW = enum.auto()
    POSITION = enum.auto()


class ActionSelfTriggerDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when an action writes to its own trigger position."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "'{self.action_name}' cannot trigger itself"
        " by writing to its own trigger position '{self.position_name}'"
    )


class ChainElementNotAssignedDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a chain element is not explicitly assigned to its parent name."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' must be explicitly assigned with an 'it has the'"
        " statement in the definition of '{self.parent_name}'"
    )


class ChainElementNotInterfacePositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a local name after an action is not an interface position of that action."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is not an interface position of the action"
        " '{self.parent_name}'; only that action's interface positions may follow"
        " it in a chained name"
    )


class ChainGlobalNameAfterActionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a global name follows an action in a chained name."""

    element_name: str
    parent_name: str
    message_format: ClassVar[str] = (
        "'{self.element_name}' is a global name, but only the interface positions"
        " of the action '{self.parent_name}' may follow it in a chained name;"
        " interface positions are written as local names"
    )


# TODO: Inform the developer if the creation occurred due to an inferred requirement
# from the caller. That's also relevant when you have multiple constructors run on
# the same position that do something conflicting to one of the other positions, and
# you need to refer to three things (the create statement that triggered the
# constructors and then the two different constructors that are conflicting).
class CreateInOccupiedPositionDiagnostic(diagnostics.Diagnostic):
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


class DeadChildPositionDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a child position assignment on a local or interface position that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        "but the child position it creates is never referenced within this "
        "definition and no move requires it; either reference "
        "'{self.position_name}::{self.quality_name}' or remove the quality assignment."
    )


class DeadEncodingQualityAssignmentDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for an encoding assignment that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here,"
        " but the value of a particle created in this position is never used, so"
        " its encoding never matters. Either use the value or remove the quality assignment."
    )


class DeadValueQualityAssignmentDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a value quality assignment that is never used."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        " but the value is never actually used on any particle created in this position. "
        " Either use the value or remove the quality assignment."
    )


class DeadValueWriteDiagnostic(diagnostics.Diagnostic):
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


class DestroyInEmptyInterfacePositionDiagnostic(diagnostics.Diagnostic):
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


class DestroyInEmptyPositionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a destroy statement's target position has no particle."""

    position_name: str
    message_format: ClassVar[str] = (
        "cannot destroy a particle in '{self.position_name}'"
        " because it does not contain one"
    )


class DestructorChangesValueDiagnostic(DestructorGuaranteeDiagnostic):
    """A destructor changes a contracted particle's value."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line changes the value of the particle in '{self.position_name}'."
    )


class DestructorProducesEmptyGuaranteeDiagnostic(DestructorGuaranteeDiagnostic):
    """Diagnostic for when a destructor leaves a contracted position empty that started occupied."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line empties '{self.position_name}' and then nothing puts the same"
        " particle back into that position."
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


class DestructorProducesOccupiedGuaranteeDiagnostic(DestructorGuaranteeDiagnostic):
    """Diagnostic for when a destructor leaves a new particle in a contracted position."""

    message_format: ClassVar[str] = (
        "a destructor must leave every contracted position in the state it was in when it started.\n"
        "However, this line creates a new particle in '{self.position_name}' and then"
        " nothing removes it from that position."
    )


class DestructorRequiresEmptyPositionDiagnostic(diagnostics.Diagnostic):
    """A destructor requires one of its contracted positions to be empty."""

    position_name: str

    message_format: ClassVar[str] = (
        "a destructor may not require a position to be empty.\n"
        "However, this line requires '{self.position_name}' to be empty when the"
        " destructor runs."
    )


class EntryPointOccupiedImpliedPositionRequirementDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an occupied implied-position requirement on the entry point."""

    position_name: str
    message_format: ClassVar[str] = (
        "the entry point action of a Define program must not infer that implied"
        " position '{self.position_name}' is occupied"
    )


class ExecutedOperationHasReadWriteViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an Operation Statements Block executing an operation that has a read/write interface view."""

    operation_name: str
    view_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' has a read/write interface view,"
        " '{self.view_name}', so you cannot execute it inside of another operation."
    )


class InferredRequirementViolationDiagnostic(diagnostics.Diagnostic):
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


class InterfaceViewWrittenTwiceDiagnostic(diagnostics.Diagnostic):
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


class LocalViewWrittenTwiceDiagnostic(diagnostics.Diagnostic):
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


class LogicalOperationReadNotSupportedDiagnostic(diagnostics.Diagnostic):
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


class LogicalOperationWriteNotSupportedDiagnostic(diagnostics.Diagnostic):
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


class MissingOperationArgumentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface view of an executed operation with no Operation Argument Statement."""

    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' requires '{self.view_name}' to look at "
        "something; add a 'with {self.view_name} looking at' line"
    )


class MoveFromEmptyPositionDiagnostic(diagnostics.Diagnostic):
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


class MoveMissingQualitiesDiagnostic(diagnostics.Diagnostic):
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


class MoveToOccupiedPositionDiagnostic(diagnostics.Diagnostic):
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


class OccupiedActionInterfaceWhenActionTriggersDiagnostic(diagnostics.Diagnostic):
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


class OperationArgumentEmptyPositionDiagnostic(diagnostics.Diagnostic):
    """An Operation Argument Statement looks at an empty position."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' has no particle in it, so a view cannot look at it."
    )


class OperationArgumentMissingQualitiesDiagnostic(diagnostics.Diagnostic):
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


class OperationArgumentOrderDiagnostic(diagnostics.Diagnostic):
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


class OutputViewLooksAtLiteralDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an output view of an executed operation looking at a literal."""

    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.operation_name}' writes to '{self.view_name}',"
        " so it cannot look at a literal."
    )


class ParentPositionNotOccupiedDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a position is accessed but its parent has no particle."""

    position_name: str
    parent_position_name: str
    message_format: ClassVar[str] = (
        "cannot access '{self.position_name}'"
        " because '{self.parent_position_name}' does not contain a particle.\n"
        "To fix this, either create a particle in '{self.parent_position_name}'"
        " or move an existing particle there."
    )


class ReadFromUnwrittenLocalViewDiagnostic(diagnostics.Diagnostic):
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


class ReadFromUnwrittenOutputViewDiagnostic(diagnostics.Diagnostic):
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


class ReadFromWrittenReadWriteViewDiagnostic(diagnostics.Diagnostic):
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


class UnconsumedActionInterfaceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface particle that remains after its caller ends."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "after triggering '{self.action_name}', this action must move or destroy every "
        "particle in that action's interface positions, but "
        "'{self.position_name}' still contains a particle when this action ends."
    )


class UndefinedOperationViewDiagnostic(diagnostics.Diagnostic):
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


class UnreadInputViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an input view that its operation never reads."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an input interface view, but nothing in this"
        " operation reads it. Either have an operation read it or remove"
        " 'it is read.'"
    )


class UnreadLocalViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local view that is written but never read."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is written, but nothing in this operation reads it."
        " Either have an operation read it, or remove it."
    )


class UnsetValueDiagnostic(diagnostics.Diagnostic):
    """A Value Setting Statement or an Operation Argument Statement reads a particle whose value is unset."""

    position_name: str
    message_format: ClassVar[str] = (
        "the particle in '{self.position_name}' must have a set value"
        " before its value can be read."
    )


class UntriggeredActionDiagnostic(DeadQualityAssignmentDiagnostic):
    """Diagnostic for a child action assignment on a local or interface position that is never triggered."""

    message_format: ClassVar[str] = (
        "'{self.quality_name}' is assigned to '{self.position_name}' here, "
        "but the action it creates is never triggered within this definition and "
        "no move requires it; either trigger it or remove the quality assignment."
    )


class UntriggeredActionInterfaceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an interface particle not present when its action triggers."""

    action_name: str
    position_name: str
    message_format: ClassVar[str] = (
        "a particle arrives in '{self.position_name}' here, but "
        "'{self.action_name}' is not triggered with that particle in this position "
        "before the particle moves or is destroyed, or before this action ends."
    )


class UntriggeredImpliedActionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an implied action that is never triggered by the implying action."""

    implied_action_name: str
    message_format: ClassVar[str] = (
        "'{self.implied_action_name}' is implied here, but it is never triggered "
        "within this action; either trigger it or remove the implication."
    )


class UnwrittenOutputViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an output view that its operation never writes to."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an output interface view, but nothing in this"
        " operation writes to it. Either have an operation write to it or"
        " remove 'it is written.'"
    )


class ValueSettingEmptyPositionDiagnostic(diagnostics.Diagnostic):
    """A Value Setting Statement references an empty position."""

    position_name: str
    message_format: ClassVar[str] = (
        "'{self.position_name}' has no particle in it, so it"
        " cannot be used in a value setting statement."
    )


class ValueSettingMissingValueQualityDiagnostic(diagnostics.Diagnostic):
    """A particle in a Value Setting Statement has no assigned value quality."""

    position_name: str
    origin_position_name: str
    message_format: ClassVar[str] = (
        "the particle in '{self.position_name}' has no assigned value quality."
        " Assign a value quality to the position where it originated:"
        " '{self.origin_position_name}'."
    )


class ValueSettingValueQualityMismatchDiagnostic(diagnostics.Diagnostic):
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


class ViewSettingInterfaceViewWrittenTwiceDiagnostic(diagnostics.Diagnostic):
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


class ViewSettingLocalViewWrittenTwiceDiagnostic(diagnostics.Diagnostic):
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


class ViewSettingReadFromUnwrittenLocalViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a View Setting Statement reading a local view before anything writes to it."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is a local view, so it cannot be read until an"
        " earlier statement writes to it. However, this view setting statement"
        " reads it before anything writes to it."
    )


class ViewSettingReadFromUnwrittenOutputViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a View Setting Statement reading an output-only view before anything writes to it."""

    view_name: str
    message_format: ClassVar[str] = (
        "'{self.view_name}' is an output-only interface view, so it cannot be"
        " read until an earlier statement writes to it. However, this view"
        " setting statement reads it before anything writes to it."
    )


class ViewSettingReadFromWrittenReadWriteViewDiagnostic(diagnostics.Diagnostic):
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


class ViewSettingReadWriteTargetNotFromExecutionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a View Setting Statement with a read/write interface view target whose source the execution statement before it did not write from the target."""

    target_name: str
    source_name: str
    message_format: ClassVar[str] = (
        "the execution statement before this view setting statement must read"
        " '{self.target_name}' and write '{self.source_name}', because"
        " '{self.target_name}' is a read/write interface view."
    )


class ViewSettingReadWriteTargetWithoutExecutionDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a View Setting Statement with a read/write interface view target that does not follow an execution statement."""

    target_name: str
    message_format: ClassVar[str] = (
        "the statement before this view setting statement, other than view"
        " setting statements directly before it, must be an execution"
        " statement, because '{self.target_name}' is a read/write interface"
        " view."
    )


class WriteToInputOnlyViewDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an executed operation writing to an input-only view."""

    looked_at_name: str
    view_name: str
    operation_name: str
    message_format: ClassVar[str] = (
        "'{self.looked_at_name}' is an input-only interface view, so it cannot be"
        " written to. However, '{self.view_name}' of '{self.operation_name}'"
        " writes to it on this line."
    )
