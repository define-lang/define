# pyright: reportUnusedCallResult=false
"""Local name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_local_name_simple(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my_pos"]


def test_local_name_underscore_start(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_private>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["_private"]


def test_local_name_with_digits(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<pos_1>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["pos_1"]


def test_local_name_single_char(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<x>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["x"]


def test_local_name_single_underscore(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["_"]


def test_local_name_starting_with_digit(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<2bad>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["2bad"]


def test_local_name_uppercase(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<MyPos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["MyPos"]


def test_local_name_missing_open_angle(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the positionmy_pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingOpenAngleBracket)
    assert str(result.exception.token) == "my_pos"
    assert result.exception.line == 2
    assert result.exception.column == 24


def test_local_name_empty(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.EmptyName)
    assert str(result.exception.token) == ">"
    assert result.exception.line == 2
    assert result.exception.column == 25


def test_local_name_with_slash(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my/pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidLocalNameCharacter)
    assert result.exception.char == "/"
    assert result.exception.line == 2
    assert result.exception.column == 25


def test_local_name_with_colon(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my:pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidLocalNameCharacter)
    assert result.exception.char == ":"
    assert result.exception.line == 2
    assert result.exception.column == 25


def test_local_name_with_global_short_form(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position</mypos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidLocalNameCharacter)
    assert result.exception.char == "/"
    assert result.exception.line == 2
    assert result.exception.column == 25


def test_local_name_with_global_long_form(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<mv:define-lang.org:other_universe:/mypos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.InvalidLocalNameCharacter)
    assert result.exception.char == ":"
    assert result.exception.line == 2
    assert result.exception.column == 25


def test_local_name_with_hyphen(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my-pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    ).tree
    assert tree is not None
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act"
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == ["my-pos"]
