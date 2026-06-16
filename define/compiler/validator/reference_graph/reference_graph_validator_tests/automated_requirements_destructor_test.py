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
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_NESTED_DESTRUCTOR = "action<my.domain.com:my_lib:/nested_destructor>"
_MAKE_THING = "action<my.domain.com:my_lib:/make_thing>"
_P = "position<my.domain.com:my_lib:/p>"

# Moves its own interface position's particle out and back, so it requires
# that position to be occupied while leaving it unchanged (no guarantee).
_DESTRUCTOR_REQUIRES_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the particle in position<item> to position<_holder>.\n"
    "        move the particle in position<_holder> to position<item>.\n"
    "    }\n"
    "}\n"
)

# Creates then destroys a particle in its own interface position, so it
# requires that position to be empty while leaving it unchanged (no guarantee).
_DESTRUCTOR_REQUIRES_EMPTY = (
    "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this particle is being destroyed.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "        destroy the particle in position<item>.\n"
    "    }\n"
    "}\n"
)


def test_occupied_interface_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</destructor>::position<item>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_occupied_interface_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_empty_interface_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR_EMPTY)}


def test_empty_interface_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor_empty.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</destructor_empty>::position<item>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorRequiresEmptyPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR_EMPTY
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor_empty>::position<item>"
    )
    assert all_diags[0].filled_at.line == 12
    assert all_diags[0].filled_at.column == 30
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR_EMPTY,
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "destructor_empty.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR_EMPTY)}


def test_intermediate_position_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "leaf.dfn": (
                "define the potential position<my.domain.com:my_lib:/leaf>.\n"
            ),
            "nested_destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/nested_destructor> {\n"
                "    define the position<holder> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</leaf>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_leaf_holder>.\n"
                "        move the particle in position<holder>::position</leaf> to position<_leaf_holder>.\n"
                "        move the particle in position<_leaf_holder> to position<holder>::position</leaf>.\n"
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
                "                it has the action</nested_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</nested_destructor>::position<holder>.\n"
                "        destroy the particle in position<box>.\n"
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
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _NESTED_DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</nested_destructor>::position<holder>::position</leaf>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _NESTED_DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 11,
            "column": 30,
            "file_path": "nested_destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {(_TEST, _NESTED_DESTRUCTOR)}


def test_locally_created_interface_particle_fires_destructor_locally(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    # The particle is created in this action's own interface position, so
    # the action owns it: the destructor's requirement is checked here rather than
    # propagated to a caller, even though position<iface> is a contracted name.
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "        destroy the particle in position<iface>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<iface>"
    assert (
        all_diags[0].position_name
        == "position<iface>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_destructor_in_init_block_checks_interface_requirement_locally(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    # position</p>'s init block creates and then destroys a particle in its
    # implied position</carrier>. The init block owns that particle, so the
    # destructor's interface-position requirement is checked locally rather than
    # propagated: position</carrier> never came from a caller.
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "carrier.dfn": (
                "define the potential position<my.domain.com:my_lib:/carrier> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</carrier>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</carrier>.\n"
                "        destroy the particle in position</carrier>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
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
    assert all_diags[0].location.line == 5
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("p.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position</carrier>"
    assert (
        all_diags[0].position_name
        == "position</carrier>::action</destructor>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {(_P, _DESTRUCTOR)}


def test_callee_attached_destructor_requirement_verified_at_owning_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """make_thing attaches a destructor in a local position and moves the particle into result without filling the destructor's required child; the destructor rides the guarantee to /test, which owns the result, so destroying it directly checks the requirement (a single DIRECT_INFERENCE step, no cascade or contract) and reports the unmet position."""
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "make_thing.dfn": (
                "define the potential action<my.domain.com:my_lib:/make_thing> {\n"
                "    define the position<result>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<temp> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<temp>.\n"
                "        move the particle in position<temp> to position<result>.\n"
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
                "                it has the action</make_thing>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</make_thing>::position<run>.\n"
                "        destroy the particle in position<box>::action</make_thing>::position<result>.\n"
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
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert (
        all_diags[0].destroy_target_name
        == "position<box>::action</make_thing>::position<result>"
    )
    assert (
        all_diags[0].position_name
        == "position<box>::action</make_thing>::position<result>::action</destructor>::position<item>"
    )
    assert all_diags[0].destroy_target_origin_at.line == 13
    assert all_diags[0].destroy_target_origin_at.column == 48
    assert all_diags[0].destroy_target_origin_at.file_path == PurePosixPath(
        "make_thing.dfn"
    )
    assert all_diags[0].auto_destruction_local_position_name is None
    assert all_diags[0].containing_definition_name is None
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _DESTRUCTOR,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MAKE_THING),
        (_TEST, _DESTRUCTOR),
    }
