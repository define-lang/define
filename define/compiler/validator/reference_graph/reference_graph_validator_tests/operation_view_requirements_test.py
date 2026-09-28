"""Reference graph validation of Matching View Requirements for Operation Argument Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_extra_caller_constraints(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_duplicate_caller_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 29
    assert diagnostic.location.column == 21
    assert diagnostic.local_name == "number"
    assert diagnostic.first_definition_line == 22


def test_value_mismatch(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.VIEW
    assert diagnostic.missing_qualities == ["value<standard:/number/rational>"]


def test_missing_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 37
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.looked_at_name == "view<number>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.VIEW
    assert diagnostic.missing_qualities == ["encoding<standard:/number/decimal/ascii>"]


def test_literal_with_encoding_constraint(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_invalid_literal_content(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLiteralContentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 30
    assert diagnostic.location.column == 68
    assert diagnostic.content == "abc"
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.reason == "'a' is not allowed in a number"


def test_literal_value_has_no_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueHasNoEncodingDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 42
    assert diagnostic.value_type == "value</count>"


def test_literal_for_view_without_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ViewMissingValueConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 21
    assert diagnostic.view_name == "view<source>"


def test_looks_at_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UndefinedLocalNameDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 30
    assert diagnostic.location.column == 42
    assert diagnostic.local_name == "view<missing>"


def test_looks_at_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.OperationArgumentPositionDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 30
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position<number>"


def test_invalid_literal_content_in_action(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.InvalidLiteralContentDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 68
    assert diagnostic.content == "x"
    assert diagnostic.potential_literal == "literal<standard:/number>"
    assert diagnostic.value_encoding == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.reason == "'x' is not allowed in a number"


def test_position_missing_value_type(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 35
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.looked_at_name == "position<second>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.POSITION
    assert diagnostic.missing_qualities == ["value<standard:/number/rational>"]


def test_position_value_mismatch(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 38
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<target>"
    assert diagnostic.looked_at_name == "position<second>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.POSITION
    assert diagnostic.missing_qualities == ["value<standard:/number/rational>"]


def test_position_missing_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(
        diagnostic, diagnostics.OperationArgumentViolatesConstraintsDiagnostic
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 39
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<source>"
    assert diagnostic.looked_at_name == "position<first>"
    assert diagnostic.looked_at_kind == diagnostics.LookedAtKind.POSITION
    assert diagnostic.missing_qualities == ["encoding<standard:/number/decimal/ascii>"]


def test_position_matching_encoding(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_particle_qualities_in_unconstrained_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)
