# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_create_in_interface_produces_occupied_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_destroy_in_interface_produces_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_move_between_interfaces_produces_empty_and_moved_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<source>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        move the particle in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<source>"
    assert isinstance(
        all_diags[1],
        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic,
    )
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 50
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<dest>"
    assert all_diags[1].origin_name == "position<source>"


def test_destroy_implied_quality_produces_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</marker>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        destroy the particle in position</marker>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</marker>"


def test_local_only_destructor_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)


def test_move_out_and_back_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        move the particle in position<item> to position<_holder>.\n"
                "        move the particle in position<_holder> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)


def test_destructor_triggering_action_that_fills_a_contracted_position_is_forbidden(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</other>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].position_name == "position<item>"
    assert isinstance(
        all_diags[1], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[1].location.line == 10
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[1].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )


def test_destructor_triggering_implied_action_that_fills_an_implied_position_is_forbidden(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "marker.dfn": "define the potential position<my.domain.com:my_lib:/marker>.\n",
            "updater.dfn": (
                "define the potential action<my.domain.com:my_lib:/updater> {\n"
                "    it also assigns the position</marker>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</marker>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</updater>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in action</updater>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "action</updater>::position<trigger_pos>"
    assert isinstance(
        all_diags[1], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("updater.dfn")
    assert all_diags[1].position_name == "position</marker>"


def test_create_then_move_out_produces_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        define the position<_holder>.\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<_holder>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(
    strict=True,
    reason="A destructor that restores every position it touches should generate no guarantees, but it currently produces spurious empty guarantees.",
)
def test_destructor_triggering_action_then_destroying_what_it_filled_generates_no_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</filler>.\n"
                "    it also assigns the position</implied>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in action</filler>::position<trigger_pos>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_destructor_surfaces_nested_guarantee_pending_under_an_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/test triggers /a, which triggered /b through interface position<box>; /b's guarantee that it fills position<out> is still pending at generate, and the destructor must surface it."""
    result = validate_project_with_reference_graph(
        {
            "b.dfn": (
                "define the potential action<my.domain.com:my_lib:/b> {\n"
                "    define the position<run>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out>.\n"
                "    }\n"
                "}\n"
            ),
            # position<box> is /a's own trigger, so nothing needs to clean it up.
            # /a triggers /b through it and cleans up only its own trigger fill.
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<box> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>::action</b>::position<run>.\n"
                "        destroy the particle in position<box>::action</b>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</a>.\n"
                "    it happens when {\n"
                "        this particle is being destroyed.\n"
                "    } and it does {\n"
                "        create a particle in action</a>::position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # The interface position whose occupancy makes /b's guarantee defer to a
    # non-empty prefix in the first place; it must stay filled for the one below.
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "action</a>::position<box>"
    # Surfaced only because the destructor drains the nested guarantee still
    # pending under position<box> at generate time. Without that drain, this
    # diagnostic disappears and only the position<box> one above remains.
    assert isinstance(
        all_diags[1], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("b.dfn")
    assert all_diags[1].position_name == "position<out>"
