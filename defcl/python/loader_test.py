from __future__ import annotations

import typing

import pytest

from crates.source_rendering.python import rendering
from defcl.python import error_types, errors, loader
from defcl.testdata.invalid.semantics.schemas import (
    integer_enum_pb2,
    wrong_value_kinds_pb2,
)
from defcl.testdata.valid.schemas import (
    imports_pb2,
    shared_pb2,
    single_toplevel_pb2,
    wrapper_pb2,
)
from tools import runfiles

if typing.TYPE_CHECKING:
    from pathlib import Path


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


def test_loading_a_message_type_again_loads_the_same_message():
    source = _testdata("valid/single_toplevel.defcl")
    first = loader.load(source, single_toplevel_pb2.SingleToplevelFile)
    second = loader.load(source, single_toplevel_pb2.SingleToplevelFile)

    assert second == first


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (r"\u005c", "\\"),
        (r"\U0000005c", "\\"),
        (r"\u005cn", "\\n"),
        (r"\U0000005cx41", "\\x41"),
        (r"\u005c\n", "\\\n"),
        (r"\\u005c", r"\u005c"),
        (r"\\\u005c", "\\\\"),
        (r"\u00e9\U0001f600", "é😀"),
    ],
)
def test_unicode_escapes_preserve_the_decoded_value(text: str, expected: str):
    result = loader.load(
        f'project: {{\n  universe_name: "{text}"\n}}\n',
        single_toplevel_pb2.SingleToplevelFile,
    )

    assert result == loader.LoadResult(
        message=single_toplevel_pb2.SingleToplevelFile(
            project=single_toplevel_pb2.SingleToplevelFile.Project(
                universe_name=expected
            )
        ),
        diagnostics=[],
    )


def test_semantic_errors_are_diagnostics_without_a_message():
    result = loader.load(
        _testdata("invalid/semantics/enums/integer_enum.defcl"),
        integer_enum_pb2.IntegerEnumFile,
    )

    assert result.message is None
    (integer_enum,) = result.diagnostics
    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=11, end_line=2, end_column=11
    )
    assert integer_enum.file_path is None
    assert integer_enum.field_name == "status"


def test_syntax_error_is_a_diagnostic_without_a_message():
    result = loader.load(
        _testdata("invalid/syntax/characters/at_sign.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
    )

    assert result.message is None
    (unexpected_character,) = result.diagnostics
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


def test_file_with_only_layout_errors_loads_with_its_diagnostics():
    result = loader.load(
        'project: {\n  universe_name: "example"\n\n}\n',
        single_toplevel_pb2.SingleToplevelFile,
    )

    assert result.message == single_toplevel_pb2.SingleToplevelFile(
        project=single_toplevel_pb2.SingleToplevelFile.Project(universe_name="example")
    )
    (blank_line,) = result.diagnostics
    assert type(blank_line) is errors.SyntaxDiagnostic
    assert blank_line.kind == error_types.SyntaxDiagnosticKind.BLANK_LINE
    assert blank_line.location == rendering.SourceLocation(
        line=3, column=1, end_line=3, end_column=1
    )
    assert blank_line.file_path is None


def test_load_file_of_a_file_with_only_fields_out_of_order_loads_with_its_diagnostics():
    path = _testdata_path(
        "invalid/semantics/field_order/field_after_higher_number.defcl"
    )

    result = loader.load_file(
        path, wrong_value_kinds_pb2.WrongValueKindsFile, rendering.SourceMap()
    )

    assert result.loaded is not None
    assert result.loaded.message == wrong_value_kinds_pb2.WrongValueKindsFile(
        config=wrong_value_kinds_pb2.WrongValueKindsFile.Config(count=1, name="a")
    )
    (field_out_of_order,) = result.diagnostics
    assert type(field_out_of_order) is errors.FieldOutOfOrderDiagnostic
    assert (
        field_out_of_order.kind == error_types.SemanticDiagnosticKind.FIELD_OUT_OF_ORDER
    )
    assert field_out_of_order.location == rendering.SourceLocation(
        line=3, column=3, end_line=3, end_column=6, file_path=path
    )
    assert field_out_of_order.file_path == path
    assert field_out_of_order.field_name == "name"
    assert field_out_of_order.later_field == "count"


def test_load_file_reads_the_file():
    result = loader.load_file(
        _testdata_path("valid/single_toplevel.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
        rendering.SourceMap(),
    )

    assert result.loaded is not None
    assert result.loaded.message == single_toplevel_pb2.SingleToplevelFile(
        project=single_toplevel_pb2.SingleToplevelFile.Project(universe_name="example")
    )
    assert result.diagnostics == []


def test_load_file_diagnostics_name_the_file():
    path = _testdata_path("invalid/semantics/enums/integer_enum.defcl")

    result = loader.load_file(
        path,
        integer_enum_pb2.IntegerEnumFile,
        rendering.SourceMap(),
    )

    assert result.loaded is None
    (integer_enum,) = result.diagnostics
    assert type(integer_enum) is errors.SemanticDiagnostic
    assert integer_enum.kind == error_types.SemanticDiagnosticKind.INTEGER_ENUM
    assert integer_enum.location == rendering.SourceLocation(
        line=2, column=11, end_line=2, end_column=11, file_path=path
    )
    assert integer_enum.file_path == path
    assert integer_enum.field_name == "status"


def test_loaded_file_locates_a_field_at_its_value():
    path = _testdata_path("valid/single_toplevel.defcl")

    result = loader.load_file(
        path, single_toplevel_pb2.SingleToplevelFile, rendering.SourceMap()
    )

    assert result.loaded is not None
    assert result.loaded.file.location_of(
        ("project", "universe_name")
    ) == rendering.SourceLocation(
        line=2, column=18, end_line=2, end_column=26, file_path=path
    )


def test_loaded_file_with_layout_errors_locates_a_field(tmp_path: Path):
    path = tmp_path / "layout.defcl"
    _ = path.write_text(
        'project: {\n  universe_name:   "example"\n}\n', encoding="utf-8", newline="\n"
    )

    result = loader.load_file(
        str(path), single_toplevel_pb2.SingleToplevelFile, rendering.SourceMap()
    )

    assert result.loaded is not None
    assert result.loaded.file.location_of(
        ("project", "universe_name")
    ) == rendering.SourceLocation(
        line=2, column=20, end_line=2, end_column=28, file_path=str(path)
    )


def test_loaded_file_cannot_locate_a_field_of_a_top_level_message_it_does_not_write():
    result = loader.load_file(
        _testdata_path("valid/single_toplevel.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
        rendering.SourceMap(),
    )

    assert result.loaded is not None
    with pytest.raises(
        ValueError, match="the file does not contain the field path's top-level message"
    ):
        _ = result.loaded.file.location_of(("settings", "name"))


def test_loaded_file_rejects_a_bool_as_an_index():
    result = loader.load_file(
        _testdata_path("valid/single_toplevel.defcl"),
        single_toplevel_pb2.SingleToplevelFile,
        rendering.SourceMap(),
    )

    assert result.loaded is not None
    with pytest.raises(TypeError, match="a field path element must be a str or an int"):
        _ = result.loaded.file.location_of(("project", True))
