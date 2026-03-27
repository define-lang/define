# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    dimension_point_tracker,
)

_POS = ast.start_of_file_position()
_POS2 = ast.SourcePosition(line=2, column=1, end_line=2, end_column=1)
_POS2_REF = ast.PositionReference(
    chain=ast.ChainedName(typed_names=[], position=_POS2),
    position=_POS2,
)

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", position=_POS),
    universe=ast.Universe(name="my_lib", position=_POS),
    position=_POS,
)

_ENCLOSING_DEF = ast.ActionDefinition(
    name=ast.DefinitionGlobalNameContent(
        fqun=_FQUN,
        path=ast.GlobalPathName(name="/my_action", position=_POS),
        position=_POS,
    ),
    position=_POS,
)


def _make_local_ref(
    name: str, pos: ast.SourcePosition = _POS
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.LocalNameContent(name=name, position=pos),
        position=pos,
    )


def _make_global_ref(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, position=_POS),
            position=_POS,
        ),
        position=_POS,
    )


def _make_position_ref(
    elements: list[ast.TypedNameReference],
    pos: ast.SourcePosition = _POS,
) -> ast.PositionReference:
    return ast.PositionReference(
        chain=ast.ChainedName(typed_names=elements, position=pos),
        position=pos,
    )


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
    assert occupant.last_position.position == _POS
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

    with pytest.raises(ValueError, match="not occupied"):
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
    ref_b = _make_position_ref([_make_local_ref("pos_b", pos=_POS2)], pos=_POS2)

    tracker.create(ref_a, frozenset())
    assert tracker.get_occupant(ref_a).last_position.position == _POS

    tracker.move(ref_a, ref_b)
    assert tracker.get_occupant(ref_b).last_position.position == _POS2


def test_create_empty_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    assert tracker.get_occupant(ref).qualities == frozenset()


def test_keys_use_double_colon_separator():
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
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(ref, frozenset(["position<x>"]))

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == frozenset(["position<x>"])


def test_move_from_local_to_global_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(local_ref, frozenset(["position<x>"]))
    tracker.move(local_ref, chain_ref)

    assert tracker.is_occupied(local_ref) is False
    assert tracker.is_occupied(chain_ref) is True
    assert tracker.get_occupant(chain_ref).qualities == frozenset(["position<x>"])


def test_move_from_global_chain_to_local():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_position_ref([_make_local_ref("pos_a")])
    chain_ref = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child")]
    )

    tracker.create(chain_ref, frozenset(["position<x>"]))
    tracker.move(chain_ref, local_ref)

    assert tracker.is_occupied(chain_ref) is False
    assert tracker.is_occupied(local_ref) is True
    assert tracker.get_occupant(local_ref).qualities == frozenset(["position<x>"])


def test_move_between_global_chains():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    chain_a = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child_a")]
    )
    chain_b = _make_position_ref(
        [_make_local_ref("pos_b"), _make_global_ref("/child_b")]
    )

    tracker.create(chain_a, frozenset(["position<x>"]))
    tracker.move(chain_a, chain_b)

    assert tracker.is_occupied(chain_a) is False
    assert tracker.is_occupied(chain_b) is True
    assert tracker.get_occupant(chain_b).qualities == frozenset(["position<x>"])


def test_create_at_interface_position_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("item")]
    )

    tracker.create(ref, frozenset(["position<q>"]))

    assert tracker.is_occupied(ref) is True
    assert tracker.get_occupant(ref).qualities == frozenset(["position<q>"])


def test_move_between_interface_position_chains():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("src")]
    )
    ref_b = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/act"), _make_local_ref("dst")]
    )

    tracker.create(ref_a, frozenset(["position<q>"]))
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True
    assert tracker.get_occupant(ref_b).qualities == frozenset(["position<q>"])


def test_destroy_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_mark_unknown_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_chain_and_local_are_independent():
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
    assert tracker.is_occupied(chain_ref) is True


def test_emptied_by_at_chain():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")], pos=_POS2
    )

    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.get_emptied_by(ref) is ref


def _make_action_ref(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, position=_POS),
            position=_POS,
        ),
        position=_POS,
    )


_ACTION_KEY_PREFIX = "position<box>::action<my.domain.com:my_lib:/other>"


def test_apply_guarantees_empty():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {"position<item>": action_contract.EmptyGuarantee()},
    )

    key = f"{_ACTION_KEY_PREFIX}::position<item>"
    assert tracker.is_occupied_by_key(key) is False
    assert tracker.has_unknown_state_by_key(key) is False


def test_apply_guarantees_occupied_by_new():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )

    tracker.apply_guarantees(
        ref,
        {
            "position<item>": action_contract.OccupiedByNewGuarantee(
                qualities=frozenset(["position<x>"]),
                caused_by=_POS2_REF,
            )
        },
    )

    key = f"{_ACTION_KEY_PREFIX}::position<item>"
    assert tracker.is_occupied_by_key(key) is True
    occupant = tracker.get_occupant_by_key(key)
    assert occupant.last_position.position == _POS2
    assert occupant.qualities == frozenset(["position<x>"])
    assert occupant.origin_position is _POS2_REF


def test_apply_guarantees_occupied_by_existing():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(item_ref, frozenset(["position<q>"]))
    tracker.create(trigger_ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {
            "position<dest>": action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    dest_key = f"{_ACTION_KEY_PREFIX}::position<dest>"
    assert tracker.is_occupied_by_key(dest_key) is True
    occupant = tracker.get_occupant_by_key(dest_key)
    assert occupant.last_position.position == _POS2
    assert occupant.qualities == frozenset(["position<q>"])
    assert occupant.origin_position is item_ref


def test_apply_guarantees_occupied_by_existing_unfulfilled_becomes_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )

    tracker.apply_guarantees(
        ref,
        {
            "position<dest>": action_contract.OccupiedByExistingGuarantee(
                origin_position=_make_position_ref([_make_local_ref("item")]),
                caused_by=_POS2_REF,
            ),
        },
    )

    dest_key = f"{_ACTION_KEY_PREFIX}::position<dest>"
    assert tracker.has_unknown_state_by_key(dest_key) is True
    assert tracker.is_occupied_by_key(dest_key) is False


def test_apply_guarantees_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {"position<item>": action_contract.UnknownGuarantee()},
    )

    key = f"{_ACTION_KEY_PREFIX}::position<item>"
    assert tracker.has_unknown_state_by_key(key) is True
    assert tracker.is_occupied_by_key(key) is False


def test_apply_guarantees_does_not_touch_unmentioned_positions():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
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
    tracker.create(untouched_ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {"position<trigger>": action_contract.EmptyGuarantee()},
    )

    assert tracker.is_occupied(untouched_ref) is True
