# pyright: reportUnusedCallResult=false
"""parse_file parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from pathlib import Path

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_parse_file(p: parser.Parser, tmp_path: Path):
    source = "define the potential position<standard:/path>.\n"
    file = tmp_path / "path.def"
    file.write_text(source, encoding="utf-8")
    tree, returned_source = p.parse_file(file)
    assert returned_source == source
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["path"]


def test_parse_file_preserves_crlf(p: parser.Parser, tmp_path: Path):
    source = "define the potential position<standard:/path>.\r\n"
    file = tmp_path / "path.def"
    file.write_bytes(source.encode("utf-8"))
    with pytest.raises(parser_exceptions.CarriageReturnError):
        _ = p.parse_file(file)


def test_parse_file_includes_path_in_error(p: parser.Parser, tmp_path: Path):
    source = "define the potential position<standard:/path>.\r\n"
    file = tmp_path / "path.def"
    file.write_bytes(source.encode("utf-8"))
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        _ = p.parse_file(file)
    assert str(file) in str(exc_info.value)
