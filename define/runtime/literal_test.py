# pyright: reportPrivateUsage=false
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Never, override

import pytest

from define.runtime import literal

if TYPE_CHECKING:
    from pathlib import Path


class TestParticle:
    def test_assign_position_sets_on_particle(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyPosition)

        assert particle.get_position(MyPosition).on_particle is particle

    def test_get_position_returns_stored_position(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyPosition)

        assert isinstance(particle.get_position(MyPosition), MyPosition)

    def test_get_position_raises_on_missing_name(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_position(MyPosition)


class TestGlobalPosition:
    def test_name_from_full_class_path(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        pos = MyPosition(literal.Particle())

        assert pos.name == f"position<{__name__}.MyPosition>"

    def test_create_particle(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == f"position<{__name__}.MyPosition>"

    def test_constraints_default_to_empty(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos.particle._qualities == {}

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        class MyPosition(literal.GlobalPosition[Never]):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintPosition,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert isinstance(
            pos.particle.get_position(ConstraintPosition), ConstraintPosition
        )

    def test_create_particle_assigns_action_constraints(self):
        class ConstraintAction(literal.Action):
            pass

        class MyPosition(literal.GlobalPosition[Never]):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintAction,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert isinstance(pos.particle.get_action(ConstraintAction), ConstraintAction)


class TestLocalPosition:
    def test_name_from_init(self):
        pos = literal.LocalPosition[Never]("my_pos")

        assert pos.name == "my_pos"

    def test_create_particle(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == "test"
        assert "test" in str(exc_info.value)

    def test_has_particle_initially_false(self):
        pos = literal.LocalPosition[Never]("test")

        assert not pos.has_particle

    def test_particle_returns_point(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()
        particle = pos.particle

        assert pos.particle is particle

    def test_particle_raises_when_none(self):
        pos = literal.LocalPosition[Never]("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.particle  # noqa: B018
        assert "test" in str(exc_info.value)

    def test_constraints_stored(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        pos = literal.LocalPosition[Never]("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        quality_types = list(pos.particle._qualities)
        assert quality_types == [ConstraintPosition]

    def test_constraints_defaults_to_empty(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()

        assert pos.particle._qualities == {}

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        pos = literal.LocalPosition[Never]("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        assert isinstance(
            pos.particle.get_position(ConstraintPosition), ConstraintPosition
        )


class TestMovePosition:
    def test_move_particle_to(self):
        source = literal.LocalPosition[Never]("source")
        dest = literal.LocalPosition[Never]("dest")
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_from_empty_raises(self):
        source = literal.LocalPosition[Never]("source")
        dest = literal.LocalPosition[Never]("dest")

        with pytest.raises(literal.NoParticleError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "source"

    def test_move_to_occupied_raises(self):
        source = literal.LocalPosition[Never]("source")
        dest = literal.LocalPosition[Never]("dest")
        source.create_particle()
        dest.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "dest"

    def test_move_with_satisfied_constraints_succeeds(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        source = literal.LocalPosition[Never](
            "position<source>", constraints=(ConstraintPosition,)
        )
        dest = literal.LocalPosition[Never](
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_with_unsatisfied_position_constraint_raises(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        source = literal.LocalPosition[Never]("position<source>")
        dest = literal.LocalPosition[Never](
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert (
            exc_info.value.constraint_name == f"position<{__name__}.ConstraintPosition>"
        )
        assert "position<dest>" in str(exc_info.value)
        assert f"position<{__name__}.ConstraintPosition>" in str(exc_info.value)

    def test_move_with_unsatisfied_action_constraint_raises(self):
        class ConstraintAction(literal.Action):
            pass

        source = literal.LocalPosition[Never]("position<source>")
        dest = literal.LocalPosition[Never](
            "position<dest>", constraints=(ConstraintAction,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == f"action<{__name__}.ConstraintAction>"

    def test_move_checks_every_destination_constraint(self):
        class SatisfiedPosition(literal.GlobalPosition[Never]):
            pass

        class UnsatisfiedPosition(literal.GlobalPosition[Never]):
            pass

        source = literal.LocalPosition[Never](
            "position<source>", constraints=(SatisfiedPosition,)
        )
        dest = literal.LocalPosition[Never](
            "position<dest>", constraints=(SatisfiedPosition, UnsatisfiedPosition)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert (
            exc_info.value.constraint_name
            == f"position<{__name__}.UnsatisfiedPosition>"
        )

    def test_move_constraint_check_does_not_transfer_on_failure(self):
        class ConstraintPosition(literal.GlobalPosition[Never]):
            pass

        source = literal.LocalPosition[Never]("position<source>")
        dest = literal.LocalPosition[Never](
            "position<dest>", constraints=(ConstraintPosition,)
        )
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError):
            source.move_particle_to(dest)

        assert source.has_particle
        assert not dest.has_particle


class TestDestroyParticle:
    def test_destroy_particle(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()

        pos.destroy_particle()

        assert not pos.has_particle

    def test_destroy_from_empty_raises(self):
        pos = literal.LocalPosition[Never]("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.destroy_particle()
        assert exc_info.value.position_name == "test"

    def test_destroy_then_create_succeeds(self):
        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()
        pos.destroy_particle()

        pos.create_particle()

        assert pos.has_particle

    def test_destroy_does_not_destroy_a_child_position(self):
        class ChildPosition(literal.GlobalPosition[Never]):
            pass

        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()
        pos.particle.assign_quality(ChildPosition)
        child_position = pos.particle.get_position(ChildPosition)
        child_position.create_particle()

        pos.destroy_particle()

        assert child_position.has_particle

    def test_destroy_does_not_destroy_action_interface_positions(self):
        class MyAction(literal.Action):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        literal.LocalPosition[Never]("position</iface1>"),
                        literal.LocalPosition[Never]("position</iface2>"),
                    ],
                )

        pos = literal.LocalPosition[Never]("test")
        pos.create_particle()
        pos.particle.assign_quality(MyAction)
        action = pos.particle.get_action(MyAction)
        iface1 = action.get_interface_position("position</iface1>")
        iface1.create_particle()
        iface2 = action.get_interface_position("position</iface2>")
        iface2.create_particle()

        pos.destroy_particle()

        assert iface1.has_particle
        assert iface2.has_particle


class TestValue:
    def test_value(self):
        particle = literal.ValueParticle[float]()
        particle.value = -12.5
        assert particle.value == -12.5

    def test_unset_value_raises(self):
        particle = literal.ValueParticle[float]()
        with pytest.raises(literal.UnsetValueError):
            _ = particle.value

    def test_moved_particle_keeps_value(self):
        source = literal.LocalPosition[int]("position<source>")
        target = literal.LocalPosition[int]("position<target>")
        source.create_particle()
        source.particle.value = 5
        source.move_particle_to(target)
        assert target.particle.value == 5


class TestStart:
    def test_start_fires_entry_constructor(self):
        fired: list[type[literal.Action]] = []

        class Entry(literal.Action):
            @override
            def run(self):
                fired.append(type(self))

        literal.start(Entry)

        assert fired == [Entry]


class TestAction:
    def test_name_from_full_class_path(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        assert action.name == f"action<{__name__}.MyAction>"

    def test_action_has_no_entry_specific_execution_method(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        assert not hasattr(action, "execute")

    def test_run_requires_an_implementation(self):
        class MyEntryPoint(literal.Action):
            pass

        entry_point = MyEntryPoint(literal.Particle())

        with pytest.raises(NotImplementedError):
            entry_point.run()

    def test_get_interface_position(self):
        particle = literal.Particle()
        pos = literal.LocalPosition[Never]("position</iface>")

        class MyAction(literal.Action):
            pass

        action = MyAction(
            particle,
            interface_positions=[pos],
        )

        assert action.get_interface_position("position</iface>") is pos

    def test_get_interface_position_with_value_type(self):
        pos = literal.LocalPosition[float]("position</iface>")

        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle(), interface_positions=[pos])
        typed_pos = action.get_interface_position("position</iface>", float)
        typed_pos.create_particle()
        typed_pos.particle.value = 2.5

        assert typed_pos is pos
        assert pos.particle.value == 2.5


class TestParticleActions:
    def test_assign_action_sets_on_particle(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyAction)

        assert particle.get_action(MyAction).on_particle is particle

    def test_get_action_returns_stored_action(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyAction)

        assert isinstance(particle.get_action(MyAction), MyAction)

    def test_get_action_raises_on_missing_name(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()

        with pytest.raises(KeyError):
            _ = particle.get_action(MyAction)


class TestImpliedQualities:
    def test_position_implied_qualities_default_to_empty(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        assert MyPosition.implied_qualities == ()

    def test_action_implied_qualities_default_to_empty(self):
        class MyAction(literal.Action):
            pass

        assert MyAction.implied_qualities == ()

    def test_implied_quality_attached_before_implying_quality(self):
        class Implied(literal.Action):
            pass

        class Implying(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = literal.LocalPosition[Never]("test", constraints=(Implying,))
        position.create_particle()

        assert list(position.particle._qualities) == [
            Implied,
            Implying,
        ]

    def test_implied_qualities_processed_in_source_order(self):
        class First(literal.Action):
            pass

        class Second(literal.Action):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                First,
                Second,
            )

        position = literal.LocalPosition[Never]("test", constraints=(Implier,))
        position.create_particle()

        assert list(position.particle._qualities) == [
            First,
            Second,
            Implier,
        ]

    def test_transitive_implied_qualities_attached(self):
        class C(literal.Action):
            pass

        class B(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (C,)

        class A(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (B,)

        position = literal.LocalPosition[Never]("test", constraints=(A,))
        position.create_particle()

        assert list(position.particle._qualities) == [
            C,
            B,
            A,
        ]

    def test_diamond_implied_quality_assigned_only_once(self):
        class Shared(literal.Action):
            pass

        class Left(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Right(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Top(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

        position = literal.LocalPosition[Never]("test", constraints=(Top,))
        position.create_particle()

        assert list(position.particle._qualities) == [
            Shared,
            Left,
            Right,
            Top,
        ]

    def test_diamond_implied_action_assigned_only_once(self):
        class Shared(literal.Action):
            pass

        class Left(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Right(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Shared,)

        class Top(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                Left,
                Right,
            )

        particle = literal.Particle()
        particle.assign_quality(Top)

        quality_types = list(particle._qualities)
        assert quality_types == [
            Shared,
            Left,
            Right,
            Top,
        ]

    def test_constraint_also_implied_by_an_earlier_constraint_assigned_once(self):
        class Implied(literal.GlobalPosition[Never]):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = literal.LocalPosition[Never]("test", constraints=(Implier, Implied))
        position.create_particle()

        quality_types = list(position.particle._qualities)
        assert quality_types == [Implied, Implier]

    def test_directly_assigned_quality_implied_by_a_later_constraint_assigned_once(
        self,
    ):
        class Implied(literal.GlobalPosition[Never]):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = literal.LocalPosition[Never]("test", constraints=(Implied, Implier))
        position.create_particle()

        quality_types = list(position.particle._qualities)
        assert quality_types == [Implied, Implier]

    def test_local_position_with_a_duplicate_constraint_raises(self):
        class Implied(literal.GlobalPosition[Never]):
            pass

        class Implier(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        with pytest.raises(literal.DuplicateConstraintError) as exc_info:
            _ = literal.LocalPosition[Never](
                "test", constraints=(Implier, Implied, Implied)
            )
        assert exc_info.value.position_name == f"position<{__name__}.Implied>"

    def test_global_position_with_a_duplicate_constraint_raises(self):
        class Foo(literal.GlobalPosition[Never]):
            pass

        with pytest.raises(literal.DuplicateConstraintError) as exc_info:

            class _Bad(literal.GlobalPosition[Never]):  # pyright: ignore[reportUnusedClass]
                constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Foo, Foo)

        assert exc_info.value.position_name == f"position<{__name__}.Foo>"

    def test_action_processes_its_implied_qualities(self):
        class ImpliedPosition(literal.GlobalPosition[Never]):
            pass

        class ImplyingAction(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedPosition,
            )

        particle = literal.Particle()
        particle.assign_quality(ImplyingAction)

        quality_types = list(particle._qualities)
        assert quality_types == [ImpliedPosition, ImplyingAction]

    def test_position_can_imply_action(self):
        class ImpliedAction(literal.Action):
            pass

        class ImplyingPosition(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedAction,
            )

        particle = literal.Particle()
        particle.assign_quality(ImplyingPosition)

        quality_types = list(particle._qualities)
        assert quality_types == [ImpliedAction, ImplyingPosition]

    def test_assign_position_twice_is_idempotent(self):
        class MyPosition(literal.GlobalPosition[Never]):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyPosition)
        particle.assign_quality(MyPosition)

        assert list(particle._qualities) == [MyPosition]

    def test_assign_action_twice_is_idempotent(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyAction)
        particle.assign_quality(MyAction)

        assert list(particle._qualities) == [MyAction]

    def test_create_particle_propagates_transitive_qualities(self):
        class Inner(literal.GlobalPosition[Never]):
            pass

        class Outer(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Inner,)

        class Container(literal.GlobalPosition[Never]):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Outer,)

        container = Container(literal.Particle())
        container.create_particle()

        quality_types = list(container.particle._qualities)
        assert quality_types == [Inner, Outer]

    def test_move_succeeds_via_transitive_implied_quality(self):
        class Implied(literal.GlobalPosition[Never]):
            pass

        class Implying(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        source = literal.LocalPosition[Never]("source", constraints=(Implying,))
        dest = literal.LocalPosition[Never]("dest", constraints=(Implied,))
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_assigned_qualities_recorded_in_assignment_order(self):
        class A(literal.GlobalPosition[Never]):
            pass

        class B(literal.GlobalPosition[Never]):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (A,)

        particle = literal.Particle()
        particle.assign_quality(B)

        quality_types = list(particle._qualities)
        assert quality_types == [A, B]

    def test_assign_action_satisfies_its_quality_type(self):
        class MyAction(literal.Action):
            pass

        particle = literal.Particle()
        particle.assign_quality(MyAction)

        assert particle.has_quality_type(MyAction)


class _Worker(literal.Action):
    @override
    def run(self):
        literal.record_operation("worker.create(item)")
        literal.record_operation("worker.destroy(item)")


class _Entry(literal.Action):
    @override
    def run(self):
        literal.record_operation("entry.create(run)")
        _Worker(self.on_particle).run()
        _Worker(self.on_particle).run()
        literal.record_operation("entry.destroy(run)")


def test_trace_records_direct_calls_and_repeated_operations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    trace_file = tmp_path / "trace.txt"
    monkeypatch.setenv("DEFINE_OPERATION_TRACE_FILE", str(trace_file))
    literal.start(_Entry, trace_operations=True)
    expected = "entry.create(run)\nworker.create(item)\nworker.destroy(item)\nworker.create(item)\nworker.destroy(item)\nentry.destroy(run)\n"
    assert trace_file.read_text() == expected
    literal.start(_Entry, trace_operations=True)
    assert trace_file.read_text() == expected


def test_disabled_tracing_does_not_write_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    trace_file = tmp_path / "trace.txt"
    monkeypatch.setenv("DEFINE_OPERATION_TRACE_FILE", str(trace_file))
    literal.start(_Entry)
    assert not trace_file.exists()


def test_tracing_without_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("DEFINE_OPERATION_TRACE_FILE", raising=False)
    monkeypatch.chdir(tmp_path)
    literal.start(_Entry, trace_operations=True)
    assert list(tmp_path.iterdir()) == []


def test_failed_action_clears_tracing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class Failing(literal.Action):
        @override
        def run(self):
            literal.record_operation("failing.create(item)")
            raise ValueError("failed action")

    trace_file = tmp_path / "trace.txt"
    monkeypatch.setenv("DEFINE_OPERATION_TRACE_FILE", str(trace_file))
    with pytest.raises(ValueError, match="failed action"):
        literal.start(Failing, trace_operations=True)
    literal.start(_Worker, trace_operations=True)
    assert trace_file.read_text() == "worker.create(item)\nworker.destroy(item)\n"
