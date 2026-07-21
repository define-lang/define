# pyright: reportPrivateUsage=false
from typing import ClassVar, override

import pytest

from define.runtime import literal


class TestParticle:
    def test_assign_position_stores_position(self):
        class MyPosition(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert isinstance(particle._positions[MyPosition], MyPosition)

    def test_assign_position_sets_on_particle(self):
        class MyPosition(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert particle.get_position(MyPosition).on_particle is particle

    def test_get_position_returns_stored_position(self):
        class MyPosition(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(MyPosition)

        assert isinstance(particle.get_position(MyPosition), MyPosition)

    def test_get_position_raises_on_missing_name(self):
        class MyPosition(literal.GlobalPosition):
            pass

        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_position(MyPosition)


class TestGlobalPosition:
    def test_name_from_full_class_path(self):
        class MyPosition(literal.GlobalPosition):
            pass

        pos = MyPosition(literal.Particle())

        assert pos.name == "position<literal_test.MyPosition>"

    def test_create_particle(self):
        class MyPosition(literal.GlobalPosition):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        class MyPosition(literal.GlobalPosition):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == "position<literal_test.MyPosition>"

    def test_constraints_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            pass

        pos = MyPosition(literal.Particle())

        assert pos._get_constraints() == ()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        class MyPosition(literal.GlobalPosition):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintPosition,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos._particle is not None
        assert ConstraintPosition in pos._particle._positions

    def test_create_particle_assigns_action_constraints(self):
        class ConstraintAction(literal.Action):
            pass

        class MyPosition(literal.GlobalPosition):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintAction,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos._particle is not None
        assert ConstraintAction in pos._particle._actions


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
            pass

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))

        assert pos._get_constraints() == (ConstraintPosition,)

    def test_constraints_defaults_to_empty(self):
        pos = literal.LocalPosition("test")

        assert pos._get_constraints() == ()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        pos = literal.LocalPosition("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        assert pos._particle is not None
        assert ConstraintPosition in pos._particle._positions


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
            pass

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
            pass

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert (
            exc_info.value.constraint_name
            == "position<literal_test.ConstraintPosition>"
        )
        assert "position<dest>" in str(exc_info.value)
        assert "position<literal_test.ConstraintPosition>" in str(exc_info.value)

    def test_move_with_unsatisfied_action_constraint_raises(self):
        class ConstraintAction(literal.Action):
            pass

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition("position<dest>", constraints=(ConstraintAction,))
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == "action<literal_test.ConstraintAction>"

    def test_move_constraint_check_does_not_transfer_on_failure(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        source = literal.LocalPosition("position<source>")
        dest = literal.LocalPosition(
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError):
            source.move_particle_to(dest)

        assert source.has_particle
        assert not dest.has_particle


class TestCreateConstructors:
    def test_create_fires_constructor(self):
        executed: list[str] = []

        class MyConstructor(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                executed.append("constructed")

        pos = literal.LocalPosition("test", constraints=(MyConstructor,))
        pos.create_particle()

        assert executed == ["constructed"]

    def test_create_does_not_fire_non_constructor(self):
        executed: list[str] = []

        class MyAction(literal.Action):
            @override
            def execute(self):
                executed.append("ran")

        pos = literal.LocalPosition("test", constraints=(MyAction,))
        pos.create_particle()

        assert executed == []

    def test_create_fires_constructors_in_assignment_order(self):
        order: list[str] = []

        class CtorA(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("A")

        class CtorB(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("B")

        pos = literal.LocalPosition("test", constraints=(CtorA, CtorB))
        pos.create_particle()

        assert order == ["A", "B"]

    def test_move_into_position_does_not_fire_constructor(self):
        executed: list[str] = []

        class MyConstructor(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                executed.append("constructed")

        source = literal.LocalPosition("source", constraints=(MyConstructor,))
        dest = literal.LocalPosition("dest", constraints=(MyConstructor,))
        source.create_particle()
        executed.clear()

        source.move_particle_to(dest)

        assert executed == []

    def test_constructor_creating_child_fires_child_constructor(self):
        order: list[str] = []

        class ChildConstructor(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("child")

        class ChildPosition(literal.GlobalPosition):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ChildConstructor,
            )

        class ParentConstructor(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("parent")
                self.on_particle.get_position(ChildPosition).create_particle()

        parent = literal.LocalPosition(
            "test", constraints=(ChildPosition, ParentConstructor)
        )
        parent.create_particle()

        assert order == ["parent", "child"]


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
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                executed.append("child destroyed")

        class ChildPosition(literal.GlobalPosition):
            pass

        pos = literal.LocalPosition("test")
        pos.create_particle()
        pos.particle.assign_position(ChildPosition)
        child_position = pos.particle.get_position(ChildPosition)
        child_position.create_particle()
        child_position.particle.assign_action(ChildDestructor)

        pos.destroy_particle()

        assert executed == ["child destroyed"]

    def test_destroy_unassigns_qualities_in_reverse_order(self):
        order: list[str] = []

        class ChildDtorA(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("A")

        class DtorB(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("B")

        class ChildDtorC(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("C")

        class PosA(literal.GlobalPosition):
            pass

        class PosC(literal.GlobalPosition):
            pass

        pos = literal.LocalPosition("test")
        pos.create_particle()
        particle = pos.particle
        particle.assign_position(PosA)
        particle.get_position(PosA).create_particle()
        particle.get_position(PosA).particle.assign_action(ChildDtorA)
        particle.assign_action(DtorB)
        particle.assign_position(PosC)
        particle.get_position(PosC).create_particle()
        particle.get_position(PosC).particle.assign_action(ChildDtorC)

        pos.destroy_particle()

        assert order == ["C", "B", "A"]

    def test_destroy_tears_down_interface_positions_in_reverse_order(self):
        order: list[str] = []

        class IfaceDtor1(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface1")

        class IfaceDtor2(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface2")

        class MyAction(literal.Action):
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
        action = pos.particle.get_action(MyAction)
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
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("iface_torn_down")

        class MyDestructor(literal.Action):
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
        action = pos.particle.get_action(MyDestructor)
        iface = action.get_interface_position("position</iface>")
        iface.create_particle()
        iface.particle.assign_action(IfaceChildDtor)

        pos.destroy_particle()

        assert order == ["destructor", "iface_torn_down"]

    def test_destroy_cascades_depth_first_not_breadth_first(self):
        order: list[str] = []

        class ChildPos(literal.GlobalPosition):
            pass

        class Left(literal.GlobalPosition):
            pass

        class Right(literal.GlobalPosition):
            pass

        class DtorL1(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("L1")

        class DtorL2(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("L2")

        class DtorR1(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("R1")

        class DtorR2(literal.Action):
            is_destructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append("R2")

        root = literal.LocalPosition("test")
        root.create_particle()
        particle = root.particle

        particle.assign_position(Left)
        left = particle.get_position(Left)
        left.create_particle()
        left.particle.assign_position(ChildPos)
        left.particle.get_position(ChildPos).create_particle()
        left.particle.get_position(ChildPos).particle.assign_action(DtorL2)
        left.particle.assign_action(DtorL1)

        particle.assign_position(Right)
        right = particle.get_position(Right)
        right.create_particle()
        right.particle.assign_position(ChildPos)
        right.particle.get_position(ChildPos).create_particle()
        right.particle.get_position(ChildPos).particle.assign_action(DtorR2)
        right.particle.assign_action(DtorR1)

        root.destroy_particle()

        # The right branch is fully destroyed (R1 then its grandchild R2) before
        # the left branch is touched. Breadth-first would instead interleave the
        # branches as ["R1", "L1", "R2", "L2"].
        assert order == ["R1", "R2", "L1", "L2"]


class TestStart:
    def test_start_fires_entry_constructor(self):
        fired: list[type[literal.Action]] = []

        class Entry(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                fired.append(type(self))

        literal.start(Entry)

        assert fired == [Entry]

    def test_reports_occupied_positions_when_env_var_set(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        class Entry(literal.Action):
            is_constructor: ClassVar[bool] = True

            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[literal.InterfacePosition("position<output>")],
                )

            @override
            def execute(self):
                self.get_interface_position("position<output>").create_particle()

        monkeypatch.setenv("DEFINE_REPORT_OCCUPIED_POSITIONS", "1")
        literal.start(Entry)

        assert (
            capsys.readouterr().out == "action<literal_test.Entry>::position<output>\n"
        )

    def test_no_report_when_env_var_unset(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        class Entry(literal.Action):
            is_constructor: ClassVar[bool] = True

        monkeypatch.delenv("DEFINE_REPORT_OCCUPIED_POSITIONS", raising=False)
        literal.start(Entry)

        assert capsys.readouterr().out == ""


class TestOccupiedPositionNames:
    def test_empty_when_nothing_occupied(self):
        class Entry(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(Entry)

        assert particle.occupied_position_names() == []

    def test_reports_occupied_global_position(self):
        class Entry(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(Entry)
        particle.get_position(Entry).create_particle()

        assert particle.occupied_position_names() == ["position<literal_test.Entry>"]

    def test_reports_nested_occupied_positions_parent_first(self):
        class Inner(literal.GlobalPosition):
            pass

        class Entry(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(Entry)
        entry = particle.get_position(Entry)
        entry.create_particle()
        entry.particle.assign_position(Inner)
        entry.particle.get_position(Inner).create_particle()

        assert particle.occupied_position_names() == [
            "position<literal_test.Entry>",
            "position<literal_test.Entry>::position<literal_test.Inner>",
        ]

    def test_reports_occupied_interface_position(self):
        class MyAction(literal.Action):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position<trigger_pos>"),
                    ],
                )

        particle = literal.Particle()
        particle.assign_action(MyAction)
        particle.get_action(MyAction).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()

        assert particle.occupied_position_names() == [
            "action<literal_test.MyAction>::position<trigger_pos>"
        ]

    def test_traverses_qualities_in_assignment_order(self):
        class MyAction(literal.Action):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.InterfacePosition("position<trigger_pos>"),
                    ],
                )

        class Later(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)
        particle.get_action(MyAction).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        particle.assign_position(Later)
        particle.get_position(Later).create_particle()

        assert particle.occupied_position_names() == [
            "action<literal_test.MyAction>::position<trigger_pos>",
            "position<literal_test.Later>",
        ]


class TestAction:
    def test_name_from_full_class_path(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        assert action.name == "action<literal_test.MyAction>"

    def test_should_execute_defaults_to_false(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        assert not action.should_execute

    def test_execute_defaults_to_noop(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        action.execute()

    def test_get_interface_position(self):
        pos = literal.InterfacePosition("position</iface>")

        class MyAction(literal.Action):
            pass

        action = MyAction(
            literal.Particle(),
            interface_positions=[pos],
            trigger_position_name="position</iface>",
        )

        assert action.get_interface_position("position</iface>") is pos

    def test_should_execute_checks_trigger_position(self):
        pos = literal.InterfacePosition("position</trigger_pos>")

        class MyAction(literal.Action):
            pass

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
            pass

        pos = literal.InterfacePosition("position</iface>", constraints=(C,))
        pos.create_particle()

        assert C in pos.particle.quality_types

    def test_retrigger_after_move_away_and_back(self):
        executed: list[str] = []

        class MyAction(literal.Action):
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
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert isinstance(particle._actions[MyAction], MyAction)

    def test_assign_action_sets_on_particle(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert particle.get_action(MyAction).on_particle is particle

    def test_get_action_returns_stored_action(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert isinstance(particle.get_action(MyAction), MyAction)

    def test_get_action_raises_on_missing_name(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_action(MyAction)


class TestImpliedQualities:
    def test_position_implied_qualities_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            pass

        assert MyPosition.implied_qualities == ()

    def test_action_implied_qualities_default_to_empty(self):
        class MyAction(literal.Action):
            pass

        assert MyAction.implied_qualities == ()

    def test_implied_quality_attached_before_implying_quality(self):
        order: list[type[literal.Quality]] = []

        class Implied(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append(type(self))

        class Implying(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

            @override
            def execute(self):
                order.append(type(self))

        position = literal.LocalPosition("test", constraints=(Implying,))
        position.create_particle()

        assert order == [Implied, Implying]

    def test_implied_qualities_processed_in_source_order(self):
        order: list[type[literal.Quality]] = []

        class First(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append(type(self))

        class Second(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append(type(self))

        class Implier(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                First,
                Second,
            )

            @override
            def execute(self):
                order.append(type(self))

        position = literal.LocalPosition("test", constraints=(Implier,))
        position.create_particle()

        assert order == [First, Second, Implier]

    def test_transitive_implied_qualities_attached(self):
        order: list[type[literal.Quality]] = []

        class C(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append(type(self))

        class B(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (C,)

            @override
            def execute(self):
                order.append(type(self))

        class A(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (B,)

            @override
            def execute(self):
                order.append(type(self))

        position = literal.LocalPosition("test", constraints=(A,))
        position.create_particle()

        assert order == [C, B, A]

    def test_diamond_implied_quality_assigned_only_once(self):
        order: list[type[literal.Quality]] = []

        class Shared(literal.Action):
            is_constructor: ClassVar[bool] = True

            @override
            def execute(self):
                order.append(type(self))

        class Left(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

            @override
            def execute(self):
                order.append(type(self))

        class Right(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

            @override
            def execute(self):
                order.append(type(self))

        class Top(literal.Action):
            is_constructor: ClassVar[bool] = True
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

            @override
            def execute(self):
                order.append(type(self))

        position = literal.LocalPosition("test", constraints=(Top,))
        position.create_particle()

        assert order == [
            Shared,
            Left,
            Right,
            Top,
        ]

    def test_diamond_implied_action_assigned_only_once(self):
        class Shared(literal.Action):
            pass

        class Left(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Right(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Top(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

        particle = literal.Particle()
        particle.assign_position(Top)

        quality_types = [type(quality) for quality in particle._assigned_qualities]
        assert quality_types == [
            Shared,
            Left,
            Right,
            Top,
        ]

    def test_constraint_also_implied_by_an_earlier_constraint_assigned_once(self):
        class Implied(literal.GlobalPosition):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = literal.LocalPosition("test", constraints=(Implier, Implied))
        position.create_particle()

        quality_types = [
            type(quality) for quality in position.particle._assigned_qualities
        ]
        assert quality_types == [Implied, Implier]

    def test_directly_assigned_quality_implied_by_a_later_constraint_assigned_once(
        self,
    ):
        class Implied(literal.GlobalPosition):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = literal.LocalPosition("test", constraints=(Implied, Implier))
        position.create_particle()

        quality_types = [
            type(quality) for quality in position.particle._assigned_qualities
        ]
        assert quality_types == [Implied, Implier]

    def test_local_position_with_a_duplicate_constraint_raises(self):
        class Implied(literal.GlobalPosition):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        with pytest.raises(literal.DuplicateConstraintError) as exc_info:
            _ = literal.LocalPosition("test", constraints=(Implier, Implied, Implied))
        assert exc_info.value.position_name == "position<literal_test.Implied>"

    def test_global_position_with_a_duplicate_constraint_raises(self):
        class Foo(literal.GlobalPosition):
            pass

        with pytest.raises(literal.DuplicateConstraintError) as exc_info:

            class _Bad(literal.GlobalPosition):  # pyright: ignore[reportUnusedClass]
                constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Foo, Foo)

        assert exc_info.value.position_name == "position<literal_test.Foo>"

    def test_action_processes_its_implied_qualities(self):
        class ImpliedPosition(literal.GlobalPosition):
            pass

        class ImplyingAction(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedPosition,
            )

        particle = literal.Particle()
        particle.assign_action(ImplyingAction)

        assert ImpliedPosition in particle._positions
        assert ImplyingAction in particle._actions

    def test_position_can_imply_action(self):
        class ImpliedAction(literal.Action):
            pass

        class ImplyingPosition(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedAction,
            )

        particle = literal.Particle()
        particle.assign_position(ImplyingPosition)

        assert ImpliedAction in particle._actions
        assert ImplyingPosition in particle._positions

    def test_assign_position_twice_is_idempotent(self):
        class MyPosition(literal.GlobalPosition):
            pass

        particle = literal.Particle()
        particle.assign_position(MyPosition)
        particle.assign_position(MyPosition)

        assert [type(quality) for quality in particle._assigned_qualities] == [
            MyPosition
        ]

    def test_assign_action_twice_is_idempotent(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)
        particle.assign_action(MyAction)

        assert [type(quality) for quality in particle._assigned_qualities] == [MyAction]

    def test_create_particle_propagates_transitive_qualities(self):
        class Inner(literal.GlobalPosition):
            pass

        class Outer(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Inner,)

        class Container(literal.GlobalPosition):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Outer,)

        container = Container(literal.Particle())
        container.create_particle()

        assert container._particle is not None
        assert Outer in container._particle._positions
        assert Inner in container._particle._positions

    def test_move_succeeds_via_transitive_implied_quality(self):
        class Implied(literal.GlobalPosition):
            pass

        class Implying(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        source = literal.LocalPosition("source", constraints=(Implying,))
        dest = literal.LocalPosition("dest", constraints=(Implied,))
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_assigned_qualities_recorded_in_assignment_order(self):
        class A(literal.GlobalPosition):
            pass

        class B(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (A,)

        particle = literal.Particle()
        particle.assign_position(B)

        quality_types = [type(quality) for quality in particle._assigned_qualities]
        assert quality_types == [A, B]

    def test_assign_action_contributes_to_quality_types(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_action(MyAction)

        assert MyAction in particle.quality_types
