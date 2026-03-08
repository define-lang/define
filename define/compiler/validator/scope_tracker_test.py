# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.validator import scope_tracker

_POS = ast.SourcePosition(line=1, column=1, end_line=1, end_column=1)

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", position=_POS),
    universe=ast.Universe(name="my_lib", position=_POS),
    position=_POS,
)


def _make_local_def(
    name: str,
    constraints: ast.PositionConstraintBlock | None = None,
) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalNameContent(name=name, position=_POS),
        constraints=constraints,
        position=_POS,
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
                        path=ast.GlobalPathName(name=path, position=_POS),
                        position=_POS,
                    ),
                    position=_POS,
                ),
                position=_POS,
            )
        )
    return ast.PositionConstraintBlock(requirements=requirements, position=_POS)


def _make_local_typed_name(
    name: str, name_type: ast.NameType = ast.NameType.POSITION
) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=name_type,
        name_content=ast.LocalNameContent(name=name, position=_POS),
        position=_POS,
    )


def _make_global_typed_name(
    path: str, name_type: ast.NameType = ast.NameType.ACTION
) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=name_type,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, position=_POS),
            position=_POS,
        ),
        position=_POS,
    )


def test_add_and_is_defined():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    local_def = _make_local_def("my_pos")
    tracker.add_local_definition(local_def)

    ref = _make_local_typed_name("my_pos")
    assert tracker.is_defined(ref) is True


def test_is_defined_unknown():
    tracker = scope_tracker.ScopeTracker(_FQUN)

    ref = _make_local_typed_name("no_such")
    assert tracker.is_defined(ref) is False


def test_definition_has_quality_match():
    constraints = _make_constraint_block((ast.NameType.ACTION, "/child"))
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("my_pos", constraints))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is True


def test_definition_has_quality_no_match():
    constraints = _make_constraint_block((ast.NameType.ACTION, "/other"))
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("my_pos", constraints))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/wrong", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is False


def test_definition_has_quality_no_constraints():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("my_pos"))

    parent = _make_local_typed_name("my_pos")
    quality = _make_global_typed_name("/child", ast.NameType.ACTION)
    assert tracker.definition_has_quality(parent, quality) is False


def test_enter_child_scope_sees_parent():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()

    ref = _make_local_typed_name("parent_pos")
    assert tracker.is_defined(ref) is True


def test_is_defined_in_current_scope_parent_not_visible():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()

    ref = _make_local_typed_name("parent_pos")
    assert tracker.is_defined(ref) is True
    assert tracker.is_defined_in_current_scope(ref) is False


def test_is_defined_in_current_scope_child_visible():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.enter_child_scope()
    tracker.add_local_definition(_make_local_def("child_pos"))

    ref = _make_local_typed_name("child_pos")
    assert tracker.is_defined_in_current_scope(ref) is True


def test_enter_child_scope_adds_to_child_layer():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("parent_pos"))

    tracker.enter_child_scope()
    tracker.add_local_definition(_make_local_def("child_pos"))

    assert tracker.is_defined(_make_local_typed_name("parent_pos")) is True
    assert tracker.is_defined(_make_local_typed_name("child_pos")) is True


def test_get_definition():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    local_def = _make_local_def("my_pos")
    tracker.add_local_definition(local_def)

    assert tracker.get_definition(_make_local_typed_name("my_pos")) is local_def
    assert tracker.get_definition(_make_local_typed_name("no_such")) is None


def test_action_name_does_not_match_position():
    tracker = scope_tracker.ScopeTracker(_FQUN)
    tracker.add_local_definition(_make_local_def("shared_name"))

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
    tracker.add_local_definition(_make_local_def("my_pos"))
    ref = _make_local_typed_name("my_pos")
    assert tracker.get_constraint_names(ref) == frozenset()
