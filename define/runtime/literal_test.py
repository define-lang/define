# pyright: reportPrivateUsage=false
from typing import ClassVar, override

import pytest

from define.runtime import literal


class TestDimensionPoint:
    def test_assign_position_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test_pos>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        dp = literal.DimensionPoint()
        pos = TrackingPosition()
        dp.assign_position(pos)

        assert triggered == ["position<test_pos>"]

    def test_assign_position_stores_position(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<quality_pos>"

        dp = literal.DimensionPoint()
        pos = MyPosition()
        dp.assign_position(pos)

        assert dp._positions["position<quality_pos>"] is pos

    def test_get_position_returns_stored_position(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<quality_pos>"

        dp = literal.DimensionPoint()
        pos = MyPosition()
        dp.assign_position(pos)

        assert dp.get_position("position<quality_pos>") is pos

    def test_get_position_raises_on_missing_name(self):
        dp = literal.DimensionPoint()

        with pytest.raises(KeyError):
            _ = dp.get_position("nonexistent")


class TestGlobalPosition:
    def test_name_from_class_var(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/thing>"

        pos = MyPosition()

        assert pos.name == "position<test.com:lib:/thing>"

    def test_create_dimension_point(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition()
        pos.create_dimension_point()

        assert pos.has_dimension_point

    def test_create_dimension_point_raises_on_duplicate(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition()
        pos.create_dimension_point()

        with pytest.raises(literal.DimensionPointExistsError) as exc_info:
            pos.create_dimension_point()
        assert exc_info.value.position_name == "position<test>"

    def test_constraints_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition()

        assert pos._get_constraints() == ()

    def test_create_dimension_point_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"
            constraints: ClassVar[tuple[literal.Constraint, ...]] = (
                ConstraintPosition,
            )

        pos = MyPosition()
        pos.create_dimension_point()

        assert pos._dimension_point is not None
        assert "position<test.com:lib:/constraint>" in pos._dimension_point._positions

    def test_create_dimension_point_assigns_action_constraints(self):
        class ConstraintAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test.com:lib:/constraint>"

        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"
            constraints: ClassVar[tuple[literal.Constraint, ...]] = (ConstraintAction,)

        pos = MyPosition()
        pos.create_dimension_point()

        assert pos._dimension_point is not None
        assert "action<test.com:lib:/constraint>" in pos._dimension_point._actions

    def test_after_assigned_default_does_nothing(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition()

        pos.after_assigned()


class TestLocalPosition:
    def test_name_from_init(self):
        pos = literal.LocalPosition("my_pos")

        assert pos.name == "my_pos"

    def test_create_dimension_point(self):
        pos = literal.LocalPosition("test")
        pos.create_dimension_point()

        assert pos.has_dimension_point

    def test_create_dimension_point_raises_on_duplicate(self):
        pos = literal.LocalPosition("test")
        pos.create_dimension_point()

        with pytest.raises(literal.DimensionPointExistsError) as exc_info:
            pos.create_dimension_point()
        assert exc_info.value.position_name == "test"

    def test_has_dimension_point_initially_false(self):
        pos = literal.LocalPosition("test")

        assert not pos.has_dimension_point

    def test_dimension_point_returns_point(self):
        pos = literal.LocalPosition("test")
        pos.create_dimension_point()

        assert pos.dimension_point is pos._dimension_point

    def test_dimension_point_raises_when_none(self):
        pos = literal.LocalPosition("test")

        with pytest.raises(literal.NoDimensionPointError):
            pos.dimension_point  # noqa: B018

    def test_constraints_stored(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<x>"

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))

        assert pos._get_constraints() == (ConstraintPosition,)

    def test_constraints_defaults_to_empty(self):
        pos = literal.LocalPosition("test")

        assert pos._get_constraints() == ()

    def test_create_dimension_point_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))
        pos.create_dimension_point()

        assert pos._dimension_point is not None
        assert "position<test.com:lib:/constraint>" in pos._dimension_point._positions


class TestMovePosition:
    def test_move_dimension_point_to(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")
        source.create_dimension_point()

        source.move_dimension_point_to(dest)

        assert not source.has_dimension_point
        assert dest.has_dimension_point

    def test_move_from_empty_raises(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")

        with pytest.raises(literal.NoDimensionPointError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "source"

    def test_move_to_occupied_raises(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")
        source.create_dimension_point()
        dest.create_dimension_point()

        with pytest.raises(literal.DimensionPointExistsError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "dest"

    def test_move_with_satisfied_constraints_succeeds(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition(
            "position<source>", constraints=(ConstraintPosition,)
        )
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_dimension_point()

        source.move_dimension_point_to(dest)

        assert not source.has_dimension_point
        assert dest.has_dimension_point

    def test_move_with_unsatisfied_position_constraint_raises(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_dimension_point()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == "position<test.com:lib:/constraint>"

    def test_move_with_unsatisfied_action_constraint_raises(self):
        class ConstraintAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition("position<dest>", constraints=(ConstraintAction,))
        source.create_dimension_point()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == "action<test.com:lib:/constraint>"

    def test_move_constraint_check_does_not_transfer_on_failure(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_dimension_point()

        with pytest.raises(literal.UnsatisfiedConstraintError):
            source.move_dimension_point_to(dest)

        assert source.has_dimension_point
        assert not dest.has_dimension_point


class TestDestroyDimensionPoint:
    def test_destroy_dimension_point(self):
        pos = literal.LocalPosition("test")
        pos.create_dimension_point()

        pos.destroy_dimension_point()

        assert not pos.has_dimension_point

    def test_destroy_from_empty_raises(self):
        pos = literal.LocalPosition("test")

        with pytest.raises(literal.NoDimensionPointError) as exc_info:
            pos.destroy_dimension_point()
        assert exc_info.value.position_name == "test"

    def test_destroy_then_create_succeeds(self):
        pos = literal.LocalPosition("test")
        pos.create_dimension_point()
        pos.destroy_dimension_point()

        pos.create_dimension_point()

        assert pos.has_dimension_point


class TestStart:
    def test_start_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<entry>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        entry = TrackingPosition()
        literal.start(entry)

        assert triggered == ["position<entry>"]


class TestAction:
    def test_name_from_class_var(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test.com:lib:/thing>"

        action = MyAction()

        assert action.name == "action<test.com:lib:/thing>"

    def test_should_execute_defaults_to_false(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        action = MyAction()

        assert not action.should_execute

    def test_execute_defaults_to_noop(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        action = MyAction()

        action.execute()

    def test_get_interface_position(self):
        pos = literal.InterfacePosition("position</iface>")

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        action = MyAction(
            interface_positions=[pos],
            trigger_position_name="position</iface>",
        )

        assert action.get_interface_position("position</iface>") is pos

    def test_should_execute_checks_trigger_position(self):
        pos = literal.InterfacePosition("position</trigger_pos>")

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        action = MyAction(
            interface_positions=[pos],
            trigger_position_name="position</trigger_pos>",
        )

        assert not action.should_execute
        pos.create_dimension_point()
        assert action.should_execute


class TestActionTriggering:
    def test_create_triggers_action(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

            def __init__(self):
                super().__init__(
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction()
        action.get_interface_position("position</trigger_pos>").create_dimension_point()

        assert executed == ["triggered"]

    def test_move_triggers_action(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

            def __init__(self):
                super().__init__(
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction()
        source = literal.LocalPosition("position</source>")
        source.create_dimension_point()
        source.move_dimension_point_to(
            action.get_interface_position("position</trigger_pos>")
        )

        assert executed == ["triggered"]

    def test_no_trigger_when_no_trigger_position(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

            @override
            def execute(self):
                executed.append("triggered")

        pos = literal.InterfacePosition("position</trigger_pos>")
        action = MyAction(interface_positions=[pos])
        pos.set_is_trigger_for(action)
        pos.create_dimension_point()

        assert executed == []

    def test_interface_position_without_trigger_works_normally(self):
        pos = literal.InterfacePosition("position</test>")
        pos.create_dimension_point()

        assert pos.has_dimension_point

    def test_retrigger_after_move_away_and_back(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

            def __init__(self):
                super().__init__(
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction()
        trigger = action.get_interface_position("position</trigger_pos>")
        trigger.create_dimension_point()
        other = literal.LocalPosition("position</other>")
        trigger.move_dimension_point_to(other)
        other.move_dimension_point_to(trigger)

        assert executed == ["triggered", "triggered"]


class TestDimensionPointActions:
    def test_assign_action_stores_action(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        dp = literal.DimensionPoint()
        action = MyAction()
        dp.assign_action(action)

        assert dp._actions["action<test>"] is action

    def test_get_action_returns_stored_action(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        dp = literal.DimensionPoint()
        action = MyAction()
        dp.assign_action(action)

        assert dp.get_action("action<test>") is action

    def test_get_action_raises_on_missing_name(self):
        dp = literal.DimensionPoint()

        with pytest.raises(KeyError):
            _ = dp.get_action("nonexistent")


class TestQualityRequirements:
    def test_position_quality_requirements_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

        assert MyPosition.quality_requirements == ()

    def test_action_quality_requirements_default_to_empty(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        assert MyAction.quality_requirements == ()

    def test_required_quality_attached_before_requiring_quality(self):
        order: list[str] = []

        class Required(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<required>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Requiring(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<requiring>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Required,)

            @override
            def after_assigned(self):
                order.append(self.name)

        dp = literal.DimensionPoint()
        dp.assign_position(Requiring())

        assert order == ["position<required>", "position<requiring>"]
        assert "position<required>" in dp._positions
        assert "position<requiring>" in dp._positions

    def test_quality_requirements_processed_in_source_order(self):
        order: list[str] = []

        class First(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<first>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Second(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<second>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Requirer(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<requirer>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (
                First,
                Second,
            )

            @override
            def after_assigned(self):
                order.append(self.name)

        dp = literal.DimensionPoint()
        dp.assign_position(Requirer())

        assert order == ["position<first>", "position<second>", "position<requirer>"]

    def test_transitive_quality_requirements_attached(self):
        order: list[str] = []

        class C(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<c>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class B(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<b>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (C,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class A(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<a>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (B,)

            @override
            def after_assigned(self):
                order.append(self.name)

        dp = literal.DimensionPoint()
        dp.assign_position(A())

        assert order == ["position<c>", "position<b>", "position<a>"]

    def test_diamond_quality_requirement_assigned_only_once(self):
        order: list[str] = []

        class Shared(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<shared>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Left(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<left>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Shared,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class Right(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<right>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Shared,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class Top(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<top>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (
                Left,
                Right,
            )

            @override
            def after_assigned(self):
                order.append(self.name)

        dp = literal.DimensionPoint()
        dp.assign_position(Top())

        assert order == [
            "position<shared>",
            "position<left>",
            "position<right>",
            "position<top>",
        ]

    def test_action_processes_its_quality_requirements(self):
        class RequiredPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<required>"

        class RequiringAction(literal.Action):
            _typed_name: ClassVar[str] = "action<requiring>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (
                RequiredPosition,
            )

        dp = literal.DimensionPoint()
        dp.assign_action(RequiringAction())

        assert "position<required>" in dp._positions
        assert "action<requiring>" in dp._actions

    def test_position_can_require_action(self):
        class RequiredAction(literal.Action):
            _typed_name: ClassVar[str] = "action<required>"

        class RequiringPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<requiring>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (
                RequiredAction,
            )

        dp = literal.DimensionPoint()
        dp.assign_position(RequiringPosition())

        assert "action<required>" in dp._actions
        assert "position<requiring>" in dp._positions

    def test_assign_position_already_present_is_no_op(self):
        triggered: list[str] = []

        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        dp = literal.DimensionPoint()
        first = MyPosition()
        dp.assign_position(first)
        dp.assign_position(MyPosition())

        assert triggered == ["position<test>"]
        assert dp._positions["position<test>"] is first

    def test_assign_action_already_present_is_no_op(self):
        class MyAction(literal.Action):
            _typed_name: ClassVar[str] = "action<test>"

        dp = literal.DimensionPoint()
        first = MyAction()
        dp.assign_action(first)
        dp.assign_action(MyAction())

        assert dp._actions["action<test>"] is first

    def test_create_dimension_point_propagates_transitive_qualities(self):
        class Inner(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<inner>"

        class Outer(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<outer>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Inner,)

        class Container(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<container>"
            constraints: ClassVar[tuple[literal.Constraint, ...]] = (Outer,)

        container = Container()
        container.create_dimension_point()

        assert container._dimension_point is not None
        assert "position<outer>" in container._dimension_point._positions
        assert "position<inner>" in container._dimension_point._positions

    def test_move_succeeds_via_transitive_quality_requirement(self):
        class Required(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<required>"

        class Requiring(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<requiring>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Required,)

        source = literal.LocalPosition("source", constraints=(Requiring,))
        dest = literal.LocalPosition("dest", constraints=(Required,))
        source.create_dimension_point()

        source.move_dimension_point_to(dest)

        assert not source.has_dimension_point
        assert dest.has_dimension_point

    def test_assigned_qualities_recorded_in_assignment_order(self):
        class A(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<a>"

        class B(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<b>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (A,)

        dp = literal.DimensionPoint()
        dp.assign_position(B())

        names = [quality.name for quality in dp._assigned_qualities]
        assert names == ["position<a>", "position<b>"]

    def test_required_quality_after_assigned_side_effects_run(self):
        class Required(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<required>"

            @override
            def after_assigned(self):
                self.create_dimension_point()

        class Requiring(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<requiring>"
            quality_requirements: ClassVar[tuple[literal.Constraint, ...]] = (Required,)

        dp = literal.DimensionPoint()
        dp.assign_position(Requiring())

        assert dp.get_position("position<required>").has_dimension_point
