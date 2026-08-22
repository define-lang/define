"""Unit tests for isolated particle-tracker state invariants.

Valid-source integration tests cover particle-statement diagnostics, requirement
inference, guarantee generation and application, and action triggering. Tests
here directly construct a tracker only when doing so isolates its state API:
particle metadata, error-state ancestry, child-name relocation and pruning,
action-parent state, and snapshots. Every exercised transition is also reachable
through the valid-source integration suite.
"""

# pyright: reportUnusedCallResult=false

from __future__ import annotations

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    particle_tracker,
    quality_assignment,
)

_LOC = ast.start_of_file_location()
_LOC2 = ast.SourceLocation(line=2, column=1, end_line=2, end_column=1)
_NO_QUALITIES = quality_assignment.EMPTY_QUALITY_ASSIGNMENTS

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _make_local_name(
    name: str, location: ast.SourceLocation = _LOC
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.LocalNameContent(name=name, location=location),
        location=location,
    )


def _make_global_name(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOC),
            location=_LOC,
        ),
        enclosing_fqun=_FQUN,
        location=_LOC,
    )


def _make_action_name(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOC),
            location=_LOC,
        ),
        enclosing_fqun=_FQUN,
        location=_LOC,
    )


def _make_position(
    *names: ast.TypedNameReference,
    location: ast.SourceLocation = _LOC,
) -> ast.PositionReference:
    return ast.PositionReference(typed_names=names, location=location)


def _quality_assignments(
    *qualities: ast.GlobalTypedNameReference,
) -> quality_assignment.QualityAssignments:
    return quality_assignment.QualityAssignments.expand_implications(
        qualities, lambda _: ()
    )


def test_create_records_particle_metadata():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    position = _make_position(_make_local_name("item"))
    qualities = _quality_assignments(_make_global_name("/x"))

    assert tracker.is_occupied(position) is False

    tracker.create(position, qualities)

    particle = tracker.get_occupant(position)
    assert particle.last_position is position
    assert particle.qualities is qualities
    assert particle.origin_position is position
    assert particle.from_caller is False


def test_create_from_caller_records_contracted_origin():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    position = _make_position(_make_local_name("local"))
    contracted_position = _make_position(_make_local_name("interface"))

    tracker.create(position, _NO_QUALITIES, from_caller=contracted_position)

    particle = tracker.get_occupant(position)
    assert particle.origin_position is contracted_position
    assert particle.from_caller is True


def test_mark_empty_records_touched_state_and_allows_create():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    position = _make_position(_make_local_name("item"))

    assert tracker.has_been_touched(position) is False

    tracker.mark_empty(position)

    assert tracker.has_been_touched(position) is True
    assert tracker.is_occupied(position) is False
    assert tracker.get_emptied_by(position) is position

    tracker.create(position, _NO_QUALITIES)

    assert tracker.is_occupied(position) is True
    assert tracker.get_emptied_by(position) is None


def test_error_state_applies_to_child_names_but_not_siblings():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    parent = _make_position(_make_local_name("parent"))
    child = _make_position(_make_local_name("parent"), _make_global_name("/child"))
    sibling = _make_position(_make_local_name("sibling"))
    tracker.create(parent, _NO_QUALITIES)

    tracker.mark_error(parent)

    assert tracker.has_error_state(parent) is True
    assert tracker.has_error_state(child) is True
    assert tracker.has_error_state(sibling) is False
    assert tracker.get_occupancy_info(parent) == particle_tracker.OccupancyInfo(
        has_error=True, occupant=None
    )


def test_occupancy_info_returns_the_particle_without_error():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    position = _make_position(_make_local_name("item"))
    tracker.create(position, _NO_QUALITIES)

    particle = tracker.get_occupant(position)

    assert tracker.get_occupancy_info(position) == particle_tracker.OccupancyInfo(
        has_error=False, occupant=particle
    )


def test_move_relocates_particle_state_and_child_names():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    source = _make_position(_make_local_name("source"))
    source_child = _make_position(
        _make_local_name("source"), _make_global_name("/child")
    )
    target = _make_position(_make_local_name("target", location=_LOC2), location=_LOC2)
    target_child = _make_position(
        _make_local_name("target"), _make_global_name("/child")
    )
    qualities = _quality_assignments(_make_global_name("/x"))
    child_qualities = _quality_assignments(_make_global_name("/y"))
    tracker.create(source, qualities)
    tracker.create(source_child, child_qualities)

    tracker.move(source, target)

    assert tracker.is_occupied(source) is False
    assert tracker.get_emptied_by(source) is source
    particle = tracker.get_occupant(target)
    assert particle.last_position is target
    assert particle.qualities is qualities
    assert particle.origin_position is source
    assert tracker.is_occupied(source_child) is False
    assert tracker.get_occupant(target_child).qualities is child_qualities


def test_action_parent_state_is_created_for_an_interface_position():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    parent = _make_position(_make_local_name("parent"))
    interface_position = _make_position(
        _make_local_name("parent"),
        _make_action_name("/act"),
        _make_local_name("item"),
    )
    tracker.create(parent, _NO_QUALITIES)

    tracker.create(interface_position, _NO_QUALITIES)

    assert tracker.is_occupied(parent) is True
    assert tracker.is_occupied(interface_position) is True


def test_destroy_prunes_child_state_and_records_empty_position():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    parent = _make_position(_make_local_name("parent"))
    child = _make_position(_make_local_name("parent"), _make_global_name("/child"))
    error_child = _make_position(
        _make_local_name("parent"), _make_global_name("/error")
    )
    tracker.create(parent, _NO_QUALITIES)
    tracker.create(child, _NO_QUALITIES)
    tracker.mark_error(error_child)

    tracker.destroy(parent)

    assert tracker.is_occupied(parent) is False
    assert tracker.get_emptied_by(parent) is parent
    assert tracker.is_occupied(child) is False
    assert tracker.has_error_state(error_child) is False


def test_snapshot_child_state_captures_occupancy_and_is_decoupled():
    tracker = particle_tracker.ParticleTracker(_make_action_name("/test"))
    parent = _make_position(_make_local_name("parent"))
    occupied = _make_position(_make_local_name("parent"), _make_local_name("occupied"))
    empty = _make_position(_make_local_name("parent"), _make_local_name("empty"))
    error = _make_position(_make_local_name("parent"), _make_local_name("error"))
    tracker.create(parent, _NO_QUALITIES)
    tracker.create(occupied, _NO_QUALITIES)
    tracker.mark_empty(empty)
    tracker.mark_error(error)

    parent_key_length = len(parent.canonical_chained_name_tuple)
    occupied_key = occupied.canonical_chained_name_tuple[parent_key_length:]
    empty_key = empty.canonical_chained_name_tuple[parent_key_length:]
    error_key = error.canonical_chained_name_tuple[parent_key_length:]
    snapshot = tracker.snapshot_child_state(parent)

    tracker.destroy(parent)

    assert snapshot == {
        occupied_key: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED,
            filled_at=occupied.location,
        ),
        empty_key: action_contract.EMPTY_OCCUPANCY,
        error_key: action_contract.ERROR_OCCUPANCY,
    }
