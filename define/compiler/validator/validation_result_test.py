# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false

from __future__ import annotations

from define.compiler import ast, test_helpers
from define.compiler.data_structures import define_path
from define.compiler.graphs import reference_graph
from define.compiler.validator import stats, validation_result

_FQUN = "my.domain.com:my_lib"


def _parse(source: str) -> validation_result.FileValidationResult:
    program = test_helpers.parse_and_transform(source)
    return validation_result.FileValidationResult(
        exception=None,
        source_lines=source.splitlines(),
        file_path=define_path.DefinePath("test.dfn"),
        root_prefix=define_path.EMPTY,
        stats=stats.ValidationTimingStats(),
        file_diagnostics=[],
        definition_results=[
            validation_result.DefinitionValidationResult(definition=definition)
            for definition in program.definitions
        ],
    )


def _first_definition(
    result: validation_result.FileValidationResult,
) -> ast.QualityDefinition:
    return result.definition_results[0].definition


def test_reference_edge_same_universe():
    result = _parse(
        f"define the potential position<{_FQUN}:/x> {{\n"
        "    it may only contain particles where {\n"
        "        it has the position</a>.\n"
        "    }\n"
        "}\n"
    )
    pos_def = _first_definition(result)
    assert isinstance(pos_def, ast.PositionDefinition)
    assert pos_def.constraints is not None
    constraint_ref = pos_def.constraints.requirements[0].typed_global_name
    edge = reference_graph.ReferenceEdge(
        enclosing_definition=pos_def,
        global_name_reference=constraint_ref,
    )
    assert edge.target_full_typed_name == f"position<{_FQUN}:/a>"


def test_reference_edge_explicit_fqun():
    result = _parse(
        f"define the potential position<{_FQUN}:/x> {{\n"
        "    it may only contain particles where {\n"
        "        it has the position<other.com:other_lib:/b>.\n"
        "    }\n"
        "}\n"
    )
    pos_def = _first_definition(result)
    assert isinstance(pos_def, ast.PositionDefinition)
    assert pos_def.constraints is not None
    constraint_ref = pos_def.constraints.requirements[0].typed_global_name
    edge = reference_graph.ReferenceEdge(
        enclosing_definition=pos_def,
        global_name_reference=constraint_ref,
    )
    assert edge.target_full_typed_name == "position<other.com:other_lib:/b>"
