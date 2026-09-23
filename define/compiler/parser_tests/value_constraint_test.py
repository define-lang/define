"""Value constraint parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_value_constraint_short_name(parse: Parse):
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value</number/rational>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/item",
        "/number/rational",
    ]
    assert get_tokens_by_type(tree, "VALUE") == ["value"]


def test_value_constraint_full_name(parse: Parse):
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value<standard:/number/rational>.\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/item",
        "standard:/number/rational",
    ]


def test_value_constraint_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/item> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value<rational>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.token == "rational"
    assert error.value.line == 3
    assert error.value.column == 26


def test_constraint_name_type_error_includes_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/item> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the thing</number>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.token == "thing<"
    assert error.value.line == 3
    assert error.value.column == 20
    assert error.value.message_format == "Expected 'position', 'action', or 'value'."
