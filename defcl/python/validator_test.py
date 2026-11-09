from __future__ import annotations

import typing

import pytest

from defcl.python import error_types, errors, validator
from source_rendering.python import rendering
from tools import runfiles

if typing.TYPE_CHECKING:
    import pathlib

_MULTIPLE_ERRORS_FILE = "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile"
_ONEOFS_FILE = "defcl.testdata.invalid.semantics.schemas.OneofsFile"
_OUT_OF_RANGE_FILE = "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile"
_SINGLE_TOPLEVEL_FILE = "defcl.testdata.valid.schemas.SingleToplevelFile"
_WRONG_VALUE_KINDS_FILE = "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile"


def _testdata_path(path: str) -> pathlib.Path:
    return runfiles.resolve(f"_main/defcl/testdata/{path}")


def _testdata(path: str) -> str:
    return _testdata_path(path).read_text(encoding="utf-8")


def _valid_schemas() -> bytes:
    return runfiles.resolve_from_env("VALID_SCHEMAS").read_bytes()


def _invalid_semantics_schemas() -> bytes:
    return runfiles.resolve_from_env("INVALID_SEMANTICS_SCHEMAS").read_bytes()


def test_valid_file_has_no_diagnostics():
    assert (
        validator.validate(
            _testdata("valid/single_toplevel.defcl"),
            _valid_schemas(),
            _SINGLE_TOPLEVEL_FILE,
        )
        == []
    )


def test_semantic_errors_are_diagnostics():
    integer_enum, scalar_for_message_field, message_value_for_scalar_field = (
        validator.validate(
            _testdata(
                "invalid/semantics/multiple_errors/errors_in_several_fields.defcl"
            ),
            _invalid_semantics_schemas(),
            _MULTIPLE_ERRORS_FILE,
        )
    )

    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=13, end_line=2, end_column=13
    )
    assert integer_enum.field_name == "status"
    assert type(scalar_for_message_field) is errors.SemanticDiagnostic
    assert (
        scalar_for_message_field.kind
        == error_types.SemanticDiagnosticKind.SCALAR_FOR_MESSAGE_FIELD
    )
    assert scalar_for_message_field.location == rendering.SourceLocation(
        line=3, column=15, end_line=3, end_column=25
    )
    assert scalar_for_message_field.field_name == "database"
    assert type(message_value_for_scalar_field) is errors.SemanticDiagnostic
    assert (
        message_value_for_scalar_field.kind
        == error_types.SemanticDiagnosticKind.MESSAGE_VALUE_FOR_SCALAR_FIELD
    )
    assert message_value_for_scalar_field.location == rendering.SourceLocation(
        line=5, column=8, end_line=5, end_column=9
    )
    assert message_value_for_scalar_field.field_name == "count"


def test_unknown_field_name_diagnostic_has_message_type():
    (unknown_field_name,) = validator.validate(
        _testdata("invalid/semantics/multiple_errors/value_of_unknown_field.defcl"),
        _invalid_semantics_schemas(),
        _MULTIPLE_ERRORS_FILE,
    )

    assert isinstance(unknown_field_name, errors.UnknownFieldNameDiagnostic)
    assert (
        unknown_field_name.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
    )
    assert unknown_field_name.location == rendering.SourceLocation(
        line=2, column=5, end_line=2, end_column=8
    )
    assert unknown_field_name.field_name == "size"
    assert (
        unknown_field_name.message_type
        == "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
    )


def test_unknown_enum_value_diagnostic_has_enum_type():
    (unknown_enum_value,) = validator.validate(
        _testdata("invalid/semantics/wrong_value_kinds/unknown_enum_value.defcl"),
        _invalid_semantics_schemas(),
        _WRONG_VALUE_KINDS_FILE,
    )

    assert isinstance(unknown_enum_value, errors.UnknownEnumValueDiagnostic)
    assert (
        unknown_enum_value.kind == error_types.SemanticDiagnosticKind.UNKNOWN_ENUM_VALUE
    )
    assert unknown_enum_value.location == rendering.SourceLocation(
        line=2, column=13, end_line=2, end_column=18
    )
    assert unknown_enum_value.field_name == "status"
    assert (
        unknown_enum_value.enum_type
        == "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile.Status"
    )


def test_integer_out_of_range_diagnostic_has_field_type():
    (integer_out_of_range,) = validator.validate(
        _testdata("invalid/semantics/out_of_range/negative_in_unsigned_field.defcl"),
        _invalid_semantics_schemas(),
        _OUT_OF_RANGE_FILE,
    )

    assert isinstance(integer_out_of_range, errors.IntegerOutOfRangeDiagnostic)
    assert (
        integer_out_of_range.kind
        == error_types.SemanticDiagnosticKind.INTEGER_OUT_OF_RANGE
    )
    assert integer_out_of_range.location == rendering.SourceLocation(
        line=2, column=19, end_line=2, end_column=20
    )
    assert integer_out_of_range.field_name == "uint32_value"
    assert integer_out_of_range.field_type == "uint32"


def test_float_out_of_range_diagnostic_has_field_type():
    (float_out_of_range,) = validator.validate(
        _testdata("invalid/semantics/out_of_range/float_rounding_to_infinity.defcl"),
        _invalid_semantics_schemas(),
        _OUT_OF_RANGE_FILE,
    )

    assert isinstance(float_out_of_range, errors.FloatOutOfRangeDiagnostic)
    assert (
        float_out_of_range.kind == error_types.SemanticDiagnosticKind.FLOAT_OUT_OF_RANGE
    )
    assert float_out_of_range.location == rendering.SourceLocation(
        line=2, column=18, end_line=2, end_column=58
    )
    assert float_out_of_range.field_name == "float_value"
    assert float_out_of_range.field_type == "float"


def test_second_field_of_oneof_diagnostic_has_oneof():
    (second_field_of_oneof,) = validator.validate(
        _testdata("invalid/semantics/oneofs/second_field.defcl"),
        _invalid_semantics_schemas(),
        _ONEOFS_FILE,
    )

    assert isinstance(second_field_of_oneof, errors.SecondFieldOfOneofDiagnostic)
    assert (
        second_field_of_oneof.kind
        == error_types.SemanticDiagnosticKind.SECOND_FIELD_OF_ONEOF
    )
    assert second_field_of_oneof.location == rendering.SourceLocation(
        line=3, column=5, end_line=3, end_column=7
    )
    assert second_field_of_oneof.field_name == "url"
    assert (
        second_field_of_oneof.oneof
        == "defcl.testdata.invalid.semantics.schemas.OneofsFile.Config.source"
    )


def test_syntax_error_is_a_diagnostic():
    (unexpected_character,) = validator.validate(
        _testdata("invalid/syntax/characters/at_sign.defcl"),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert type(unexpected_character) is errors.UnexpectedCharacterDiagnostic
    assert (
        unexpected_character.kind
        == error_types.SyntaxDiagnosticKind.UNEXPECTED_CHARACTER
    )
    assert unexpected_character.location == rendering.SourceLocation(
        line=2, column=8, end_line=2, end_column=8
    )
    assert unexpected_character.character == "@"


def test_syntax_error_without_a_character_is_a_plain_syntax_diagnostic():
    (missing_colon,) = validator.validate(
        _testdata("invalid/syntax/separators/missing_colon.defcl"),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    )

    assert type(missing_colon) is errors.SyntaxDiagnostic
    assert missing_colon.kind == error_types.SyntaxDiagnosticKind.MISSING_COLON
    assert missing_colon.location == rendering.SourceLocation(
        line=2, column=10, end_line=2, end_column=10
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
    assert validator.validate_file(
        str(_testdata_path("valid/single_toplevel.defcl")),
        rendering.SourceMap(),
        _valid_schemas(),
        _SINGLE_TOPLEVEL_FILE,
    ) == ('project: {\n    universe_name: "example"\n}\n', [])


def test_validate_file_registers_the_file_and_puts_its_diagnostics_in_it():
    path = str(_testdata_path("invalid/semantics/enums/integer_enum.defcl"))
    source_map = rendering.SourceMap()

    source, (integer_enum,) = validator.validate_file(
        path,
        source_map,
        _invalid_semantics_schemas(),
        "defcl.testdata.invalid.semantics.schemas.IntegerEnumFile",
    )

    assert source == "config: {\n    status: 0\n}\n"
    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=13, end_line=2, end_column=13, file_path=path
    )
    assert integer_enum.field_name == "status"
    assert integer_enum.format(source_map) == (
        f'File "{path}", line 2, column 13\n'
        "    status: 0\n"
        "            ^\n"
        "status: Integer enum values are not allowed"
    )


def test_validate_file_of_a_missing_file_raises_file_not_found_error():
    with pytest.raises(FileNotFoundError):
        _ = validator.validate_file(
            "no_such_file.defcl",
            rendering.SourceMap(),
            _valid_schemas(),
            _SINGLE_TOPLEVEL_FILE,
        )
