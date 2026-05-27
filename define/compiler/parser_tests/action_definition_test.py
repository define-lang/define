# pyright: reportUnusedCallResult=false
"""Action definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import diagnostics, parser, parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_action_definition_without_body_is_error(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        parse("define the potential action<standard:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.token.type == "DOT"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 44


def test_action_definition_with_body_parses(parse: Parse) -> None:
    tree = parse(
        "define the potential action<standard:/path> {\n"
        + "    define the position<pp>.\n"
        + "    it happens when {\n"
        + "        the position<pp> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<noop>.\n"
        + "        create a particle in position<noop>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]


def test_action_definition_missing_open_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential actionstandard:/path>.\n")
    assert str(exc_info.value.token) == "standard:/path"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 28
    assert exc_info.value.name == "standard:/path"


def test_action_definition_empty_name_content(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse("define the potential action<>.\n")
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 29


def test_action_with_empty_inner_blocks(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_with_local_position_definition(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_action_with_constrained_local_position_definition(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the action</do_work>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/do_work",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_action_with_multiple_local_position_definitions(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "        the position<first_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "first_pos",
        "second_pos",
        "first_pos",
    ]


def test_action_with_mixed_local_position_definition_forms(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<first_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "first_pos",
        "second_pos",
        "first_pos",
    ]


def test_action_block_with_comments_and_blank_lines(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "\n"
        + "    # a comment\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_action_block_with_full_fqun(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/some/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/some/path"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_action_block_comment_after_trigger_open(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when { # comment\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_block_comment_after_action_close(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    } # comment\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_block_no_indentation(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a particle.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert len(result.diagnostics) == 3
    for i, d in enumerate(result.diagnostics):
        assert isinstance(d, diagnostics.IncorrectIndentationDiagnostic)
        assert d.location.line == i + 2
        assert d.expected_indent == 4
        assert d.actual_indent == 0
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(result.tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_block_blank_lines_in_trigger_block(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "\n"
        + "        the position<run> has a particle.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_block_blank_lines_in_action_block(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "\n"
        + "\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_block_with_local_position_definition_in_action_statements(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "inner_pos",
    ]


def test_action_block_with_multiple_local_position_definitions_in_action_statements(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<first_inner>.\n"
        + "        define the position<second_inner>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "first_inner",
        "second_inner",
    ]


def test_action_block_with_local_position_definitions_inside_and_outside_action_statements(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<outer_pos>.\n"
        + "    it happens when {\n"
        + "        the position<outer_pos> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "outer_pos",
        "outer_pos",
        "inner_pos",
    ]


def test_two_action_definitions_in_same_file(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/first> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
        + "define the potential action<mv:define-lang.org:parser:/second> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/first",
        "mv:define-lang.org:parser:/second",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "my_pos",
        "my_pos",
    ]


def test_action_block_missing_trigger_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<my_pos>.\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 1


def test_global_position_definition_not_allowed_in_action_definition_block(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.GlobalPositionDefinitionInLocalContext
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "define the potential position"
    assert exc_info.value.token.type == "DEFINE_THE_POTENTIAL_POSITION"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 5


def test_global_position_definition_not_allowed_in_action_statements_block(
    parse: Parse,
) -> None:
    with pytest.raises(
        parser_exceptions.GlobalPositionDefinitionInLocalContext
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "define the potential position"
    assert exc_info.value.token.type == "DEFINE_THE_POTENTIAL_POSITION"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_action_block_missing_action_statements_block(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 6


def test_action_block_missing_outer_close(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
        )
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 6
    assert exc_info.value.column == 6


def test_action_block_extra_space_before_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path>  {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 1
    assert exc_info.value.column == 61


def test_action_block_no_newline_after_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        parse("define the potential action<mv:define-lang.org:parser:/path> {}\n")
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_action_block_missing_newline_after_outer_open_brace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterOpenBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/path> { it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_action_block_missing_newline_after_inner_close(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }}\n"
        )
    assert str(exc_info.value.token) == "}"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 6


def test_trigger_and_action_on_wrong_line(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }\n"
            + "    and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.line == 5
    assert exc_info.value.column == 6


def test_local_position_after_trigger_and_action(parse: Parse) -> None:
    with pytest.raises(
        parser_exceptions.InvalidPositionDefinitionLocationInAction
    ) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    define the position<late_pos>.\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "define the position"
    assert exc_info.value.line == 7
    assert exc_info.value.column == 5


def test_second_trigger_and_action_block_pair_not_allowed(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "it happens when"
    assert exc_info.value.line == 7
    assert exc_info.value.column == 5


def test_missing_close_brace_followed_by_global_definition(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "define the potential position<mv:define-lang.org:parser:/my_action>.\n"
        )
    assert str(exc_info.value.token) == "define the potential position"
    assert exc_info.value.line == 7
    assert exc_info.value.column == 1


def test_action_statements_block_invalid_statement(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        nonsense\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "nonsense"
    assert exc_info.value.line == 6
    assert exc_info.value.column == 9


def test_action_statements_block_with_create_particle_local_position(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
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
    ]


def test_action_statements_block_with_create_particle_short_global_position(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_create_particle_full_global_position(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "mv:define-lang.org:parser:/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_create_particle_chain(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<to>::action</deposit>::position<run>.\n"
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
        "to",
        "run",
    ]


def test_action_statements_block_with_create_particle_short_global_chain(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/to",
        "/deposit",
        "/run",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "run"]


def test_action_statements_block_with_create_particle_any_typed_chain(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/start",
        "/end",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "mid",
    ]


def test_action_statements_block_with_mixed_statements_and_multiple_create_particles(
    parse: Parse,
) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        create a particle in position<inner_pos>.\n"
        + "        create a particle in position</global_run>::action</deposit>::position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/my_action",
        "/global_run",
        "/deposit",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "inner_pos",
        "inner_pos",
        "inner_pos",
    ]
