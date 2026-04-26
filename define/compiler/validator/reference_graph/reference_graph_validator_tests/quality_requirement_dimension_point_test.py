# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

_CHILD_DFN = "define the potential position<my.domain.com:my_lib:/child>.\n"

_PLAIN_DFN = "define the potential position<my.domain.com:my_lib:/plain>.\n"

_PARENT_DFN = (
    "define the potential position<my.domain.com:my_lib:/parent> {\n"
    "    this dimension point must have the position</child>.\n"
    "    after it is assigned {\n"
    "        create a dimension point in position</child>.\n"
    "    }\n"
    "}\n"
)

_OTHER_PARENT_DFN = (
    "define the potential position<my.domain.com:my_lib:/other_parent> {\n"
    "    this dimension point must have the position</child>.\n"
    "    after it is assigned {\n"
    "        create a dimension point in position</child>.\n"
    "    }\n"
    "}\n"
)


def test_create_in_quality_required_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_between_quality_required_positions(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "other_parent.dfn": _OTHER_PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
                "    this dimension point must have the position</other_parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</parent>.\n"
                "        move the dimension point in position</parent> to position</other_parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(
    reason=(
        "Validator does not propagate a global QRS-bearing position's init-block"
        " effects through chained access rooted at that global. After"
        " `create a dimension point in position</parent>`, the validator does"
        " not infer that parent's `after it is assigned` block has filled"
        " position</parent>::position</child>, so subsequent access to that"
        " chained position is wrongly seen as empty."
    ),
    strict=True,
)
def test_chained_child_access_via_quality_required_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
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


def test_destroy_in_quality_required_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</parent>.\n"
                "        destroy the dimension point in position</parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(
    reason=(
        "Validator is not tracking dimension point qualities correctly across"
        " moves, somehow: it does not detect that the source DP lacks a quality"
        " transitively required by the destination position, so no"
        " MoveViolatesConstraintsDiagnostic is emitted."
    ),
    strict=True,
)
def test_move_into_quality_required_position_missing_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "plain.dfn": _PLAIN_DFN,
            "parent.dfn": _PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</plain>.\n"
                "    this dimension point must have the position</parent>.\n"
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


def test_create_in_occupied_quality_required_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</child>.\n"
                "        create a dimension point in position</child>.\n"
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
    assert all_diags[0].position_name == "position</child>"
    assert all_diags[0].created_at.line == 7
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("test.dfn")


@pytest.mark.xfail(
    reason=(
        "Inference error: a destroy in a quality-required position whose state"
        " has not been touched by the action body should infer the position is"
        " OCCUPIED on entry (turning the destroy into an inferred caller-side"
        " requirement). Instead the validator infers EMPTY and emits"
        " DestroyInEmptyPositionDiagnostic."
    ),
    strict=True,
)
def test_destroy_in_empty_quality_required_position_inferrs_created(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_empty_quality_required_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "other_parent.dfn": _OTHER_PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
                "    this dimension point must have the position</other_parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</parent> to position</other_parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</parent>"


def test_round_trip_local_to_quality_required_back_to_local_preserves_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local_a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</parent>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local_b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</parent>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local_a>.\n"
                "        move the dimension point in position<local_a> to position</parent>.\n"
                "        move the dimension point in position</parent> to position<local_b>.\n"
                "        destroy the dimension point in position<local_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(
    reason=(
        "Validator is not tracking dimension point qualities correctly across"
        " moves, somehow: when a DP is moved out of a quality-required global"
        " position, the validator drops the QRS-derived transitive quality"
        " (here `child`), so the next move into a constrained local fails"
        " with MoveViolatesConstraintsDiagnostic instead of succeeding."
    ),
    strict=True,
)
def test_round_trip_quality_required_to_local_back_to_quality_required_preserves_transitive_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "parent.dfn": _PARENT_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</parent>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position</parent>.\n"
                "        move the dimension point in position</parent> to position<local>.\n"
                "        move the dimension point in position<local> to position</parent>.\n"
                "        destroy the dimension point in position</parent>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_move_from_local_to_quality_required_marks_local_empty(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position</child>.\n"
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


def test_move_from_quality_required_to_local_marks_quality_required_empty(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": _CHILD_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    this dimension point must have the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        create a dimension point in position</child>.\n"
                "        move the dimension point in position</child> to position<local>.\n"
                "        destroy the dimension point in position</child>.\n"
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
    assert all_diags[0].position_name == "position</child>"
