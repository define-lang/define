# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import PurePosixPath

import lark_cython
import pytest

from define.compiler import ast, name_parser, parser_exceptions


def _make_name_content_token(value: str, line: int, column: int) -> lark_cython.Token:
    return lark_cython.Token(
        "NAME_CONTENT",
        value,
        line=line,
        column=column,
        end_line=line,
        end_column=column + len(value),
    )


def _require_fqun(name: ast.GlobalNameContent[ast.Fqun | None]) -> ast.Fqun:
    assert name.fqun is not None
    return name.fqun


def test_parse_local_name():
    token = _make_name_content_token("my_local", line=2, column=10)
    local_name = name_parser.parse_local_name(token)

    assert local_name.name == "my_local"
    assert local_name.location.line == 2
    assert local_name.location.column == 10


def test_parse_global_name_definition_standard_form():
    token = _make_name_content_token("standard:/root/path", line=3, column=5)
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert name.path.name == "/root/path"
    assert name.path.location.column == 14
    assert name.path.location.end_column == 24
    assert fqun.universe.name == "standard"
    assert fqun.universe.location.column == 5
    assert fqun.universe.location.end_column == 13
    assert fqun.authority is None
    assert fqun.multiverse is None


def test_parse_global_name_definition_three_part_fqun():
    token = _make_name_content_token(
        "mv:define-lang.org:runtime:/do/work",
        line=1,
        column=1,
    )
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.multiverse.location.column == 1
    assert fqun.multiverse.location.end_column == 3
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.authority.location.column == 4
    assert fqun.authority.location.end_column == 19
    assert fqun.universe.name == "runtime"
    assert fqun.universe.location.column == 20
    assert fqun.universe.location.end_column == 27
    assert name.path.name == "/do/work"


def test_parse_global_name_definition_two_part_fqun():
    token = _make_name_content_token(
        "my.domain.com:my_lib:/some/path",
        line=1,
        column=5,
    )
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert fqun.authority is not None
    assert fqun.authority.name == "my.domain.com"
    assert fqun.authority.location.column == 5
    assert fqun.authority.location.end_column == 18
    assert fqun.universe.name == "my_lib"
    assert fqun.universe.location.column == 19
    assert fqun.universe.location.end_column == 25
    assert fqun.multiverse is None
    assert name.path.name == "/some/path"


def test_parse_global_name_definition_single_char_universe():
    token = _make_name_content_token("x:/path", line=1, column=1)
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert fqun.universe.name == "x"
    assert name.path.name == "/path"


def test_parse_global_name_reference_short_form():
    token = _make_name_content_token("/position/path", line=6, column=12)
    name = name_parser.parse_global_name_reference(token)

    assert name.fqun is None
    assert name.path.name == "/position/path"


def test_parse_global_name_reference_leading_colon_treated_as_path():
    token = _make_name_content_token(":/path", line=1, column=1)
    name = name_parser.parse_global_name_reference(token)

    assert name.fqun is None
    assert name.path.name == ":/path"


def test_parse_global_name_reference_full_form():
    token = _make_name_content_token(
        "mv:acme.dev:tooling:/action/run",
        line=8,
        column=4,
    )
    name = name_parser.parse_global_name_reference(token)
    fqun = _require_fqun(name)

    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.multiverse.location.column == 4
    assert fqun.multiverse.location.end_column == 6
    assert fqun.authority is not None
    assert fqun.authority.name == "acme.dev"
    assert fqun.authority.location.column == 7
    assert fqun.authority.location.end_column == 15
    assert fqun.universe.name == "tooling"
    assert fqun.universe.location.column == 16
    assert fqun.universe.location.end_column == 23
    assert name.path.name == "/action/run"
    assert name.path.location.column == 24
    assert name.path.location.end_column == 35


def test_parse_global_name_reference_full_form_authority_with_path():
    token = _make_name_content_token(
        "mv:acme.dev/team/repo:tooling:/action/run",
        line=8,
        column=4,
    )
    name = name_parser.parse_global_name_reference(token)
    fqun = _require_fqun(name)

    assert fqun.authority is not None
    assert fqun.authority.name == "acme.dev/team/repo"
    assert fqun.universe.name == "tooling"
    assert name.path.name == "/action/run"


def test_parse_global_name_reference_bare_slash():
    token = _make_name_content_token("/", line=1, column=1)
    name = name_parser.parse_global_name_reference(token)

    assert name.fqun is None
    assert name.path.name == "/"


def test_global_name_definition_rejects_bare_slash():
    token = _make_name_content_token("/", line=1, column=10)
    with pytest.raises(
        parser_exceptions.DefinitionGlobalNameContentRequiresFqun
    ) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.context == "/"
    assert error.value.line == 1
    assert error.value.column == 10


def test_global_name_definition_requires_fqun():
    token = _make_name_content_token("/path/only", line=1, column=30)
    with pytest.raises(
        parser_exceptions.DefinitionGlobalNameContentRequiresFqun
    ) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.context == "/path/only"
    assert error.value.line == 1
    assert error.value.column == 30


def test_global_name_definition_rejects_too_many_fqun_parts():
    token = _make_name_content_token("a:b:c:d:/x", line=1, column=1)
    with pytest.raises(parser_exceptions.GlobalNameInvalidFqunFormat) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 1
    assert error.value.column == 1


def test_global_name_reference_rejects_too_many_fqun_parts():
    token = _make_name_content_token(
        "mv:define-lang.org:parser:extra:/text", line=5, column=52
    )
    file_path = PurePosixPath("set_value.dfn")
    with pytest.raises(parser_exceptions.GlobalNameInvalidFqunFormat) as error:
        name_parser.parse_global_name_reference(token, file_path)
    assert error.value.line == 5
    assert error.value.column == 52
    assert error.value.context == "mv:define-lang.org:parser:extra:/text"
    assert error.value.file_path == file_path


def test_positions_for_fqun_and_path():
    token = _make_name_content_token(
        "mv:define-lang.org:runtime:/alpha/beta",
        line=9,
        column=15,
    )
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)
    assert token.column is not None
    assert isinstance(name, ast.DefinitionGlobalNameContent)
    assert fqun.universe.location.column > token.column
    assert name.path.location.line == 9
    assert name.path.location.column > token.column


def test_parse_literal_content():
    token = _make_name_content_token(' Hello 世界 # <>:{} \\" \\\\ \\n \\\\n ', 3, 20)
    assert (
        name_parser.parse_literal_content(token) == ' Hello 世界 # <>:{} " \\ \n \\n '
    )


def test_parse_literal_content_invalid_escape():
    token = _make_name_content_token(r"hello\tworld", 3, 20)
    file_path = PurePosixPath("set_value.dfn")
    with pytest.raises(parser_exceptions.InvalidLiteralEscape) as error:
        name_parser.parse_literal_content(token, file_path)
    assert error.value.line == 3
    assert error.value.column == 26
    assert error.value.char == "t"
    assert error.value.file_path == file_path


@pytest.mark.parametrize("escape", [r"\>", r"\:"])
def test_parse_literal_content_invalid_punctuation_escapes(escape: str):
    token = _make_name_content_token(escape, 2, 10)
    with pytest.raises(parser_exceptions.InvalidLiteralEscape) as error:
        name_parser.parse_literal_content(token)
    assert error.value.line == 2
    assert error.value.column == 11
    assert error.value.char == escape[1]


@pytest.mark.parametrize(
    "char",
    [
        "\x00",
        "\t",
        "\r",
        "\x7f",
        "\x85",
        "\xa0",
        "\u2028",
        "\u2029",
        "\ud800",
        "\ufeff",
    ],
)
def test_parse_literal_content_invalid_file_characters(char: str):
    token = _make_name_content_token("before" + char + "after", 4, 10)
    with pytest.raises(parser_exceptions.InvalidLiteralCharacter) as error:
        name_parser.parse_literal_content(token)
    assert error.value.line == 4
    assert error.value.column == 16
    assert error.value.char == char
