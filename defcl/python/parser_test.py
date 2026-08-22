# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import Path

import pytest

from defcl.python import exceptions, parser
from defcl.testdata.valid.schemas import (
    integers_pb2,
    nested_messages_pb2,
    repeated_messages_pb2,
    single_toplevel_pb2,
    strings_pb2,
)

_TESTDATA_PATH = Path(__file__).parent.parent / "testdata" / "valid"


class TestParseValidFiles:
    _parser: parser.Parser = parser.Parser()

    def test_single_toplevel(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "single_toplevel.defcl",
            single_toplevel_pb2.SingleToplevelFile,
        )
        assert result.project.universe_name == "example"

    def test_integers(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "integers.defcl",
            integers_pb2.IntegersFile,
        )
        assert result.config.positive == 10
        assert result.config.negative == -5
        assert result.config.zero == 0

    def test_strings(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "strings.defcl",
            strings_pb2.StringsFile,
        )
        assert result.config.basic == "hello"
        assert result.config.with_newline == "line1\nline2"

    def test_nested_messages(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "nested_messages.defcl",
            nested_messages_pb2.NestedMessagesFile,
        )
        assert result.project.name == "my_project"
        assert result.project.database.host == "localhost"
        assert result.project.database.port == 5432
        assert result.project.database.pool.max_connections == 10

    def test_empty_repeated_messages(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "empty_repeated_messages.defcl",
            repeated_messages_pb2.RepeatedMessagesFile,
        )
        assert len(result.project.dependencies) == 0

    def test_repeated_messages(self):
        result = self._parser.parse_file(
            _TESTDATA_PATH / "repeated_messages.defcl",
            repeated_messages_pb2.RepeatedMessagesFile,
        )
        assert len(result.project.dependencies) == 2


class TestPathNamePropagation:
    _parser: parser.Parser = parser.Parser()

    def test_syntax_error_includes_path_name(self):
        with pytest.raises(exceptions.BooleanNotSupportedError) as exc_info:
            self._parser.parse(
                "a: {\n    b: true\n}\n",
                single_toplevel_pb2.SingleToplevelFile,
                path_name="my/config.defcl",
            )
        assert str(exc_info.value).startswith('File "my/config.defcl"')

    def test_semantic_error_includes_path_name(self):
        with pytest.raises(exceptions.RepeatedFieldWithoutBracketsError) as exc_info:
            self._parser.parse(
                'project: {\n    dependencies: {\n        universe: "x"\n    }\n}\n',
                repeated_messages_pb2.RepeatedMessagesFile,
                path_name="my/config.defcl",
            )
        assert str(exc_info.value).startswith('File "my/config.defcl"')

    def test_parse_file_includes_path_in_error(self):
        with pytest.raises(exceptions.MissingTrailingNewlineError) as exc_info:
            self._parser.parse_file(
                _TESTDATA_PATH
                / ".."
                / "invalid"
                / "syntax"
                / "file_format"
                / "no_trailing_newline.defcl",
                single_toplevel_pb2.SingleToplevelFile,
            )
        assert 'no_trailing_newline.defcl"' in str(exc_info.value)


class TestParseFile:
    _parser: parser.Parser = parser.Parser()

    def test_reads_utf8_from_file(self, tmp_path: Path):
        path = tmp_path / "utf8.defcl"
        path.write_bytes(b'project: {\n    universe_name: "caf\xc3\xa9"\n}\n')
        result = self._parser.parse_file(path, single_toplevel_pb2.SingleToplevelFile)
        assert result.project.universe_name == "café"

    def test_preserves_carriage_return_from_file(self, tmp_path: Path):
        path = tmp_path / "crlf.defcl"
        path.write_bytes(b'project: {\r\n    universe_name: "example"\r\n}\r\n')
        with pytest.raises(exceptions.CarriageReturnNotAllowedError):
            self._parser.parse_file(path, single_toplevel_pb2.SingleToplevelFile)
