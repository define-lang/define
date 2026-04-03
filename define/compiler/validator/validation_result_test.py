# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, parser, transformer
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.graphs import reference_graph
from define.compiler.validator import stats, test_helpers, validation_result
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator

_FQUN = "my.domain.com:my_lib"


def _validate_single_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> validation_result.FileValidationResult:
    relative_path = PurePosixPath("test.dfn")
    (tmp_path / relative_path).write_text(source, encoding="utf-8")
    test_helpers.write_project_config(tmp_path, _FQUN)
    monkeypatch.chdir(tmp_path)
    program_result = program_validator.ProgramStructuralValidator().validate_program(
        relative_path
    )
    reference_graph_validator.ReferenceGraphValidator(
        program_result.reference_graph,
        program_result.definition_results,
    ).validate()
    assert len(program_result.file_results) == 1
    return program_result.file_results[0]


def _parse(source: str) -> validation_result.FileValidationResult:
    parse_result = parser.Parser().parse(source)
    assert parse_result.diagnostics == []
    assert parse_result.tree is not None
    program = transformer.DefineTransformer().transform(parse_result.tree)
    return validation_result.FileValidationResult(
        exception=None,
        source=source,
        file_path=PurePosixPath("test.dfn"),
        root_prefix=PurePosixPath("."),
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
        "    it may only contain dimension points where {\n"
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
        "    it may only contain dimension points where {\n"
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


class TestTriggerPositionInfo:
    def test_checked_position_name_with_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
            f"define the potential action<{_FQUN}:/alarm> {{\n"
            "    define the position<triggered>.\n"
            "    it happens when {\n"
            "        the position<triggered> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<_noop>.\n"
            "        create a dimension point in position<_noop>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].trigger_positions) == 1
        assert (
            result.definition_results[0]
            .trigger_positions[0]
            .checked_position_name_with_prefix
            == f"action<{_FQUN}:/alarm>::position<triggered>"
        )


class TestActionBodyEffect:
    def test_create_to_local_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
            f"define the potential action<{_FQUN}:/test> {{\n"
            "    define the position<run>.\n"
            "    define the position<target>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<target>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].action_body_effects) == 1
        effect = result.definition_results[0].action_body_effects[0]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position
        assert effect.target_action_name == f"action<{_FQUN}:/test>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/test>::position<target>"
        )

    def test_create_to_statement_local_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
            f"define the potential action<{_FQUN}:/test> {{\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<target>.\n"
            "        create a dimension point in position<target>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].action_body_effects) == 1
        effect = result.definition_results[0].action_body_effects[0]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position
        assert effect.target_action_name == f"action<{_FQUN}:/test>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/test>::position<target>"
        )

    def test_move_to_local_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<a>.\n"
            "    define the position<b>.\n"
            "    it happens when {\n"
            "        the position<a> has a dimension point.\n"
            "    } and it does {\n"
            "        move the dimension point in position<a> to position<b>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].action_body_effects) == 1
        effect = result.definition_results[0].action_body_effects[0]
        assert isinstance(effect.statement, ast.MoveDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position
        assert effect.target_action_name == f"action<{_FQUN}:/act>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/act>::position<b>"
        )

    def test_create_to_explicit_action(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "other.dfn": (
                    f"define the potential action<{_FQUN}:/other> {{\n"
                    "    define the position<tp>.\n"
                    "    it happens when {\n"
                    "        the position<tp> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "test.dfn": (
                    f"define the potential action<{_FQUN}:/act> {{\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</other>::position<tp>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        act_result = result.program_result.definition_results[f"action<{_FQUN}:/act>"]
        assert len(act_result.action_body_effects) == 2
        effect = act_result.action_body_effects[1]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position
        assert effect.target_action_name == f"action<{_FQUN}:/other>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/other>::position<tp>"
        )
        test_helpers.assert_action_calls(
            result.action_call_graph, f"action<{_FQUN}:/act>", f"action<{_FQUN}:/other>"
        )

    def test_create_through_local_prefix(
        self,
        validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "other.dfn": (
                    f"define the potential action<{_FQUN}:/other> {{\n"
                    "    define the position<tp>.\n"
                    "    it happens when {\n"
                    "        the position<tp> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "test.dfn": (
                    f"define the potential action<{_FQUN}:/act> {{\n"
                    "    define the position<run>.\n"
                    "    define the position<local> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<local>.\n"
                    "        create a dimension point in position<local>::action</other>::position<tp>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        act_result = result.program_result.definition_results[f"action<{_FQUN}:/act>"]
        assert len(act_result.action_body_effects) == 2
        effect = act_result.action_body_effects[1]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position
        assert effect.target_action_name == f"action<{_FQUN}:/other>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/other>::position<tp>"
        )
        test_helpers.assert_action_calls(
            result.action_call_graph, f"action<{_FQUN}:/act>", f"action<{_FQUN}:/other>"
        )
