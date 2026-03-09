# pyright: reportUnusedCallResult=false
"""Trigger condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_trigger_condition_with_local_position(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_trigger_condition_with_short_global_position(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        the position</some_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/some_pos",
    ]


def test_trigger_condition_with_full_fqun_position(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        the position<mv:define-lang.org:parser:/some_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/some_pos",
    ]


def test_trigger_condition_with_action_type(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        the action<my_act> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["my_act"]


def test_trigger_condition_with_comments(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        the position<run> has a dimension point.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_trigger_condition_with_blank_lines(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "\n"
        + "        the position<run> has a dimension point.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_trigger_condition_with_chained_local_position_reference(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos>::action<my_act>::position<inner> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == [
        "my_pos",
        "my_pos",
        "my_act",
        "inner",
    ]


def test_trigger_condition_with_chained_global_position_reference(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        the position</pos>::action</act>::position</inner> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/pos",
        "/act",
        "/inner",
    ]


def test_trigger_block_same_line_no_space(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {} and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.EmptyBlock)
    assert result.exception.token == "}"
    assert result.exception.token.type == "RBRACE"
    assert result.exception.line == 3
    assert result.exception.column == 22


def test_trigger_block_same_line_with_space(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when { } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAfterOpenBrace)
    assert result.exception.token == " "
    assert result.exception.token.type == "SPACE"
    assert result.exception.line == 3
    assert result.exception.column == 22


def test_trigger_block_closing_brace_same_line(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {}\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.EmptyBlock)
    assert result.exception.token == "}"
    assert result.exception.token.type == "RBRACE"
    assert result.exception.line == 3
    assert result.exception.column == 22


def test_empty_trigger_block_is_error(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        result.exception, parser_exceptions.MissingTriggerConditionContent
    )
    assert result.exception.token == "}"
    assert result.exception.token.type == "RBRACE"
    assert result.exception.line == 3
    assert result.exception.column == 5


def test_invalid_content_in_trigger_block(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        nonsense\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidTriggerConditionsBlock)
    assert result.exception.token == "nonsense"
    assert result.exception.token.type == "LOCAL_NAME_CONTENT"
    assert result.exception.line == 4
    assert result.exception.column == 9


def test_missing_terminator_after_trigger_condition(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminator)
    assert result.exception.token == "\n"
    assert result.exception.token.type == "NEWLINE"
    assert result.exception.line == 4
    assert result.exception.column == 48


def test_trigger_condition_chained_trailing_separator(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>::position</y>:: has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.line == 4
    assert result.exception.column == 42


def test_trigger_condition_chained_single_trailing_separator(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>:: has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedNameType)
    assert result.exception.line == 4
    assert result.exception.column == 28


def test_missing_space_before_has_a_dimension_point(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(
        result.exception, parser_exceptions.InvalidHasADimensionPointSyntax
    )
    assert result.exception.line == 4
    assert result.exception.column == 26


def test_missing_has_a_dimension_point(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(
        result.exception, parser_exceptions.InvalidHasADimensionPointSyntax
    )
    assert result.exception.token == "."
    assert result.exception.token.type == "DOT"
    assert result.exception.line == 4
    assert result.exception.column == 26
