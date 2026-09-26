from __future__ import annotations

import ast

from define.testdata import diagnostic_assertions


def _problems(source: str) -> list[str]:
    function = ast.parse(source).body[0]
    assert isinstance(function, ast.FunctionDef)
    return diagnostic_assertions.unasserted_diagnostic_fields(function)


def test_all_fields_asserted():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().all_diagnostics
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags[0].location.line == 7
    assert diags[0].location.column == 33
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].position_name == "position<target>"
""")
        == []
    )


def test_missing_location_and_field():
    assert _problems("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().all_diagnostics
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags[0].location.line == 7
    assert diags[0].location.column == 33
""") == [
        "line 4: validate_testdata_structural().all_diagnostics[0] is a DestroyInEmptyPositionDiagnostic, but the test does not assert on location.file_path, position_name"
    ]


def test_whole_location_asserted():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diag = validate_testdata_structural().all_diagnostics[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diag.location == location
    assert diag.position_name == "position<target>"
""")
        == []
    )


def test_tuple_unpacking():
    assert _problems("""
def test_case(validate_testdata_structural):
    first, second = validate_testdata_structural().all_diagnostics
    assert isinstance(first, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert isinstance(second, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert first.location.line == 7
    assert first.location.column == 33
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.position_name == "position<target>"
""") == [
        "line 5: validate_testdata_structural().all_diagnostics[1] is a DestroyInEmptyPositionDiagnostic, but the test does not assert on location.line, location.column, location.file_path, position_name"
    ]


def test_loop_assertions_apply_to_each_element():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().all_diagnostics
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert isinstance(diags[1], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags[0].position_name == "position<first>"
    assert diags[1].position_name == "position<second>"
    for diag in diags:
        assert diag.location.line == 7
        assert diag.location.column == 33
        assert diag.location.file_path == PurePosixPath("test.dfn")
""")
        == []
    )


def test_loop_element_checked_alone():
    assert _problems("""
def test_case(validate_testdata_structural):
    for diag in validate_testdata_structural().all_diagnostics:
        assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
        assert diag.location.line == 7
""") == [
        "line 4: validate_testdata_structural().all_diagnostics[*each] is a DestroyInEmptyPositionDiagnostic, but the test does not assert on location.column, location.file_path, position_name"
    ]


def test_list_equality_asserts_every_element():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().all_diagnostics
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags == [expected]
""")
        == []
    )


def test_not_none_check_does_not_assert_optional_location():
    assert _problems("""
def test_case(validate_testdata_structural):
    diag = validate_testdata_structural().all_diagnostics[0]
    assert isinstance(diag, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diag.location == location
    assert diag.position_name == "position<dest>"
    assert diag.occupied_at is not None
    assert diag.occupied_at.line == 13
""") == [
        "line 4: validate_testdata_structural().all_diagnostics[0] is a MoveToOccupiedPositionDiagnostic, but the test does not assert on occupied_at.column, occupied_at.file_path"
    ]


def test_none_check_asserts_optional_location():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diag = validate_testdata_structural().all_diagnostics[0]
    assert isinstance(diag, diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diag.location == location
    assert diag.position_name == "position<dest>"
    assert diag.occupied_at is None
""")
        == []
    )


def test_boolean_and_helper_assertions():
    assert (
        _problems("""
def test_case(validate_testdata_project_with_reference_graph):
    diag = validate_testdata_project_with_reference_graph().program_result.all_diagnostics[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location == location
    assert diag.position_name == "position<box>" and diag.action_name == action_name
    assert not diag.required_empty
    assert not diag.required_value
    assert_propagation_chain(diag, step)
""")
        == []
    )


def test_isinstance_on_field_asserts_field():
    assert (
        _problems("""
def test_case(validate_testdata_structural):
    diag = validate_testdata_structural().all_diagnostics[0]
    assert isinstance(diag, diagnostics.ConfigLoadErrorDiagnostic)
    assert diag.location == location
    assert isinstance(diag.error, config.NotProjectRootError)
""")
        == []
    )


def test_field_asserted_without_diagnostic_class():
    assert _problems("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().file_results[0].diagnostics
    assert diags[0].location.line == 7
""") == [
        "line 4: assert isinstance(validate_testdata_structural().file_results[0].diagnostics[0], diagnostics.<class>) before asserting on its fields"
    ]


def test_message_assertion_on_checked_diagnostic():
    function = ast.parse("""
def test_case(validate_testdata_structural):
    diag = validate_testdata_structural().all_diagnostics[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert "position<target>" in diag.message
""").body[0]
    assert isinstance(function, ast.FunctionDef)
    assert diagnostic_assertions.diagnostic_message_assertions(function) == [
        "line 5: assert on the fields of validate_testdata_structural().all_diagnostics[0] instead of its message"
    ]


def test_message_assertion_on_unchecked_diagnostic():
    function = ast.parse("""
def test_case(validate_testdata_structural):
    diags = validate_testdata_structural().file_results[0].diagnostics
    assert diags[1].message == "text"
""").body[0]
    assert isinstance(function, ast.FunctionDef)
    assert diagnostic_assertions.diagnostic_message_assertions(function) == [
        "line 4: assert on the fields of validate_testdata_structural().file_results[0].diagnostics[1] instead of its message"
    ]


def test_message_of_other_value_allowed():
    function = ast.parse("""
def test_case(validate_testdata_structural):
    result = validate_testdata_structural()
    assert result.all_exceptions[0].message == "text"
""").body[0]
    assert isinstance(function, ast.FunctionDef)
    assert diagnostic_assertions.diagnostic_message_assertions(function) == []
