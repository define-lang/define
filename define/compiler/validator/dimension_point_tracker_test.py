# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator import dimension_point_tracker, scope_tracker

_POS = ast.SourcePosition(line=1, column=1, end_line=1, end_column=1)
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


def _make_position_ref(chain: list[ast.TypedName]) -> ast.PositionReference:
    return ast.PositionReference(chain=chain, position=_POS)


def _make_scope_with_def(name: str) -> scope_tracker.ScopeTracker:
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.enter_child_scope()
    scope.add_local_definition(_make_local_def(name))
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


def test_get_local_position_reference_not_in_current_scope():
    scope = scope_tracker.ScopeTracker(_FQUN)
    scope.add_local_definition(_make_local_def("parent_pos"))
    scope.enter_child_scope()
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("parent_pos")])

    result = tracker.get_local_position_reference(ref, scope)

    assert result is None


def test_create_and_is_occupied():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref)

    assert tracker.is_occupied(ref) is True


def test_not_occupied_initially():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    assert tracker.is_occupied(ref) is False


def test_get_occupant():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    local_ref = _make_local_ref("my_pos", _POS2)
    ref = _make_position_ref([local_ref])

    tracker.create(ref)
    occupant = tracker.get_occupant(ref)

    assert occupant is local_ref


def test_create_already_occupied_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    ref = _make_position_ref([_make_local_ref("my_pos")])

    tracker.create(ref)

    with pytest.raises(ValueError, match="already occupied"):
        tracker.create(ref)


def test_move():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(from_ref)
    tracker.move(from_ref, to_ref)

    assert tracker.is_occupied(from_ref) is False
    assert tracker.is_occupied(to_ref) is True


def test_move_from_empty_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    with pytest.raises(ValueError, match="not occupied"):
        tracker.move(from_ref, to_ref)


def test_move_to_occupied_raises():
    tracker = dimension_point_tracker.LocalDimensionPointTracker(_ENCLOSING_DEF)
    from_ref = _make_position_ref([_make_local_ref("pos_a")])
    to_ref = _make_position_ref([_make_local_ref("pos_b")])

    tracker.create(from_ref)
    tracker.create(to_ref)

    with pytest.raises(ValueError, match="already occupied"):
        tracker.move(from_ref, to_ref)
