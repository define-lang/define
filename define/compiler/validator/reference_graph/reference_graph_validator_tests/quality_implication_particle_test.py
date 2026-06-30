# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_IMPLIED_DFN = "define the potential position<my.domain.com:my_lib:/implied>.\n"

_TRANSITIVE_IMPLIED_DFN = (
    "define the potential position<my.domain.com:my_lib:/transitive_implied>.\n"
)


def test_create_in_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_between_implied_positions(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implier.dfn": "define the potential position<my.domain.com:my_lib:/implier>.\n",
            "other_implier.dfn": "define the potential position<my.domain.com:my_lib:/other_implier>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    it also assigns the position</other_implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implier>.\n"
                "        move the particle in position</implier> to position</other_implier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_chained_child_access_via_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</parent>.\n"
                "        destroy the particle in position</parent>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_destroy_after_create_in_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implier.dfn": "define the potential position<my.domain.com:my_lib:/implier>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implier>.\n"
                "        destroy the particle in position</implier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_into_implied_position_missing_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "plain.dfn": "define the potential position<my.domain.com:my_lib:/plain>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</plain>.\n"
                "    it also assigns the position</parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</plain>.\n"
                "        move the particle in position</plain> to position</parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position</plain>"
    assert all_diags[0].target_position == "position</parent>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/child>",
    ]


def test_create_in_occupied_implied_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")


def test_destroy_in_empty_implied_position_inferrs_created(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_empty_implied_position_infers_occupied(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implier.dfn": "define the potential position<my.domain.com:my_lib:/implier>.\n",
            "other_implier.dfn": "define the potential position<my.domain.com:my_lib:/other_implier>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    it also assigns the position</other_implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implier> to position</other_implier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_round_trip_local_to_implied_back_to_local_preserves_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local_a> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<bearer>.\n"
                "        define the position<local_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local_a>.\n"
                "        move the particle in position<local_a> to position<bearer>.\n"
                "        move the particle in position<bearer> to position<local_b>.\n"
                "        destroy the particle in position<local_b>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_round_trip_implied_to_local(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            # TODO: Rename these and improve this test to prove that qualities
            # are preserved.
            "implier.dfn": "define the potential position<my.domain.com:my_lib:/implier>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a particle in position</implier>.\n"
                "        move the particle in position</implier> to position<local>.\n"
                "        move the particle in position<local> to position</implier>.\n"
                "        destroy the particle in position</implier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_local_to_implied_marks_local_empty(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a particle in position<local>.\n"
                "        move the particle in position<local> to position</implied>.\n"
                "        destroy the particle in position<local>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<local>"


def test_move_from_implied_to_local_marks_implied_empty(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a particle in position</implied>.\n"
                "        move the particle in position</implied> to position<local>.\n"
                "        destroy the particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"


def test_move_respects_direct_implied_qualities(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<source> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<destination> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<source>.\n"
                "        move the particle in position<source> to position<destination>.\n"
                "        destroy the particle in position<destination>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_respects_transitively_constructed_occupancy(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "transitive_implied.dfn": _TRANSITIVE_IMPLIED_DFN,
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</transitive_implied>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</transitive_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "holder.dfn": (
                "define the potential position<my.domain.com:my_lib:/holder> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</inner>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    it also assigns the position</holder>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</holder>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<source> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<destination> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</holder>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<source>.\n"
                "        move the particle in position<source> to position<destination>.\n"
                "        destroy the particle in position<destination>::position</holder>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_two_different_implier_constructors_conflict(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "first_implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/first_implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "second_implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/second_implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</first_implier>.\n"
                "            it has the action</second_implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is True
    assert diag.action_name == "action<my.domain.com:my_lib:/second_implier>"
    assert diag.position_name == "position<box>::position</implied>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.end_line == 12
    assert diag.location.end_column == 43
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::position</implied>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "first_implier.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/second_implier>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/second_implier>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 30,
            "file_path": "second_implier.dfn",
        },
    )


def test_three_level_chain_create_destroy_create_constructors(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "cell.dfn": "define the potential position<my.domain.com:my_lib:/cell>.\n",
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</cell>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</cell>.\n"
                "    }\n"
                "}\n"
            ),
            "emptier.dfn": (
                "define the potential action<my.domain.com:my_lib:/emptier> {\n"
                "    it also assigns the position</cell>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        destroy the particle in position</cell>.\n"
                "    }\n"
                "}\n"
            ),
            "refiller.dfn": (
                "define the potential action<my.domain.com:my_lib:/refiller> {\n"
                "    it also assigns the position</cell>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</cell>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</filler>.\n"
                "            it has the action</emptier>.\n"
                "            it has the action</refiller>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_sibling_constructor_empty_guarantee_violates_later_occupied_requirement(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "slot.dfn": "define the potential position<my.domain.com:my_lib:/slot>.\n",
            "emptier.dfn": (
                "define the potential action<my.domain.com:my_lib:/emptier> {\n"
                "    it also assigns the position</slot>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</slot>.\n"
                "        destroy the particle in position</slot>.\n"
                "    }\n"
                "}\n"
            ),
            "requirer.dfn": (
                "define the potential action<my.domain.com:my_lib:/requirer> {\n"
                "    it also assigns the position</slot>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        destroy the particle in position</slot>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</emptier>.\n"
                "            it has the action</requirer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.InferredRequirementViolationDiagnostic)
    assert diag.required_empty is False
    assert diag.action_name == "action<my.domain.com:my_lib:/requirer>"
    assert diag.position_name == "position<box>::position</slot>"
    assert diag.location.line == 12
    assert diag.location.column == 30
    assert diag.location.end_line == 12
    assert diag.location.end_column == 43
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        diag,
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/test>",
            "triggered_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "action<my.domain.com:my_lib:/requirer>",
            "triggered_quality_name": None,
            "line": 6,
            "column": 33,
            "file_path": "requirer.dfn",
        },
    )


def test_destroy_in_emptied_interface_child_after_constructor_fills_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "emptier.dfn": "define the potential position<my.domain.com:my_lib:/emptier>.\n",
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</emptier>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</filler>.\n"
                "            it has the position</emptier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<source>.\n"
                "        destroy the particle in position<source>::position</emptier>.\n"
                "        destroy the particle in position<source>::position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diag.location.line == 14
    assert diag.location.column == 33
    assert diag.location.end_line == 14
    assert diag.location.end_column == 69
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.position_name == "position<source>::position</emptier>"
