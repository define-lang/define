# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_EMPTY = "action<my.domain.com:my_lib:/destructor_empty>"
_P = "position<my.domain.com:my_lib:/p>"


def test_occupied_implied_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor.dfn": (
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
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_occupied_implied_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor.dfn": (
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
    assert all_diags[0].position_name == "position<box>::position</marker>"
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR)}


def test_empty_implied_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor_empty.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        create a dimension point in position</marker>.\n"
                "        destroy the dimension point in position</marker>.\n"
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


def test_empty_implied_requirement_violated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor_empty.dfn": (
                "define the potential action<my.domain.com:my_lib:/destructor_empty> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this dimension point is being destroyed.\n"
                "    } and it does {\n"
                "        create a dimension point in position</marker>.\n"
                "        destroy the dimension point in position</marker>.\n"
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
                "                it has the action</destructor_empty>.\n"
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
        all_diags[0], diagnostics.DestructorRequiresEmptyPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].destructor_name == _DESTRUCTOR_EMPTY
    assert all_diags[0].destroy_target_name == "position<box>"
    assert all_diags[0].position_name == "position<box>::position</marker>"
    assert all_diags[0].inferred_at.line == 6
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor_empty.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert all_diags[0].filled_at.line == 12
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert result.action_call_graph.unique_edges() == {(_TEST, _DESTRUCTOR_EMPTY)}


def test_destructor_in_init_block_checks_implied_requirement_locally(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    # position</p>'s init block creates and then destroys a dimension point in its
    # implied position</carrier>, whose destructor requires its own implied
    # position</marker>. The init block owns that dimension point, so the
    # requirement is checked locally rather than propagated.
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "destructor.dfn": (
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
            ),
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
    assert all_diags[0].position_name == "position</carrier>::position</marker>"
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("destructor.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_P, _DESTRUCTOR)}
