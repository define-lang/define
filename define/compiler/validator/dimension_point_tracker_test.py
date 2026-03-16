# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator import dimension_point_tracker, scope_tracker

_POS = ast.START_OF_FILE_POSITION
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


def test_get_local_position_reference_single_local_in_scope():
    scope = _make_scope_with_def("my_pos")
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    result = tracker.get_local_position_reference(ref, scope)

    assert result is not None
    assert isinstance(result, ast.LocalTypedNameReference)
    assert result.name_content.name == "my_pos"


def test_get_local_position_reference_multi_item_chain():
    scope = _make_scope_with_def("my_pos")
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos"), _make_global_ref("/child")])

    result = tracker.get_local_position_reference(ref, scope)

    assert result is None


def test_get_local_position_reference_global_reference():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.enter_child_scope()
    ref = _make_position_ref([_make_global_ref("/some_pos")])

    result = tracker.get_local_position_reference(ref, scope)

    assert result is None


def test_get_local_position_reference_in_parent_scope():
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.add_definition(_make_local_def("parent_pos"))
    scope.enter_child_scope()
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("parent_pos")])

    result = tracker.get_local_position_reference(ref, scope)

    assert result is not None


def test_create_and_is_occupied():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    assert tracker.is_occupied(ref) is False


def test_get_occupant():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_local_ref("my_pos", _POS2)
    ref = _make_position_ref([local_ref])

    tracker.create(ref, frozenset(["position<x>"]))
    occupant = tracker.get_occupant(ref)

    assert isinstance(occupant, dimension_point_tracker.DimensionPointInfo)
    assert occupant.creation_position is local_ref
    assert occupant.qualities == frozenset(["position<x>"])


def test_create_already_occupied_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref, frozenset())


def test_destroy():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a")])

    tracker.create(ref, frozenset())
    tracker.destroy(ref)

    assert tracker.is_occupied(ref) is False


def test_destroy_from_empty_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("pos_a")])

    with pytest.raises(ValueError, match="not occupied"):
        tracker.destroy(ref)


def test_move():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(from_ref, frozenset())
    tracker.move(from_ref, to_ref)

    assert tracker.is_occupied(from_ref) is False
    assert tracker.is_occupied(to_ref) is True


def test_move_from_empty_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    with pytest.raises(ValueError, match="not occupied"):
        tracker.move(from_ref, to_ref)


def test_mark_unknown_state():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.mark_unknown_state(ref)

    assert tracker.has_unknown_state(ref) is True


def test_no_unknown_state_initially():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    assert tracker.has_unknown_state(ref) is False


def test_unknown_state_does_not_affect_other_keys():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_b = _make_position_ref([_make_local_ref("pos_b")])

    tracker.mark_unknown_state(ref_a)

    assert tracker.has_unknown_state(ref_a) is True
    assert tracker.has_unknown_state(ref_b) is False


def test_move_to_occupied_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(from_ref, frozenset())
    tracker.create(to_ref, frozenset())

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(from_ref, to_ref)


def test_create_stores_qualities():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset(["position<x>"]))

    assert tracker.get_occupant(ref).qualities == frozenset(["position<x>"])


def test_move_preserves_qualities():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])
    qualities = frozenset(["position<x>", "action<y>"])

    tracker.create(from_ref, qualities)
    tracker.move(from_ref, to_ref)

    assert tracker.get_occupant(to_ref).qualities == qualities


def test_move_updates_creation_position():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(from_ref, frozenset())
    assert (
        tracker.get_occupant(from_ref).creation_position
        is from_ref.chain.typed_names[0]
    )

    tracker.move(from_ref, to_ref)
    assert tracker.get_occupant(to_ref).creation_position is to_ref.chain.typed_names[0]


def test_create_empty_qualities():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref, frozenset())

    assert tracker.get_occupant(ref).qualities == frozenset()


def test_keys_use_double_colon_separator():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref_a = _make_position_ref([_make_local_ref("pos_a")])
    ref_ab = _make_position_ref([_make_local_ref("pos_a"), _make_global_ref("/child")])

    tracker.create(ref_a, frozenset())

    assert tracker.is_occupied(ref_a) is True
    assert tracker.is_occupied(ref_ab) is False
