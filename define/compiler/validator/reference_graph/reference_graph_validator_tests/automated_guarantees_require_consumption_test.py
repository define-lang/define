# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import pytest

from define.compiler import diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_CHILD = "action<my.domain.com:my_lib:/child>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"
_PARENT = "action<my.domain.com:my_lib:/parent>"
_TEST = "action<my.domain.com:my_lib:/test>"
_WORKER = "action<my.domain.com:my_lib:/worker>"

_DLP_45_NOT_IMPLEMENTED = "DLP 45 interface consumption is not implemented"


@pytest.mark.xfail(strict=True, reason=_DLP_45_NOT_IMPLEMENTED)
def test_triggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_retriggered_action_interface_particle_may_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


@pytest.mark.xfail(strict=True, reason=_DLP_45_NOT_IMPLEMENTED)
def test_retriggered_action_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert diagnostic.position_name == "position<box>::action</worker>::position<input>"
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [
        (_TEST, _WORKER),
        (_TEST, _WORKER),
    ]


@pytest.mark.xfail(strict=True, reason=_DLP_45_NOT_IMPLEMENTED)
def test_caller_move_between_callee_interfaces_does_not_consume_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


@pytest.mark.xfail(strict=True, reason=_DLP_45_NOT_IMPLEMENTED)
def test_callee_move_between_its_interfaces_requires_caller_consumption(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</worker>"
    assert (
        diagnostic.position_name == "position<box>::action</worker>::position<result>"
    )
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


@pytest.mark.xfail(strict=True, reason=_DLP_45_NOT_IMPLEMENTED)
def test_constructor_interface_particle_must_depart_before_caller_ends(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diagnostic = all_diags[0]
    assert isinstance(diagnostic, diagnostics.UnconsumedActionInterfaceDiagnostic)
    assert diagnostic.action_name == "action</construct>"
    assert (
        diagnostic.position_name
        == "position<box>::action</construct>::position<result>"
    )
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert action_graph(result.operation_graphs) == [(_TEST, _CONSTRUCT)]


def test_local_parent_auto_destruction_consumes_action_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [(_TEST, _WORKER)]


def test_deeper_action_implied_position_can_leave_with_interface_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_TEST, _PARENT),
        (_TEST, _CHILD),
    ]
