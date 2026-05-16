# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

import pytest

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors


def test_single_level_transitivity_satisfies_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
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
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_single_level_transitivity_does_not_include_unrelated(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "unrelated.dfn": "define the potential position<my.domain.com:my_lib:/unrelated>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</unrelated>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/unrelated>",
    ]


def test_multi_level_transitivity(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "transitive_implied.dfn": "define the potential position<my.domain.com:my_lib:/transitive_implied>.\n",
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied> {\n"
                "    it also assigns the position</transitive_implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</transitive_implied>.\n"
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
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</transitive_implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_diamond_transitivity_create_conflict_detected(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    # Two impliers both implying the same position and both creating in it
    # via their init blocks is genuinely illegal: when the second implier's
    # init block runs, the implied position has already been filled by the
    # first, so the second's EMPTY-from-Create requirement is violated.
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier_one.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier_one> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier_two.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier_two> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier_one>.\n"
                "            it has the position</implier_two>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag,
        diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic,
    )
    assert diag.create_target_name == "position<source>"
    assert (
        diag.init_block_position_name == "position<my.domain.com:my_lib:/implier_two>"
    )
    assert diag.position_name == "position<source>::position</implied>"
    assert diag.location.line == 17
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.inferred_at.line == 4
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("implier_two.dfn")
    assert diag.filled_at.line == 4
    assert diag.filled_at.column == 37
    assert diag.filled_at.file_path == PurePosixPath("implier_one.dfn")
    assert diag.propagated_from_locations == []


def test_diamond_transitivity_with_create_destroy_succeeds(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier_one.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier_one> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "        destroy the dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier_two.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier_two> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "        destroy the dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier_one>.\n"
                "            it has the position</implier_two>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_action_interface_position_has_quality_with_implication_move_succeeds(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_matching_implied_but_not_matching_impliers_for_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "independent.dfn": (
                "define the potential position<my.domain.com:my_lib:/independent> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</independent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/independent>",
    ]


def test_action_guarantee_preserves_transitive_qualities(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<trigger_pos> to position<output>.\n"
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
                "                it has the action</forwarder>.\n"
                "            }\n"
                "        }\n"
                "        define the position<source> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        define the position<final_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<box>::action</forwarder>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</forwarder>::position<output> to position<final_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_action_creates_dp_in_interface_position_with_implication_constraint(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "creator.dfn": (
                "define the potential action<my.domain.com:my_lib:/creator> {\n"
                "    define the position<run>.\n"
                "    define the position<output> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<output>.\n"
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
                "                it has the action</creator>.\n"
                "            }\n"
                "        }\n"
                "        define the position<final_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</implied>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</creator>::position<run>.\n"
                "        move the dimension point in position<box>::action</creator>::position<output> to position<final_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_trigger_position_has_implication_implied(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
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
                "    define the position<run> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<stash> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<run> to position<stash>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_inferred_occupied_interface_position_has_implication_implied(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
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
                "    define the position<input> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<stash> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<input> to position<stash>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_propagated_requirement_dp_has_implication_implied(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</implied>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<input> to position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    define the position<final> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implied>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box>::action</inner>::position<run>.\n"
                "        move the dimension point in position<box>::action</inner>::position<output> to position<final>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<wrapper> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<wrapper>::action</middle>::position<box>.\n"
                "        create a dimension point in position<wrapper>::action</middle>::position<box>::action</inner>::position<input>.\n"
                "        create a dimension point in position<wrapper>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_same_path_in_different_fquns_are_distinct_qualities(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    main_fqun = "mv:define-lang.org:cross_implication_main"
    a_fqun = "mv:define-lang.org:cross_implication_lib_a"
    b_fqun = "mv:define-lang.org:cross_implication_lib_b"
    result = validate_project_with_reference_graph(
        {
            "a/foo.dfn": f"define the potential position<{a_fqun}:/foo>.\n",
            "b/foo.dfn": f"define the potential position<{b_fqun}:/foo>.\n",
            "implier.dfn": (
                f"define the potential position<{main_fqun}:/implier> {{\n"
                f"    it also assigns the position<{a_fqun}:/foo>.\n"
                "    after it is assigned {\n"
                f"        create a dimension point in position<{a_fqun}:/foo>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{main_fqun}:/test> {{\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                f"            it has the position<{b_fqun}:/foo>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=main_fqun,
        local_deps={a_fqun: "a", b_fqun: "b"},
        sub_roots={"a": a_fqun, "b": b_fqun},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{b_fqun}:/foo>",
    ]


@pytest.mark.xfail(
    reason=(
        "When a position is assigned to a dimension point, the init blocks of"
        " its transitively implied positions do not run."
    ),
    strict=True,
)
def test_required_position_init_block_creates_dp_for_move(
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
                "        define the position<_temp>.\n"
                "        move the dimension point in position</implied> to position<_temp>.\n"
                "        move the dimension point in position<_temp> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source>::position</implied> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(
    reason=(
        "When a position is assigned to a dimension point, the init blocks of"
        " its transitively implied positions do not run."
    ),
    strict=True,
)
def test_required_position_init_block_fills_position(
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
                "        define the position<_temp>.\n"
                "        move the dimension point in position</implied> to position<_temp>.\n"
                "        move the dimension point in position<_temp> to position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        create a dimension point in position<source>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<source>::position</implied>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 56
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 74
    assert all_diags[0].populated_at.file_path == PurePosixPath("implier.dfn")


def test_unresolved_implication_target_is_skipped(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</missing>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</missing>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</implier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[0].file_path == "missing.dfn"
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 34
    assert isinstance(all_diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[1].file_path == "missing.dfn"
    assert all_diags[1].location.line == 4
    assert all_diags[1].location.column == 46
