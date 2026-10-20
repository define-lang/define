"""Value constraint parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import global_typed_names

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_value_constraint_short_name(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value</number/natural>.\n"
        + "    }\n"
        + "}\n"
    )
    assert global_typed_names(program) == [
        "position<mv:define-lang.org:parser:/item>",
        "value</number/natural>",
    ]


def test_value_constraint_full_name(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/item> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the value<standard:/number/natural>.\n"
        + "    }\n"
        + "}\n"
    )
    assert global_typed_names(program) == [
        "position<mv:define-lang.org:parser:/item>",
        "value<standard:/number/natural>",
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
    assert error.value.location.line == 3
    assert error.value.location.column == 26
    assert error.value.location.end_column == 33


def test_constraint_name_type_error_includes_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/item> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the thing</number>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_column == 25
