# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the constructor guarantee scenarios are complex enough to need
# prose explanations of what each test verifies.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_nested_constructor_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>::position</a>"
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].position_name == "position<box>::position</a>::position</dep>"


def test_constructor_overrides_inner_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_no_constructor_no_effect(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_inferred_occupied_does_not_apply_constructor_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct_a>"
    assert all_diags[0].position_name == "position<item>"


def test_caller_sees_constructor_child_guarantees_through_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>"
    )


def test_nested_quality_guarantees_visible_through_action_chain(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>::position</dep>"
    )


_PARENT_FQUN = "mv:define-lang.org:parent"
_CHILD_FQUN = "mv:define-lang.org:child"


def test_cross_universe_constraint_triggers_constructor(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 121
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 42
    assert all_diags[0].populated_at.file_path == PurePosixPath("lib/construct_a.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == f"position<box>::position<{_CHILD_FQUN}:/b>"
    assert all_diags[1].populated_at.line == 6
    assert all_diags[1].populated_at.column == 30
    assert all_diags[1].populated_at.end_line == 6
    assert all_diags[1].populated_at.end_column == 42
    assert all_diags[1].populated_at.file_path == PurePosixPath("lib/construct_b.dfn")


def test_constructor_applies_after_non_constructor_action_in_constraints(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 19
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "position<box>::position</target>::position</bar>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 44
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct_bar.dfn")


def test_constrained_constructor_assigns_implied_in_parent(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 9
    assert all_diags[0].location.end_column == 56
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</p>::position</r>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 42
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct_q.dfn")
