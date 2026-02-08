from pathlib import Path

import pytest

from defcl.python import exceptions
from defcl.python.validator import semantics, syntax
from defcl.testdata.invalid.semantics.schemas import (
    integer_enum_pb2,
    nested_integer_enum_pb2,
    nested_no_brackets_message_pb2,
    nested_no_brackets_scalar_pb2,
    no_brackets_message_pb2,
    no_brackets_scalar_pb2,
    repeated_integer_enum_pb2,
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

    def test_integer_enum_in_repeated_message(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "repeated_integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                repeated_integer_enum_pb2.RepeatedIntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "status"
        assert exc_info.value.line == 4
        assert exc_info.value.column == 11

    def test_nested_integer_enum_value(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "nested_integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                nested_integer_enum_pb2.NestedIntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "status"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9


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

    def test_nested_repeated_message_without_brackets(self):
        path = _INVALID_SEMANTICS_PATH / "repeated" / "nested_no_brackets_message.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(
            exceptions.RepeatedFieldWithoutBracketsError,
        ) as exc_info:
            semantics.validate(
                tree,
                nested_no_brackets_message_pb2.NestedNoBracketsMessageFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "dependencies"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9

    def test_nested_repeated_scalar_without_brackets(self):
        path = _INVALID_SEMANTICS_PATH / "repeated" / "nested_no_brackets_scalar.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(
            exceptions.RepeatedFieldWithoutBracketsError,
        ) as exc_info:
            semantics.validate(
                tree,
                nested_no_brackets_scalar_pb2.NestedNoBracketsScalarFile,
                path_name=path,
            )
        assert exc_info.value.field_name == "tags"
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9

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
