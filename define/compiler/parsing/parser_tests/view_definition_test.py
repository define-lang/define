# pyright: reportUnusedCallResult=false
"""View definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


_OPERATION_PREFIX = "define the operation<mv:define-lang.org:parser:/add> {\n"

_OPERATION_SUFFIX = (
    "    it does {\n" + "        execute the encoding operation.\n" + "    }\n" + "}\n"
)


def test_value_constraint(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "VALUE") == ["value"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "/number",
    ]


def test_value_and_encoding_constraints(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value<mv:define-lang.org:parser:/number>.\n"
        + "            it has the encoding</decimal>.\n"
        + "        }\n"
        + "    }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "VALUE") == ["value"]
    assert get_tokens_by_type(tree, "ENCODING") == ["encoding"]
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/add",
        "mv:define-lang.org:parser:/number",
        "/decimal",
    ]


def test_requires_local_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view</left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 2
    assert error.value.column == 21
    assert error.value.char == "/"


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(_OPERATION_PREFIX + "    define the view<left>.\n" + _OPERATION_SUFFIX)
    assert error.value.line == 2
    assert error.value.column == 26
    assert error.value.token == "."


def test_read_and_written(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it is written.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "IT_IS_READ") == ["it is read"]
    assert get_tokens_by_type(tree, "IT_IS_WRITTEN") == ["it is written"]


def test_written_only(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "    define the view<left> {\n"
        + "        it is written.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "IT_IS_READ") == []
    assert get_tokens_by_type(tree, "IT_IS_WRITTEN") == ["it is written"]


def test_blank_lines_between_direction_statements(parse: Parse):
    tree = parse(
        _OPERATION_PREFIX
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "\n"
        + "        it is written.\n"
        + "\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + _OPERATION_SUFFIX
    )
    assert get_tokens_by_type(tree, "IT_IS_READ") == ["it is read"]
    assert get_tokens_by_type(tree, "IT_IS_WRITTEN") == ["it is written"]


def test_requires_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 3
    assert error.value.column == 9
    assert error.value.token == "it may only contain particles where"


def test_requires_direction_statement_in_empty_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 3
    assert error.value.column == 5
    assert error.value.token == "}"


def test_disallows_written_before_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is written.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 4
    assert error.value.column == 9
    assert error.value.token == "it is read"


def test_disallows_repeated_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 4
    assert error.value.column == 9
    assert error.value.token == "it is read"


def test_disallows_repeated_written(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "it is written"


def test_disallows_repeated_written_without_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is written.\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 4
    assert error.value.column == 9
    assert error.value.token == "it is written"


def test_disallows_read_after_read_and_written(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "it is read"


def test_disallows_direction_statement_after_constraint_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "        it is written.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 7
    assert error.value.column == 9
    assert error.value.token == "it is written"


def test_requires_constraint_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDefinitionBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 4
    assert error.value.column == 5
    assert error.value.token == "}"


def test_requires_constraint_block_after_both_directions(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDefinitionBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "it has the"


def test_disallows_direction_statement_in_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the position<p> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 3
    assert error.value.column == 9
    assert error.value.token == "it is read"


def test_requires_constraint(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionConstraintContent) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "}"


def test_disallows_literal_constraint(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the literal</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 5
    assert error.value.column == 24
    assert error.value.token == "literal"


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.QualityImplicationInWrongLocation) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it also assigns the position</a>.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.line == 3
    assert error.value.column == 9
    assert error.value.token == "it also assigns the"


def test_disallows_direction_statement_after_potential_position_constraint_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the potential position<mv:define-lang.org:parser:/p> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + "    it is read.\n"
            + "}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 5
    assert error.value.token == "it is read"


def test_disallows_direction_statement_after_local_position_constraint_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the position<p> {\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "        it is written.\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 6
    assert error.value.column == 9
    assert error.value.token == "it is written"


def test_disallows_global_context(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        parse(
            "define the view<left> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 1
    assert error.value.column == 1
    assert error.value.token == "define the view"


def test_disallows_action_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionDefinitionsBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 5
    assert error.value.token == "define the view"
