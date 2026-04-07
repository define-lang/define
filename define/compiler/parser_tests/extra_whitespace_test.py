# pyright: reportUnusedCallResult=false
"""Extra whitespace parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse


def test_file_all_spaces(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("   ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_file_spaces_and_newlines_only(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(" \n  \n ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_extra_space_after_define_in_position_definition(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define  the potential position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token.startswith("define  the potential position<")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_extra_space_after_the_in_position_definition(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the  potential position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token.startswith("define the  potential position<")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_extra_space_after_potential_in_position_definition(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the potential  position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token.startswith("define the potential  position<")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_extra_space_after_potential_in_action_definition(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the potential  action<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.token.startswith("define the potential  action<")
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_extra_space_in_local_position_definition_in_action_block(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    define  the position<my_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.startswith("define  the position<")
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_extra_space_in_trigger_clause_in_action_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens  when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token.startswith("it happens  when {")
    assert exc_info.value.line == 3
    assert exc_info.value.column == 5


def test_extra_space_in_and_it_does_clause_in_action_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    }  and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == " "
    assert exc_info.value.line == 5
    assert exc_info.value.column == 6


def test_extra_space_after_and_it_does_before_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does  {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == " "
    assert exc_info.value.line == 5
    assert exc_info.value.column == 18


def test_extra_space_before_local_name_in_position_requirement_statement(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position  </child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == " "
    assert exc_info.value.token.type == "SPACE"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 28
    assert exc_info.value.name == " "
