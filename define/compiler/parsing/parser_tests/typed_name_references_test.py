# pyright: reportUnusedCallResult=false
"""Typed global-name reference parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import global_typed_names

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_typed_global_name_reference_short_position_name(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert global_typed_names(program) == [
        "position<mv:define-lang.org:parser:/root>",
        "position</child>",
    ]


def test_typed_global_name_reference_short_action_name(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert global_typed_names(program) == [
        "position<mv:define-lang.org:parser:/root>",
        "action</do_work>",
    ]


def test_typed_global_name_reference_full_name(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/root> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action<mv:define-lang.org:parser:/do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    assert global_typed_names(program) == [
        "position<mv:define-lang.org:parser:/root>",
        "action<mv:define-lang.org:parser:/do_work>",
    ]


def test_typed_global_name_reference_local_style_name_is_global_terminal(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/root> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position<foo>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_column == 31
