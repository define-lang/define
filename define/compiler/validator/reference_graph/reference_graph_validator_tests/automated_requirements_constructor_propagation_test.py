# pyright: reportUnusedCallResult=false

# This file only covers OCCUPIED-state propagation. EMPTY-state propagation
# through constructors is structurally impossible to observe: a constructor on
# /p fires when the caller creates a particle with /p as a quality, so any
# EMPTY requirement is only observed directly by the creator, instantly at the
# moment of creation.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED_ACTION = "action<my.domain.com:my_lib:/implied_action>"
_P = "action<my.domain.com:my_lib:/p>"


def test_action_occupied_requirement_for_interface_position_propagates_via_constructor_implied_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _P
    assert all_diags[0].required_empty is False
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/implied_action>",
            "line": 6,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/implied_action>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )


def test_action_occupied_requirement_on_implied_position_propagates_via_constructor_via_implied_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _P
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<box>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 8,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.CONSTRUCTOR_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/p>",
            "line": 11,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/p>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/implied_action>",
            "line": 6,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/implied_action>",
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )
