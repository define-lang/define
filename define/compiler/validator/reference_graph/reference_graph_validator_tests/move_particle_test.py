# pyright: reportUnusedCallResult=false

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataNonFilesystemWithReferenceGraph,
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_local_positions_and_move(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_between_interface_positions(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_from_chained(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_from_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_move_from_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_shared_interface_constraint(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_valid_local_positions(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_move_from_child_to_parents_empty_sibling(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_duplicate_source_definition_does_not_add_move_constraint_diagnostics(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "action"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 1


def test_undefined_from_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    results = validate_testdata_non_filesystem_with_reference_graph().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 30


def test_undefined_to_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    results = validate_testdata_non_filesystem_with_reference_graph().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 52


def test_both_positions_undefined(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    results = validate_testdata_non_filesystem_with_reference_graph().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<bad_from>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 30
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<bad_to>"
    assert diags[1].location.line == 6
    assert diags[1].location.column == 52


def test_same_fqun_must_use_short_form_in_from(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 58


def test_same_fqun_must_use_short_form_in_to(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
    )
    assert all_diags[0].fqun == "my.domain.com:my_lib"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 80


def test_valid_global_to_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "position</global_pos>"
    assert all_diags[0].full_global_name == "position<my.domain.com:my_lib:/global_pos>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 53


def test_move_to_same_position_does_not_mark_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    results = validate_testdata_non_filesystem_with_reference_graph().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveToSamePositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 45
    assert diags[0].position_name == "position<a>"
    assert isinstance(diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[1].location.line == 9
    assert diags[1].location.column == 30
    assert diags[1].position_name == "position<a>"
    assert diags[1].populated_at.line == 7


def test_move_to_chained_prefix_marks_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 74
    assert all_diags[0].source_position == "position<local_pos>"
    assert all_diags[0].target_position == "position<local_pos>::position</target_pos>"
