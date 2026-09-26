# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_move_to_chained_dest_violates_constraints(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<dest>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position</x>",
    ]


def test_move_to_chained_dest_satisfies_constraints(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_to_chained_dest_unconstrained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_chained_to_local_violates_constraints(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 59
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<b>::position</x>"
    assert all_diags[0].target_position == "position<c>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_move_from_chained_to_local_satisfies_constraints(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_unconstrained_local_to_chained_constrained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<dest>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position</x>",
    ]


def test_definition_local_to_chained_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<dest>::position</y>"
    assert all_diags[0].missing_qualities == [
        "position</x>",
    ]


def test_definition_local_to_chained_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_chained_to_definition_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 59
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<b>::position</x>"
    assert all_diags[0].target_position == "position<dest>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_chained_to_definition_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_move_from_multi_element_chain_to_unconstrained_local(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_multi_element_chain_to_constrained_local(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_three_element_chain_to_three_element_chain_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_three_element_chain_to_three_element_chain_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 73
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<a>::position</x>::position</y>"
    assert all_diags[0].target_position == "position<b>::position</z>::position</w>"
    assert all_diags[0].missing_qualities == [
        "position</x>",
    ]


def test_move_from_local_local_chain(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    results = result.file_results
    assert len(results[0].diagnostics) == 1
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert results[0].diagnostics[0].location.line == 9
    assert results[0].diagnostics[0].location.column == 43
    assert results[0].diagnostics[0].location.file_path is None
    assert results[0].diagnostics[0].local_name == "position<b>"
    assert results[0].diagnostics[0].preceding_name == "position<a>"


def test_move_from_local_local_local_chain(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    results = result.file_results
    assert len(results[0].diagnostics) == 2
    assert isinstance(
        results[0].diagnostics[0],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert results[0].diagnostics[0].location.line == 11
    assert results[0].diagnostics[0].location.column == 43
    assert results[0].diagnostics[0].location.file_path is None
    assert results[0].diagnostics[0].local_name == "position<b>"
    assert results[0].diagnostics[0].preceding_name == "position<a>"
    assert isinstance(
        results[0].diagnostics[1],
        diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    )
    assert results[0].diagnostics[1].location.line == 11
    assert results[0].diagnostics[1].location.column == 56
    assert results[0].diagnostics[1].location.file_path is None
    assert results[0].diagnostics[1].local_name == "position<c>"
    assert results[0].diagnostics[1].preceding_name == "position<b>"
