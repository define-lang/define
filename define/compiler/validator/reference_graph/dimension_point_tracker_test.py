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

_TRIGGER_REF = ast.LocalTypedNameReference(
    name_type=ast.NameType.POSITION,
    name_content=ast.LocalNameContent(name="pp", location=_LOC),
    location=_LOC,
)

_ENCLOSING_DEF = ast.ActionDefinition(
    name=ast.DefinitionGlobalNameContent(
        fqun=_FQUN,
        path=ast.GlobalPathName(name="/my_action", location=_LOC),
        location=_LOC,
    ),
    quality_implications=[],
    interface_positions=[],
    trigger_conditions=ast.TriggerConditionsBlock(
        conditions=[
            ast.TriggerConditionStatement(typed_name=_TRIGGER_REF, location=_LOC)
        ],
        location=_LOC,
    ),
    action_statements=ast.ActionStatementsBlock(statements=[], location=_LOC),
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
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    assert tracker.is_occupied(_make_position_ref([_make_local_ref("my_pos")])) is False


def test_get_occupant():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset(["position<x>"]))
    occupant = tracker.get_occupant(ref)

    assert isinstance(occupant, dimension_point_tracker.DimensionPointInfo)
    assert occupant.last_position.location == _LOC
    assert occupant.qualities == frozenset(["position<x>"])


def test_create_already_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref, frozenset())


def test_destroy():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a")])

    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    with pytest.raises(ValueError, match="not occupied"):
        tracker.destroy(_make_position_ref([_make_local_ref("pos_a")]))


def test_move():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, frozenset())
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True


def test_move_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    with pytest.raises(KeyError):
        tracker.move(
            _make_position_ref([_make_local_ref("pos_a")]),
            _make_position_ref([_make_local_ref("pos_b")]),
        )


def test_mark_unknown_state():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_no_unknown_state_initially():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    assert (
        tracker.has_unknown_state(_make_position_ref([_make_local_ref("my_pos")]))
        is False
    )


def test_unknown_state_does_not_affect_other_keys():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

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
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, frozenset())
    tracker.mark_unknown(parent_ref)

    assert tracker.has_unknown_state(parent_ref) is True
    assert tracker.has_unknown_state(child_ref) is True


def test_move_to_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, frozenset())
    tracker.create(ref_b, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(ref_a, ref_b)


def test_create_stores_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset(["position<x>"]))

    assert tracker.get_occupant(ref).qualities == frozenset(["position<x>"])


def test_move_preserves_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])
    qualities = frozenset(["position<x>", "action<y>"])

    tracker.create(ref_a, qualities)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).qualities == qualities


def test_move_updates_ref():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref(
        [_make_local_ref("pos_b", location=_LOC2)], location=_LOC2
    )

    tracker.create(ref_a, frozenset())
    assert tracker.get_occupant(ref_a).last_position.location == _LOC

    tracker.move(ref_a, ref_b)
    assert tracker.get_occupant(ref_b).last_position.location == _LOC2


def test_create_empty_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    assert tracker.get_occupant(ref).qualities == frozenset()


def test_keys_use_separate_trie_levels():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_chain = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(ref_a, frozenset())

    assert tracker.is_occupied(ref_a) is True
    assert tracker.is_occupied(ref_chain) is False


def test_move_preserves_origin_position():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(ref_a, frozenset())
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).origin_position is ref_a


def test_create_at_global_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, frozenset())
    tracker.create(ref, frozenset(["position<x>"]))

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == frozenset(["position<x>"])


def test_move_from_local_to_global_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    dest_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, frozenset(["position<x>"]))
    tracker.create(dest_parent_ref, frozenset())
    tracker.move(local_ref, chain_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is True
    assert tracker.get_occupant(chain_ref).qualities == frozenset(["position<x>"])


def test_move_from_global_chain_to_local():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_parent_ref = _make_position_ref([_make_local_ref("pos_b")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(chain_parent_ref, frozenset())
    tracker.create(chain_ref, frozenset(["position<x>"]))
    tracker.move(chain_ref, local_ref)

    assert tracker.is_occupied(chain_ref) is False
    assert tracker.is_occupied(local_ref) is True
    assert tracker.get_occupant(local_ref).qualities == frozenset(["position<x>"])


def test_move_between_global_chains():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_a = _make_position_ref([_make_local_ref("pos_a")])
    parent_b = _make_position_ref([_make_local_ref("pos_b")])
    chain_a = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child_a")]
    )
    chain_b = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child_b")]
    )

    tracker.create(parent_a, frozenset())
    tracker.create(parent_b, frozenset())
    tracker.create(chain_a, frozenset(["position<x>"]))
    tracker.move(chain_a, chain_b)

    assert tracker.is_occupied(chain_a) is False
    assert tracker.is_occupied(chain_b) is True
    assert tracker.get_occupant(chain_b).qualities == frozenset(["position<x>"])


def test_create_at_interface_position_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("item")]
    )

    tracker.create(box_ref, frozenset())
    tracker.create(ref, frozenset(["position<q>"]))

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == frozenset(["position<q>"])


def test_action_parent_auto_created_for_single_action_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    item_ref = _make_position_ref([_make_local_ref("item")])
    ref = _make_position_ref(
        [_make_local_ref("item"), _make_action_ref("/foo"), _make_local_ref("trigger")]
    )

    tracker.create(item_ref, frozenset())
    tracker.create(ref, frozenset())

    assert tracker.is_occupied(ref) is True


def test_chained_position_without_intermediate_fails():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("local")])
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_global_ref("/mid"), _make_global_ref("/last")]
    )

    tracker.create(local_ref, frozenset())

    with pytest.raises(KeyError):
        tracker.create(ref, frozenset())


def test_action_chain_without_parent_position_fails():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("local"), _make_action_ref("/foo"), _make_local_ref("iface")]
    )

    with pytest.raises(KeyError):
        tracker.create(ref, frozenset())


def test_nested_action_chain_without_intermediate_fails():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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

    tracker.create(item_ref, frozenset())

    with pytest.raises(KeyError):
        tracker.create(ref, frozenset())


def test_move_between_interface_position_chains():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref_a = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("src")]
    )
    ref_b = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("dst")]
    )

    tracker.create(box_ref, frozenset())
    tracker.create(ref_a, frozenset(["position<q>"]))
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True
    assert tracker.get_occupant(ref_b).qualities == frozenset(["position<q>"])


def test_destroy_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(parent_ref, frozenset())
    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_prunes_children():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, frozenset())
    tracker.create(child_ref, frozenset())
    tracker.destroy(parent_ref)

    assert tracker.is_occupied(parent_ref) is False
    assert tracker.is_occupied(child_ref) is False


def test_mark_unknown_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_destroy_clears_unknown_children():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    child_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(parent_ref, frozenset())
    tracker.create(child_ref, frozenset())
    tracker.mark_unknown(child_ref)

    assert tracker.has_unknown_state(child_ref) is True

    tracker.destroy(parent_ref)

    assert tracker.has_unknown_state(child_ref) is False


def test_destroy_parent_also_destroys_child():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, frozenset())
    tracker.create(chain_ref, frozenset())

    assert tracker.is_occupied(local_ref) is True
    assert tracker.is_occupied(chain_ref) is True

    tracker.destroy(local_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is False


def test_emptied_by_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    parent_ref = _make_position_ref([_make_local_ref("pos_a")])
    ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")], location=_LOC2
    )

    tracker.create(parent_ref, frozenset())
    tracker.create(ref, frozenset())
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
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, frozenset())
    tracker.create(ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {("position<item>",): action_contract.EmptyGuarantee(caused_by=_POS2_REF)},
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(key) is False
    assert tracker.has_unknown_state_by_key(key) is False


def test_apply_guarantees_occupied_by_new():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )

    tracker.create(box_ref, frozenset())
    tracker.apply_guarantees(
        ref,
        {
            ("position<item>",): action_contract.OccupiedByNewGuarantee(
                qualities=frozenset(["position<x>"]),
                caused_by=_POS2_REF,
            )
        },
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(key) is True
    occupant = tracker.get_occupant_by_key(key)
    assert occupant.last_position.location == _LOC2
    assert occupant.qualities == frozenset(["position<x>"])
    assert occupant.origin_position is _POS2_REF


def test_apply_guarantees_occupied_by_existing():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(box_ref, frozenset())
    tracker.create(item_ref, frozenset(["position<q>"]))
    tracker.create(trigger_ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {
            ("position<dest>",): action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.is_occupied_by_key(dest_key) is True
    occupant = tracker.get_occupant_by_key(dest_key)
    assert occupant.last_position.location == _LOC2
    assert occupant.qualities == frozenset(["position<q>"])
    assert occupant.origin_position is item_ref


def test_apply_guarantees_occupied_by_existing_moves_children():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(box_ref, frozenset())
    tracker.create(item_ref, frozenset(["position<q>"]))
    tracker.create(child_ref, frozenset(["position<r>"]))
    tracker.create(trigger_ref, frozenset())

    tracker.apply_guarantees(
        trigger_ref,
        {
            ("position<dest>",): action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    new_child_key = (
        *_ACTION_KEY_PREFIX,
        "position<dest>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert tracker.is_occupied_by_key(new_child_key) is True
    assert tracker.get_occupant_by_key(new_child_key).qualities == frozenset(
        ["position<r>"]
    )


def test_apply_guarantees_occupied_by_existing_swap():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(box_ref, frozenset())
    tracker.create(item_ref, frozenset(["position<q>"]))
    tracker.create(item_child_ref, frozenset(["position<r>"]))
    tracker.create(dest_ref, frozenset(["position<s>"]))
    tracker.create(dest_child_ref, frozenset(["position<t>"]))
    tracker.create(trigger_ref, frozenset())

    tracker.apply_guarantees(
        trigger_ref,
        {
            ("position<dest>",): action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
            ("position<item>",): action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("dest")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.is_occupied_by_key(dest_key) is True
    assert tracker.get_occupant_by_key(dest_key).qualities == frozenset(["position<q>"])

    new_child_a_key = (
        *_ACTION_KEY_PREFIX,
        "position<dest>",
        "position<my.domain.com:my_lib:/child_a>",
    )
    assert tracker.is_occupied_by_key(new_child_a_key) is True
    assert tracker.get_occupant_by_key(new_child_a_key).qualities == frozenset(
        ["position<r>"]
    )

    item_key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.is_occupied_by_key(item_key) is True
    assert tracker.get_occupant_by_key(item_key).qualities == frozenset(["position<s>"])

    new_child_b_key = (
        *_ACTION_KEY_PREFIX,
        "position<item>",
        "position<my.domain.com:my_lib:/child_b>",
    )
    assert tracker.is_occupied_by_key(new_child_b_key) is True
    assert tracker.get_occupant_by_key(new_child_b_key).qualities == frozenset(
        ["position<t>"]
    )


def test_apply_guarantees_occupied_by_existing_unfulfilled_becomes_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )

    tracker.create(box_ref, frozenset())
    tracker.apply_guarantees(
        ref,
        {
            ("position<dest>",): action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    dest_key = (*_ACTION_KEY_PREFIX, "position<dest>")
    assert tracker.has_unknown_state_by_key(dest_key) is True
    assert tracker.is_occupied_by_key(dest_key) is False


def test_apply_guarantees_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    box_ref = _make_position_ref([_make_local_ref("box")])
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(box_ref, frozenset())
    tracker.create(ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {("position<item>",): action_contract.UnknownGuarantee(caused_by=_POS2_REF)},
    )

    key = (*_ACTION_KEY_PREFIX, "position<item>")
    assert tracker.has_unknown_state_by_key(key) is True
    assert tracker.is_occupied_by_key(key) is False


def test_apply_guarantees_does_not_touch_unmentioned_positions():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(box_ref, frozenset())
    tracker.create(untouched_ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {("position<trigger>",): action_contract.EmptyGuarantee(caused_by=_POS2_REF)},
    )

    assert tracker.is_occupied(untouched_ref) is True
