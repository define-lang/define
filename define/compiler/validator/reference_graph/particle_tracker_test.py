# pyright: reportUnusedCallResult=false

# TODO: Evaluate how much this unit suite catches beyond the reference-graph
# integration tests. Keep cases that isolate meaningful ParticleTracker
# invariants, and remove cases whose maintenance cost only duplicates integration
# coverage.

import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
    particle_tracker,
    quality_assignment,
)

_LOC = ast.start_of_file_location()

_NO_QUALITIES = quality_assignment.EMPTY_QUALITY_ASSIGNMENTS
_LOC2 = ast.SourceLocation(line=2, column=1, end_line=2, end_column=1)
_POS2_REF = ast.PositionReference(
    typed_names=(
        ast.LocalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.LocalNameContent(name="dummy", location=_LOC2),
            location=_LOC2,
        ),
    ),
    location=_LOC2,
)


_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _make_local_ref(
    name: str, location: ast.SourceLocation = _LOC
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.LocalNameContent(name=name, location=location),
        location=location,
    )


_DUMMY_ACTION = ast.ActionDefinition(
    name=ast.DefinitionGlobalNameContent(
        fqun=_FQUN,
        path=ast.GlobalPathName(name="/dummy", location=_LOC),
        location=_LOC,
    ),
    location=_LOC,
    quality_implications=(),
    interface_positions=(),
    trigger_conditions=ast.TriggerConditionsBlock(
        conditions=(
            ast.PositionPresenceStatement(
                typed_name=_make_local_ref("dummy"), location=_LOC
            ),
        ),
        location=_LOC,
    ),
    action_statements=ast.ActionStatementsBlock(statements=(), location=_LOC),
)


def _make_requirement(
    state: action_contract.PositionOccupancyState,
    position: ast.PositionReference,
) -> action_contract.PositionRequirement:
    return action_contract.PositionRequirement(
        required_state=state,
        position=position,
        inferred_at=position.location,
        enclosing_action=_DUMMY_ACTION,
    )


def _make_global_ref(path: str) -> ast.GlobalTypedNameReference:
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


def _quality_assignments(
    *qualities: ast.GlobalTypedNameReference,
) -> quality_assignment.QualityAssignments:
    return quality_assignment.QualityAssignments.expand_implications(
        qualities, lambda _: ()
    )


def _make_position_ref(
    elements: list[ast.TypedNameReference],
    location: ast.SourceLocation = _LOC,
) -> ast.PositionReference:
    return ast.PositionReference(typed_names=tuple(elements), location=location)


def test_create_and_is_occupied():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, _NO_QUALITIES)

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = particle_tracker.ParticleTracker()

    assert tracker.is_occupied(_make_position_ref([_make_local_ref("my_pos")])) is False


def test_get_occupant():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, _quality_assignments(_make_global_ref("/x")))
    occupant = tracker.get_occupant(ref)

    assert isinstance(occupant, particle_tracker.ParticleInfo)
    assert occupant.last_position.location == _LOC
    assert tuple(occupant.qualities) == (_make_global_ref("/x"),)


def test_create_already_occupied_raises():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, _NO_QUALITIES)

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref, _NO_QUALITIES)


def test_destroy():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("pos_a")])

    tracker.create(ref, _NO_QUALITIES)
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_from_empty_raises():
    tracker = particle_tracker.ParticleTracker()

    with pytest.raises(ValueError, match="not occupied"):
        tracker.destroy(_make_position_ref([_make_local_ref("pos_a")]))


def test_move():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, _NO_QUALITIES)
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True


def test_move_from_empty_raises():
    tracker = particle_tracker.ParticleTracker()

    with pytest.raises(KeyError):
        tracker.move(
            _make_position_ref([_make_local_ref("pos_a")]),
            _make_position_ref([_make_local_ref("pos_b")]),
        )


def test_mark_error_state():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.mark_error(ref)

    assert tracker.has_error_state(ref) is True


def test_no_error_state_initially():
    tracker = particle_tracker.ParticleTracker()

    assert (
        tracker.has_error_state(_make_position_ref([_make_local_ref("my_pos")]))
        is False
    )


def test_error_state_does_not_affect_other_keys():
    tracker = particle_tracker.ParticleTracker()

    tracker.mark_error(_make_position_ref([_make_local_ref("pos_a")]))

    assert (
        tracker.has_error_state(_make_position_ref([_make_local_ref("pos_a")])) is True
    )
    assert (
        tracker.has_error_state(_make_position_ref([_make_local_ref("pos_b")])) is False
    )


def test_error_state_propagates_to_descendants():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.mark_error(parent_ref)

    assert tracker.has_error_state(parent_ref) is True
    assert tracker.has_error_state(child_ref) is True


def test_move_to_occupied_raises():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, _NO_QUALITIES)
    tracker.create(ref_b, _NO_QUALITIES)

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(ref_a, ref_b)


def test_create_stores_qualities():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, _quality_assignments(_make_global_ref("/x")))

    assert tuple(tracker.get_occupant(ref).qualities) == (_make_global_ref("/x"),)


def test_move_preserves_qualities():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])
    qualities = _quality_assignments(_make_global_ref("/x"), _make_global_ref("/y"))

    tracker.create(ref_a, qualities)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).qualities is qualities


def test_move_updates_ref():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref(
        [_make_local_ref("pos_b", location=_LOC2)], location=_LOC2
    )

    tracker.create(ref_a, _NO_QUALITIES)
    assert tracker.get_occupant(ref_a).last_position.location == _LOC

    tracker.move(ref_a, ref_b)
    assert tracker.get_occupant(ref_b).last_position.location == _LOC2


def test_create_empty_qualities():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, _NO_QUALITIES)

    assert tuple(tracker.get_occupant(ref).qualities) == ()


def test_keys_use_separate_trie_levels():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_chain = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(ref_a, _NO_QUALITIES)

    assert tracker.is_occupied(ref_a) is True
    assert tracker.is_occupied(ref_chain) is False


def test_move_preserves_origin_position():
    tracker = particle_tracker.ParticleTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, _NO_QUALITIES)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).origin_position is ref_a


def test_create_at_global_chain():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.create(ref, _quality_assignments(_make_global_ref("/x")))

    assert tracker.is_occupied(ref) is True
    assert tuple(tracker.get_occupant(ref).qualities) == (_make_global_ref("/x"),)


def test_move_from_local_to_global_chain():
    tracker = particle_tracker.ParticleTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    dest_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, _quality_assignments(_make_global_ref("/x")))
    tracker.create(dest_parent_ref, _NO_QUALITIES)
    tracker.move(local_ref, chain_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is True
    assert tuple(tracker.get_occupant(chain_ref).qualities) == (_make_global_ref("/x"),)


def test_move_from_global_chain_to_local():
    tracker = particle_tracker.ParticleTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(chain_parent_ref, _NO_QUALITIES)
    tracker.create(chain_ref, _quality_assignments(_make_global_ref("/x")))
    tracker.move(chain_ref, local_ref)

    assert tracker.is_occupied(chain_ref) is False
    assert tracker.is_occupied(local_ref) is True
    assert tuple(tracker.get_occupant(local_ref).qualities) == (_make_global_ref("/x"),)


def test_move_between_global_chains():
    tracker = particle_tracker.ParticleTracker()
    parent_a = _make_position_ref([_make_local_ref("pos_a")])
    parent_b = _make_position_ref([_make_local_ref("pos_b")])
    chain_a = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child_a")]
    )
    chain_b = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child_b")]
    )

    tracker.create(parent_a, _NO_QUALITIES)
    tracker.create(parent_b, _NO_QUALITIES)
    tracker.create(chain_a, _quality_assignments(_make_global_ref("/x")))
    tracker.move(chain_a, chain_b)

    assert tracker.is_occupied(chain_a) is False
    assert tracker.is_occupied(chain_b) is True
    assert tuple(tracker.get_occupant(chain_b).qualities) == (_make_global_ref("/x"),)


def test_create_at_interface_position_chain():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("item")]
    )

    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(ref, _quality_assignments(_make_global_ref("/q")))

    assert tracker.is_occupied(ref) is True
    assert tuple(tracker.get_occupant(ref).qualities) == (_make_global_ref("/q"),)


def test_action_parent_auto_created_for_single_action_chain():
    tracker = particle_tracker.ParticleTracker()
    item_ref = _make_position_ref([_make_local_ref("item")])
    ref = _make_position_ref(
        [_make_local_ref("item"), _make_action_ref("/foo"), _make_local_ref("trigger")]
    )

    tracker.create(item_ref, _NO_QUALITIES)
    tracker.create(ref, _NO_QUALITIES)

    assert tracker.is_occupied(ref) is True


def test_chained_position_without_intermediate_fails():
    tracker = particle_tracker.ParticleTracker()
    local_ref = _make_position_ref([_make_local_ref("local")])
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_global_ref("/mid"), _make_global_ref("/last")]
    )

    tracker.create(local_ref, _NO_QUALITIES)

    with pytest.raises(KeyError):
        tracker.create(ref, _NO_QUALITIES)


def test_action_chain_without_parent_position_fails():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_action_ref("/foo"), _make_local_ref("iface")]
    )

    with pytest.raises(KeyError):
        tracker.create(ref, _NO_QUALITIES)


def test_nested_action_chain_without_intermediate_fails():
    tracker = particle_tracker.ParticleTracker()
    item_ref = _make_position_ref([_make_local_ref("item")])
    ref = _make_position_ref(
        [
            _make_local_ref("item"),
            _make_action_ref("/foo"),
            _make_local_ref("trigger"),
            _make_action_ref("/bar"),
            _make_local_ref("last"),
        ]
    )

    tracker.create(item_ref, _NO_QUALITIES)

    with pytest.raises(KeyError):
        tracker.create(ref, _NO_QUALITIES)


def test_move_between_interface_position_chains():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref_a = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("src")]
    )
    ref_b = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("dst")]
    )

    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(ref_a, _quality_assignments(_make_global_ref("/q")))
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True
    assert tuple(tracker.get_occupant(ref_b).qualities) == (_make_global_ref("/q"),)


def test_destroy_at_chain():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.create(ref, _NO_QUALITIES)
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_prunes_children():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.create(child_ref, _NO_QUALITIES)
    tracker.destroy(parent_ref)

    assert tracker.is_occupied(parent_ref) is False
    assert tracker.is_occupied(child_ref) is False


def test_mark_error_at_chain():
    tracker = particle_tracker.ParticleTracker()
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.mark_error(ref)

    assert tracker.has_error_state(ref) is True


def test_destroy_clears_error_children():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.create(child_ref, _NO_QUALITIES)
    tracker.mark_error(child_ref)

    assert tracker.has_error_state(child_ref) is True

    tracker.destroy(parent_ref)

    assert tracker.has_error_state(child_ref) is False


def test_destroy_parent_also_destroys_child():
    tracker = particle_tracker.ParticleTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, _NO_QUALITIES)
    tracker.create(chain_ref, _NO_QUALITIES)

    assert tracker.is_occupied(local_ref) is True
    assert tracker.is_occupied(chain_ref) is True

    tracker.destroy(local_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is False


def test_emptied_by_at_chain():
    tracker = particle_tracker.ParticleTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")], location=_LOC2
    )

    tracker.create(parent_ref, _NO_QUALITIES)
    tracker.create(ref, _NO_QUALITIES)
    tracker.destroy(ref)

    assert tracker.get_emptied_by(ref) is ref


def _make_action_ref(path: str) -> ast.GlobalTypedNameReference:
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


def _make_action_trigger(path: str) -> operation_graph.ActionTrigger:
    return operation_graph.ActionTrigger(
        callee=ast.ActionReference(
            typed_names=(_make_action_ref(path),),
            location=_LOC,
        ),
        trigger_operation=operation_graph.CreateNode(
            node_id=1,
            depends_on=(),
            target=_POS2_REF,
        ),
        bindings={},
        action_parent_last_operation=operation_graph.ActionParentLastOperationNode(
            node_id=0,
            depends_on=(),
        ),
    )


_ACTION_KEY_PREFIX = ("position<box>", "action<my.domain.com:my_lib:/other>")


def _apply_guarantees(
    tracker: particle_tracker.ParticleTracker,
    for_position: ast.PositionReference,
    guarantees: list[action_contract.GuaranteePair],
    acting_on: ast.PositionReference | None = None,
):
    """Apply a bare guarantee list (no triggered contracts) at for_position.

    ``acting_on`` is the position whose fill fired the trigger; it defaults to
    ``for_position`` but tests whose trigger position is not itself body-filled
    pass a body-created position so the operation graph has a firing operation.
    """
    action_chain = for_position.get_chain_to_last_action()
    assert action_chain is not None
    tracker.apply_guarantees(
        action_chain,
        action_contract.Guarantees(own=guarantees, nested=()),
        acting_on if acting_on is not None else for_position,
        [],
    )


def test_apply_guarantees_empty():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<item>",),
                action_contract.EmptyGuarantee(
                    caused_by=_POS2_REF, operation_positions=()
                ),
            )
        ],
    )

    assert tracker.is_occupied(ref) is False
    assert tracker.has_error_state(ref) is False


def test_apply_guarantees_occupied_by_new():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )

    tracker.create(box_ref, _NO_QUALITIES)
    qualities = _quality_assignments(_make_global_ref("/x"))
    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<item>",),
                action_contract.OccupiedByNewGuarantee(
                    qualities=qualities,
                    origin_position=_POS2_REF,
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            )
        ],
        acting_on=box_ref,
    )

    assert tracker.is_occupied(ref) is True
    occupant = tracker.get_occupant(ref)
    assert occupant.last_position.location == _LOC2
    assert occupant.qualities is qualities
    assert occupant.origin_position is _POS2_REF
    assert occupant.from_caller is False


def test_apply_guarantees_occupied_by_existing():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )
    item_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    trigger_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(item_ref, _quality_assignments(_make_global_ref("/q")))
    tracker.create(trigger_ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            ),
        ],
    )

    dest_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("dest")]
    )
    assert tracker.is_occupied(dest_ref) is True
    occupant = tracker.get_occupant(dest_ref)
    assert occupant.last_position.location == _LOC2
    assert tuple(occupant.qualities) == (_make_global_ref("/q"),)
    assert occupant.origin_position is item_ref


def test_apply_guarantees_occupied_by_existing_moves_children():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    item_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    child_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("item"),
            _make_global_ref("/child"),
        ]
    )
    trigger_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("trigger")]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(item_ref, _quality_assignments(_make_global_ref("/q")))
    tracker.create(child_ref, _quality_assignments(_make_global_ref("/r")))
    tracker.create(trigger_ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        trigger_ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            ),
        ],
    )

    new_child_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("dest"),
            _make_global_ref("/child"),
        ]
    )
    assert tracker.is_occupied(new_child_ref) is True
    assert tuple(tracker.get_occupant(new_child_ref).qualities) == (
        _make_global_ref("/r"),
    )


def test_apply_guarantees_occupied_by_existing_swap():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    item_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    item_child_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("item"),
            _make_global_ref("/child_a"),
        ]
    )
    dest_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("dest")]
    )
    dest_child_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("dest"),
            _make_global_ref("/child_b"),
        ]
    )
    trigger_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("trigger")]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(item_ref, _quality_assignments(_make_global_ref("/q")))
    tracker.create(item_child_ref, _quality_assignments(_make_global_ref("/r")))
    tracker.create(dest_ref, _quality_assignments(_make_global_ref("/s")))
    tracker.create(dest_child_ref, _quality_assignments(_make_global_ref("/t")))
    tracker.create(trigger_ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        trigger_ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            ),
            (
                ("position<item>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("dest")]),
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            ),
        ],
    )

    assert tracker.is_occupied(dest_ref) is True
    assert tuple(tracker.get_occupant(dest_ref).qualities) == (_make_global_ref("/q"),)

    new_child_a_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("dest"),
            _make_global_ref("/child_a"),
        ]
    )
    assert tracker.is_occupied(new_child_a_ref) is True
    assert tuple(tracker.get_occupant(new_child_a_ref).qualities) == (
        _make_global_ref("/r"),
    )

    assert tracker.is_occupied(item_ref) is True
    assert tuple(tracker.get_occupant(item_ref).qualities) == (_make_global_ref("/s"),)

    new_child_b_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("item"),
            _make_global_ref("/child_b"),
        ]
    )
    assert tracker.is_occupied(new_child_b_ref) is True
    assert tuple(tracker.get_occupant(new_child_b_ref).qualities) == (
        _make_global_ref("/t"),
    )


def test_apply_guarantees_occupied_by_existing_unfulfilled_becomes_error():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )

    tracker.create(box_ref, _NO_QUALITIES)
    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            ),
        ],
        acting_on=box_ref,
    )

    dest_ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("dest")]
    )
    assert tracker.has_error_state(dest_ref) is True
    assert tracker.is_occupied(dest_ref) is False


def test_apply_guarantees_error():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<item>",),
                action_contract.ErrorGuarantee(
                    caused_by=_POS2_REF, operation_positions=()
                ),
            )
        ],
    )

    assert tracker.has_error_state(ref) is True
    assert tracker.is_occupied(ref) is False


def test_apply_guarantees_does_not_touch_unmentioned_positions():
    tracker = particle_tracker.ParticleTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )
    untouched_ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("untouched"),
        ]
    )
    tracker.create(box_ref, _NO_QUALITIES)
    tracker.create(untouched_ref, _NO_QUALITIES)

    _apply_guarantees(
        tracker,
        ref,
        [
            (
                ("position<trigger>",),
                action_contract.EmptyGuarantee(
                    caused_by=_POS2_REF, operation_positions=()
                ),
            )
        ],
        acting_on=box_ref,
    )

    assert tracker.is_occupied(untouched_ref) is True


def test_generate_own_guarantees_skips_occupied_by_existing_at_origin():
    tracker = particle_tracker.ParticleTracker()
    run_name = _make_local_ref("run")
    run_ref = _make_position_ref([run_name])

    tracker.create(run_ref, _NO_QUALITIES, from_caller=run_ref)

    assert tracker.generate_own_guarantees((run_name,), (), {}) == []


def test_generate_own_guarantees_emits_occupied_by_existing_when_moved():
    a_name = _make_local_ref("a")
    b_name = _make_local_ref("b")
    a_ref = _make_position_ref([a_name])
    b_ref = _make_position_ref([b_name], location=_LOC2)
    tracker = particle_tracker.ParticleTracker()

    tracker.operation_graph.record_requirement(
        a_ref, action_contract.PositionOccupancyState.OCCUPIED
    )
    tracker.create(a_ref, _NO_QUALITIES, from_caller=a_ref)
    tracker.move(a_ref, b_ref)

    guarantees = tracker.generate_own_guarantees((a_name, b_name), (), {})

    assert len(guarantees) == 2
    by_key = dict(guarantees)
    empty_guarantee = by_key[("position<a>",)]
    assert isinstance(empty_guarantee, action_contract.EmptyGuarantee)
    assert empty_guarantee.caused_by is a_ref
    occupied_guarantee = by_key[("position<b>",)]
    assert isinstance(occupied_guarantee, action_contract.OccupiedByExistingGuarantee)
    assert occupied_guarantee.origin_position is a_ref
    assert occupied_guarantee.caused_by.location == _LOC2


def test_generate_own_guarantees_emits_unchanged_for_touched_inferred_empty():
    tracker = particle_tracker.ParticleTracker()
    x_name = _make_local_ref("x")
    x_ref = _make_position_ref([x_name])

    tracker.create(x_ref, _NO_QUALITIES)
    tracker.destroy(x_ref)

    requirements = {
        ("position<x>",): _make_requirement(
            action_contract.PositionOccupancyState.EMPTY, x_ref
        )
    }

    guarantees = tracker.generate_own_guarantees((x_name,), (), requirements)

    assert len(guarantees) == 1
    key, guarantee = guarantees[0]
    assert key == ("position<x>",)
    assert isinstance(guarantee, action_contract.UnchangedGuarantee)


def test_generate_own_guarantees_emits_empty_when_inferred_occupied():
    x_name = _make_local_ref("x")
    x_ref = _make_position_ref([x_name])
    requirements = {
        ("position<x>",): _make_requirement(
            action_contract.PositionOccupancyState.OCCUPIED,
            x_ref,
        )
    }
    tracker = particle_tracker.ParticleTracker()

    tracker.operation_graph.record_requirement(
        x_ref, action_contract.PositionOccupancyState.OCCUPIED
    )
    tracker.create(x_ref, _NO_QUALITIES, from_caller=x_ref)
    destroy_ref = _make_position_ref([_make_local_ref("x", location=_LOC2)], _LOC2)
    tracker.destroy(destroy_ref)

    guarantees = tracker.generate_own_guarantees((x_name,), (), requirements)

    assert len(guarantees) == 1
    key, guarantee = guarantees[0]
    assert key == ("position<x>",)
    assert isinstance(guarantee, action_contract.EmptyGuarantee)
    assert guarantee.caused_by.location == _LOC2


def test_snapshot_child_state_captures_each_occupancy_kind():
    tracker = particle_tracker.ParticleTracker()
    parent = _make_position_ref([_make_local_ref("parent")])
    child = _make_position_ref([_make_local_ref("parent"), _make_local_ref("child")])
    grandchild = _make_position_ref(
        [_make_local_ref("parent"), _make_local_ref("child"), _make_local_ref("gc")]
    )
    emptied = _make_position_ref(
        [_make_local_ref("parent"), _make_local_ref("emptied")]
    )
    deep_error = _make_position_ref(
        [_make_local_ref("parent"), _make_local_ref("branch"), _make_local_ref("leaf")]
    )

    tracker.create(parent, _NO_QUALITIES)
    tracker.create(child, _NO_QUALITIES)
    tracker.create(grandchild, _quality_assignments(_make_global_ref("/x")))
    tracker.create(emptied, _NO_QUALITIES)
    tracker.destroy(emptied)
    tracker.mark_error(deep_error)

    parent_key = parent.canonical_chained_name_tuple
    child_rel = child.canonical_chained_name_tuple[len(parent_key) :]
    grandchild_rel = grandchild.canonical_chained_name_tuple[len(parent_key) :]
    emptied_rel = emptied.canonical_chained_name_tuple[len(parent_key) :]
    deep_rel = deep_error.canonical_chained_name_tuple[len(parent_key) :]

    # `parent::branch` has no occupancy of its own (it exists only as an
    # ancestor of the error leaf), so it is absent from the snapshot.
    assert tracker.snapshot_child_state(parent) == {
        child_rel: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED, filled_at=child.location
        ),
        grandchild_rel: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED,
            filled_at=grandchild.location,
        ),
        emptied_rel: action_contract.EMPTY_OCCUPANCY,
        deep_rel: action_contract.ERROR_OCCUPANCY,
    }


def test_snapshot_child_state_is_decoupled_from_later_mutation():
    tracker = particle_tracker.ParticleTracker()
    parent = _make_position_ref([_make_local_ref("parent")])
    child = _make_position_ref([_make_local_ref("parent"), _make_local_ref("child")])
    grandchild = _make_position_ref(
        [_make_local_ref("parent"), _make_local_ref("child"), _make_local_ref("gc")]
    )

    tracker.create(parent, _NO_QUALITIES)
    tracker.create(child, _NO_QUALITIES)
    tracker.create(grandchild, _quality_assignments(_make_global_ref("/x")))

    parent_key = parent.canonical_chained_name_tuple
    child_rel = child.canonical_chained_name_tuple[len(parent_key) :]
    grandchild_rel = grandchild.canonical_chained_name_tuple[len(parent_key) :]

    snapshot = tracker.snapshot_child_state(parent)

    tracker.destroy(parent)
    tracker.create(parent, _NO_QUALITIES)
    tracker.create(child, _NO_QUALITIES)
    tracker.mark_error(grandchild)

    assert tracker.snapshot_child_state(parent) == {
        child_rel: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED, filled_at=child.location
        ),
        grandchild_rel: action_contract.ERROR_OCCUPANCY,
    }
    assert snapshot == {
        child_rel: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED, filled_at=child.location
        ),
        grandchild_rel: action_contract.ChildOccupancy(
            action_contract.PositionOccupancyState.OCCUPIED,
            filled_at=grandchild.location,
        ),
    }


def test_generate_flattened_guarantees_includes_callee_derived_key():
    tracker = particle_tracker.ParticleTracker()
    box_name = _make_local_ref("box")
    box_ref = _make_position_ref([box_name])
    item_ref = _make_position_ref(
        [box_name, _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, _NO_QUALITIES, from_caller=box_ref)
    trigger_ref = _make_position_ref([_make_local_ref("trigger")])
    tracker.create(trigger_ref, _NO_QUALITIES)
    _apply_guarantees(
        tracker,
        item_ref,
        [
            (
                ("position<item>",),
                action_contract.OccupiedByNewGuarantee(
                    qualities=quality_assignment.EMPTY_QUALITY_ASSIGNMENTS,
                    origin_position=_POS2_REF,
                    caused_by=_POS2_REF,
                    operation_positions=(),
                ),
            )
        ],
        acting_on=trigger_ref,
    )
    item_key = (*_ACTION_KEY_PREFIX, "position<item>")

    assert tracker.generate_own_guarantees((box_name,), (), {}) == []

    flattened = tracker.generate_flattened_guarantees((box_name,), (), {})
    assert len(flattened) == 1
    key, guarantee = flattened[0]
    assert key == item_key
    assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)


def test_generate_flattened_guarantees_flattens_pending_nested_guarantee():
    tracker = particle_tracker.ParticleTracker()
    box_name = _make_local_ref("box")
    box_ref = _make_position_ref([box_name])
    tracker.create(box_ref, _NO_QUALITIES, from_caller=box_ref)
    trigger_ref = _make_position_ref([_make_local_ref("trigger")])
    tracker.create(trigger_ref, _NO_QUALITIES)
    nested_trigger = _make_action_trigger("/other")
    nested = action_contract.NestedGuarantees(
        guarantees=action_contract.Guarantees(
            own=[
                (
                    ("position<item>",),
                    action_contract.OccupiedByNewGuarantee(
                        qualities=quality_assignment.EMPTY_QUALITY_ASSIGNMENTS,
                        origin_position=_POS2_REF,
                        caused_by=_POS2_REF,
                        operation_positions=(),
                    ),
                )
            ],
            nested=(),
        ),
        trigger=nested_trigger,
    )
    # The particle in position<box> has a triggered action whose guarantees
    # carry the nested guarantee; apply_guarantees always gets that action chain.
    box_trigger = ast.ActionReference(
        typed_names=(box_name, _make_action_ref("/outer")), location=_LOC
    )
    tracker.apply_guarantees(
        box_trigger,
        action_contract.Guarantees(
            own=[], nested=((nested_trigger.action_chain, nested),)
        ),
        trigger_ref,
        [],
    )
    item_key = (*_ACTION_KEY_PREFIX, "position<item>")

    assert tracker.generate_own_guarantees((box_name,), (), {}) == []

    flattened = tracker.generate_flattened_guarantees((box_name,), (), {})
    assert len(flattened) == 1
    key, guarantee = flattened[0]
    assert key == item_key
    assert isinstance(guarantee, action_contract.OccupiedByNewGuarantee)


def _make_nested_level(
    action_path: str,
    item: str,
    child_nested: action_contract.NestedGuaranteesByActionChain,
) -> tuple[tuple[str, ...], action_contract.NestedGuarantees]:
    trigger = _make_action_trigger(action_path)
    return (
        trigger.action_chain,
        action_contract.NestedGuarantees(
            guarantees=action_contract.Guarantees(
                own=[
                    (
                        (item,),
                        action_contract.OccupiedByNewGuarantee(
                            qualities=quality_assignment.EMPTY_QUALITY_ASSIGNMENTS,
                            origin_position=_POS2_REF,
                            caused_by=_POS2_REF,
                            operation_positions=(),
                        ),
                    ),
                ],
                nested=child_nested,
            ),
            trigger=trigger,
        ),
    )


def test_generate_flattened_guarantees_flattens_many_nested_levels():
    tracker = particle_tracker.ParticleTracker()
    box_name = _make_local_ref("box")
    box_ref = _make_position_ref([box_name])
    tracker.create(box_ref, _NO_QUALITIES, from_caller=box_ref)
    marker_name = _make_local_ref("marker")
    marker_ref = _make_position_ref([marker_name])
    tracker.create(marker_ref, _NO_QUALITIES)

    # Three levels of nesting, each deferred behind the one above it.
    level3 = _make_nested_level("/c", "position<item_c>", ())
    level2 = _make_nested_level("/b", "position<item_b>", (level3,))
    level1 = _make_nested_level("/a", "position<item_a>", (level2,))
    box_trigger = ast.ActionReference(
        typed_names=(box_name, _make_action_ref("/outer")), location=_LOC
    )
    tracker.apply_guarantees(
        box_trigger,
        action_contract.Guarantees(own=[], nested=(level1,)),
        marker_ref,
        [],
    )

    interface_names = (box_name, marker_name)
    own = tracker.generate_own_guarantees(interface_names, (), {})
    assert [key for key, _ in own] == [("position<marker>",)]

    flattened = tracker.generate_flattened_guarantees(interface_names, (), {})
    assert {key for key, _ in flattened} == {
        ("position<marker>",),
        ("position<box>", "action<my.domain.com:my_lib:/a>", "position<item_a>"),
        ("position<box>", "action<my.domain.com:my_lib:/b>", "position<item_b>"),
        ("position<box>", "action<my.domain.com:my_lib:/c>", "position<item_c>"),
    }
