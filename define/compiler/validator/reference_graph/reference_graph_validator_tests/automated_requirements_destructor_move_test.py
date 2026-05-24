# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"


def test_interface_to_local_occupied_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<tmp> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        define the position<_leaf>.\n"
                "        move the dimension point in position<source> to position<tmp>.\n"
                "        move the dimension point in position<tmp>::position</child> to position<_leaf>.\n"
                "        move the dimension point in position<_leaf> to position<tmp>::position</child>.\n"
                "        move the dimension point in position<tmp> to position<source>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>::position</child>.\n"
                "        destroy the dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_interface_to_local_occupied_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<tmp> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        define the position<_leaf>.\n"
                "        move the dimension point in position<source> to position<tmp>.\n"
                "        move the dimension point in position<tmp>::position</child> to position<_leaf>.\n"
                "        move the dimension point in position<_leaf> to position<tmp>::position</child>.\n"
                "        move the dimension point in position<tmp> to position<source>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>.\n"
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
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<source>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 17
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_interface_to_local_empty_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<tmp> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<source> to position<tmp>.\n"
                "        create a dimension point in position<tmp>::position</child>.\n"
                "        destroy the dimension point in position<tmp>::position</child>.\n"
                "        move the dimension point in position<tmp> to position<source>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>::position</child>.\n"
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
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<source>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 16
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_implied_to_local_occupied_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<tmp> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        define the position<_leaf>.\n"
                "        move the dimension point in position</marker> to position<tmp>.\n"
                "        move the dimension point in position<tmp>::position</child> to position<_leaf>.\n"
                "        move the dimension point in position<_leaf> to position<tmp>::position</child>.\n"
                "        move the dimension point in position<tmp> to position</marker>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</marker>.\n"
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
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::position</marker>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 13
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_implied_to_local_empty_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/marker> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<tmp> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position</marker> to position<tmp>.\n"
                "        create a dimension point in position<tmp>::position</child>.\n"
                "        destroy the dimension point in position<tmp>::position</child>.\n"
                "        move the dimension point in position<tmp> to position</marker>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</marker>.\n"
                "        create a dimension point in position<box>::position</marker>::position</child>.\n"
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
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::position</marker>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 12
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_interface_to_implied_occupied_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "dest_marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/dest_marker> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</dest_marker>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_leaf>.\n"
                "        move the dimension point in position<source> to position</dest_marker>.\n"
                "        move the dimension point in position</dest_marker>::position</child> to position<_leaf>.\n"
                "        move the dimension point in position<_leaf> to position</dest_marker>::position</child>.\n"
                "        move the dimension point in position</dest_marker> to position<source>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</destructor>::position<source>.\n"
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
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</destructor>::position<source>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 13
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_implied_to_implied_occupied_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "source_marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/source_marker> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "dest_marker.dfn": (
                "define the potential position<my.domain.com:my_lib:/dest_marker> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "destructor.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor> {\n"
                "    it also assigns the position</source_marker>.\n"
                "    it also assigns the position</dest_marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_leaf>.\n"
                "        move the dimension point in position</source_marker> to position</dest_marker>.\n"
                "        move the dimension point in position</dest_marker>::position</child> to position<_leaf>.\n"
                "        move the dimension point in position<_leaf> to position</dest_marker>::position</child>.\n"
                "        move the dimension point in position</dest_marker> to position</source_marker>.\n"
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
                "                it has the action</destructor>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</source_marker>.\n"
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
    assert all_diags[0].destructor_name == _DESTRUCTOR
    assert all_diags[0].destroy_target_name == "position<box>"
    assert (
        all_diags[0].position_name
        == "position<box>::position</source_marker>::position</child>"
    )
    assert all_diags[0].inferred_at.line == 9
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}
