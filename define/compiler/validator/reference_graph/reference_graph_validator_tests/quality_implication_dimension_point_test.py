# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

_IMPLIED_DFN = "define the potential position<my.domain.com:my_lib:/implied>.\n"

_IMPLIER_DFN = (
    "define the potential position<my.domain.com:my_lib:/implier> {\n"
    "    it also assigns the position</implied>.\n"
    "    after it is assigned {\n"
    "        create a dimension point in position</implied>.\n"
    "    }\n"
    "}\n"
)

_OTHER_IMPLIER_DFN = (
    "define the potential position<my.domain.com:my_lib:/other_implier> {\n"
    "    it also assigns the position</implied>.\n"
    "    after it is assigned {\n"
    "        create a dimension point in position</implied>.\n"
    "    }\n"
    "}\n"
)

_TRANSITIVE_IMPLIED_DFN = (
    "define the potential position<my.domain.com:my_lib:/transitive_implied>.\n"
)

_IMPLIED_WITH_TRANSITIVE_IMPLICATION_DFN = (
    "define the potential position<my.domain.com:my_lib:/implied> {\n"
    "    it also assigns the position</transitive_implied>.\n"
    "    after it is assigned {\n"
    "        create a dimension point in position</transitive_implied>.\n"
    "    }\n"
    "}\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied>.\n"
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
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "other_implier.dfn": _OTHER_IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    it also assigns the position</other_implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implier>.\n"
                "        move the dimension point in position</implier> to position</other_implier>.\n"
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
                "    it may only contain dimension points where {\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</parent>.\n"
                "        destroy the dimension point in position</parent>::position</child>.\n"
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
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implier>.\n"
                "        destroy the dimension point in position</implier>.\n"
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
                "    it may only contain dimension points where {\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</plain>.\n"
                "        move the dimension point in position</plain> to position</parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 57
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied>.\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 37
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position</implied>.\n"
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
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "other_implier.dfn": _OTHER_IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    it also assigns the position</other_implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</implier> to position</other_implier>.\n"
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
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local_a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local_b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local_a>.\n"
                "        move the dimension point in position<local_a> to position</implier>.\n"
                "        move the dimension point in position</implier> to position<local_b>.\n"
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
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a dimension point in position</implier>.\n"
                "        move the dimension point in position</implier> to position<local>.\n"
                "        move the dimension point in position<local> to position</implier>.\n"
                "        destroy the dimension point in position</implier>.\n"
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position</implied>.\n"
                "        destroy the dimension point in position<local>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 40
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
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a dimension point in position</implied>.\n"
                "        move the dimension point in position</implied> to position<local>.\n"
                "        destroy the dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</implied>"


def test_move_respects_direct_implied_qualities(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<source> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<destination> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<destination>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_respects_transitive_implied_qualities(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "transitive_implied.dfn": _TRANSITIVE_IMPLIED_DFN,
            "implied.dfn": _IMPLIED_WITH_TRANSITIVE_IMPLICATION_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<source> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<destination> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</transitive_implied>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<destination>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_parent_and_child_implied_init_blocks_conflict(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/implier>"
    assert diag.position_name == "position<box>::position</implied>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.end_line == 11
    assert diag.location.end_column == 50
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.end_line == 4
    assert diag.inferred_at.end_column == 55
    assert diag.inferred_at.file_path == PurePosixPath("implier.dfn")
    assert diag.filled_at.line == 3
    assert diag.filled_at.column == 37
    assert diag.filled_at.end_line == 3
    assert diag.filled_at.end_column == 55
    assert diag.filled_at.file_path == PurePosixPath("implied.dfn")
    assert diag.propagated_from_locations == []


def test_two_different_implier_init_blocks_conflict(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "first_implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/first_implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "second_implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/second_implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</first_implier>.\n"
                "            it has the position</second_implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert diag.create_target_name == "position<box>"
    assert (
        diag.init_block_position_name
        == "position<my.domain.com:my_lib:/second_implier>"
    )
    assert diag.position_name == "position<box>::position</implied>"
    assert diag.location.line == 12
    assert diag.location.column == 37
    assert diag.location.end_line == 12
    assert diag.location.end_column == 50
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.end_line == 4
    assert diag.inferred_at.end_column == 55
    assert diag.inferred_at.file_path == PurePosixPath("second_implier.dfn")
    assert diag.filled_at.line == 4
    assert diag.filled_at.column == 37
    assert diag.filled_at.end_line == 4
    assert diag.filled_at.end_column == 55
    assert diag.filled_at.file_path == PurePosixPath("first_implier.dfn")
    assert diag.propagated_from_locations == []


def test_three_level_chain_create_destroy_create_init_blocks(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "sub_implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/sub_implied> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</sub_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied> {\n"
                "    it also assigns the position</sub_implied>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</sub_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</sub_implied>.\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "        create a dimension point in position</sub_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_sibling_init_block_empty_guarantee_violates_later_occupied_requirement(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "emptier.dfn": (
                "define the potential position<my.domain.com:my_lib:/emptier> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</emptier>.\n"
                "        destroy the dimension point in position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
            "requirer.dfn": (
                "define the potential position<my.domain.com:my_lib:/requirer> {\n"
                "    it also assigns the position</emptier>.\n"
                "    after it is assigned {\n"
                "        destroy the dimension point in position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</requirer>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag, diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/requirer>"
    assert diag.position_name == "position<box>::position</emptier>"
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.end_line == 11
    assert diag.location.end_column == 50
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 40
    assert diag.inferred_at.end_line == 4
    assert diag.inferred_at.end_column == 58
    assert diag.inferred_at.file_path == PurePosixPath("requirer.dfn")
    assert diag.propagated_from_locations == []


def test_destroy_in_emptied_interface_child_after_init_block_empties_it(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "emptier.dfn": (
                "define the potential position<my.domain.com:my_lib:/emptier> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</emptier>.\n"
                "        destroy the dimension point in position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</emptier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        destroy the dimension point in position<source>::position</emptier>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diag.location.line == 12
    assert diag.location.column == 40
    assert diag.location.end_line == 12
    assert diag.location.end_column == 76
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.position_name == "position<source>::position</emptier>"
