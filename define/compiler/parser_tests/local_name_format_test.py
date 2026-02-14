# pyright: reportUnusedCallResult=false
"""Local name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

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
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "my_pos",
    ]


def test_local_name_underscore_start(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_private>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "_private",
    ]


def test_local_name_with_digits(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<pos_1>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "pos_1",
    ]


def test_local_name_single_char(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<x>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "x",
    ]


def test_local_name_single_underscore(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "_",
    ]


def test_local_name_starting_with_digit(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<2bad>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "2bad",
    ]


def test_local_name_uppercase(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<MyPos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "MyPos",
    ]


def test_local_name_missing_open_angle(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracketError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the positionmy_pos>.\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "my_pos"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 24


def test_local_name_empty(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyNameError) as exc_info:
        p.parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<>.\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 25


def test_local_name_with_hyphen(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my-pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "my-pos",
    ]


def test_local_name_with_slash(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my/pos>.\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "my/pos",
    ]
