from __future__ import annotations

import typing

import pytest

from crates.source_rendering.python import rendering
from defcl.python import error_types, errors, validator
from tools import runfiles

if typing.TYPE_CHECKING:
    import pathlib

_MULTIPLE_ERRORS_FILE = "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile"
_ONEOFS_FILE = "defcl.testdata.invalid.semantics.schemas.OneofsFile"
_OUT_OF_RANGE_FILE = "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile"
_SINGLE_TOPLEVEL_FILE = "defcl.testdata.valid.schemas.SingleToplevelFile"
_WRONG_VALUE_KINDS_FILE = "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile"
_RIGHT_TO_LEFT_OVERRIDE = "\u202e"
# What a line with bytes that are not valid UTF-8 shows in their place.
_REPLACEMENT_CHARACTER = "\ufffd"


def _testdata_path(path: str) -> pathlib.Path:
    return runfiles.resolve(f"_main/defcl/testdata/{path}")


def _testdata(path: str) -> str:
    return _testdata_path(path).read_text(encoding="utf-8")


def _valid_schemas() -> bytes:
    return runfiles.resolve_from_env("VALID_SCHEMAS").read_bytes()


def _invalid_semantics_schemas() -> bytes:
    return runfiles.resolve_from_env("INVALID_SEMANTICS_SCHEMAS").read_bytes()


def test_valid_file_has_no_diagnostics():
    assert validator.validate(
        _testdata("valid/single_toplevel.defcl"),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    ) == (True, [])


def test_semantic_errors_are_diagnostics():
    (
        understood,
        (
            integer_enum,
            scalar_for_message_field,
            message_value_for_scalar_field,
        ),
    ) = validator.validate(
        _testdata("invalid/semantics/multiple_errors/errors_in_several_fields.defcl"),
        _invalid_semantics_schemas(),
        _MULTIPLE_ERRORS_FILE,
    )

    assert understood is False
    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=11, end_line=2, end_column=11
    )
    assert integer_enum.file_path is None
    assert integer_enum.field_name == "status"
    assert type(scalar_for_message_field) is errors.SemanticDiagnostic
    assert (
        scalar_for_message_field.kind
        == error_types.SemanticDiagnosticKind.SCALAR_FOR_MESSAGE_FIELD
    )
    assert scalar_for_message_field.location == rendering.SourceLocation(
        line=3, column=13, end_line=3, end_column=23
    )
    assert scalar_for_message_field.file_path is None
    assert scalar_for_message_field.field_name == "database"
    assert type(message_value_for_scalar_field) is errors.SemanticDiagnostic
    assert (
        message_value_for_scalar_field.kind
        == error_types.SemanticDiagnosticKind.MESSAGE_VALUE_FOR_SCALAR_FIELD
    )
    assert message_value_for_scalar_field.location == rendering.SourceLocation(
        line=4, column=10, end_line=6, end_column=3
    )
    assert message_value_for_scalar_field.file_path is None
    assert message_value_for_scalar_field.field_name == "count"


def test_unknown_field_name_diagnostic_has_message_type():
    understood, (unknown_field_name,) = validator.validate(
        _testdata("invalid/semantics/multiple_errors/value_of_unknown_field.defcl"),
        _invalid_semantics_schemas(),
        _MULTIPLE_ERRORS_FILE,
    )

    assert understood is False

    assert isinstance(unknown_field_name, errors.UnknownFieldNameDiagnostic)
    assert (
        unknown_field_name.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
    )
    assert unknown_field_name.location == rendering.SourceLocation(
        line=2, column=3, end_line=2, end_column=6
    )
    assert unknown_field_name.file_path is None
    assert unknown_field_name.field_name == "size"
    assert (
        unknown_field_name.message_type
        == "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
    )


def test_unknown_enum_value_diagnostic_has_enum_type():
    understood, (unknown_enum_value,) = validator.validate(
        _testdata("invalid/semantics/wrong_value_kinds/unknown_enum_value.defcl"),
        _invalid_semantics_schemas(),
        _WRONG_VALUE_KINDS_FILE,
    )

    assert understood is False

    assert isinstance(unknown_enum_value, errors.UnknownEnumValueDiagnostic)
    assert (
        unknown_enum_value.kind == error_types.SemanticDiagnosticKind.UNKNOWN_ENUM_VALUE
    )
    assert unknown_enum_value.location == rendering.SourceLocation(
        line=2, column=11, end_line=2, end_column=16
    )
    assert unknown_enum_value.file_path is None
    assert unknown_enum_value.field_name == "status"
    assert (
        unknown_enum_value.enum_type
        == "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile.Status"
    )


def test_integer_out_of_range_diagnostic_has_field_type():
    understood, (integer_out_of_range,) = validator.validate(
        _testdata("invalid/semantics/out_of_range/negative_in_unsigned_field.defcl"),
        _invalid_semantics_schemas(),
        _OUT_OF_RANGE_FILE,
    )

    assert understood is False

    assert isinstance(integer_out_of_range, errors.IntegerOutOfRangeDiagnostic)
    assert (
        integer_out_of_range.kind
        == error_types.SemanticDiagnosticKind.INTEGER_OUT_OF_RANGE
    )
    assert integer_out_of_range.location == rendering.SourceLocation(
        line=2, column=17, end_line=2, end_column=18
    )
    assert integer_out_of_range.file_path is None
    assert integer_out_of_range.field_name == "uint32_value"
    assert integer_out_of_range.field_type == "uint32"


def test_float_out_of_range_diagnostic_has_field_type():
    understood, (float_out_of_range,) = validator.validate(
        _testdata("invalid/semantics/out_of_range/float_rounding_to_infinity.defcl"),
        _invalid_semantics_schemas(),
        _OUT_OF_RANGE_FILE,
    )

    assert understood is False

    assert isinstance(float_out_of_range, errors.FloatOutOfRangeDiagnostic)
    assert (
        float_out_of_range.kind == error_types.SemanticDiagnosticKind.FLOAT_OUT_OF_RANGE
    )
    assert float_out_of_range.location == rendering.SourceLocation(
        line=2, column=16, end_line=2, end_column=56
    )
    assert float_out_of_range.file_path is None
    assert float_out_of_range.field_name == "float_value"
    assert float_out_of_range.field_type == "float"


def test_second_field_of_oneof_diagnostic_has_oneof():
    understood, (second_field_of_oneof,) = validator.validate(
        _testdata("invalid/semantics/oneofs/second_field.defcl"),
        _invalid_semantics_schemas(),
        _ONEOFS_FILE,
    )

    assert understood is False

    assert isinstance(second_field_of_oneof, errors.SecondFieldOfOneofDiagnostic)
    assert (
        second_field_of_oneof.kind
        == error_types.SemanticDiagnosticKind.SECOND_FIELD_OF_ONEOF
    )
    assert second_field_of_oneof.location == rendering.SourceLocation(
        line=3, column=3, end_line=3, end_column=5
    )
    assert second_field_of_oneof.file_path is None
    assert second_field_of_oneof.field_name == "url"
    assert (
        second_field_of_oneof.oneof
        == "defcl.testdata.invalid.semantics.schemas.OneofsFile.Config.source"
    )


def test_field_out_of_order_diagnostic_has_later_field():
    understood, (field_out_of_order,) = validator.validate(
        _testdata("invalid/semantics/field_order/field_after_higher_number.defcl"),
        _invalid_semantics_schemas(),
        _WRONG_VALUE_KINDS_FILE,
    )

    assert understood is True

    assert isinstance(field_out_of_order, errors.FieldOutOfOrderDiagnostic)
    assert (
        field_out_of_order.kind == error_types.SemanticDiagnosticKind.FIELD_OUT_OF_ORDER
    )
    assert field_out_of_order.location == rendering.SourceLocation(
        line=3, column=3, end_line=3, end_column=6
    )
    assert field_out_of_order.file_path is None
    assert field_out_of_order.field_name == "name"
    assert field_out_of_order.later_field == "count"


def test_wrong_indentation_diagnostic_has_expected_spaces():
    understood, (wrong_indentation,) = validator.validate(
        'project: {\n universe_name: "example"\n}\n',
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is True

    assert isinstance(wrong_indentation, errors.WrongIndentationDiagnostic)
    assert wrong_indentation.kind == error_types.SyntaxDiagnosticKind.WRONG_INDENTATION
    assert wrong_indentation.location == rendering.SourceLocation(
        line=2, column=1, end_line=2, end_column=1
    )
    assert wrong_indentation.file_path is None
    assert wrong_indentation.expected_spaces == 2


def test_layout_errors_come_before_semantic_errors():
    understood, (wrong_indentation, unknown_field_name) = validator.validate(
        "project: {\n size: 1\n}\n",
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is False

    assert isinstance(wrong_indentation, errors.WrongIndentationDiagnostic)
    assert wrong_indentation.kind == error_types.SyntaxDiagnosticKind.WRONG_INDENTATION
    assert wrong_indentation.location == rendering.SourceLocation(
        line=2, column=1, end_line=2, end_column=1
    )
    assert wrong_indentation.file_path is None
    assert wrong_indentation.expected_spaces == 2
    assert isinstance(unknown_field_name, errors.UnknownFieldNameDiagnostic)
    assert (
        unknown_field_name.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
    )
    assert unknown_field_name.location == rendering.SourceLocation(
        line=2, column=2, end_line=2, end_column=5
    )
    assert unknown_field_name.file_path is None
    assert unknown_field_name.field_name == "size"
    assert (
        unknown_field_name.message_type
        == "defcl.testdata.valid.schemas.SingleToplevelFile.Project"
    )


def test_syntax_error_is_a_diagnostic():
    understood, (unexpected_character,) = validator.validate(
        _testdata("invalid/syntax/characters/at_sign.defcl"),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is False

    assert type(unexpected_character) is errors.UnexpectedCharacterDiagnostic
    assert (
        unexpected_character.kind
        == error_types.SyntaxDiagnosticKind.UNEXPECTED_CHARACTER
    )
    assert unexpected_character.location == rendering.SourceLocation(
        line=2, column=6, end_line=2, end_column=6
    )
    assert unexpected_character.file_path is None
    assert unexpected_character.character == "@"


def test_invalid_utf8_is_an_invalid_encoding_diagnostic():
    path = str(_testdata_path("invalid/syntax/characters/invalid_utf8.defcl"))
    source_map = rendering.SourceMap()

    source, (invalid_encoding,) = validator.validate_file(
        path, source_map, _valid_schemas(), _SINGLE_TOPLEVEL_FILE
    )

    assert source is None
    assert type(invalid_encoding) is errors.InvalidEncodingDiagnostic
    assert invalid_encoding.kind == error_types.SyntaxDiagnosticKind.INVALID_ENCODING
    assert invalid_encoding.location == rendering.SourceLocation(
        line=2, column=12, end_line=2, end_column=12, file_path=path
    )
    assert invalid_encoding.file_path == path
    assert invalid_encoding.byte == 0xFF
    assert invalid_encoding.format(source_map) == (
        f'File "{path}", line 2, column 12\n'
        f'    b: "café {_REPLACEMENT_CHARACTER}"\n'
        "             ^\n"
        "Invalid UTF-8: the byte \\xff does not start a valid character"
    )


def test_control_character_in_a_comment_is_a_control_character_diagnostic():
    understood, (control_character,) = validator.validate(
        'project: {\n  # a\x01b\n  universe_name: "example"\n}\n',
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is True
    assert type(control_character) is errors.ControlCharacterDiagnostic
    assert control_character.kind == error_types.SyntaxDiagnosticKind.CONTROL_CHARACTER
    assert control_character.location == rendering.SourceLocation(
        line=2, column=6, end_line=2, end_column=6
    )
    assert control_character.file_path is None
    assert control_character.character == "\x01"


def test_invisible_character_in_a_string_is_an_invisible_character_diagnostic():
    understood, (invisible_character,) = validator.validate(
        f'project: {{\n  universe_name: "a{_RIGHT_TO_LEFT_OVERRIDE}b"\n}}\n',
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is False
    assert type(invisible_character) is errors.InvisibleCharacterDiagnostic
    assert (
        invisible_character.kind == error_types.SyntaxDiagnosticKind.INVISIBLE_CHARACTER
    )
    assert invisible_character.location == rendering.SourceLocation(
        line=2, column=20, end_line=2, end_column=20
    )
    assert invisible_character.file_path is None
    assert invisible_character.character == _RIGHT_TO_LEFT_OVERRIDE


def test_syntax_error_without_a_character_is_a_plain_syntax_diagnostic():
    understood, (missing_colon,) = validator.validate(
        _testdata("invalid/syntax/separators/missing_colon.defcl"),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert understood is False

    assert type(missing_colon) is errors.SyntaxDiagnostic
    assert missing_colon.kind == error_types.SyntaxDiagnosticKind.MISSING_COLON
    assert missing_colon.location == rendering.SourceLocation(
        line=2, column=8, end_line=2, end_column=8
    )
    assert missing_colon.file_path is None


def test_error_about_the_whole_text_has_no_location():
    understood, (missing_top_level_message,) = validator.validate(
        "", _valid_schemas(), _SINGLE_TOPLEVEL_FILE
    )

    assert understood is False
    assert type(missing_top_level_message) is errors.SyntaxDiagnostic
    assert (
        missing_top_level_message.kind
        == error_types.SyntaxDiagnosticKind.MISSING_TOP_LEVEL_MESSAGE
    )
    assert missing_top_level_message.location is None
    assert missing_top_level_message.file_path is None
    assert (
        missing_top_level_message.format(rendering.SourceMap())
        == "The file has no top-level message"
    )


def test_error_about_the_whole_file_names_the_file():
    path = str(_testdata_path("invalid/syntax/file_format/empty_file.defcl"))
    source_map = rendering.SourceMap()

    source, (missing_top_level_message,) = validator.validate_file(
        path, source_map, _valid_schemas(), _SINGLE_TOPLEVEL_FILE
    )

    assert source is None
    assert type(missing_top_level_message) is errors.SyntaxDiagnostic
    assert (
        missing_top_level_message.kind
        == error_types.SyntaxDiagnosticKind.MISSING_TOP_LEVEL_MESSAGE
    )
    assert missing_top_level_message.location is None
    assert missing_top_level_message.file_path == path
    assert missing_top_level_message.format(source_map) == (
        f'File "{path}"\nThe file has no top-level message'
    )


def test_undecodable_descriptor_set_raises_invalid_schema_error():
    with pytest.raises(errors.InvalidSchemaError):
        _ = validator.validate(
            _testdata("valid/single_toplevel.defcl"), b"\xff", _SINGLE_TOPLEVEL_FILE
        )


def test_missing_message_type_raises_invalid_schema_error():
    with pytest.raises(errors.InvalidSchemaError):
        _ = validator.validate(
            _testdata("valid/single_toplevel.defcl"),
            _valid_schemas(),
            "defcl.testdata.valid.schemas.NoSuchFile",
        )


def test_validate_file_of_a_valid_file_returns_its_text_and_no_diagnostics():
    file, diagnostics = validator.validate_file(
        str(_testdata_path("valid/single_toplevel.defcl")),
        rendering.SourceMap(),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert file is not None
    assert file.text() == 'project: {\n  universe_name: "example"\n}\n'
    assert diagnostics == []


def test_validate_file_registers_the_file_and_puts_its_diagnostics_in_it():
    path = str(_testdata_path("invalid/semantics/enums/integer_enum.defcl"))
    source_map = rendering.SourceMap()

    source, (integer_enum,) = validator.validate_file(
        path,
        source_map,
        _invalid_semantics_schemas(),
        "defcl.testdata.invalid.semantics.schemas.IntegerEnumFile",
    )

    assert source is None
    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=11, end_line=2, end_column=11, file_path=path
    )
    assert integer_enum.file_path == path
    assert integer_enum.field_name == "status"
    assert integer_enum.format(source_map) == (
        f'File "{path}", line 2, column 11\n'
        "    status: 0\n"
        "            ^\n"
        "status: Integer enum values are not allowed"
    )


def test_validate_file_of_a_file_with_only_fields_out_of_order_returns_its_text():
    path = str(
        _testdata_path("invalid/semantics/field_order/field_after_higher_number.defcl")
    )

    source, (field_out_of_order,) = validator.validate_file(
        path,
        rendering.SourceMap(),
        _invalid_semantics_schemas(),
        _WRONG_VALUE_KINDS_FILE,
    )

    assert source is not None
    assert source.text() == 'config: {\n  count: 1\n  name: "a"\n}\n'
    assert isinstance(field_out_of_order, errors.FieldOutOfOrderDiagnostic)
    assert (
        field_out_of_order.kind == error_types.SemanticDiagnosticKind.FIELD_OUT_OF_ORDER
    )
    assert field_out_of_order.location == rendering.SourceLocation(
        line=3, column=3, end_line=3, end_column=6, file_path=path
    )
    assert field_out_of_order.file_path == path
    assert field_out_of_order.field_name == "name"
    assert field_out_of_order.later_field == "count"


def test_validate_file_with_a_missing_message_type_raises_invalid_schema_error():
    with pytest.raises(errors.InvalidSchemaError):
        _ = validator.validate_file(
            str(_testdata_path("valid/single_toplevel.defcl")),
            rendering.SourceMap(),
            _valid_schemas(),
            "defcl.testdata.valid.schemas.NoSuchFile",
        )


def test_validate_file_of_a_missing_file_raises_file_not_found_error():
    with pytest.raises(FileNotFoundError):
        _ = validator.validate_file(
            "no_such_file.defcl",
            rendering.SourceMap(),
            _valid_schemas(),
            _SINGLE_TOPLEVEL_FILE,
        )
