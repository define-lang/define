# pyright: reportUnusedCallResult=false

from __future__ import annotations

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

_PARENT = "mv:define-lang.org:parent"
_CHILD = "mv:define-lang.org:child"


def test_cross_fqun_local_to_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_cross_fqun_local_to_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_local_to_chained_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_cross_fqun_local_to_chained_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_chained_to_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_cross_fqun_chained_to_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_move_to_chained_action_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_cross_fqun_move_to_chained_action_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/quality>",
    ]


def test_cross_fqun_move_from_chained_nonexistent_local_to_constrained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ChainElementNotInterfacePositionDiagnostic
    )
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == f"action<{_CHILD}:/act>"
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 84
