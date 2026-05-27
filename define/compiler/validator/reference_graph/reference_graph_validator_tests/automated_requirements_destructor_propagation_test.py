# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_MID = "action<my.domain.com:my_lib:/mid>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"

_DESTRUCTOR_REQUIRES_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this dimension point is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the dimension point in position<item> to position<_holder>.\n"
    "        move the dimension point in position<_holder> to position<item>.\n"
    "    }\n"
    "}\n"
)

_DESTRUCTOR_REQUIRES_EMPTY = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this dimension point is being destroyed.\n"
    "    } and it does {\n"
    "        create a dimension point in position<item>.\n"
    "        destroy the dimension point in position<item>.\n"
    "    }\n"
    "}\n"
)

_DESTRUCTOR_REQUIRES_IMPLIED_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    it also assigns the position</marker>.\n"
    "    it happens when {\n"
    "        this dimension point is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_holder>.\n"
    "        move the dimension point in position</marker> to position<_holder>.\n"
    "        move the dimension point in position<_holder> to position</marker>.\n"
    "    }\n"
    "}\n"
)

_DESTRUCTOR_REQUIRES_CHILD_OCCUPIED = (
    "define the potential action<my.domain.com:my_lib:/destructor> {\n"
    "    define the position<holder> {\n"
    "        it may only contain dimension points where {\n"
    "            it has the position</leaf>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        this dimension point is being destroyed.\n"
    "    } and it does {\n"
    "        define the position<_leaf_holder>.\n"
    "        move the dimension point in position<holder>::position</leaf> to position<_leaf_holder>.\n"
    "        move the dimension point in position<_leaf_holder> to position<holder>::position</leaf>.\n"
    "    }\n"
    "}\n"
)


def test_interface_occupied_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    # action_name is the immediate triggered action (mid); the destructor that
    # fires through mid's destruction-of-incoming shows up as a step in the
    # propagation chain.
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 40
    assert all_diags[0].inferred_at.end_line == 11
    assert all_diags[0].inferred_at.end_column == 58
    assert all_diags[0].inferred_at.file_path == PurePosixPath("mid.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<item>",
            "line": 7,
            "column": 37,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_interface_empty_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_EMPTY,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>::action</destructor>::position<item>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    # action_name is the immediate triggered action (mid); the destructor that
    # fires through mid's destruction-of-incoming shows up as a step in the
    # propagation chain.
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 40
    assert all_diags[0].inferred_at.end_line == 11
    assert all_diags[0].inferred_at.end_column == 58
    assert all_diags[0].inferred_at.file_path == PurePosixPath("mid.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<item>",
            "line": 6,
            "column": 37,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_implied_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor.dfn": _DESTRUCTOR_REQUIRES_IMPLIED_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    # action_name is the immediate triggered action (mid); the destructor that
    # fires through mid's destruction-of-incoming shows up as a step in the
    # propagation chain.
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::position</marker>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 40
    assert all_diags[0].inferred_at.end_line == 11
    assert all_diags[0].inferred_at.end_column == 58
    assert all_diags[0].inferred_at.file_path == PurePosixPath("mid.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</marker>",
            "line": 7,
            "column": 37,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_child_requirement_propagates_and_is_violated_at_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "leaf.dfn": "define the potential position<my.domain.com:my_lib:/leaf>.\n",
            "destructor.dfn": _DESTRUCTOR_REQUIRES_CHILD_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>::action</destructor>::position<holder>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    # action_name is the immediate triggered action (mid); the destructor that
    # fires through mid's destruction-of-incoming shows up as a step in the
    # propagation chain.
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<holder>::position</leaf>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 40
    assert all_diags[0].inferred_at.end_line == 11
    assert all_diags[0].inferred_at.end_column == 58
    assert all_diags[0].inferred_at.file_path == PurePosixPath("mid.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</leaf>",
            "line": 11,
            "column": 37,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_requirement_follows_moved_in_dimension_point_to_contracted_origin(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local_box>.\n"
                "        move the dimension point in position<incoming> to position<local_box>.\n"
                "        destroy the dimension point in position<local_box>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    # action_name is the immediate triggered action (mid); the destructor that
    # fires through mid's destruction-of-incoming shows up as a step in the
    # propagation chain.
    assert all_diags[0].action_name == _MID
    assert (
        all_diags[0].position_name
        == "position<box>::action</mid>::position<incoming>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 13
    assert all_diags[0].inferred_at.column == 40
    assert all_diags[0].inferred_at.end_line == 13
    assert all_diags[0].inferred_at.end_column == 59
    assert all_diags[0].inferred_at.file_path == PurePosixPath("mid.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<item>",
            "line": 7,
            "column": 37,
            "file_path": "destructor.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }


def test_propagated_requirement_satisfied_at_caller_produces_no_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "mid.dfn": (
                "define the potential action<my.domain.com:my_lib:/mid> {\n"
                "    define the position<incoming> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<incoming>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>.\n"
                "        create a dimension point in position<box>::action</mid>::position<incoming>::action</destructor>::position<item>.\n"
                "        create a dimension point in position<box>::action</mid>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MID),
        (_MID, _DESTRUCTOR),
    }
