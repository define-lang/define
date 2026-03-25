# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    dimension_point_tracker,
)

_POS = ast.start_of_file_position()
_POS2 = ast.SourcePosition(line=2, column=1, end_line=2, end_column=1)

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


def _make_local_def(name: str) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalNameContent(name=name, position=_POS),
        constraints=None,
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
) -> ast.PositionReference:
    return ast.PositionReference(
        chain=ast.ChainedName(typed_names=elements, position=_POS),
        position=_POS,
    )


def _make_scope_with_def(name: str) -> scope_tracker.ScopeTracker:
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.enter_child_scope()
    scope.add_definition(_make_local_def(name))
    return scope


def test_get_local_position_single_local_in_scope():
    scope = _make_scope_with_def("my_pos")
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    result = tracker.get_local_position(ref, scope)

    assert result is not None
    assert isinstance(result, ast.LocalTypedNameReference)
    assert result.name_content.name == "my_pos"


def test_get_local_position_multi_item_chain():
    scope = _make_scope_with_def("my_pos")
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos"), _make_global_ref("/child")])

    result = tracker.get_local_position(ref, scope)

    assert result is None


def test_get_local_position_global_reference():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.enter_child_scope()
    ref = _make_position_ref([_make_global_ref("/some_pos")])

    result = tracker.get_local_position(ref, scope)

    assert result is None


def test_get_local_position_in_parent_scope():
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.add_definition(_make_local_def("parent_pos"))
    scope.enter_child_scope()
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("parent_pos")])

    result = tracker.get_local_position(ref, scope)

    assert result is not None


def test_create_and_is_occupied():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.create(ref, frozenset())

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    assert tracker.is_occupied(_make_local_ref("my_pos")) is False


def test_get_occupant():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.create(ref, frozenset(["position<x>"]))
    occupant = tracker.get_occupant(ref)

    assert isinstance(occupant, dimension_point_tracker.DimensionPointInfo)
    assert occupant.code_position == _POS
    assert occupant.qualities == frozenset(["position<x>"])


def test_create_already_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.create(ref, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref, frozenset())


def test_destroy():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("pos_a")

    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    with pytest.raises(ValueError, match="not occupied"):
        tracker.destroy(_make_local_ref("pos_a"))


def test_move():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_b = _make_local_ref("pos_b")

    tracker.create(ref_a, frozenset())
    tracker.move(ref_a, ref_b)

    assert tracker.is_occupied(ref_a) is False
    assert tracker.is_occupied(ref_b) is True


def test_move_from_empty_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    with pytest.raises(ValueError, match="not occupied"):
        tracker.move(
            _make_local_ref("pos_a"),
            _make_local_ref("pos_b"),
        )


def test_mark_unknown_state():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.mark_unknown(ref)

    assert tracker.has_unknown_state(ref) is True


def test_no_unknown_state_initially():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    assert tracker.has_unknown_state(_make_local_ref("my_pos")) is False


def test_unknown_state_does_not_affect_other_keys():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)

    tracker.mark_unknown(_make_local_ref("pos_a"))

    assert tracker.has_unknown_state(_make_local_ref("pos_a")) is True
    assert tracker.has_unknown_state(_make_local_ref("pos_b")) is False


def test_move_to_occupied_raises():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_b = _make_local_ref("pos_b")

    tracker.create(ref_a, frozenset())
    tracker.create(ref_b, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(ref_a, ref_b)


def test_create_stores_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.create(ref, frozenset(["position<x>"]))

    assert tracker.get_occupant(ref).qualities == frozenset(["position<x>"])


def test_move_preserves_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_b = _make_local_ref("pos_b")
    qualities = frozenset(["position<x>", "action<y>"])

    tracker.create(ref_a, qualities)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).qualities == qualities


def test_move_updates_code_position():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_b = _make_local_ref("pos_b", pos=_POS2)

    tracker.create(ref_a, frozenset())
    assert tracker.get_occupant(ref_a).code_position == _POS

    tracker.move(ref_a, ref_b)
    assert tracker.get_occupant(ref_b).code_position == _POS2


def test_create_empty_qualities():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_local_ref("my_pos")

    tracker.create(ref, frozenset())

    assert tracker.get_occupant(ref).qualities == frozenset()


def test_keys_use_double_colon_separator():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_chain = _make_position_ref(
        [_make_local_ref("pos_a"), _make_global_ref("/child")]
    )

    tracker.create(ref_a, frozenset())

    assert tracker.is_occupied(ref_a) is True
    assert tracker.is_occupied(ref_chain) is False


def test_move_preserves_origin_position():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_local_ref("pos_a")
    ref_b = _make_local_ref("pos_b")
    origin_def = _make_local_def("pos_a")

    tracker.create(ref_a, frozenset(), origin_position=origin_def)
    tracker.move(ref_a, ref_b)

    assert tracker.get_occupant(ref_b).origin_position is origin_def


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


def test_interface_position_key():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )

    key = tracker.interface_position_key(ref, "item")

    assert key == "position<box>::action<my.domain.com:my_lib:/other>::position<item>"


def test_interface_position_key_sibling():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger_pos"),
        ]
    )

    key = tracker.interface_position_key(ref, "item")

    assert key == "position<box>::action<my.domain.com:my_lib:/other>::position<item>"


def test_apply_guarantees_empty():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [_make_local_ref("box"), _make_action_ref("/other"), _make_local_ref("item")]
    )
    tracker.create(ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {"item": action_contract.EmptyGuarantee(position=_make_local_def("item"))},
    )

    key = tracker.interface_position_key(ref, "item")
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
            "item": action_contract.OccupiedByNewGuarantee(
                position=_make_local_def("item"),
                qualities=frozenset(["position<x>"]),
                caused_by=_POS2,
            )
        },
    )

    key = tracker.interface_position_key(ref, "item")
    assert tracker.is_occupied_by_key(key) is True
    occupant = tracker.get_occupant_by_key(key)
    assert occupant.code_position == _POS2
    assert occupant.qualities == frozenset(["position<x>"])
    assert occupant.origin_position is None


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
    item_def = _make_local_def("item")
    origin_def = _make_local_def("origin")
    tracker.create(item_ref, frozenset(["position<q>"]), origin_position=origin_def)
    tracker.create(trigger_ref, frozenset())

    tracker.apply_guarantees(
        ref,
        {
            "dest": action_contract.OccupiedByExistingGuarantee(
                position=_make_local_def("dest"),
                origin_position=item_def,
                caused_by=_POS2,
            ),
        },
    )

    dest_key = tracker.interface_position_key(ref, "dest")
    assert tracker.is_occupied_by_key(dest_key) is True
    occupant = tracker.get_occupant_by_key(dest_key)
    assert occupant.code_position == _POS2
    assert occupant.qualities == frozenset(["position<q>"])
    assert occupant.origin_position is origin_def


def test_apply_guarantees_occupied_by_existing_unfulfilled_becomes_unknown():
    tracker = dimension_point_tracker.DimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref(
        [
            _make_local_ref("box"),
            _make_action_ref("/other"),
            _make_local_ref("trigger"),
        ]
    )
    item_def = _make_local_def("item")

    tracker.apply_guarantees(
        ref,
        {
            "dest": action_contract.OccupiedByExistingGuarantee(
                position=_make_local_def("dest"),
                origin_position=item_def,
                caused_by=_POS2,
            ),
        },
    )

    dest_key = tracker.interface_position_key(ref, "dest")
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
        {"item": action_contract.UnknownGuarantee(position=_make_local_def("item"))},
    )

    key = tracker.interface_position_key(ref, "item")
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
        {
            "trigger": action_contract.EmptyGuarantee(
                position=_make_local_def("trigger")
            )
        },
    )

    assert tracker.is_occupied(untouched_ref) is True
