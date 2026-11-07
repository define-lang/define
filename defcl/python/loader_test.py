from __future__ import annotations

import pytest

from defcl.python import error_types, errors, loader, locations
from defcl.testdata.invalid.semantics.schemas import integer_enum_pb2
from defcl.testdata.valid.schemas import (
    imports_pb2,
    shared_pb2,
    single_toplevel_pb2,
    wrapper_pb2,
)
from tools import runfiles


def _testdata_path(path: str) -> str:
    return str(runfiles.resolve(f"_main/defcl/testdata/{path}"))


def _testdata(path: str) -> str:
    return runfiles.resolve(f"_main/defcl/testdata/{path}").read_text(encoding="utf-8")


def test_valid_file_loads_into_its_message():
    result = loader.load(
        _testdata("valid/single_toplevel.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
    )

    assert result == loader.LoadResult(
        message=single_toplevel_pb2.SingleToplevelFile(
            project=single_toplevel_pb2.SingleToplevelFile.Project(
                universe_name="example"
            )
        ),
        diagnostics=[],
    )


def test_message_types_from_imported_files_load():
    result = loader.load(_testdata("valid/imports.defcl"), imports_pb2.ImportsFile)

    assert result.message == imports_pb2.ImportsFile(
        wrapper=wrapper_pb2.Wrapper(shared=shared_pb2.Shared(name="a")),
        shared=shared_pb2.Shared(name="b"),
    )
    assert result.diagnostics == []


def test_semantic_errors_are_diagnostics_without_a_message():
    result = loader.load(
        _testdata("invalid/semantics/enums/integer_enum.defcl"),
        integer_enum_pb2.IntegerEnumFile,
    )

    assert result.message is None
    (integer_enum,) = result.diagnostics
    assert integer_enum.kind == error_types.DiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == locations.SourceLocation(2, 13, 2, 13)
    assert integer_enum.field_name == "status"
    assert type(integer_enum) is errors.DclDiagnostic
    assert integer_enum.rendered == (
        "line 2, column 13\n"
        "    status: 0\n"
        "            ^\n"
        "status: Integer enum values are not allowed"
    )


def test_syntax_error_raises_dcl_error():
    with pytest.raises(errors.DclError) as exc_info:
        _ = loader.load(
            _testdata("invalid/syntax/characters/at_sign.defcl"),
            single_toplevel_pb2.SingleToplevelFile,
        )

    assert isinstance(exc_info.value, errors.UnexpectedCharacterError)
    assert exc_info.value.kind == error_types.DclErrorKind.UNEXPECTED_CHARACTER
    assert exc_info.value.location == locations.SourceLocation(2, 8, 2, 8)
    assert exc_info.value.character == "@"
    assert str(exc_info.value) == (
        "line 2, column 8\n    b: @\n       ^\nUnexpected character '@' (U+0040)"
    )


def test_load_file_reads_the_file():
    result = loader.load_file(
        _testdata_path("valid/single_toplevel.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
    )

    assert result.message == single_toplevel_pb2.SingleToplevelFile(
        project=single_toplevel_pb2.SingleToplevelFile.Project(universe_name="example")
    )
    assert result.diagnostics == []


def test_load_file_diagnostics_name_the_file():
    path = _testdata_path("invalid/semantics/enums/integer_enum.defcl")

    result = loader.load_file(path, integer_enum_pb2.IntegerEnumFile)

    assert result.message is None
    (integer_enum,) = result.diagnostics
    assert integer_enum.kind == error_types.DiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == locations.SourceLocation(2, 13, 2, 13)
    assert integer_enum.field_name == "status"
    assert type(integer_enum) is errors.DclDiagnostic
    assert integer_enum.rendered == (
        f'File "{path}", line 2, column 13\n'
        "    status: 0\n"
        "            ^\n"
        "status: Integer enum values are not allowed"
    )
