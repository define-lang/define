# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false

from pathlib import PurePosixPath

from define.compiler import ast, parser, transformer
from define.compiler.validator import stats, validation_result

_FQUN = "my.domain.com:my_lib"


def _parse(source: str) -> validation_result.ValidationResult:
    tree = parser.Parser().parse(source)
    program = transformer.DefineTransformer().transform(tree)
    return validation_result.ValidationResult(
        diagnostics=[],
        exception=None,
        source=source,
        file_path=PurePosixPath("test.def"),
        root_prefix=PurePosixPath("."),
        stats=stats.ValidationTimingStats(),
        definitions=program.definitions,
    )


def test_reference_edge_same_universe():
    result = _parse(
        f"define the potential position<{_FQUN}:/x> {{\n"
        "it may only contain dimension points where {\n"
        "it has the position</a>.\n"
        "}\n"
        "}\n"
    )
    pos_def = result.definitions[0]
    assert isinstance(pos_def, ast.PositionDefinition)
    assert pos_def.constraints is not None
    constraint_ref = pos_def.constraints.requirements[0].typed_global_name
    edge = validation_result.ReferenceEdge(
        enclosing_definition=pos_def,
        global_name_reference=constraint_ref,
    )
    assert edge.full_typed_name == f"position<{_FQUN}:/a>"


def test_reference_edge_explicit_fqun():
    result = _parse(
        f"define the potential position<{_FQUN}:/x> {{\n"
        "it may only contain dimension points where {\n"
        "it has the position<other.com:other_lib:/b>.\n"
        "}\n"
        "}\n"
    )
    pos_def = result.definitions[0]
    assert isinstance(pos_def, ast.PositionDefinition)
    assert pos_def.constraints is not None
    constraint_ref = pos_def.constraints.requirements[0].typed_global_name
    edge = validation_result.ReferenceEdge(
        enclosing_definition=pos_def,
        global_name_reference=constraint_ref,
    )
    assert edge.full_typed_name == "position<other.com:other_lib:/b>"


def test_definitions_by_name():
    result = _parse(f"define the potential position<{_FQUN}:/a>.\n")
    assert list(result.definitions_by_name.keys()) == [f"position<{_FQUN}:/a>"]
    assert result.definitions_by_name[f"position<{_FQUN}:/a>"] is result.definitions[0]


def test_definitions_by_name_empty():
    result = validation_result.ValidationResult(
        diagnostics=[],
        exception=None,
        source=None,
        file_path=PurePosixPath("test.def"),
        root_prefix=PurePosixPath("."),
        stats=stats.ValidationTimingStats(),
    )
    assert result.definitions_by_name == {}


def test_position_constraints_with_constraints():
    result = _parse(
        f"define the potential position<{_FQUN}:/a> {{\n"
        "it may only contain dimension points where {\n"
        "it has the position</child>.\n"
        "it has the position</other>.\n"
        "}\n"
        "}\n"
    )
    assert result.global_position_definition_constraints == {
        f"position<{_FQUN}:/a>": frozenset(
            {
                f"position<{_FQUN}:/child>",
                f"position<{_FQUN}:/other>",
            }
        ),
    }


def test_position_constraints_no_constraints():
    result = _parse(f"define the potential position<{_FQUN}:/a>.\n")
    assert result.global_position_definition_constraints == {
        f"position<{_FQUN}:/a>": frozenset(),
    }


def test_position_constraints_skips_actions():
    result = _parse(f"define the potential action<{_FQUN}:/act>.\n")
    assert result.global_position_definition_constraints == {}


def test_action_local_constraints_with_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "define the position<pos_a> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</child>.\n"
        "}\n"
        "}\n"
        "define the position<pos_b> {\n"
        "it may only contain dimension points where {\n"
        "it has the position</x>.\n"
        "it has the position</y>.\n"
        "}\n"
        "}\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    assert result.action_local_position_constraints == {
        f"action<{_FQUN}:/act>": {
            "pos_a": frozenset({f"position<{_FQUN}:/child>"}),
            "pos_b": frozenset(
                {
                    f"position<{_FQUN}:/x>",
                    f"position<{_FQUN}:/y>",
                }
            ),
        },
    }


def test_action_local_constraints_no_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "define the position<pos_a>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    assert result.action_local_position_constraints == {
        f"action<{_FQUN}:/act>": {
            "pos_a": frozenset(),
        },
    }


def test_action_local_constraints_no_block():
    result = _parse(f"define the potential action<{_FQUN}:/act>.\n")
    assert result.action_local_position_constraints == {}


def test_action_local_constraints_skips_positions():
    result = _parse(
        f"define the potential position<{_FQUN}:/a> {{\n"
        "it may only contain dimension points where {\n"
        "it has the position</child>.\n"
        "}\n"
        "}\n"
    )
    assert result.action_local_position_constraints == {}
