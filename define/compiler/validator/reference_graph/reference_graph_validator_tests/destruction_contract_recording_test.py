# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_CLOSE_FILE = "action<my.domain.com:my_lib:/close_file>"
_CLOSE_TWO = "action<my.domain.com:my_lib:/close_two>"
_MID = "action<my.domain.com:my_lib:/mid>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DELETE_DESTRUCTOR = "action<my.domain.com:my_lib:/delete_destructor>"


def test_contract_keyed_on_contracted_origin_after_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving a caller-passed particle into a local position inside mid and destroying it there keys the Destruction Contract on the contracted origin (mid's interface), so the caller verifies its attached destructor against that origin."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the particle in position<incoming> to position<local_box>.\n"
                "        destroy the particle in position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DELETE_DESTRUCTOR
    # Keyed on the contracted origin (mid's interface), not the local position
    # mid actually destroyed it in.
    assert (
        all_diags[0].destroy_target_name
        == "position<box>::action</mid>::position<incoming>"
    )
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</file>"
    )
    assert all_diags[0].destroy_target_origin_at.line == 18
    assert all_diags[0].destroy_target_origin_at.column == 30
    assert all_diags[0].destroy_target_origin_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].auto_destruction_local_position_name is None
    assert all_diags[0].containing_definition_name is None
    # mid destroys the particle (in its local_box, line 13); /test attached the
    # destructor at the my_file creation (line 18).
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 13,
            "column": 33,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_moved_in_contracted_origin_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the required position is filled before the particle is passed in, the destructor mid fires (after moving it to a local position) is satisfied."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the particle in position<incoming> to position<local_box>.\n"
                "        destroy the particle in position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_auto_destruction_records_contract_verified_by_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving a caller-passed particle into a local position inside mid and letting it auto-destroy at block end the Destruction Contract carries the auto-destruction site so /test's diagnostic names mid's local position and mid as the containing definition."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the particle in position<incoming> to position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 51
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DELETE_DESTRUCTOR
    assert (
        all_diags[0].destroy_target_name
        == "position<box>::action</mid>::position<incoming>"
    )
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</file>"
    )
    assert all_diags[0].destroy_target_origin_at.line == 18
    assert all_diags[0].destroy_target_origin_at.column == 30
    assert all_diags[0].destroy_target_origin_at.file_path == PurePosixPath("test.dfn")
    # The auto-destruction happened inside mid, in its local_box, at block end.
    assert all_diags[0].auto_destruction_local_position_name == "position<local_box>"
    assert all_diags[0].containing_definition_name == _MID
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _MID,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 11,
            "column": 9,
            "file_path": "mid.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_auto_destruction_contract_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the required position is filled before the particle is passed in, the auto-destruction-fired destructor verifies satisfied."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</file>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the particle in position<incoming> to position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::action</mid>::position<incoming>.\n"
                "        create a particle in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_MID, _DELETE_DESTRUCTOR),
        (_TEST, _MID),
    ]


def test_destroyer_destroys_implied_position_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroying a particle in close_file's own implied position</slot> (not an interface position); with the required child filled, the caller-attached destructor verifies satisfied."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "slot.dfn": (
                "define the potential position<my.domain.com:my_lib:/slot> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    it also assigns the position</slot>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</slot>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        create a particle in position<my_file>::position</file>.\n"
                "        move the particle in position<my_file> to position<box>::position</slot>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_destroyer_destroys_implied_position_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The destroyed particle is in close_file's implied position</slot>, so the contract's destroyed position remaps through the implied-quality prefix (position<box>::position</slot>, not under action</close_file>)."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "slot.dfn": (
                "define the potential position<my.domain.com:my_lib:/slot> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "delete_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/delete_destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "close_file.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_file> {\n"
                "    it also assigns the position</slot>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</slot>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_file>.\n"
                "            }\n"
                "        }\n"
                "        define the position<my_file> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</file>.\n"
                "                it has the action</delete_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<my_file>.\n"
                "        move the particle in position<my_file> to position<box>::position</slot>.\n"
                "        create a particle in position<box>::action</close_file>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DELETE_DESTRUCTOR
    # Implied position remaps under position<box>, not under action</close_file>.
    assert all_diags[0].destroy_target_name == "position<box>::position</slot>"
    assert (
        all_diags[0].position_name == "position<box>::position</slot>::position</file>"
    )
    assert all_diags[0].destroy_target_origin_at.line == 18
    assert all_diags[0].destroy_target_origin_at.column == 30
    assert all_diags[0].destroy_target_origin_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].auto_destruction_local_position_name is None
    assert all_diags[0].containing_definition_name is None
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_CASCADE,
            "enclosing_quality_name": _CLOSE_FILE,
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 7,
            "column": 33,
            "file_path": "close_file.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DESTRUCTOR_ATTACHED,
            "enclosing_quality_name": "position<my_file>",
            "triggered_quality_name": _DELETE_DESTRUCTOR,
            "line": 14,
            "column": 28,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DELETE_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "delete_destructor.dfn",
        },
    )
    assert result.action_call_graph.edges() == [
        (_CLOSE_FILE, _DELETE_DESTRUCTOR),
        (_TEST, _CLOSE_FILE),
    ]


def test_destruction_contracts_verified_in_execution_order(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroying target1 then target2 in close_two, the caller verifies the two caller-attached destructors in that execution order, so the first diagnostic concerns target1."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "close_two.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_two> {\n"
                "    define the position<target1>.\n"
                "    define the position<target2>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target1>.\n"
                "        destroy the particle in position<target2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_two>.\n"
                "            }\n"
                "        }\n"
                "        define the position<one> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        define the position<two> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<one>.\n"
                "        create a particle in position<two>.\n"
                "        move the particle in position<one> to position<box>::action</close_two>::position<target1>.\n"
                "        move the particle in position<two> to position<box>::action</close_two>::position<target2>.\n"
                "        create a particle in position<box>::action</close_two>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresOccupiedPositionDiagnostic
    )
    assert isinstance(
        all_diags[1], diagnostics.DestructorRequiresOccupiedPositionDiagnostic
    )
    # target1 is destroyed before target2, so its diagnostic comes first.
    assert (
        all_diags[0].destroy_target_name
        == "position<box>::action</close_two>::position<target1>"
    )
    assert (
        all_diags[0].position_name
        == "position<box>::action</close_two>::position<target1>::position</file>"
    )
    assert all_diags[0].destroy_target_origin_at.line == 22
    assert all_diags[0].destroy_target_origin_at.column == 30
    assert all_diags[0].destroy_target_origin_at.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[1].destroy_target_name
        == "position<box>::action</close_two>::position<target2>"
    )
    assert (
        all_diags[1].position_name
        == "position<box>::action</close_two>::position<target2>::position</file>"
    )
    assert all_diags[1].destroy_target_origin_at.line == 23
    assert all_diags[1].destroy_target_origin_at.column == 30
    assert all_diags[1].destroy_target_origin_at.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.edges() == [
        (_CLOSE_TWO, _DESTRUCTOR),
        (_CLOSE_TWO, _DESTRUCTOR),
        (_TEST, _CLOSE_TWO),
    ]


def test_both_destructions_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When both destroyed particles have their caller-attached destructor's required position filled, neither destruction produces a diagnostic."""
    result = validate_project_with_reference_graph(
        {
            "file.dfn": "define the potential position<my.domain.com:my_lib:/file>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</file>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position</file> to position<_holder>.\n"
                "        move the particle in position<_holder> to position</file>.\n"
                "    }\n"
                "}\n"
            ),
            "close_two.dfn": (
                "define the potential action<my.domain.com:my_lib:/close_two> {\n"
                "    define the position<target1>.\n"
                "    define the position<target2>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<target1>.\n"
                "        destroy the particle in position<target2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</close_two>.\n"
                "            }\n"
                "        }\n"
                "        define the position<one> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        define the position<two> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<one>.\n"
                "        create a particle in position<one>::position</file>.\n"
                "        create a particle in position<two>.\n"
                "        create a particle in position<two>::position</file>.\n"
                "        move the particle in position<one> to position<box>::action</close_two>::position<target1>.\n"
                "        move the particle in position<two> to position<box>::action</close_two>::position<target2>.\n"
                "        create a particle in position<box>::action</close_two>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_CLOSE_TWO, _DESTRUCTOR),
        (_CLOSE_TWO, _DESTRUCTOR),
        (_TEST, _CLOSE_TWO),
    ]
