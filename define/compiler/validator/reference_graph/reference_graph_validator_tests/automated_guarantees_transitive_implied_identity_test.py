# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"

_TRANSITIVE_EDGES = {
    (_TEST, _IMPLIED),
    (_IMPLIER, _FORWARDER),
    (_FORWARDER, _IMPLIED),
}


def test_implied_to_implied_identity_preserved_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_b.dfn": "define the potential position<my.domain.com:my_lib:/implied_b>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    it also assigns the position</implied_b>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</implied_a> to position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::position</implied_b> to position<verify_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_implied_to_implied_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_b.dfn": "define the potential position<my.domain.com:my_lib:/implied_b>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    it also assigns the position</implied_b>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</implied_a> to position</implied_b>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::position</implied_b> to position<fail_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 25
    assert all_diags[0].location.column == 76
    assert all_diags[0].location.end_line == 25
    assert all_diags[0].location.end_column == 95
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<box>::position</implied_b>"
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_implied_to_interface_identity_preserved_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</implied_a> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<out> to position<verify_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_implied_to_interface_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "implied_a.dfn": "define the potential position<my.domain.com:my_lib:/implied_a>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_a>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position</implied_a> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<out> to position<fail_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 25
    assert all_diags[0].location.column == 94
    assert all_diags[0].location.end_line == 25
    assert all_diags[0].location.end_column == 113
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_interface_to_interface_identity_preserved_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<in>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<in> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<in>.\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::action</implied_action>::position<in>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<out> to position<verify_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_interface_to_interface_identity_blocks_move_to_unrelated_quality_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "secret.dfn": "define the potential position<my.domain.com:my_lib:/secret>.\n",
            "other.dfn": "define the potential position<my.domain.com:my_lib:/other>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<in>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<in> to position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<in>.\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<my_secret_holder>.\n"
                "        create a dimension point in position<box>.\n"
                "        move the dimension point in position<my_secret_holder> to position<box>::action</implied_action>::position<in>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<out> to position<fail_dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 25
    assert all_diags[0].location.column == 94
    assert all_diags[0].location.end_line == 25
    assert all_diags[0].location.end_column == 113
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES
