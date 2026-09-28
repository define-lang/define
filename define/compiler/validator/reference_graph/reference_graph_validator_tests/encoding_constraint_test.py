"""Dead code rules for encoding constraints on positions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_unused_encoding_is_dead(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadEncodingConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 28
    assert diagnostic.constraint_name == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.position_name == "position<number>"


def test_value_setting_keeps_encoding_alive(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_operation_execution_keeps_encoding_alive(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_callee_contract_keeps_encoding_alive(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_unconstrained_callee_does_not_keep_encoding_alive(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadEncodingConstraintDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 28
    assert diagnostic.location.column == 28
    assert diagnostic.constraint_name == "encoding<standard:/number/decimal/ascii>"
    assert diagnostic.position_name == "position<number>"


def test_own_contract_keeps_encoding_alive(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)
