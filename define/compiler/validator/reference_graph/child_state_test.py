from __future__ import annotations

import random

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    child_state,
    position_occupancy,
)


def test_independent_callers():
    location = ast.start_of_file_location()
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, location
    )
    original_values = {
        ("parent",): occupied,
        ("parent", "empty"): position_occupancy.EMPTY_OCCUPANCY,
        ("parent", "error"): position_occupancy.ERROR_OCCUPANCY,
    }
    original = child_state.FlatChildState(original_values)
    first = original.with_caller({("first",): occupied})
    second = original.with_caller({("second",): position_occupancy.ERROR_OCCUPANCY})
    for position, occupancy in original_values.items():
        assert original.get(position) is occupancy
        assert first.get(position) is occupancy
        assert second.get(position) is occupancy
    assert original.get(("first",)) is None
    assert original.get(("second",)) is None
    assert first.get(("first",)) is occupied
    assert first.get(("second",)) is None
    assert second.get(("first",)) is None
    assert second.get(("second",)) is position_occupancy.ERROR_OCCUPANCY
    assert first.get(("unknown",)) is None


def test_repeated_compaction_preserves_earlier_states():
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, ast.start_of_file_location()
    )
    occupancies = (
        occupied,
        position_occupancy.EMPTY_OCCUPANCY,
        position_occupancy.ERROR_OCCUPANCY,
    )
    snapshots: list[child_state.ChildState] = []
    oracles: list[position_occupancy.ChildOccupancyMap] = []
    snapshot: child_state.ChildState = child_state.FlatChildState({})
    expected: position_occupancy.ChildOccupancyMap = {}
    first = 0
    for count in [16, 17, 32, 33, 64]:
        caller: position_occupancy.ChildOccupancyMap = {}
        for index in range(first, count):
            caller[(str(index),)] = occupancies[index % len(occupancies)]
        expected = caller | expected
        snapshot = snapshot.with_caller(caller)
        snapshots.append(snapshot)
        oracles.append(expected)
        first = count
    assert isinstance(snapshots[0], child_state.FlatChildState)
    assert isinstance(snapshots[1], child_state.ExtendedChildState)
    assert isinstance(snapshots[2], child_state.FlatChildState)
    assert isinstance(snapshots[3], child_state.ExtendedChildState)
    assert isinstance(snapshots[4], child_state.FlatChildState)
    for actual, oracle in zip(snapshots, oracles, strict=True):
        for index in range(65):
            position = (str(index),)
            assert actual.get(position) is oracle.get(position)


def test_large_branching_callers_preserve_retained_knowledge():
    randomizer = random.Random(74921)  # noqa: S311 - Reproducible caller topology.
    initial: position_occupancy.ChildOccupancyMap = {}
    for index in range(1_024):
        initial[(str(index),)] = position_occupancy.EMPTY_OCCUPANCY
    histories: list[child_state.ChildState] = [child_state.FlatChildState(initial)]
    oracles = [initial]
    for index in range(80):
        callee = randomizer.randrange(len(histories))
        knowledge: position_occupancy.ChildOccupancyMap = {}
        for key in range(1_024 + index * 300, 1_324 + index * 300):
            knowledge[(str(key),)] = position_occupancy.ERROR_OCCUPANCY
        oracles.append(knowledge | oracles[callee])
        histories.append(histories[callee].with_caller(knowledge))
    positions = [(str(index),) for index in range(1_024 + 80 * 300 + 1)]
    for snapshot, expected in zip(histories, oracles, strict=True):
        for position in positions:
            assert snapshot.get(position) is expected.get(position)
