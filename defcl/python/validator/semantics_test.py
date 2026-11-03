from __future__ import annotations

from pathlib import Path

import pytest

from defcl.python import exceptions
from defcl.python.validator import semantics, syntax
from defcl.testdata.invalid.semantics.schemas import (
    field_written_twice_pb2,
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
    def test_integer_enum_in_second_top_level_message(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "second_top_level.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                integer_enum_pb2.IntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.line == 5
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "status"

    def test_integer_enum_value(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                integer_enum_pb2.IntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "status"

    def test_integer_enum_in_repeated_message(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "repeated_integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                repeated_integer_enum_pb2.RepeatedIntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.line == 4
        assert exc_info.value.column == 11
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "status"

    def test_nested_integer_enum_value(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "nested_integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                nested_integer_enum_pb2.NestedIntegerEnumFile,
                path_name=path,
            )
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "status"


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
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "tags"

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
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "dependencies"

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
        assert exc_info.value.line == 3
        assert exc_info.value.column == 9
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "tags"

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
        assert exc_info.value.line == 2
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "dependencies"


class TestFieldWrittenTwice:
    def test_repeated_field_written_twice(self):
        path = _INVALID_SEMANTICS_PATH / "field_written_twice" / "repeated_field.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.FieldWrittenTwiceError) as exc_info:
            semantics.validate(
                tree,
                field_written_twice_pb2.FieldWrittenTwiceFile,
                path_name=path,
            )
        assert exc_info.value.line == 3
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "dependencies"

    def test_scalar_field_written_twice(self):
        path = _INVALID_SEMANTICS_PATH / "field_written_twice" / "scalar_field.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.FieldWrittenTwiceError) as exc_info:
            semantics.validate(
                tree,
                field_written_twice_pb2.FieldWrittenTwiceFile,
                path_name=path,
            )
        assert exc_info.value.line == 3
        assert exc_info.value.column == 5
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "universe_name"

    def test_top_level_message_written_twice(self):
        path = (
            _INVALID_SEMANTICS_PATH / "field_written_twice" / "top_level_message.defcl"
        )
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.FieldWrittenTwiceError) as exc_info:
            semantics.validate(
                tree,
                field_written_twice_pb2.FieldWrittenTwiceFile,
                path_name=path,
            )
        assert exc_info.value.line == 4
        assert exc_info.value.column == 1
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "project"

    def test_field_written_twice_in_repeated_message(self):
        path = _INVALID_SEMANTICS_PATH / "field_written_twice" / "nested_field.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.FieldWrittenTwiceError) as exc_info:
            semantics.validate(
                tree,
                field_written_twice_pb2.FieldWrittenTwiceFile,
                path_name=path,
            )
        assert exc_info.value.line == 6
        assert exc_info.value.column == 13
        assert exc_info.value.path_name == path
        assert exc_info.value.field_name == "universe"


class TestErrorMessages:
    def test_field_written_twice_error_with_path(self):
        path = _INVALID_SEMANTICS_PATH / "field_written_twice" / "scalar_field.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.FieldWrittenTwiceError) as exc_info:
            semantics.validate(
                tree,
                field_written_twice_pb2.FieldWrittenTwiceFile,
                path_name=path,
            )
        assert str(exc_info.value) == (
            f'File "{path}", line 3, column 5\n'
            "universe_name: Field is already written in this message"
        )

    def test_integer_enum_error_with_path(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                integer_enum_pb2.IntegerEnumFile,
                path_name=path,
            )
        assert str(exc_info.value) == (
            f'File "{path}", line 2, column 5\n'
            "status: Integer enum values are not allowed"
        )

    def test_integer_enum_error_without_path(self):
        path = _INVALID_SEMANTICS_PATH / "enums" / "integer_enum.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(exceptions.IntegerEnumError) as exc_info:
            semantics.validate(
                tree,
                integer_enum_pb2.IntegerEnumFile,
            )
        assert str(exc_info.value) == (
            "line 2, column 5\nstatus: Integer enum values are not allowed"
        )

    def test_repeated_field_error_with_path(self):
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
        assert str(exc_info.value) == (
            f'File "{path}", line 2, column 5\n'
            "tags: Repeated fields must use bracket [] syntax"
        )

    def test_repeated_field_error_without_path(self):
        path = _INVALID_SEMANTICS_PATH / "repeated" / "no_brackets_scalar.defcl"
        tree = _parser.parse_file(path)
        with pytest.raises(
            exceptions.RepeatedFieldWithoutBracketsError,
        ) as exc_info:
            semantics.validate(
                tree,
                no_brackets_scalar_pb2.NoBracketsScalarFile,
            )
        assert str(exc_info.value) == (
            "line 2, column 5\ntags: Repeated fields must use bracket [] syntax"
        )
