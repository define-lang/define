# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    dimension_point_tracker,
)

_LOC = ast.start_of_file_location()
_LOC2 = ast.SourceLocation(line=2, column=1, end_line=2, end_column=1)
_POS2_REF = ast.PositionReference(
    typed_names=[
        ast.LocalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.LocalNameContent(name="dummy", location=_LOC2),
            location=_LOC2,
        )
    ],
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
    quality_implications=[],
    interface_positions=[],
    trigger_conditions=ast.TriggerConditionsBlock(
        conditions=[
            ast.TriggerConditionStatement(
                typed_name=_make_local_ref("dummy"), location=_LOC
            )
        ],
        location=_LOC,
    ),
    action_statements=ast.ActionStatementsBlock(statements=[], location=_LOC),
)


def _make_requirement(
    state: action_contract.PositionOccupancyState,
    inferred_from: ast.PositionReference,
) -> action_contract.PositionRequirement:
    return action_contract.PositionRequirement(
        required_state=state,
        inferred_from=inferred_from,
        enclosing_quality=_DUMMY_ACTION,
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


def _make_position_ref(
    elements: list[ast.TypedNameReference],
    location: ast.SourceLocation = _LOC,
) -> ast.PositionReference:
    return ast.PositionReference(typed_names=elements, location=location)


def test_create_and_is_occupied():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, [])

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = dimension_point_tracker.DimensionPointTracker()

    assert tracker.is_occupied(_make_position_ref([_make_local_ref("my_pos")])) is False


def test_get_occupant():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, [_make_global_ref("/x")])
    occupant = tracker.get_occupant(ref)

    assert isinstance(occupant, dimension_point_tracker.DimensionPointInfo)
    assert occupant.last_position.location == _LOC
    assert occupant.qualities == [_make_global_ref("/x")]


def test_create_already_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, [])

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref, [])


def test_destroy():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("pos_a")])

    tracker.create(ref, [])
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker()

    with pytest.raises(ValueError, match="not occupied"):
        tracker.destroy(_make_position_ref([_make_local_ref("pos_a")]))


def test_move():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, [])
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True


def test_move_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker()

    with pytest.raises(KeyError):
        tracker.move(
            _make_position_ref([_make_local_ref("pos_a")]),
            _make_position_ref([_make_local_ref("pos_b")]),
        )


def test_mark_unknown_state():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_no_unknown_state_initially():
    tracker = dimension_point_tracker.DimensionPointTracker()

    assert (
        tracker.has_unknown_state(_make_position_ref([_make_local_ref("my_pos")]))
        is False
    )


def test_unknown_state_does_not_affect_other_keys():
    tracker = dimension_point_tracker.DimensionPointTracker()

    tracker.mark_unknown(_make_position_ref([_make_local_ref("pos_a")]))

    assert (
        tracker.has_unknown_state(_make_position_ref([_make_local_ref("pos_a")]))
        is True
    )
    assert (
        tracker.has_unknown_state(_make_position_ref([_make_local_ref("pos_b")]))
        is False
    )


def test_unknown_state_propagates_to_descendants():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, [])
    tracker.mark_unknown(parent_ref)

    assert tracker.has_unknown_state(parent_ref) is True
    assert tracker.has_unknown_state(child_ref) is True


def test_move_to_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, [])
    tracker.create(ref_b, [])

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(ref_a, ref_b)


def test_create_stores_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, [_make_global_ref("/x")])

    assert tracker.get_occupant(ref).qualities == [_make_global_ref("/x")]


def test_move_preserves_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])
    qualities = [_make_global_ref("/x"), _make_global_ref("/y")]

    tracker.create(ref_a, qualities)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).qualities == qualities


def test_move_updates_ref():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref(
        [_make_local_ref("pos_b", location=_LOC2)], location=_LOC2
    )

    tracker.create(ref_a, [])
    assert tracker.get_occupant(ref_a).last_position.location == _LOC

    tracker.move(ref_a, ref_b)
    assert tracker.get_occupant(ref_b).last_position.location == _LOC2


def test_create_empty_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, [])

    assert tracker.get_occupant(ref).qualities == []


def test_keys_use_separate_trie_levels():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_chain = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(ref_a, [])

    assert tracker.is_occupied(ref_a) is True
    assert tracker.is_occupied(ref_chain) is False


def test_move_preserves_origin_position():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, [])
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).origin_position is ref_a


def test_create_at_global_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, [])
    tracker.create(ref, [_make_global_ref("/x")])

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == [_make_global_ref("/x")]


def test_move_from_local_to_global_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    dest_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, [_make_global_ref("/x")])
    tracker.create(dest_parent_ref, [])
    tracker.move(local_ref, chain_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is True
    assert tracker.get_occupant(chain_ref).qualities == [_make_global_ref("/x")]


def test_move_from_global_chain_to_local():
    tracker = dimension_point_tracker.DimensionPointTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(chain_parent_ref, [])
    tracker.create(chain_ref, [_make_global_ref("/x")])
    tracker.move(chain_ref, local_ref)

    assert tracker.is_occupied(chain_ref) is False
    assert tracker.is_occupied(local_ref) is True
    assert tracker.get_occupant(local_ref).qualities == [_make_global_ref("/x")]


def test_move_between_global_chains():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_a = _make_position_ref([_make_local_ref("pos_a")])
    parent_b = _make_position_ref([_make_local_ref("pos_b")])
    chain_a = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child_a")]
    )
    chain_b = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child_b")]
    )

    tracker.create(parent_a, [])
    tracker.create(parent_b, [])
    tracker.create(chain_a, [_make_global_ref("/x")])
    tracker.move(chain_a, chain_b)

    assert tracker.is_occupied(chain_a) is False
    assert tracker.is_occupied(chain_b) is True
    assert tracker.get_occupant(chain_b).qualities == [_make_global_ref("/x")]


def test_create_at_interface_position_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("item")]
    )

    tracker.create(box_ref, [])
    tracker.create(ref, [_make_global_ref("/q")])

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == [_make_global_ref("/q")]


def test_action_parent_auto_created_for_single_action_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    item_ref = _make_position_ref([_make_local_ref("item")])
    ref = _make_position_ref(
        [_make_local_ref("item"), _make_action_ref("/foo"), _make_local_ref("trigger")]
    )

    tracker.create(item_ref, [])
    tracker.create(ref, [])

    assert tracker.is_occupied(ref) is True


def test_chained_position_without_intermediate_fails():
    tracker = dimension_point_tracker.DimensionPointTracker()
    local_ref = _make_position_ref([_make_local_ref("local")])
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_global_ref("/mid"), _make_global_ref("/last")]
    )

    tracker.create(local_ref, [])

    with pytest.raises(KeyError):
        tracker.create(ref, [])


def test_action_chain_without_parent_position_fails():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_action_ref("/foo"), _make_local_ref("iface")]
    )

    with pytest.raises(KeyError):
        tracker.create(ref, [])


def test_nested_action_chain_without_intermediate_fails():
    tracker = dimension_point_tracker.DimensionPointTracker()
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

    tracker.create(item_ref, [])

    with pytest.raises(KeyError):
        tracker.create(ref, [])


def test_move_between_interface_position_chains():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref_a = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("src")]
    )
    ref_b = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("dst")]
    )

    tracker.create(box_ref, [])
    tracker.create(ref_a, [_make_global_ref("/q")])
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True
    assert tracker.get_occupant(ref_b).qualities == [_make_global_ref("/q")]


def test_destroy_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, [])
    tracker.create(ref, [])
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_prunes_children():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, [])
    tracker.create(child_ref, [])
    tracker.destroy(parent_ref)

    assert tracker.is_occupied(parent_ref) is False
    assert tracker.is_occupied(child_ref) is False


def test_mark_unknown_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_destroy_clears_unknown_children():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, [])
    tracker.create(child_ref, [])
    tracker.mark_unknown(child_ref)

    assert tracker.has_unknown_state(child_ref) is True

    tracker.destroy(parent_ref)

    assert tracker.has_unknown_state(child_ref) is False


def test_destroy_parent_also_destroys_child():
    tracker = dimension_point_tracker.DimensionPointTracker()
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, [])
    tracker.create(chain_ref, [])

    assert tracker.is_occupied(local_ref) is True
    assert tracker.is_occupied(chain_ref) is True

    tracker.destroy(local_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is False


def test_emptied_by_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker()
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")], location=_LOC2
    )

    tracker.create(parent_ref, [])
    tracker.create(ref, [])
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


_ACTION_KEY_PREFIX = ("position<box>", "action<my.domain.com:my_lib:/other>")


def test_apply_guarantees_empty():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, [])
    tracker.create(ref, [])

    tracker.apply_guarantees(
        ref,
        [(("position<item>",), action_contract.EmptyGuarantee(caused_by=_POS2_REF))],
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(key) is False
    assert tracker.has_unknown_state_by_key(key) is False


def test_apply_guarantees_occupied_by_new():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )

    tracker.create(box_ref, [])
    tracker.apply_guarantees(
        ref,
        [
            (
                ("position<item>",),
                action_contract.OccupiedByNewGuarantee(
                    qualities=[_make_global_ref("/x")],
                    caused_by=_POS2_REF,
                ),
            )
        ],
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(key) is True
    occupant = tracker.get_occupant_by_key(key)
    assert occupant.last_position.location == _LOC2
    assert occupant.qualities == [_make_global_ref("/x")]
    assert occupant.origin_position is _POS2_REF
    assert occupant.from_caller is False


def test_apply_guarantees_occupied_by_existing():
    tracker = dimension_point_tracker.DimensionPointTracker()
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
    tracker.create(box_ref, [])
    tracker.create(item_ref, [_make_global_ref("/q")])
    tracker.create(trigger_ref, [])

    tracker.apply_guarantees(
        ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                ),
            ),
        ],
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.is_occupied_by_key(dest_key) is True
    occupant = tracker.get_occupant_by_key(dest_key)
    assert occupant.last_position.location == _LOC2
    assert occupant.qualities == [_make_global_ref("/q")]
    assert occupant.origin_position is item_ref


def test_apply_guarantees_occupied_by_existing_moves_children():
    tracker = dimension_point_tracker.DimensionPointTracker()
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
    tracker.create(box_ref, [])
    tracker.create(item_ref, [_make_global_ref("/q")])
    tracker.create(child_ref, [_make_global_ref("/r")])
    tracker.create(trigger_ref, [])

    tracker.apply_guarantees(
        trigger_ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                ),
            ),
        ],
    )

    new_child_key = (
        *_ACTION_KEY_PREFIX,
        "position<dest>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert tracker.is_occupied_by_key(new_child_key) is True
    assert tracker.get_occupant_by_key(new_child_key).qualities == [
        _make_global_ref("/r")
    ]


def test_apply_guarantees_occupied_by_existing_swap():
    tracker = dimension_point_tracker.DimensionPointTracker()
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
    tracker.create(box_ref, [])
    tracker.create(item_ref, [_make_global_ref("/q")])
    tracker.create(item_child_ref, [_make_global_ref("/r")])
    tracker.create(dest_ref, [_make_global_ref("/s")])
    tracker.create(dest_child_ref, [_make_global_ref("/t")])
    tracker.create(trigger_ref, [])

    tracker.apply_guarantees(
        trigger_ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                ),
            ),
            (
                ("position<item>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("dest")]),
                    caused_by=_POS2_REF,
                ),
            ),
        ],
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.is_occupied_by_key(dest_key) is True
    assert tracker.get_occupant_by_key(dest_key).qualities == [_make_global_ref("/q")]

    new_child_a_key = (
        *_ACTION_KEY_PREFIX,
        "position<dest>",
        "position<my.domain.com:my_lib:/child_a>",
    )
    assert tracker.is_occupied_by_key(new_child_a_key) is True
    assert tracker.get_occupant_by_key(new_child_a_key).qualities == [
        _make_global_ref("/r")
    ]

    item_key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(item_key) is True
    assert tracker.get_occupant_by_key(item_key).qualities == [_make_global_ref("/s")]

    new_child_b_key = (
        *_ACTION_KEY_PREFIX,
        "position<item>",
        "position<my.domain.com:my_lib:/child_b>",
    )
    assert tracker.is_occupied_by_key(new_child_b_key) is True
    assert tracker.get_occupant_by_key(new_child_b_key).qualities == [
        _make_global_ref("/t")
    ]


def test_apply_guarantees_occupied_by_existing_unfulfilled_becomes_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )

    tracker.create(box_ref, [])
    tracker.apply_guarantees(
        ref,
        [
            (
                ("position<dest>",),
                action_contract.OccupiedByExistingGuarantee(
                    origin_position=_make_position_ref([_make_local_ref("item")]),
                    caused_by=_POS2_REF,
                ),
            ),
        ],
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.has_unknown_state_by_key(dest_key) is True
    assert tracker.is_occupied_by_key(dest_key) is False


def test_apply_guarantees_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker()
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, [])
    tracker.create(ref, [])

    tracker.apply_guarantees(
        ref,
        [(("position<item>",), action_contract.UnknownGuarantee(caused_by=_POS2_REF))],
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.has_unknown_state_by_key(key) is True
    assert tracker.is_occupied_by_key(key) is False


def test_apply_guarantees_does_not_touch_unmentioned_positions():
    tracker = dimension_point_tracker.DimensionPointTracker()
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
    tracker.create(box_ref, [])
    tracker.create(untouched_ref, [])

    tracker.apply_guarantees(
        ref,
        [(("position<trigger>",), action_contract.EmptyGuarantee(caused_by=_POS2_REF))],
    )

    assert tracker.is_occupied(untouched_ref) is True


def test_generate_guarantees_skips_occupied_by_existing_at_origin():
    tracker = dimension_point_tracker.DimensionPointTracker()
    run_name = _make_local_ref("run")
    run_ref = _make_position_ref([run_name])

    tracker.create(run_ref, [], from_caller=run_ref)

    assert tracker.generate_guarantees([run_name], [], {}) == []


def test_generate_guarantees_emits_occupied_by_existing_when_moved():
    tracker = dimension_point_tracker.DimensionPointTracker()
    a_name = _make_local_ref("a")
    b_name = _make_local_ref("b")
    a_ref = _make_position_ref([a_name])
    b_ref = _make_position_ref([b_name], location=_LOC2)

    tracker.create(a_ref, [], from_caller=a_ref)
    tracker.move(a_ref, b_ref)

    guarantees = tracker.generate_guarantees([a_name, b_name], [], {})

    assert len(guarantees) == 2
    by_key = dict(guarantees)
    empty_guarantee = by_key[("position<a>",)]
    assert isinstance(empty_guarantee, action_contract.EmptyGuarantee)
    assert empty_guarantee.caused_by is a_ref
    occupied_guarantee = by_key[("position<b>",)]
    assert isinstance(occupied_guarantee, action_contract.OccupiedByExistingGuarantee)
    assert occupied_guarantee.origin_position is a_ref
    assert occupied_guarantee.caused_by.location == _LOC2


def test_generate_guarantees_skips_empty_when_inferred_empty():
    tracker = dimension_point_tracker.DimensionPointTracker()
    x_name = _make_local_ref("x")
    x_ref = _make_position_ref([x_name])

    tracker.create(x_ref, [])
    tracker.destroy(x_ref)

    requirements = {
        ("position<x>",): _make_requirement(
            action_contract.PositionOccupancyState.EMPTY, x_ref
        )
    }

    assert tracker.generate_guarantees([x_name], [], requirements) == []


def test_generate_guarantees_emits_empty_when_inferred_occupied():
    tracker = dimension_point_tracker.DimensionPointTracker()
    x_name = _make_local_ref("x")
    x_ref = _make_position_ref([x_name])

    tracker.create(x_ref, [], from_caller=x_ref)
    destroy_ref = _make_position_ref([_make_local_ref("x", location=_LOC2)], _LOC2)
    tracker.destroy(destroy_ref)

    requirements = {
        ("position<x>",): _make_requirement(
            action_contract.PositionOccupancyState.OCCUPIED, x_ref
        )
    }

    guarantees = tracker.generate_guarantees([x_name], [], requirements)

    assert len(guarantees) == 1
    key, guarantee = guarantees[0]
    assert key == ("position<x>",)
    assert isinstance(guarantee, action_contract.EmptyGuarantee)
    assert guarantee.caused_by.location == _LOC2
