# pyright: reportUnusedCallResult=false
import lark
import pytest

from define.compiler import ast, name_parser, parser_exceptions


def _make_name_content_token(value: str, line: int, column: int) -> lark.Token:
    return lark.Token(
        "NAME_CONTENT",
        value,
        line=line,
        column=column,
        end_line=line,
        end_column=column + len(value),
        start_pos=0,
        end_pos=len(value),
    )


def _require_fqun(name: ast.GlobalName) -> ast.Fqun:
    assert name.fqun is not None
    return name.fqun


def test_parse_local_name():
    token = _make_name_content_token("my_local", line=2, column=10)
    local_name = name_parser.parse_local_name(token)

    assert local_name.name == "my_local"
    assert local_name.position.line == 2
    assert local_name.position.column == 10


def test_parse_global_name_definition_standard_form():
    token = _make_name_content_token("standard:/root/path", line=3, column=5)
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert name.path.path_string == "/root/path"
    assert fqun.universe.name == "standard"
    assert fqun.authority is None
    assert fqun.multiverse is None


def test_parse_global_name_definition_three_part_fqun():
    token = _make_name_content_token(
        "mv:define-lang.org/core/lib:runtime:/do/work",
        line=1,
        column=1,
    )
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)

    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.domain == "define-lang.org"
    assert fqun.authority.path == ["core", "lib"]
    assert fqun.universe.name == "runtime"
    assert name.path.path_string == "/do/work"


def test_parse_global_name_reference_short_form():
    token = _make_name_content_token("/position/path", line=6, column=12)
    name = name_parser.parse_global_name_reference(token)

    assert name.fqun is None
    assert name.path.path_string == "/position/path"


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
    assert fqun.authority is not None
    assert fqun.authority.domain == "acme.dev"
    assert fqun.universe.name == "tooling"
    assert name.path.path_string == "/action/run"


def test_global_name_definition_requires_fqun():
    token = _make_name_content_token("/path/only", line=1, column=30)
    with pytest.raises(
        parser_exceptions.GlobalNameDefinitionRequiresFqunError
    ) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 1
    assert error.value.column == 30


def test_global_name_reference_rejects_local_name_shape():
    token = _make_name_content_token("child_name", line=4, column=20)
    with pytest.raises(
        parser_exceptions.GlobalNamePathMustStartWithSlashError
    ) as error:
        name_parser.parse_global_name_reference(token)
    assert error.value.line == 4
    assert error.value.column == 20


def test_global_name_path_rejects_empty_segment():
    token = _make_name_content_token("standard:/a//b", line=2, column=5)
    with pytest.raises(parser_exceptions.GlobalNamePathEmptySegmentError) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 2
    assert error.value.column == 17


def test_global_name_path_rejects_trailing_slash():
    token = _make_name_content_token("standard:/a/b/", line=2, column=5)
    with pytest.raises(parser_exceptions.GlobalNamePathTrailingSlashError) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 2
    assert error.value.column == 18


def test_global_name_definition_rejects_too_many_fqun_parts():
    token = _make_name_content_token("a:b:c:d:/x", line=1, column=1)
    with pytest.raises(parser_exceptions.GlobalNameInvalidFqunFormatError) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 1
    assert error.value.column == 1


def test_global_name_rejects_empty_authority_path_segment():
    token = _make_name_content_token("example.com//repo:my_lib:/path", line=3, column=7)
    with pytest.raises(
        parser_exceptions.GlobalNameEmptyAuthorityPathSegmentError
    ) as error:
        name_parser.parse_global_name_definition(token)
    assert error.value.line == 3
    assert error.value.column == 7


def test_positions_for_fqun_and_path_segments():
    token = _make_name_content_token(
        "mv:define-lang.org:runtime:/alpha/beta",
        line=9,
        column=15,
    )
    name = name_parser.parse_global_name_definition(token)
    fqun = _require_fqun(name)
    assert token.column is not None
    assert isinstance(name, ast.GlobalNameDefinition)
    assert fqun.universe.position.column > token.column
    assert name.path.segments[0].position.line == 9
    assert name.path.segments[0].position.column > token.column


def test_name_parser_error_message_format():
    token = _make_name_content_token("standard:/a//b", line=2, column=5)
    with pytest.raises(parser_exceptions.GlobalNamePathEmptySegmentError) as error:
        name_parser.parse_global_name_definition(token)
    expected = "\n".join(
        [
            "line 2, column 17",
            "standard:/a//b",
            "Global name path must not contain '//'",
        ]
    )
    assert str(error.value) == expected
