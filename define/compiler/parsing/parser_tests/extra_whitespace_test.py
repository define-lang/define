# pyright: reportUnusedCallResult=false
"""Extra whitespace parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_file_all_spaces(parse: Parse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("   ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_file_spaces_and_newlines_only(parse: Parse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(" \n  \n ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_extra_space_after_define_in_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define  the potential position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 7
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 8


def test_extra_space_after_the_in_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the  potential position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 11
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 12


def test_extra_space_after_potential_in_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the potential  position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 21
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 22


def test_extra_space_before_missing_space_in_position_definition(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define  thepotential position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 7
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 8


def test_spaces_after_define_at_end_of_line(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define  \n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 8


def test_space_after_define_at_end_of_line(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define \n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 7


def test_extra_space_after_potential_in_action_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the potential  action<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 21
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 22


def test_extra_space_in_local_position_definition_in_action_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    define  the position<my_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 11
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 12


def test_extra_space_in_trigger_clause_in_action_block(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens  when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 16


def test_extra_space_in_and_it_does_clause_in_action_block(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }  and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 7


def test_extra_space_after_and_it_does_before_open_brace(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does  {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 18
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 19


def test_extra_space_before_local_name_in_quality_assignment_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.SpaceBeforeOpenAngleBracket) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position  </child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 28
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 29


def test_space_before_name_in_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.SpaceBeforeOpenAngleBracket) as exc_info:
        parse("define the potential position <mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 30


def test_extra_space_after_create_a_particle_in(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in  position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 30


def test_extra_space_before_to_in_move_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        move the particle in position<src>  to position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 43
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 44


def test_extra_space_after_to_in_move_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        move the particle in position<src> to  position<dest>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 47


def test_extra_space_after_the_in_trigger_condition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the  position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 12
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 13


def test_extra_space_before_has_a_particle(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>  has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 27


def test_extra_space_in_constructor_condition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        this  particle is created.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 13
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 14


def test_extra_space_in_action_statement_words(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create  a particle in position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 16


def test_extra_space_before_position_definition_brace(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>  {\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 64


def test_extra_space_before_encoding_in_encoding_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the  encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 15
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 16


def test_extra_space_in_encoding_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it  has the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 7
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 8


def test_extra_space_in_view_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it  is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 11
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 12


def test_extra_space_in_view_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may  only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 15
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 16


def test_extra_space_in_view_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the  view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 15
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 16


def test_extra_space_in_operation_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute  the operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 16
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 17
