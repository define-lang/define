# pyright: reportPrivateUsage=false
from pathlib import Path
from typing import ClassVar, override

import pytest

from define.runtime import literal


def _local_position(
    name: str,
    constraints: tuple[type[literal.Quality], ...] = (),
    *,
    scheduler: literal.Scheduler | None = None,
) -> literal.LocalPosition:
    if scheduler is None:
        scheduler = literal.Scheduler()
    return literal.LocalPosition(name, constraints, scheduler=scheduler)


class TestParticle:
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

        assert pos.name == f"position<{__name__}.MyPosition>"

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
        assert exc_info.value.position_name == f"position<{__name__}.MyPosition>"

    def test_constraints_default_to_empty(self):
        class MyPosition(literal.GlobalPosition):
            pass

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert pos.particle.quality_types == frozenset()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        class MyPosition(literal.GlobalPosition):
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

        class MyPosition(literal.GlobalPosition):
            constraints: ClassVar[tuple[type[literal.Quality], ...]] = (
                ConstraintAction,
            )

        pos = MyPosition(literal.Particle())
        pos.create_particle()

        assert isinstance(pos.particle.get_action(ConstraintAction), ConstraintAction)


class TestLocalPosition:
    def test_name_from_init(self):
        pos = _local_position("my_pos")

        assert pos.name == "my_pos"

    def test_create_particle(self):
        pos = _local_position("test")
        pos.create_particle()

        assert pos.has_particle

    def test_create_particle_raises_on_duplicate(self):
        pos = _local_position("test")
        pos.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            pos.create_particle()
        assert exc_info.value.position_name == "test"
        assert "test" in str(exc_info.value)

    def test_has_particle_initially_false(self):
        pos = _local_position("test")

        assert not pos.has_particle

    def test_particle_returns_point(self):
        pos = _local_position("test")
        pos.create_particle()
        particle = pos.particle

        assert pos.particle is particle

    def test_particle_raises_when_none(self):
        pos = _local_position("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.particle  # noqa: B018
        assert "test" in str(exc_info.value)

    def test_constraints_stored(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        pos = _local_position("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        assert pos.particle.quality_types == frozenset((ConstraintPosition,))

    def test_constraints_defaults_to_empty(self):
        pos = _local_position("test")
        pos.create_particle()

        assert pos.particle.quality_types == frozenset()

    def test_create_particle_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        pos = _local_position("test", constraints=(ConstraintPosition,))
        pos.create_particle()

        assert isinstance(
            pos.particle.get_position(ConstraintPosition), ConstraintPosition
        )


class TestMovePosition:
    def test_move_particle_to(self):
        source = _local_position("source")
        dest = _local_position("dest")
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_from_empty_raises(self):
        source = _local_position("source")
        dest = _local_position("dest")

        with pytest.raises(literal.NoParticleError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "source"

    def test_move_to_occupied_raises(self):
        source = _local_position("source")
        dest = _local_position("dest")
        source.create_particle()
        dest.create_particle()

        with pytest.raises(literal.ParticleExistsError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "dest"

    def test_move_with_satisfied_constraints_succeeds(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        source = _local_position("position<source>", constraints=(ConstraintPosition,))
        dest = _local_position("position<dest>", constraints=(ConstraintPosition,))
        source.create_particle()

        source.move_particle_to(dest)

        assert not source.has_particle
        assert dest.has_particle

    def test_move_with_unsatisfied_position_constraint_raises(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        source = _local_position("position<source>")
        dest = _local_position("position<dest>", constraints=(ConstraintPosition,))
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

        source = _local_position("position<source>")
        dest = _local_position("position<dest>", constraints=(ConstraintAction,))
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError) as exc_info:
            source.move_particle_to(dest)
        assert exc_info.value.position_name == "position<dest>"
        assert exc_info.value.constraint_name == f"action<{__name__}.ConstraintAction>"

    def test_move_constraint_check_does_not_transfer_on_failure(self):
        class ConstraintPosition(literal.GlobalPosition):
            pass

        source = _local_position("position<source>")
        dest = _local_position("position<dest>", constraints=(ConstraintPosition,))
        source.create_particle()

        with pytest.raises(literal.UnsatisfiedConstraintError):
            source.move_particle_to(dest)

        assert source.has_particle
        assert not dest.has_particle


class TestDestroyParticle:
    def test_destroy_particle(self):
        pos = _local_position("test")
        pos.create_particle()

        pos.destroy_particle()

        assert not pos.has_particle

    def test_destroy_from_empty_raises(self):
        pos = _local_position("test")

        with pytest.raises(literal.NoParticleError) as exc_info:
            pos.destroy_particle()
        assert exc_info.value.position_name == "test"

    def test_destroy_then_create_succeeds(self):
        pos = _local_position("test")
        pos.create_particle()
        pos.destroy_particle()

        pos.create_particle()

        assert pos.has_particle

    def test_destroy_does_not_destroy_a_child_position(self):
        class ChildPosition(literal.GlobalPosition):
            pass

        pos = _local_position("test")
        pos.create_particle()
        pos.particle.assign_position(ChildPosition)
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
                        _local_position(
                            "position</iface1>", scheduler=on_particle.scheduler
                        ),
                        _local_position(
                            "position</iface2>", scheduler=on_particle.scheduler
                        ),
                    ],
                )

        pos = _local_position("test")
        pos.create_particle()
        pos.particle.assign_action(MyAction)
        action = pos.particle.get_action(MyAction)
        iface1 = action.get_interface_position("position</iface1>")
        iface1.create_particle()
        iface2 = action.get_interface_position("position</iface2>")
        iface2.create_particle()

        pos.destroy_particle()

        assert iface1.has_particle
        assert iface2.has_particle


class TestStart:
    def test_start_fires_entry_constructor(self):
        fired: list[type[literal.Action]] = []

        class Entry(literal.EntryPoint):
            @override
            def execute(self, scheduler: literal.Scheduler):
                fired.append(type(self))

        literal.start(Entry)

        assert fired == [Entry]

    def test_reports_occupied_positions_when_env_var_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        class Entry(literal.EntryPoint):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        _local_position(
                            "position<output>", scheduler=on_particle.scheduler
                        )
                    ],
                )

            @override
            def execute(self, scheduler: literal.Scheduler):
                self.get_interface_position("position<output>").create_particle()

        occupied_positions_file = tmp_path / "occupied_positions.txt"
        monkeypatch.setenv(
            "DEFINE_REPORT_OCCUPIED_POSITIONS", str(occupied_positions_file)
        )
        literal.start(Entry)

        assert (
            occupied_positions_file.read_text()
            == f"action<{__name__}.Entry>::position<output>\n"
        )

    def test_no_report_when_env_var_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        class Entry(literal.EntryPoint):
            @override
            def execute(self, scheduler: literal.Scheduler):
                pass

        occupied_positions_file = tmp_path / "occupied_positions.txt"
        monkeypatch.delenv("DEFINE_REPORT_OCCUPIED_POSITIONS", raising=False)
        literal.start(Entry)

        assert not occupied_positions_file.exists()


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

        assert particle.occupied_position_names() == [f"position<{__name__}.Entry>"]

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
            f"position<{__name__}.Entry>",
            f"position<{__name__}.Entry>::position<{__name__}.Inner>",
        ]

    def test_reports_occupied_interface_position(self):
        class MyAction(literal.Action):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        _local_position(
                            "position<trigger_pos>", scheduler=on_particle.scheduler
                        ),
                    ],
                )

        particle = literal.Particle()
        particle.assign_action(MyAction)
        particle.get_action(MyAction).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()

        assert particle.occupied_position_names() == [
            f"action<{__name__}.MyAction>::position<trigger_pos>"
        ]

    def test_traverses_qualities_in_assignment_order(self):
        class MyAction(literal.Action):
            def __init__(self, on_particle: literal.Particle):
                super().__init__(
                    on_particle,
                    interface_positions=[
                        _local_position(
                            "position<trigger_pos>", scheduler=on_particle.scheduler
                        ),
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
            f"action<{__name__}.MyAction>::position<trigger_pos>",
            f"position<{__name__}.Later>",
        ]


class TestAction:
    def test_name_from_full_class_path(self):
        class MyAction(literal.Action):
            pass

        action = MyAction(literal.Particle())

        assert action.name == f"action<{__name__}.MyAction>"

    def test_entry_point_execute_requires_an_implementation(self):
        class MyEntryPoint(literal.EntryPoint):
            pass

        entry_point = MyEntryPoint(literal.Particle())

        with pytest.raises(NotImplementedError):
            entry_point.execute(literal.Scheduler())

    def test_get_interface_position(self):
        particle = literal.Particle()
        pos = _local_position("position</iface>", scheduler=particle.scheduler)

        class MyAction(literal.Action):
            pass

        action = MyAction(
            particle,
            interface_positions=[pos],
        )

        assert action.get_interface_position("position</iface>") is pos


class TestParticleActions:
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
        class Implied(literal.Action):
            pass

        class Implying(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        position = _local_position("test", constraints=(Implying,))
        position.create_particle()

        assert [type(quality) for quality in position.particle._assigned_qualities] == [
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

        position = _local_position("test", constraints=(Implier,))
        position.create_particle()

        assert [type(quality) for quality in position.particle._assigned_qualities] == [
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

        position = _local_position("test", constraints=(A,))
        position.create_particle()

        assert [type(quality) for quality in position.particle._assigned_qualities] == [
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

        position = _local_position("test", constraints=(Top,))
        position.create_particle()

        assert [type(quality) for quality in position.particle._assigned_qualities] == [
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

        position = _local_position("test", constraints=(Implier, Implied))
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

        position = _local_position("test", constraints=(Implied, Implier))
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
            _ = _local_position("test", constraints=(Implier, Implied, Implied))
        assert exc_info.value.position_name == f"position<{__name__}.Implied>"

    def test_global_position_with_a_duplicate_constraint_raises(self):
        class Foo(literal.GlobalPosition):
            pass

        with pytest.raises(literal.DuplicateConstraintError) as exc_info:

            class _Bad(literal.GlobalPosition):  # pyright: ignore[reportUnusedClass]
                constraints: ClassVar[tuple[type[literal.Quality], ...]] = (Foo, Foo)

        assert exc_info.value.position_name == f"position<{__name__}.Foo>"

    def test_action_processes_its_implied_qualities(self):
        class ImpliedPosition(literal.GlobalPosition):
            pass

        class ImplyingAction(literal.Action):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedPosition,
            )

        particle = literal.Particle()
        particle.assign_action(ImplyingAction)

        assert particle.quality_types == frozenset((ImpliedPosition, ImplyingAction))

    def test_position_can_imply_action(self):
        class ImpliedAction(literal.Action):
            pass

        class ImplyingPosition(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (
                ImpliedAction,
            )

        particle = literal.Particle()
        particle.assign_position(ImplyingPosition)

        assert particle.quality_types == frozenset((ImpliedAction, ImplyingPosition))

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

        assert container.particle.quality_types == frozenset((Outer, Inner))

    def test_move_succeeds_via_transitive_implied_quality(self):
        class Implied(literal.GlobalPosition):
            pass

        class Implying(literal.GlobalPosition):
            implied_qualities: ClassVar[tuple[type[literal.Quality], ...]] = (Implied,)

        source = _local_position("source", constraints=(Implying,))
        dest = _local_position("dest", constraints=(Implied,))
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
