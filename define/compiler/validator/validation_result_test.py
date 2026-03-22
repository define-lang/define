# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, parser, transformer
from define.compiler.graphs import reference_graph
from define.compiler.validator import (
    program_validator,
    stats,
    validation_result,
)
from define.compiler.validator.program_validator_tests import test_helpers

_FQUN = "my.domain.com:my_lib"


def _validate_single_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> validation_result.FileValidationResult:
    relative_path = PurePosixPath("test.def")
    (tmp_path / relative_path).write_text(source, encoding="utf-8")
    test_helpers.write_project_config(tmp_path, _FQUN)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    return results[0]


def _parse(source: str) -> validation_result.FileValidationResult:
    parse_result = parser.Parser().parse(source)
    assert parse_result.diagnostics == []
    assert parse_result.tree is not None
    program = transformer.DefineTransformer().transform(parse_result.tree)
    return validation_result.FileValidationResult(
        exception=None,
        source=source,
        file_path=PurePosixPath("test.def"),
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


def _first_definition_result(
    result: validation_result.FileValidationResult,
) -> validation_result.DefinitionValidationResult:
    return result.definition_results[0]


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


def test_position_constraints_with_constraints():
    result = _parse(
        f"define the potential position<{_FQUN}:/a> {{\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</child>.\n"
        "        it has the position</other>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).position_constraint_names == frozenset(
        {
            f"position<{_FQUN}:/child>",
            f"position<{_FQUN}:/other>",
        }
    )


def test_position_constraints_no_constraints():
    result = _parse(f"define the potential position<{_FQUN}:/a>.\n")
    assert _first_definition_result(result).position_constraint_names == frozenset()


def test_position_constraints_skips_actions():
    result = _parse(f"define the potential action<{_FQUN}:/act>.\n")
    assert _first_definition_result(result).position_constraint_names == frozenset()


def test_action_local_constraints_with_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</child>.\n"
        "        }\n"
        "    }\n"
        "    define the position<pos_b> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</x>.\n"
        "            it has the position</y>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).action_local_position_constraint_names == {
        "pos_a": frozenset({f"position<{_FQUN}:/child>"}),
        "pos_b": frozenset(
            {
                f"position<{_FQUN}:/x>",
                f"position<{_FQUN}:/y>",
            }
        ),
    }


def test_action_local_constraints_no_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "    define the position<pos_a>.\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).action_local_position_constraint_names == {
        "pos_a": frozenset(),
    }


def test_action_local_constraints_ignore_later_duplicate_with_different_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</first>.\n"
        "        }\n"
        "    }\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</second>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).action_local_position_constraint_names == {
        "pos_a": frozenset({f"position<{_FQUN}:/first>"}),
    }


def test_action_local_constraints_ignore_later_duplicate_that_adds_constraints():
    result = _parse(
        f"define the potential action<{_FQUN}:/act> {{\n"
        "    define the position<pos_a>.\n"
        "    define the position<pos_a> {\n"
        "        it may only contain dimension points where {\n"
        "            it has the position</second>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<pos_a> has a dimension point.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a dimension point in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).action_local_position_constraint_names == {
        "pos_a": frozenset(),
    }


def test_action_local_constraints_no_block():
    result = _parse(f"define the potential action<{_FQUN}:/act>.\n")
    assert _first_definition_result(result).action_local_position_constraint_names == {}


def test_action_local_constraints_skips_positions():
    result = _parse(
        f"define the potential position<{_FQUN}:/a> {{\n"
        "    it may only contain dimension points where {\n"
        "        it has the position</child>.\n"
        "    }\n"
        "}\n"
    )
    assert _first_definition_result(result).action_local_position_constraint_names == {}


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
        assert effect.modified_position is effect.statement.target_position.chain
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
        assert effect.modified_position is effect.statement.target_position.chain
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
        assert effect.modified_position is effect.statement.target_position.chain
        assert effect.target_action_name == f"action<{_FQUN}:/act>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/act>::position<b>"
        )

    def test_create_to_explicit_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
            f"define the potential action<{_FQUN}:/act> {{\n"
            "    define the position<run>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</other>::position<tp>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].action_body_effects) == 1
        effect = result.definition_results[0].action_body_effects[0]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position.chain
        assert effect.target_action_name == f"action<{_FQUN}:/other>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/other>::position<tp>"
        )

    def test_create_through_local_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        result = _validate_single_file(
            tmp_path,
            monkeypatch,
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
            "        create a dimension point in position<local>::action</other>::position<tp>.\n"
            "    }\n"
            "}\n",
        )
        assert len(result.definition_results[0].action_body_effects) == 1
        effect = result.definition_results[0].action_body_effects[0]
        assert isinstance(effect.statement, ast.CreateDimensionPointStatement)
        assert effect.modified_position is effect.statement.target_position.chain
        assert effect.target_action_name == f"action<{_FQUN}:/other>"
        assert (
            effect.affected_position_qualified_chained_name
            == f"action<{_FQUN}:/other>::position<tp>"
        )
