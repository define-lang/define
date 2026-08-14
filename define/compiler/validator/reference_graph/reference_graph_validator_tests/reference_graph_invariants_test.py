"""Tests for invariants of reference_graph.py itself, triggered by actual Define code."""

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics


def test_multiple_pending_depth_updates_do_not_hide_cycle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    diagnostics_found = result.program_result.all_diagnostics
    assert len(diagnostics_found) == 1
    diagnostic = diagnostics_found[0]
    assert isinstance(diagnostic, diagnostics.CircularGlobalReferenceDiagnostic)
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 20
    assert diagnostic.location.end_line == 3
    assert diagnostic.location.end_column == 32
    assert diagnostic.location.file_path == PurePosixPath("c.dfn")
    assert diagnostic.cycle == [
        "position<mv:define-lang.org:reference_graph_depth:/a>",
        "position<mv:define-lang.org:reference_graph_depth:/e>",
        "position<mv:define-lang.org:reference_graph_depth:/c>",
        "position<mv:define-lang.org:reference_graph_depth:/a>",
    ]


def test_rejected_cycle_restores_depths_for_later_edge(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    diagnostics_found = result.program_result.all_diagnostics
    assert len(diagnostics_found) == 2
    first_diagnostic = diagnostics_found[0]
    assert isinstance(first_diagnostic, diagnostics.CircularGlobalReferenceDiagnostic)
    assert first_diagnostic.location.line == 3
    assert first_diagnostic.location.column == 20
    assert first_diagnostic.location.end_line == 3
    assert first_diagnostic.location.end_column == 35
    assert first_diagnostic.location.file_path == PurePosixPath("b.dfn")
    assert first_diagnostic.cycle == [
        "position<mv:define-lang.org:reference_graph_rollback:/test>",
        "position<mv:define-lang.org:reference_graph_rollback:/c>",
        "position<mv:define-lang.org:reference_graph_rollback:/a>",
        "position<mv:define-lang.org:reference_graph_rollback:/b>",
        "position<mv:define-lang.org:reference_graph_rollback:/test>",
    ]
    second_diagnostic = diagnostics_found[1]
    assert isinstance(second_diagnostic, diagnostics.CircularGlobalReferenceDiagnostic)
    assert second_diagnostic.location.line == 4
    assert second_diagnostic.location.column == 20
    assert second_diagnostic.location.end_line == 4
    assert second_diagnostic.location.end_column == 32
    assert second_diagnostic.location.file_path == PurePosixPath("b.dfn")
    assert second_diagnostic.cycle == [
        "position<mv:define-lang.org:reference_graph_rollback:/c>",
        "position<mv:define-lang.org:reference_graph_rollback:/a>",
        "position<mv:define-lang.org:reference_graph_rollback:/b>",
        "position<mv:define-lang.org:reference_graph_rollback:/c>",
    ]


def test_visited_reference_does_not_skip_independent_definition(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    diagnostics_found = result.program_result.all_diagnostics
    assert len(diagnostics_found) == 1
    diagnostic = diagnostics_found[0]
    assert isinstance(diagnostic, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diagnostic.location.line == 14
    assert diagnostic.location.column == 30
    assert diagnostic.location.end_line == 14
    assert diagnostic.location.end_column == 44
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.position_name == "position<work>"
    assert diagnostic.populated_at.line == 13
    assert diagnostic.populated_at.column == 30
    assert diagnostic.populated_at.end_line == 13
    assert diagnostic.populated_at.end_column == 44
    assert diagnostic.populated_at.file_path == PurePosixPath("test.dfn")
