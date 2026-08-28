# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph_set,
)
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )

_TEST = "action<my.domain.com:my_lib:/test>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_MAIN_FQUN = "mv:define-lang.org:main_lib"
_DEP_FQUN = "mv:define-lang.org:dep_lib"


def test_cross_fqun_inner_requirement_renders_correctly(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 21
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is True
    assert diag.action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        diag.position_name
        == f"position<box>::action</outer>::position<iface>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<box>::action</outer>::position<iface>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_propagates(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_cross_fqun_occupied_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/outer>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "line": 18,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/inner>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "lib/inner.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/outer>"),
        (f"action<{_MAIN_FQUN}:/outer>", f"action<{_DEP_FQUN}:/inner>"),
    }


def test_complex_chain_same_fqun_position_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/foo>"
    assert (
        all_diags[0].position_name
        == "position<local>::position</x>::action</foo>::position<iface>::position</middle_position>::position</bar_position>::position</leaf>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::position</x>::action</foo>::position<iface>::position</middle_position>::position</bar_position>::position</leaf>",
            "triggered_quality_name": None,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": "action<my.domain.com:my_lib:/foo>",
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/foo>",
            "triggered_quality_name": _MIDDLE,
            "line": 18,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _MIDDLE,
            "triggered_quality_name": "action<my.domain.com:my_lib:/bar>",
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/bar>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        ("action<my.domain.com:my_lib:/foo>", _MIDDLE),
        (_TEST, "action<my.domain.com:my_lib:/foo>"),
        (_MIDDLE, "action<my.domain.com:my_lib:/bar>"),
    }


def test_complex_chain_cross_fqun_position_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.location.line == 23
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.required_empty is True
    assert diag.action_name == f"action<{_MAIN_FQUN}:/foo>"
    assert (
        diag.position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::position</middle_position>::position</bar_position>::position<{_DEP_FQUN}:/x>"
    )
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": f"position<local>::position</x>::action</foo>::position<iface>::position</middle_position>::position</bar_position>::position<{_DEP_FQUN}:/x>",
            "triggered_quality_name": None,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/test>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/foo>",
            "triggered_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "line": 18,
            "column": 30,
            "file_path": "foo.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": f"action<{_MAIN_FQUN}:/middle>",
            "triggered_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "line": 18,
            "column": 30,
            "file_path": "middle.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": f"action<{_DEP_FQUN}:/bar>",
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "lib/bar.dfn",
        },
    )
    assert action_graph_set(result.operation_graphs) == {
        (f"action<{_MAIN_FQUN}:/test>", f"action<{_MAIN_FQUN}:/foo>"),
        (f"action<{_MAIN_FQUN}:/foo>", f"action<{_MAIN_FQUN}:/middle>"),
        (f"action<{_MAIN_FQUN}:/middle>", f"action<{_DEP_FQUN}:/bar>"),
    }
