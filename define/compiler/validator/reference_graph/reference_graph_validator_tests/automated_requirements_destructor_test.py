# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_NESTED_DESTRUCTOR = "action<my.domain.com:my_lib:/nested_destructor>"
_P = "position<my.domain.com:my_lib:/p>"

# Moves its own interface position's dimension point out and back, so it requires
# that position to be occupied while leaving it unchanged (no guarantee).
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

# Creates then destroys a dimension point in its own interface position, so it
# requires that position to be empty while leaving it unchanged (no guarantee).
_DESTRUCTOR_REQUIRES_EMPTY = (
    "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        this dimension point is being destroyed.\n"
    "    } and it does {\n"
    "        create a dimension point in position<item>.\n"
    "        destroy the dimension point in position<item>.\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<item>.\n"
                "        destroy the dimension point in position<box>.\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        destroy the dimension point in position<box>.\n"
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
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        destroy the dimension point in position<box>.\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</destructor_empty>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor_empty>::position<item>.\n"
                "        destroy the dimension point in position<box>.\n"
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
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR_EMPTY
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor_empty>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 6
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor_empty.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert all_diags[0].filled_at.line == 12
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
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
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</nested_destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</nested_destructor>::position<holder>.\n"
                "        destroy the dimension point in position<box>.\n"
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
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _NESTED_DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</nested_destructor>::position<holder>::position</leaf>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("nested_destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _NESTED_DESTRUCTOR)}


def test_locally_created_interface_dimension_point_fires_destructor_locally(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    # The dimension point is created in this action's own interface position, so
    # the action owns it: the destructor's requirement is checked here rather than
    # propagated to a caller, even though position<iface> is a contracted name.
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>.\n"
                "        destroy the dimension point in position<iface>.\n"
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
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<iface>"
    assert (
        all_diags[0].position_name
        == "position<iface>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_destructor_in_init_block_checks_interface_requirement_locally(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    # position</p>'s init block creates and then destroys a dimension point in its
    # implied position</carrier>. The init block owns that dimension point, so the
    # destructor's interface-position requirement is checked locally rather than
    # propagated: position</carrier> never came from a caller.
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _DESTRUCTOR_REQUIRES_OCCUPIED,
            "carrier.dfn": (
                "define the potential position<my.domain.com:my_lib:/carrier> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</carrier>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</carrier>.\n"
                "        destroy the dimension point in position</carrier>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
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
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("p.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position</carrier>"
    assert (
        all_diags[0].position_name
        == "position</carrier>::action</destructor>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_P, _DESTRUCTOR)}
