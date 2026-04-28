# pyright: reportUnusedCallResult=false
import pytest

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors


def test_single_level_transitivity_satisfies_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
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
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "unrelated.dfn": "define the potential position<my.domain.com:my_lib:/unrelated>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
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
            "grandchild.dfn": "define the potential position<my.domain.com:my_lib:/grandchild>.\n",
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it also assigns the position</grandchild>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</grandchild>.\n"
                "    }\n"
                "}\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</grandchild>.\n"
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


def test_diamond_transitivity(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent_one.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent_one> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "parent_two.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent_two> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent_one>.\n"
                "            it has the position</parent_two>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
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
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential action<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
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


def test_matching_children_but_not_matching_parents_for_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "independent.dfn": (
                "define the potential position<my.domain.com:my_lib:/independent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
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
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
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
                "                it has the position</parent>.\n"
                "            }\n"
                "        }\n"
                "        define the position<final_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child>.\n"
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
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "creator.dfn": (
                "define the potential action<my.domain.com:my_lib:/creator> {\n"
                "    define the position<run>.\n"
                "    define the position<output> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
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
                "                it has the position</child>.\n"
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


def test_trigger_position_has_implication_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<stash> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
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


def test_inferred_occupied_interface_position_has_implication_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<stash> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
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


def test_propagated_requirement_dp_has_implication_child(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": "define the potential position<my.domain.com:my_lib:/child>.\n",
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<run>.\n"
                "    define the position<input> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
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
                "            it has the position</child>.\n"
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
            "parent.dfn": (
                f"define the potential position<{main_fqun}:/parent> {{\n"
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
                "            it has the position</parent>.\n"
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


_IMPLIED_INIT_BLOCK_XFAIL_REASON = (
    "Validator does not yet engage init blocks of implied positions."
    " Two related gaps in"
    " define/compiler/validator/reference_graph/definition_postorder_validator.py:"
    " (1) _apply_position_init_guarantees iterates constraints.requirements"
    " (the constraint block only) rather than the transitive implication closure,"
    " so /child's init block is never applied when a DP gets /parent and /parent"
    " implies /child; (2) _check_chain_element_in_constraints checks"
    " constraint_names (constraint block only -- see ast.py PositionDefinition"
    " .constraint_names), so chain access like <source>::position</child>"
    " is rejected when /child is reached only via /parent's implication. Both"
    " pieces need to recognize transitive implications for these tests to pass."
)


@pytest.mark.xfail(reason=_IMPLIED_INIT_BLOCK_XFAIL_REASON, strict=True)
def test_required_position_init_block_creates_dp_for_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        define the position<_temp>.\n"
                "        move the dimension point in position</child> to position<_temp>.\n"
                "        move the dimension point in position<_temp> to position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        move the dimension point in position<source>::position</child> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


@pytest.mark.xfail(reason=_IMPLIED_INIT_BLOCK_XFAIL_REASON, strict=True)
def test_required_position_init_block_fills_position(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
                "    it also assigns the position</child>.\n"
                "    after it is assigned {\n"
                "        define the position<_temp>.\n"
                "        move the dimension point in position</child> to position<_temp>.\n"
                "        move the dimension point in position<_temp> to position</child>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<source> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</parent>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<source>.\n"
                "        create a dimension point in position<source>::position</child>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<source>::position</child>"
    assert all_diags[0].created_at.line == 3
    assert all_diags[0].created_at.column == 9


def test_unresolved_implication_target_is_skipped(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "parent.dfn": (
                "define the potential position<my.domain.com:my_lib:/parent> {\n"
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
                "            it has the position</parent>.\n"
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
