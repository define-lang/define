# pyright: reportPrivateUsage=false
from typing import ClassVar, override

import pytest

from define.runtime import literal


class TestParticle:
    def test_assign_position_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test_pos>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        particle = literal.Particle()
        particle.assign_position(TrackingPosition)

        assert triggered == ["position<test_pos>"]

    def test_assign_position_stores_position(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<quality_pos>"

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert isinstance(particle._positions["position<quality_pos>"], MyPosition)

    def test_assign_position_sets_on_particle(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<quality_pos>"

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert particle.get_position("position<quality_pos>").on_particle is particle

    def test_get_position_returns_stored_position(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<quality_pos>"

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert isinstance(particle.get_position("position<quality_pos>"), MyPosition)

    def test_get_position_raises_on_missing_name(self):
        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_position("nonexistent")


class TestGlobalPosition:
    def test_name_from_class_var(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/thing>"

        pos = MyPosition(literal.Particle())

        assert pos.name == "position<test.com:lib:/thing>"

    def test_create_particle(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == "position<test>"

    def test_constraints_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition(literal.Particle())

        assert pos._get_constraints() == ()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintPosition,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos._particle is not None
        assert "position<test.com:lib:/constraint>" in pos._particle._positions

    def test_create_particle_assigns_action_constraints(self):
        class ConstraintAction(literal.Action):
            typed_name: ClassVar[str] = "action<test.com:lib:/constraint>"

        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintAction,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos._particle is not None
        assert "action<test.com:lib:/constraint>" in pos._particle._actions

    def test_after_assigned_default_does_nothing(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

        pos = MyPosition(literal.Particle())

        pos.after_assigned()


class TestLocalPosition:
    def test_name_from_init(self):
        pos = literal.LocalPosition("my_pos")

        assert pos.name == "my_pos"

    def test_create_particle(self):
        pos = literal.LocalPosition("test")
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        pos = literal.LocalPosition("test")
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == "test"
        assert "test" in str(exc_info.value)

    def test_has_particle_initially_false(self):
        pos = literal.LocalPosition("test")

        assert not pos.has_particle

    def test_particle_returns_point(self):
        pos = literal.LocalPosition("test")
        pos.create_particle()

        assert pos.particle is pos._particle

    def test_particle_raises_when_none(self):
        pos = literal.LocalPosition("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.particle  # noqa: B018
        assert "test" in str(exc_info.value)

    def test_constraints_stored(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<x>"

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))

        assert pos._get_constraints() == (ConstraintPosition,)

    def test_constraints_defaults_to_empty(self):
        pos = literal.LocalPosition("test")

        assert pos._get_constraints() == ()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        assert pos._particle is not None
        assert "position<test.com:lib:/constraint>" in pos._particle._positions


class TestMovePosition:
    def test_move_particle_to(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_from_empty_raises(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")

        with pytest.raises(literal.NoParticleError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "source"

    def test_move_to_occupied_raises(self):
        source = literal.LocalPosition("source")
        dest = literal.LocalPosition("dest")
        source.create_particle()
        dest.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "dest"

    def test_move_with_satisfied_constraints_succeeds(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition(
            "position<source>", constraints=(ConstraintPosition,)
        )
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_with_unsatisfied_position_constraint_raises(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == "position<test.com:lib:/constraint>"
        assert "position<dest>" in str(exc_info.value)
        assert "position<test.com:lib:/constraint>" in str(exc_info.value)

    def test_move_with_unsatisfied_action_constraint_raises(self):
        class ConstraintAction(literal.Action):
            typed_name: ClassVar[str] = "action<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition("position<dest>", constraints=(ConstraintAction,))
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == "action<test.com:lib:/constraint>"

    def test_move_constraint_check_does_not_transfer_on_failure(self):
        class ConstraintPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test.com:lib:/constraint>"

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError):
            source.move_particle_to(dest)

        assert source.has_particle
        assert not dest.has_particle


class TestDestroyParticle:
    def test_destroy_particle(self):
        pos = literal.LocalPosition("test")
        pos.create_particle()

        pos.destroy_particle()

        assert not pos.has_particle

    def test_destroy_from_empty_raises(self):
        pos = literal.LocalPosition("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.destroy_particle()
        assert exc_info.value.position_name == "test"

    def test_destroy_then_create_succeeds(self):
        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.destroy_particle()

        pos.create_particle()

        assert pos.has_particle

    def test_destroy_fires_destructor(self):
        executed: list[str] = []

        class MyDestructor(literal.Action):
            typed_name: ClassVar[str] = "action<dtor>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                executed.append("destroyed")

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_action(MyDestructor)

        pos.destroy_particle()

        assert executed == ["destroyed"]

    def test_destroy_does_not_fire_non_destructor(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<act>"

            @override
            def execute(self):
                executed.append("ran")

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_action(MyAction)

        pos.destroy_particle()

        assert executed == []

    def test_destroy_cascades_into_child_position_destructor(self):
        executed: list[str] = []

        class ChildDestructor(literal.Action):
            typed_name: ClassVar[str] = "action<child_dtor>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                executed.append("child destroyed")

        class ChildPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<child_pos>"

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_position(ChildPosition)
        child_position = pos.particle.get_position("position<child_pos>")
        child_position.create_particle()
        child_position.particle.assign_action(ChildDestructor)

        pos.destroy_particle()

        assert executed == ["child destroyed"]

    def test_destroy_unassigns_qualities_in_reverse_order(self):
        order: list[str] = []

        class ChildDtorA(literal.Action):
            typed_name: ClassVar[str] = "action<child_a>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("A")

        class DtorB(literal.Action):
            typed_name: ClassVar[str] = "action<b>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("B")

        class ChildDtorC(literal.Action):
            typed_name: ClassVar[str] = "action<child_c>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("C")

        class PosA(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<a>"

        class PosC(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<c>"

        pos = literal.LocalPosition("test")
        pos.create_particle()
        particle = pos.particle
        particle.assign_position(PosA)
        particle.get_position("position<a>").create_particle()
        particle.get_position("position<a>").particle.assign_action(ChildDtorA)
        particle.assign_action(DtorB)
        particle.assign_position(PosC)
        particle.get_position("position<c>").create_particle()
        particle.get_position("position<c>").particle.assign_action(ChildDtorC)

        pos.destroy_particle()

        assert order == ["C", "B", "A"]

    def test_destroy_tears_down_interface_positions_in_reverse_order(self):
        order: list[str] = []

        class IfaceDtor1(literal.Action):
            typed_name: ClassVar[str] = "action<iface_dtor1>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface1")

        class IfaceDtor2(literal.Action):
            typed_name: ClassVar[str] = "action<iface_dtor2>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface2")

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<act>"

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</iface1>"),
                        literal.InterfacePosition("position</iface2>"),
                    ],
                )

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_action(MyAction)
        action = pos.particle.get_action("action<act>")
        iface1 = action.get_interface_position("position</iface1>")
        iface1.create_particle()
        iface1.particle.assign_action(IfaceDtor1)
        iface2 = action.get_interface_position("position</iface2>")
        iface2.create_particle()
        iface2.particle.assign_action(IfaceDtor2)

        pos.destroy_particle()

        assert order == ["iface2", "iface1"]

    def test_destroy_with_empty_interface_position_does_not_raise(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<act>"

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</iface>"),
                    ],
                )

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_action(MyAction)

        pos.destroy_particle()

        assert not pos.has_particle

    def test_destructor_runs_before_its_interface_positions_destroyed(self):
        order: list[str] = []

        class IfaceChildDtor(literal.Action):
            typed_name: ClassVar[str] = "action<iface_child>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface_torn_down")

        class MyDestructor(literal.Action):
            typed_name: ClassVar[str] = "action<dtor>"
            is_destructor: ClassVar[bool] = True

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</iface>"),
                    ],
                )

            @override
            def execute(self):
                order.append("destructor")

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_action(MyDestructor)
        action = pos.particle.get_action("action<dtor>")
        iface = action.get_interface_position("position</iface>")
        iface.create_particle()
        iface.particle.assign_action(IfaceChildDtor)

        pos.destroy_particle()

        assert order == ["destructor", "iface_torn_down"]

    def test_destroy_cascades_depth_first_not_breadth_first(self):
        order: list[str] = []

        class ChildPos(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<child>"

        class Left(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<left>"

        class Right(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<right>"

        class DtorL1(literal.Action):
            typed_name: ClassVar[str] = "action<l1>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("L1")

        class DtorL2(literal.Action):
            typed_name: ClassVar[str] = "action<l2>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("L2")

        class DtorR1(literal.Action):
            typed_name: ClassVar[str] = "action<r1>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("R1")

        class DtorR2(literal.Action):
            typed_name: ClassVar[str] = "action<r2>"
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("R2")

        root = literal.LocalPosition("test")
        root.create_particle()
        particle = root.particle

        particle.assign_position(Left)
        left = particle.get_position("position<left>")
        left.create_particle()
        left.particle.assign_position(ChildPos)
        left.particle.get_position("position<child>").create_particle()
        left.particle.get_position("position<child>").particle.assign_action(DtorL2)
        left.particle.assign_action(DtorL1)

        particle.assign_position(Right)
        right = particle.get_position("position<right>")
        right.create_particle()
        right.particle.assign_position(ChildPos)
        right.particle.get_position("position<child>").create_particle()
        right.particle.get_position("position<child>").particle.assign_action(DtorR2)
        right.particle.assign_action(DtorR1)

        root.destroy_particle()

        # The right branch is fully destroyed (R1 then its grandchild R2) before
        # the left branch is touched. Breadth-first would instead interleave the
        # branches as ["R1", "L1", "R2", "L2"].
        assert order == ["R1", "R2", "L1", "L2"]


class TestStart:
    def test_start_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<entry>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        literal.start(TrackingPosition)

        assert triggered == ["position<entry>"]


class TestAction:
    def test_name_from_class_var(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test.com:lib:/thing>"

        action = MyAction(literal.Particle())

        assert action.name == "action<test.com:lib:/thing>"

    def test_should_execute_defaults_to_false(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        action = MyAction(literal.Particle())

        assert not action.should_execute

    def test_execute_defaults_to_noop(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        action = MyAction(literal.Particle())

        action.execute()

    def test_get_interface_position(self):
        pos = literal.InterfacePosition("position</iface>")

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        action = MyAction(
            literal.Particle(),
            interface_positions=[pos],
            trigger_position_name="position</iface>",
        )

        assert action.get_interface_position("position</iface>") is pos

    def test_should_execute_checks_trigger_position(self):
        pos = literal.InterfacePosition("position</trigger_pos>")

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        action = MyAction(
            literal.Particle(),
            interface_positions=[pos],
            trigger_position_name="position</trigger_pos>",
        )

        assert not action.should_execute
        pos.create_particle()
        assert action.should_execute


class TestActionTriggering:
    def test_create_triggers_action(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction(literal.Particle())
        action.get_interface_position("position</trigger_pos>").create_particle()

        assert executed == ["triggered"]

    def test_move_triggers_action(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction(literal.Particle())
        source = literal.LocalPosition("position</source>")
        source.create_particle()
        source.move_particle_to(action.get_interface_position("position</trigger_pos>"))

        assert executed == ["triggered"]

    def test_no_trigger_when_no_trigger_position(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

            @override
            def execute(self):
                executed.append("triggered")

        pos = literal.InterfacePosition("position</trigger_pos>")
        action = MyAction(literal.Particle(), interface_positions=[pos])
        pos.set_is_trigger_for(action)
        pos.create_particle()

        assert executed == []

    def test_interface_position_without_trigger_works_normally(self):
        pos = literal.InterfacePosition("position</test>")
        pos.create_particle()

        assert pos.has_particle

    def test_interface_position_applies_constraints_on_create(self):
        class C(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<c>"

        pos = literal.InterfacePosition("position</iface>", constraints=(C,))
        pos.create_particle()

        assert C in pos.particle.quality_types

    def test_retrigger_after_move_away_and_back(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position</trigger_pos>"),
                    ],
                    trigger_position_name="position</trigger_pos>",
                )

            @override
            def execute(self):
                executed.append("triggered")

        action = MyAction(literal.Particle())
        trigger = action.get_interface_position("position</trigger_pos>")
        trigger.create_particle()
        other = literal.LocalPosition("position</other>")
        trigger.move_particle_to(other)
        other.move_particle_to(trigger)

        assert executed == ["triggered", "triggered"]


class TestParticleActions:
    def test_assign_action_stores_action(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert isinstance(particle._actions["action<test>"], MyAction)

    def test_assign_action_sets_on_particle(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert particle.get_action("action<test>").on_particle is particle

    def test_get_action_returns_stored_action(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert isinstance(particle.get_action("action<test>"), MyAction)

    def test_get_action_raises_on_missing_name(self):
        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_action("nonexistent")


class TestImpliedQualities:
    def test_position_implied_qualities_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

        assert MyPosition.implied_qualities == ()

    def test_action_implied_qualities_default_to_empty(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        assert MyAction.implied_qualities == ()

    def test_implied_quality_attached_before_implying_quality(self):
        order: list[str] = []

        class Implied(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implied>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Implying(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implying>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

            @override
            def after_assigned(self):
                order.append(self.name)

        particle = literal.Particle()
        particle.assign_position(Implying)

        assert order == ["position<implied>", "position<implying>"]
        assert "position<implied>" in particle._positions
        assert "position<implying>" in particle._positions

    def test_implied_qualities_processed_in_source_order(self):
        order: list[str] = []

        class First(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<first>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Second(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<second>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Implier(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implier>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                First,
                Second,
            )

            @override
            def after_assigned(self):
                order.append(self.name)

        particle = literal.Particle()
        particle.assign_position(Implier)

        assert order == ["position<first>", "position<second>", "position<implier>"]

    def test_transitive_implied_qualities_attached(self):
        order: list[str] = []

        class C(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<c>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class B(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<b>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (C,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class A(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<a>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (B,)

            @override
            def after_assigned(self):
                order.append(self.name)

        particle = literal.Particle()
        particle.assign_position(A)

        assert order == ["position<c>", "position<b>", "position<a>"]

    def test_diamond_implied_quality_assigned_only_once(self):
        order: list[str] = []

        class Shared(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<shared>"

            @override
            def after_assigned(self):
                order.append(self.name)

        class Left(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<left>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class Right(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<right>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

            @override
            def after_assigned(self):
                order.append(self.name)

        class Top(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<top>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

            @override
            def after_assigned(self):
                order.append(self.name)

        particle = literal.Particle()
        particle.assign_position(Top)

        assert order == [
            "position<shared>",
            "position<left>",
            "position<right>",
            "position<top>",
        ]

    def test_diamond_implied_action_assigned_only_once(self):
        class Shared(literal.Action):
            typed_name: ClassVar[str] = "action<shared>"

        class Left(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<left>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Right(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<right>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Top(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<top>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

        particle = literal.Particle()
        particle.assign_position(Top)

        names = [quality.name for quality in particle._assigned_qualities]
        assert names == [
            "action<shared>",
            "position<left>",
            "position<right>",
            "position<top>",
        ]

    def test_action_processes_its_implied_qualities(self):
        class ImpliedPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implied>"

        class ImplyingAction(literal.Action):
            typed_name: ClassVar[str] = "action<implying>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedPosition,
            )

        particle = literal.Particle()
        particle.assign_action(ImplyingAction)

        assert "position<implied>" in particle._positions
        assert "action<implying>" in particle._actions

    def test_position_can_imply_action(self):
        class ImpliedAction(literal.Action):
            typed_name: ClassVar[str] = "action<implied>"

        class ImplyingPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implying>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedAction,
            )

        particle = literal.Particle()
        particle.assign_position(ImplyingPosition)

        assert "action<implied>" in particle._actions
        assert "position<implying>" in particle._positions

    def test_assign_position_duplicate_raises(self):
        triggered: list[str] = []

        class MyPosition(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<test>"

            @override
            def after_assigned(self):
                triggered.append(self.name)

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        with pytest.raises(literal.DuplicateQualityAssignmentError) as exc_info:
            particle.assign_position(MyPosition)
        assert exc_info.value.position_name == "position<test>"
        assert triggered == ["position<test>"]

    def test_assign_action_duplicate_raises(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        particle = literal.Particle()
        particle.assign_action(MyAction)

        with pytest.raises(literal.DuplicateQualityAssignmentError) as exc_info:
            particle.assign_action(MyAction)
        assert exc_info.value.position_name == "action<test>"

    def test_create_particle_propagates_transitive_qualities(self):
        class Inner(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<inner>"

        class Outer(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<outer>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Inner,)

        class Container(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<container>"
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Outer,)

        container = Container(literal.Particle())
        container.create_particle()

        assert container._particle is not None
        assert "position<outer>" in container._particle._positions
        assert "position<inner>" in container._particle._positions

    def test_move_succeeds_via_transitive_implied_quality(self):
        class Implied(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implied>"

        class Implying(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implying>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        source = literal.LocalPosition("source", constraints=(Implying,))
        dest = literal.LocalPosition("dest", constraints=(Implied,))
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_assigned_qualities_recorded_in_assignment_order(self):
        class A(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<a>"

        class B(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<b>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (A,)

        particle = literal.Particle()
        particle.assign_position(B)

        names = [quality.name for quality in particle._assigned_qualities]
        assert names == ["position<a>", "position<b>"]

    def test_assign_action_contributes_to_quality_types(self):
        class MyAction(literal.Action):
            typed_name: ClassVar[str] = "action<test>"

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert MyAction in particle.quality_types

    def test_implied_quality_after_assigned_side_effects_run(self):
        class Implied(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implied>"

            @override
            def after_assigned(self):
                self.create_particle()

        class Implying(literal.GlobalPosition):
            typed_name: ClassVar[str] = "position<implying>"
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        particle = literal.Particle()
        particle.assign_position(Implying)

        assert particle.get_position("position<implied>").has_particle
