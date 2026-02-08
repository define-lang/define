from pathlib import Path

import pytest

from defcl.python import exceptions
from defcl.python.validator import semantics, syntax
from defcl.testdata.invalid.semantics.schemas import (
    integer_enum_pb2,
    no_brackets_message_pb2,
    no_brackets_scalar_pb2,
)

_INVALID_SEMANTICS_PATH = (
    Path(__file__).parent.parent.parent / "testdata" / "invalid" / "semantics"
)
_parser = syntax.Parser()


class TestIntegerEnum:
    def test_integer_enum_value(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                integer_enum_pb2.IntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "status"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5


class TestRepeatedFieldWithoutBrackets:
    def test_repeated_scalar_without_brackets(self):
        path = _INVALID_SEMANTICS_PATH / "repeated" / "no_brackets_scalar.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(
            exceptions.RepeatedFieldWithoutBracketsError,
        ) as exc_info:
            semantics.validate(
                tree,
                no_brackets_scalar_pb2.NoBracketsScalarFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "tags"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5

    def test_repeated_message_without_brackets(self):
        path = _INVALID_SEMANTICS_PATH / "repeated" / "no_brackets_message.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(
            exceptions.RepeatedFieldWithoutBracketsError,
        ) as exc_info:
            semantics.validate(
                tree,
                no_brackets_message_pb2.NoBracketsMessageFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "dependencies"
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5
