# pyright: reportUnusedCallResult=false
"""Value setting statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler import parser
    from define.compiler.parser_tests.conftest import Parse


def test_action_statements_block_with_value_setting_local_positions(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<source> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "source",
        "dest",
    ]


def test_action_statements_block_with_value_setting_short_global_positions(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position</source> to position</dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/source",
        "/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_value_setting_full_global_positions(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<mv:define-lang.org:parser:/source> to position<mv:define-lang.org:parser:/dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/source",
        "mv:define-lang.org:parser:/dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_value_setting_chained_target(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src>::action</deposit>::position<inner> to position<dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "inner",
        "dest",
    ]


def test_action_statements_block_with_value_setting_chained_source(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src> to position<dest>::action</deposit>::position<inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "dest",
        "inner",
    ]


def test_action_statements_block_with_value_setting_both_chained(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<src>::action</a1> to position<dest>::action</a2>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/a1",
        "/a2",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "src",
        "dest",
    ]


def test_action_statements_block_with_mixed_create_and_move_statements(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "        set the value of position<run> to position<done>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "run",
        "run",
        "done",
    ]


def test_action_statements_block_with_value_setting_mixed_local_and_global(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        set the value of position<local_src> to position</global_dest>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_dest",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "local_src",
    ]


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
    + "    it happens when {\n"
    + "        this particle is created.\n"
    + "    } and it does {\n"
)


def test_missing_to(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        parse(
            _ACTION_PREFIX + "        set the value of position<dest>.\n" + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 40
    assert error.value.token == "."


def test_missing_source(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrActionOrLiteral) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to .\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 44
    assert error.value.token == "."


def test_missing_target(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        parse(_ACTION_PREFIX + "        set the value of .\n" + "    }\n}\n")
    assert error.value.line == 5
    assert error.value.column == 26
    assert error.value.token == "."


def test_missing_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedChainSeparatorOrTerminator) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest> to position<src>\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 57
    assert error.value.token == "\n"


def test_value_setting_outside_action(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        parse("set the value of position<dest> to position<src>.\n")
    assert error.value.line == 1
    assert error.value.column == 1
    assert error.value.token == "set the value of "


def test_missing_to_at_eof(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        parse(_ACTION_PREFIX + "        set the value of position<dest>")
    assert error.value.line == 5
    assert error.value.column == 39
    assert error.value.token == ""


def test_missing_to_after_chained_target(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueSettingStatementSyntax) as error:
        parse(
            _ACTION_PREFIX
            + "        set the value of position<dest>::position<child>.\n"
            + "    }\n}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 57
    assert error.value.token == "."


def test_missing_to_during_transformation(p: parser.Parser):
    result = p.parse_and_transform(
        _ACTION_PREFIX
        + "        move the particle in position<src> to position<dest>.\n"
        + "        set the value of position<dest>"
    )
    assert result.diagnostics == []
    assert isinstance(
        result.exception, parser_exceptions.InvalidValueSettingStatementSyntax
    )
    assert result.exception.line == 6
    assert result.exception.column == 39
    assert result.exception.token == ""


def test_missing_move_to_after_value_setting(p: parser.Parser):
    result = p.parse_and_transform(
        _ACTION_PREFIX
        + "        set the value of position<dest> to position<src>.\n"
        + "        move the particle in position<src>.\n"
        + "    }\n}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidMoveStatementSyntax)
    assert result.exception.line == 6
    assert result.exception.column == 43
    assert result.exception.token == "."
