# pyright: reportUnusedCallResult=false
# pyright: reportPrivateUsage=false
from typing import override

import pytest

from define.runtime import literal


class TestDimensionPoint:
    def test_assign_quality_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.Position):
            @override
            def after_assigned(self):
                triggered.append(self.name)

        dp = literal.DimensionPoint()
        pos = TrackingPosition("test_pos")
        dp.assign_quality(pos)

        assert triggered == ["test_pos"]

    def test_assign_quality_stores_quality(self):
        dp = literal.DimensionPoint()
        pos = literal.Position("quality_pos")
        dp.assign_quality(pos)

        assert dp._qualities["quality_pos"] is pos


class TestPosition:
    def test_create_dimension_point(self):
        pos = literal.Position("test")
        dp = pos.create_dimension_point()

        assert pos.has_dimension_point
        assert isinstance(dp, literal.DimensionPoint)

    def test_create_dimension_point_raises_on_duplicate(self):
        pos = literal.Position("test")
        pos.create_dimension_point()

        with pytest.raises(literal.DimensionPointExistsError) as exc_info:
            pos.create_dimension_point()
        assert exc_info.value.position_name == "test"

    def test_has_dimension_point_initially_false(self):
        pos = literal.Position("test")

        assert not pos.has_dimension_point

    def test_move_dimension_point_to(self):
        source = literal.Position("source")
        dest = literal.Position("dest")
        source.create_dimension_point()

        source.move_dimension_point_to(dest)

        assert not source.has_dimension_point
        assert dest.has_dimension_point

    def test_move_from_empty_raises(self):
        source = literal.Position("source")
        dest = literal.Position("dest")

        with pytest.raises(literal.NoDimensionPointError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "source"

    def test_move_to_occupied_raises(self):
        source = literal.Position("source")
        dest = literal.Position("dest")
        source.create_dimension_point()
        dest.create_dimension_point()

        with pytest.raises(literal.DimensionPointExistsError) as exc_info:
            source.move_dimension_point_to(dest)
        assert exc_info.value.position_name == "dest"

    def test_name_property(self):
        pos = literal.Position("my_pos")

        assert pos.name == "my_pos"

    def test_after_assigned_default_does_nothing(self):
        pos = literal.Position("test")

        pos.after_assigned()

    def test_constraints_stored(self):
        pos = literal.Position("test", constraints=["action<x>"])

        assert pos._constraints == ["action<x>"]

    def test_constraints_defaults_to_empty(self):
        pos = literal.Position("test")

        assert pos._constraints == []


class TestStart:
    def test_start_triggers_after_assigned(self):
        triggered: list[str] = []

        class TrackingPosition(literal.Position):
            @override
            def after_assigned(self):
                triggered.append(self.name)

        entry = TrackingPosition("entry")
        literal.start(entry)

        assert triggered == ["entry"]
