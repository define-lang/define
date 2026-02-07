from pathlib import Path

from defcl.python import parser
from defcl.testdata.valid.schemas import (
    integers_pb2,
    repeated_messages_pb2,
    single_toplevel_pb2,
    strings_pb2,
)

_TESTDATA_PATH = Path(__file__).parent.parent / "testdata" / "valid"


class TestParseValidFiles:
    def test_single_toplevel(self):
        result = parser.parse_file(
            _TESTDATA_PATH / "single_toplevel.defcl",
            single_toplevel_pb2.SingleToplevelFile,
        )
        assert result.project.universe_name == "example"

    def test_integers(self):
        result = parser.parse_file(
            _TESTDATA_PATH / "integers.defcl",
            integers_pb2.IntegersFile,
        )
        assert result.config.positive == 10
        assert result.config.negative == -5
        assert result.config.zero == 0

    def test_strings(self):
        result = parser.parse_file(
            _TESTDATA_PATH / "strings.defcl",
            strings_pb2.StringsFile,
        )
        assert result.config.basic == "hello"
        assert result.config.with_newline == "line1\nline2"

    def test_repeated_messages(self):
        result = parser.parse_file(
            _TESTDATA_PATH / "repeated_messages.defcl",
            repeated_messages_pb2.RepeatedMessagesFile,
        )
        assert len(result.project.dependencies) == 2
