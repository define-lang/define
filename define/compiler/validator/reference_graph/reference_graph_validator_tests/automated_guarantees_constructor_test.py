# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"


def test_constructor_implied_position_guarantee_visible_to_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "color.dfn": "define the potential position<my.domain.com:my_lib:/color>.\n",
            # Assigns an implied position and fills it, so creating a particle
            # that bears it guarantees the implied position ends up occupied.
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the position</color>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</color>.\n"
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
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>::position</color>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    # The caller can destroy the particle in box::position</color> only because
    # the constructor's guarantee tells it that position ends up occupied.
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _CONSTRUCT)]


def test_constructor_occupied_guarantee_conflicts_with_caller_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "color.dfn": "define the potential position<my.domain.com:my_lib:/color>.\n",
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it also assigns the position</color>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</color>.\n"
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
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</color>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    # The constructor already filled box::position</color>, so the caller's own
    # create there conflicts with that guarantee.
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</color>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct.dfn")
    assert result.action_call_graph.edges() == [(_TEST, _CONSTRUCT)]
