# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_CALLER = "action<my.domain.com:my_lib:/caller>"
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_DELETE_FILE1 = "action<my.domain.com:my_lib:/delete_file1>"
_DELETE_FILE2 = "action<my.domain.com:my_lib:/delete_file2>"
_DELETE_FILE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_file_destructor>"
_DELETE_EMPTY_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_empty_destructor>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_C = "action<my.domain.com:my_lib:/destructor_c>"


def test_circular_destructor_contract_is_skipped(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</close_file>"
    assert all_diags[0].position_name == "position<dependency>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path == PurePosixPath("destructor.dfn")
    assert isinstance(all_diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[1].cycle == [_DESTRUCTOR, _CLOSE_FILE, _DESTRUCTOR]
    assert all_diags[1].location.line == 4
    assert all_diags[1].location.column == 24
    assert all_diags[1].location.file_path == PurePosixPath("close_file.dfn")
    assert result.action_call_graph.edges() == [(_TEST, _CLOSE_FILE)]


def test_circular_caller_attached_destructor_contract_is_skipped(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</caller>"
    assert all_diags[0].position_name == "position<dependency>"
    assert all_diags[0].location.line == 4
    assert all_diags[0].location.column == 24
    assert all_diags[0].location.file_path == PurePosixPath("destructor.dfn")
    assert isinstance(all_diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
    assert all_diags[1].cycle == [_DESTRUCTOR, _CALLER, _DESTRUCTOR]
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 28
    assert all_diags[1].location.file_path == PurePosixPath("caller.dfn")
    assert result.action_call_graph.edges() == [(_CALLER, _CLOSE_FILE)]


def test_missing_caller_attached_destructor_is_reported_and_skipped(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].file_path == "missing_destructor.dfn"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 35
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.edges() == [(_TEST, _CLOSE_FILE)]


def test_caller_known_child_state_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_caller_known_child_state_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 15,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 21,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_caller_known_empty_requirement_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_EMPTY_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_caller_known_empty_requirement_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is True
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_EMPTY_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 22,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>::position</file>",
            "triggered_quality_name": None,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_EMPTY_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_EMPTY_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "delete_empty_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_EMPTY_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_two_caller_attached_destructors_verified_independently(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</b>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 18,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 26,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_B,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_b.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_all_caller_attached_destructors_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_three_destructors_with_two_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</c>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_C,
            "line": 18,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 26,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR_C,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_C,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_c.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].required_empty is False
    assert all_diags[1].action_name == _CLOSE_FILE
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</b>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 17,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 26,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR_B,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_B,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor_b.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR_C),
        (_CLOSE_FILE, _DESTRUCTOR_B),
        (_CLOSE_FILE, _DESTRUCTOR_A),
        (_TEST, _CLOSE_FILE),
    ]


def test_declared_quality_destructor_verified_once(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 17,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<target>",
            "triggered_quality_name": _DESTRUCTOR,
            "line": 4,
            "column": 24,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DESTRUCTOR,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_declared_quality_destructor_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_constructor_consumer_caller_known_satisfied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_constructor_consumer_caller_known_violated(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 20,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_visible_and_caller_attached_destructors_coexist(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 25
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].required_empty is False
    assert all_diags[0].action_name == _CLOSE_FILE
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_file>::position<target>::position</file1>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 25,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<target>",
            "triggered_quality_name": _DELETE_FILE1,
            "line": 4,
            "column": 24,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE1,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE1,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file1.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 25
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].required_empty is False
    assert all_diags[1].action_name == _CLOSE_FILE
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_file>::position<target>::position</file2>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.QUALITY_ASSIGNED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_FILE2,
            "line": 19,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.PARTICLE_ORIGIN,
            "enclosing_quality_name": "position<box>::action</close_file>::position<target>",
            "triggered_quality_name": None,
            "line": 23,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _CLOSE_FILE,
            "line": 25,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_FILE2,
            "line": 11,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_FILE2,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_file2.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_FILE1),
        (_CLOSE_FILE, _DELETE_FILE2),
        (_TEST, _CLOSE_FILE),
    ]
