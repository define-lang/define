# pyright: reportUnusedCallResult=false
"""Typed global-name reference parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_typed_global_name_reference_short_position_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "/child",
    ]


def test_typed_global_name_reference_short_action_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "/do_work",
    ]


def test_typed_global_name_reference_full_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action<mv:define-lang.org:parser:/do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "mv:define-lang.org:parser:/do_work",
    ]


def test_typed_global_name_reference_local_style_name_is_global_terminal(
    p: parser.Parser,
) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position<foo>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "foo",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == []
