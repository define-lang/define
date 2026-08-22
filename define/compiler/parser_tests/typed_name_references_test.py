# pyright: reportUnusedCallResult=false
"""Typed global-name reference parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_typed_global_name_reference_short_position_name(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "/child",
    ]


def test_typed_global_name_reference_short_action_name(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "/do_work",
    ]


def test_typed_global_name_reference_full_name(parse: Parse) -> None:
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action<mv:define-lang.org:parser:/do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/root",
        "mv:define-lang.org:parser:/do_work",
    ]


def test_typed_global_name_reference_local_style_name_is_global_terminal(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/root> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position<foo>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == "foo"
    assert exc_info.value.token.type == "LOCAL_NAME_CONTENT"
    assert exc_info.value.line == 3
    assert exc_info.value.column == 29
