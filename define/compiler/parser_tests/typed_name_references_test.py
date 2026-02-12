# pyright: reportUnusedCallResult=false
"""Typed global-name reference parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_typed_global_name_reference_short_position_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["root", "child"]


def test_typed_global_name_reference_short_action_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["root", "do_work"]


def test_typed_global_name_reference_full_name(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain dimension points where {\n"
        + "        it has the action<mv:define-lang.org:parser:/do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["mv", "mv"]
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [
        "define-lang.org",
        "define-lang.org",
    ]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["parser", "parser"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["root", "do_work"]


def test_typed_global_name_reference_rejects_local_name(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse(
            "define the potential position<mv:define-lang.org:parser:/root> {\n"
            + "    it may only contain dimension points where {\n"
            + "        it has the position<child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert str(exc_info.value.token) == "child"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 29
