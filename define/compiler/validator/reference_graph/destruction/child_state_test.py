from __future__ import annotations

import random

from define.compiler import ast, chained_name
from define.compiler.validator.reference_graph import (
    action_contract,
    position_occupancy,
)
from define.compiler.validator.reference_graph.destruction import child_state
from define.compiler.validator.reference_graph.particles import particle_info


def _chain(*names: str) -> chained_name.ChainedNameTuple:
    return chained_name.ChainedNameTuple(names)


def test_independent_callers():
    location = ast.start_of_file_location()
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, location
    )
    original_values = {
        _chain("parent"): occupied,
        _chain("parent", "empty"): position_occupancy.EMPTY_OCCUPANCY,
        _chain("parent", "error"): position_occupancy.ERROR_OCCUPANCY,
    }
    original = child_state.FlatChildStateStore(original_values)
    first = original.with_caller({_chain("first"): occupied})
    second = original.with_caller(
        {_chain("second"): position_occupancy.ERROR_OCCUPANCY}
    )
    for position, occupancy in original_values.items():
        assert original.get(position) is occupancy
        assert first.get(position) is occupancy
        assert second.get(position) is occupancy
    assert original.get(_chain("first")) is None
    assert original.get(_chain("second")) is None
    assert first.get(_chain("first")) is occupied
    assert first.get(_chain("second")) is None
    assert second.get(_chain("first")) is None
    assert second.get(_chain("second")) is position_occupancy.ERROR_OCCUPANCY
    assert first.get(_chain("unknown")) is None


def test_repeated_compaction_preserves_earlier_states():
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, ast.start_of_file_location()
    )
    occupancies = (
        occupied,
        position_occupancy.EMPTY_OCCUPANCY,
        position_occupancy.ERROR_OCCUPANCY,
    )
    snapshots: list[child_state.ChildStateStore[position_occupancy.ChildOccupancy]] = []
    oracles: list[child_state.ChildOccupancyMap] = []
    snapshot: child_state.ChildStateStore[position_occupancy.ChildOccupancy] = (
        child_state.FlatChildStateStore({})
    )
    expected: child_state.ChildOccupancyMap = {}
    first = 0
    for count in [16, 17, 32, 33, 64]:
        caller: child_state.ChildOccupancyMap = {}
        for index in range(first, count):
            caller[_chain(str(index))] = occupancies[index % len(occupancies)]
        expected = caller | expected
        snapshot = snapshot.with_caller(caller)
        snapshots.append(snapshot)
        oracles.append(expected)
        first = count
    assert isinstance(snapshots[0], child_state.FlatChildStateStore)
    assert isinstance(snapshots[1], child_state.ExtendedChildStateStore)
    assert isinstance(snapshots[2], child_state.FlatChildStateStore)
    assert isinstance(snapshots[3], child_state.ExtendedChildStateStore)
    assert isinstance(snapshots[4], child_state.FlatChildStateStore)
    for actual, oracle in zip(snapshots, oracles, strict=True):
        for index in range(65):
            position = _chain(str(index))
            assert actual.get(position) is oracle.get(position)


def test_large_branching_callers_preserve_retained_knowledge():
    randomizer = random.Random(74921)  # noqa: S311 - Reproducible caller topology.
    initial: child_state.ChildOccupancyMap = {}
    for index in range(1_024):
        initial[_chain(str(index))] = position_occupancy.EMPTY_OCCUPANCY
    histories: list[child_state.ChildStateStore[position_occupancy.ChildOccupancy]] = [
        child_state.FlatChildStateStore(initial)
    ]
    oracles = [initial]
    for index in range(80):
        callee = randomizer.randrange(len(histories))
        knowledge: child_state.ChildOccupancyMap = {}
        for key in range(1_024 + index * 300, 1_324 + index * 300):
            knowledge[_chain(str(key))] = position_occupancy.ERROR_OCCUPANCY
        oracles.append(knowledge | oracles[callee])
        histories.append(histories[callee].with_caller(knowledge))
    positions = [_chain(str(index)) for index in range(1_024 + 80 * 300 + 1)]
    for snapshot, expected in zip(histories, oracles, strict=True):
        for position in positions:
            assert snapshot.get(position) is expected.get(position)


def test_resolve_value_without_changing_occupancy():
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, ast.start_of_file_location()
    )
    original = action_contract.ChildState(
        child_state.FlatChildStateStore({_chain("value"): occupied}),
        child_state.FlatChildStateStore({}),
        {},
    )
    first = original.with_caller(
        {}, {_chain("value"): particle_info.ParticleValueState.SET}, {}
    )
    second = original.with_caller(
        {}, {_chain("value"): particle_info.ParticleValueState.UNSET}, {}
    )
    assert original.with_caller({}, {}, {}) is original
    assert first.occupancy is original.occupancy
    assert second.occupancy is original.occupancy
    assert original.occupancy.get(_chain("value")) is occupied
    assert original.values.get(_chain("value")) is None
    assert first.values.get(_chain("value")) == particle_info.ParticleValueState.SET
    assert second.values.get(_chain("value")) == particle_info.ParticleValueState.UNSET
    conflicting = first.with_caller(
        {}, {_chain("value"): particle_info.ParticleValueState.UNSET}, {}
    )
    assert (
        conflicting.values.get(_chain("value")) == particle_info.ParticleValueState.SET
    )


def test_value_and_occupancy_stores_compact_independently():
    occupied = position_occupancy.ChildOccupancy(
        position_occupancy.PositionOccupancyState.OCCUPIED, ast.start_of_file_location()
    )
    occupancies = {_chain(str(index)): occupied for index in range(32)}
    values = {
        _chain(str(index)): particle_info.ParticleValueState.SET for index in range(16)
    }
    original = action_contract.ChildState(
        child_state.FlatChildStateStore(occupancies),
        child_state.FlatChildStateStore(values),
        {},
    )
    first = original.with_caller(
        {}, {_chain("16"): particle_info.ParticleValueState.UNSET}, {}
    )
    second = first.with_caller(
        {}, {_chain("17"): particle_info.ParticleValueState.SET}, {}
    )
    assert isinstance(second.values, child_state.ExtendedChildStateStore)
    assert second.occupancy is original.occupancy
    additions = {
        _chain(str(index)): particle_info.ParticleValueState.UNSET
        for index in range(18, 32)
    }
    final = second.with_caller({}, additions, {})
    assert isinstance(final.values, child_state.FlatChildStateStore)
    assert final.occupancy is original.occupancy
    assert original.values.get(_chain("16")) is None
    assert first.values.get(_chain("17")) is None
    for index in range(32):
        assert final.occupancy.get(_chain(str(index))) is occupied
        expected = (
            particle_info.ParticleValueState.SET
            if index < 16 or index == 17
            else particle_info.ParticleValueState.UNSET
        )
        assert final.values.get(_chain(str(index))) == expected
    expanded = final.with_caller({_chain("32"): occupied}, {}, {})
    assert expanded.values is final.values
    assert isinstance(expanded.occupancy, child_state.ExtendedChildStateStore)
    assert expanded.occupancy.get(_chain("32")) is occupied
    assert final.occupancy.get(_chain("32")) is None
    resolved = expanded.with_caller(
        {}, {_chain("32"): particle_info.ParticleValueState.SET}, {}
    )
    assert resolved.occupancy is expanded.occupancy
    assert resolved.values.get(_chain("32")) == particle_info.ParticleValueState.SET
    assert expanded.values.get(_chain("32")) is None
