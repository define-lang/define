# pyright: reportUnusedCallResult=false

import pytest

from define.compiler import ast
from define.compiler.validator import scope_tracker

_LOC = ast.start_of_file_location()

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _make_local_def(
    name: str,
    constraints: ast.PositionConstraintBlock | None = None,
) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalNameContent(name=name, location=_LOC),
        constraints=constraints,
        location=_LOC,
    )


def _make_constraint_block(
    *typed_names: tuple[ast.NameType, str],
) -> ast.PositionConstraintBlock:
    requirements: list[ast.PositionRequirementStatement] = []
    for name_type, path in typed_names:
        requirements.append(
            ast.PositionRequirementStatement(
                typed_global_name=ast.GlobalTypedNameReference(
                    name_type=name_type,
                    name_content=ast.ReferenceGlobalNameContent(
                        fqun=None,
                        path=ast.GlobalPathName(name=path, location=_LOC),
                        location=_LOC,
                    ),
                    location=_LOC,
                ),
                location=_LOC,
            )
        )
    return ast.PositionConstraintBlock(requirements=requirements, location=_LOC)


def _make_global_position_def(
    path: str,
    constraints: ast.PositionConstraintBlock | None = None,
    location: ast.SourceLocation = _LOC,
) -> ast.PositionDefinition:
    return ast.PositionDefinition(
        name=ast.DefinitionGlobalNameContent(
            fqun=_FQUN,
            path=ast.GlobalPathName(name=path, location=location),
            location=location,
        ),
        constraints=constraints,
        location=location,
    )


def _make_local_typed_name(
    name: str, name_type: ast.NameType = ast.NameType.POSITION
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=name_type,
        name_content=ast.LocalNameContent(name=name, location=_LOC),
        location=_LOC,
    )


def _make_global_typed_name(
    path: str, name_type: ast.NameType = ast.NameType.ACTION
) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=name_type,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOC),
            location=_LOC,
        ),
        location=_LOC,
    )


def test_add_and_is_defined():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    local_def = _make_local_def("my_pos")
    tracker.add_definition(local_def)

    ref = _make_local_typed_name("my_pos")
    assert tracker.is_defined(ref) is True


def test_is_defined_unknown():
    tracker = scope_tracker.ScopeTracker(_FQUN)

    ref = _make_local_typed_name("no_such")
    assert tracker.is_defined(ref) is False


def test_definition_has_quality_match():
    constraints = _make_constraint_block((ast.NameType.ACTION, "/child"))
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos", constraints))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is True


def test_definition_has_quality_no_match():
    constraints = _make_constraint_block((ast.NameType.ACTION, "/other"))
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos", constraints))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/wrong", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is False


def test_definition_has_quality_no_constraints():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos"))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is False


def test_enter_child_scope_sees_parent():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()

    ref = _make_local_typed_name("parent_pos")
    assert tracker.is_defined(ref) is True


def test_is_defined_in_current_scope_parent_not_visible():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()

    ref = _make_local_typed_name("parent_pos")
    assert tracker.is_defined(ref) is True
    assert tracker.is_defined_in_current_scope(ref) is False


def test_is_defined_in_current_scope_child_visible():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.enter_child_scope()
    tracker.add_definition(_make_local_def("child_pos"))

    ref = _make_local_typed_name("child_pos")
    assert tracker.is_defined_in_current_scope(ref) is True


def test_enter_child_scope_adds_to_child_layer():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()
    tracker.add_definition(_make_local_def("child_pos"))

    assert tracker.is_defined(_make_local_typed_name("parent_pos")) is True
    assert tracker.is_defined(_make_local_typed_name("child_pos")) is True


def test_defined_on_line():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    local_def = _make_local_def("my_pos")
    tracker.add_definition(local_def)

    assert tracker.defined_on_line(_make_local_typed_name("my_pos")) == 1


def test_defined_on_line_raises_for_undefined():
    tracker = scope_tracker.ScopeTracker(_FQUN)

    with pytest.raises(KeyError):
        tracker.defined_on_line(_make_local_typed_name("no_such"))


def test_action_name_does_not_match_position():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("shared_name"))

    pos_ref = _make_local_typed_name("shared_name", ast.NameType.POSITION)
    act_ref = _make_local_typed_name("shared_name", ast.NameType.ACTION)

    assert tracker.is_defined(pos_ref) is True
    assert tracker.is_defined(act_ref) is False


def test_get_constraint_names_returns_empty_frozenset_for_undefined():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    ref = _make_local_typed_name("no_such")
    assert tracker.get_constraint_names(ref) == frozenset()


def test_get_constraint_names_returns_empty_frozenset_for_unconstrained():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos"))
    ref = _make_local_typed_name("my_pos")
    assert tracker.get_constraint_names(ref) == frozenset()


def test_add_global_position_definition():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    global_def = _make_global_position_def("/my_pos")
    tracker.add_definition(global_def)

    ref = _make_global_typed_name("/my_pos", ast.NameType.POSITION)
    assert tracker.is_defined(ref) is True


def test_global_position_defined_on_line():
    location = ast.SourceLocation(line=5, column=1, end_line=5, end_column=1)
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_global_position_def("/my_pos", location=location))

    ref = _make_global_typed_name("/my_pos", ast.NameType.POSITION)
    assert tracker.defined_on_line(ref) == 5


def test_global_position_with_constraints():
    constraints = _make_constraint_block((ast.NameType.ACTION, "/child"))
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_global_position_def("/my_pos", constraints))

    parent = _make_global_typed_name("/my_pos", ast.NameType.POSITION)
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is True


def test_global_position_without_constraints():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_global_position_def("/my_pos"))

    parent = _make_global_typed_name("/my_pos", ast.NameType.POSITION)
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is False


def _make_position_ref(
    elements: list[ast.TypedNameReference],
) -> ast.PositionReference:
    return ast.PositionReference(typed_names=elements, location=_LOC)


def test_is_defined_local_single_local_in_scope():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos"))
    position = _make_position_ref([_make_local_typed_name("my_pos")])

    assert tracker.is_defined_local(position) is True


def test_is_defined_local_multi_item_chain():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("my_pos"))
    position = _make_position_ref(
        [
            _make_local_typed_name("my_pos"),
            _make_global_typed_name("/child", ast.NameType.POSITION),
        ]
    )

    assert tracker.is_defined_local(position) is False


def test_is_defined_local_global_reference():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    position = _make_position_ref(
        [_make_global_typed_name("/some_pos", ast.NameType.POSITION)]
    )

    assert tracker.is_defined_local(position) is False


def test_is_defined_local_not_in_scope():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    position = _make_position_ref([_make_local_typed_name("missing")])

    assert tracker.is_defined_local(position) is False


def test_is_defined_local_in_parent_scope():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_definition(_make_local_def("parent_pos"))
    tracker.enter_child_scope()
    position = _make_position_ref([_make_local_typed_name("parent_pos")])

    assert tracker.is_defined_local(position) is True
