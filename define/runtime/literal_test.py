# pyright: reportPrivateUsage=false
from typing import ClassVar, override

import pytest

from define.runtime import literal


class TestDimensionPoint:
    def test_assign_quality_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.LocalPosition):
            @override
            def after_assigned(self):
                triggered.append(self.name)

        dp = literal.DimensionPoint()
        pos = TrackingPosition("test_pos")
        dp.assign_quality(pos)

        assert triggered == ["test_pos"]

    def test_assign_quality_stores_quality(self):
        dp = literal.DimensionPoint()
        pos = literal.LocalPosition("quality_pos")
        dp.assign_quality(pos)

        assert dp._qualities["quality_pos"] is pos

    def test_get_position_returns_stored_quality(self):
        dp = literal.DimensionPoint()
        pos = literal.LocalPosition("quality_pos")
        dp.assign_quality(pos)

        assert dp.get_position("quality_pos") is pos

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

        assert pos._get_constraints() == []

    def test_create_dimension_point_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<constraint>"

        class MyPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<test>"
            constraints: ClassVar[list[type[literal.GlobalPosition]]] = [
                ConstraintPosition,
            ]

        pos = MyPosition()
        pos.create_dimension_point()

        assert pos._dimension_point is not None
        assert "position<constraint>" in pos._dimension_point._qualities

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

        pos = literal.LocalPosition("test", constraints=[ConstraintPosition])

        assert pos._get_constraints() == [ConstraintPosition]

    def test_constraints_defaults_to_empty(self):
        pos = literal.LocalPosition("test")

        assert pos._get_constraints() == []

    def test_create_dimension_point_assigns_constraint_qualities(self):
        class ConstraintPosition(literal.GlobalPosition):
            _typed_name: ClassVar[str] = "position<constraint>"

        pos = literal.LocalPosition("test", constraints=[ConstraintPosition])
        pos.create_dimension_point()

        assert pos._dimension_point is not None
        assert "position<constraint>" in pos._dimension_point._qualities


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
