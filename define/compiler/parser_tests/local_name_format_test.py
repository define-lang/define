# pyright: reportUnusedCallResult=false
"""Local name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_local_name_simple(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos", "my_pos"]


def test_local_name_underscore_start(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_private>.\n"
        + "    it happens when {\n"
        + "        the position<_private> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "_private",
        "_private",
    ]


def test_local_name_with_digits(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<pos_1>.\n"
        + "    it happens when {\n"
        + "        the position<pos_1> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["pos_1", "pos_1"]


def test_local_name_single_char(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<x>.\n"
        + "    it happens when {\n"
        + "        the position<x> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["x", "x"]


def test_local_name_single_underscore(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_>.\n"
        + "    it happens when {\n"
        + "        the position<_> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["_", "_"]


def test_local_name_starting_with_digit(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<2bad>.\n"
        + "    it happens when {\n"
        + "        the position<2bad> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["2bad", "2bad"]


def test_local_name_uppercase(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<MyPos>.\n"
        + "    it happens when {\n"
        + "        the position<MyPos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["MyPos", "MyPos"]


def test_local_name_with_space(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position< >.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.line == 3
    assert exc_info.value.column == 25


def test_local_name_first_char_colon(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<:>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 25


def test_local_name_first_char_slash(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position</>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 25


def test_local_name_missing_open_angle(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the positionmy_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "my_pos"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 24
    assert exc_info.value.name == "my_pos"


def test_local_name_empty(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 25


def test_local_name_with_angle_bracket(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<<>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", "<", "run"]


def test_local_name_dot_then_angle_bracket(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<.<>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["run", ".<", "run"]


def test_local_name_dot_then_slash(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<./>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 26


def test_local_name_brace_then_slash(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<}/>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 26


def test_local_name_angle_bracket_then_slash(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<</>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 26


def test_local_name_angle_bracket_then_colon(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<<:>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 26


def test_local_name_with_slash(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<my/pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 3
    assert exc_info.value.column == 27


def test_local_name_with_colon(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<my:pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 27


def test_local_name_with_global_short_form(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position</mypos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 25


def test_local_name_with_global_long_form(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<mv:define-lang.org:other_universe:/mypos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a dimension point.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.line == 3
    assert exc_info.value.column == 27


def test_local_name_with_hyphen(parse: Parse) -> None:
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my-pos>.\n"
        + "    it happens when {\n"
        + "        the position<my-pos> has a dimension point.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my-pos", "my-pos"]
