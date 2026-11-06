from __future__ import annotations

import pytest

from defcl.python2 import error_types, errors, validator
from tools import runfiles

_MULTIPLE_ERRORS_FILE = "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile"
_SINGLE_TOPLEVEL_FILE = "defcl.testdata.valid.schemas.SingleToplevelFile"


def _testdata(path: str) -> str:
    return runfiles.resolve(f"_main/defcl/testdata/{path}").read_text(encoding="utf-8")


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

    assert integer_enum.kind == error_types.DiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == errors.SourceLocation(2, 13, 2, 13)
    assert integer_enum.field_name == "status"
    assert integer_enum.message_type is None
    assert (
        scalar_for_message_field.kind
        == error_types.DiagnosticKind.SCALAR_FOR_MESSAGE_FIELD
    )
    assert scalar_for_message_field.location == errors.SourceLocation(3, 15, 3, 25)
    assert scalar_for_message_field.field_name == "database"
    assert scalar_for_message_field.message_type is None
    assert (
        message_value_for_scalar_field.kind
        == error_types.DiagnosticKind.MESSAGE_VALUE_FOR_SCALAR_FIELD
    )
    assert message_value_for_scalar_field.location == errors.SourceLocation(5, 8, 5, 9)
    assert message_value_for_scalar_field.field_name == "count"
    assert message_value_for_scalar_field.message_type is None


def test_unknown_field_name_diagnostic_has_message_type():
    (unknown_field_name,) = validator.validate(
        _testdata("invalid/semantics/multiple_errors/value_of_unknown_field.defcl"),
        _invalid_semantics_schemas(),
        _MULTIPLE_ERRORS_FILE,
    )

    assert unknown_field_name.kind == error_types.DiagnosticKind.UNKNOWN_FIELD_NAME
    assert unknown_field_name.location == errors.SourceLocation(2, 5, 2, 8)
    assert unknown_field_name.field_name == "size"
    assert (
        unknown_field_name.message_type
        == "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
    )


def test_syntax_error_raises_dcl_error():
    with pytest.raises(errors.DclError) as exc_info:
        _ = validator.validate(
            _testdata("invalid/syntax/characters/at_sign.defcl"),
            _valid_schemas(),
            _SINGLE_TOPLEVEL_FILE,
        )

    assert exc_info.value.kind == error_types.DclErrorKind.UNEXPECTED_CHARACTER
    assert exc_info.value.location == errors.SourceLocation(2, 8, 2, 8)
    assert exc_info.value.character == "@"


def test_syntax_error_without_a_character_has_none():
    with pytest.raises(errors.DclError) as exc_info:
        _ = validator.validate(
            _testdata("invalid/syntax/separators/missing_colon.defcl"),
            _valid_schemas(),
            _SINGLE_TOPLEVEL_FILE,
        )

    assert exc_info.value.kind == error_types.DclErrorKind.MISSING_COLON
    assert exc_info.value.location == errors.SourceLocation(2, 10, 2, 10)
    assert exc_info.value.character is None


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
