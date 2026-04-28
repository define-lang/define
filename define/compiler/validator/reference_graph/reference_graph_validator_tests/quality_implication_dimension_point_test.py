# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

_IMPLIED_DFN = "define the potential position<my.domain.com:my_lib:/implied>.\n"

_PLAIN_DFN = "define the potential position<my.domain.com:my_lib:/plain>.\n"

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


@pytest.mark.xfail(
    reason=(
        "Expected: no diagnostics. Actual: validator emits"
        " DestroyInEmptyPositionDiagnostic for position</parent>::position</child>."
    ),
    strict=True,
)
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


@pytest.mark.xfail(
    reason=(
        "Validator is not tracking dimension point qualities correctly across"
        " moves, somehow: it does not detect that the source DP lacks a quality"
        " transitively required by the destination position, so no"
        " MoveViolatesConstraintsDiagnostic is emitted."
    ),
    strict=True,
)
def test_move_into_implied_position_missing_quality(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": _IMPLIED_DFN,
            "plain.dfn": _PLAIN_DFN,
            "implier.dfn": _IMPLIER_DFN,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</plain>.\n"
                "    it also assigns the position</implier>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</plain>.\n"
                "        move the dimension point in position</plain> to position</implier>.\n"
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
    assert all_diags[0].target_position == "position</implier>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/implied>",
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


@pytest.mark.xfail(
    reason="We should be inferring that a DP exists in position</implier>.",
    strict=True,
)
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
