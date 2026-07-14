# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied_a> to position</implied_b>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "                it has the position</implied_a>.\n"
                "                it has the position</implied_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::position</implied_b> to position<verify_dest>.\n"
                "        create a particle in position<verify_dest>::position</secret>.\n"
                "        create a particle in position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied_a> to position</implied_b>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "                it has the position</implied_a>.\n"
                "                it has the position</implied_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::position</implied_b> to position<fail_dest>.\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<my_secret_holder>::position</secret>.\n"
                "        create a particle in position<fail_dest>.\n"
                "        create a particle in position<fail_dest>::position</other>.\n"
                "        create a particle in position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 69
    assert all_diags[0].location.end_line == 28
    assert all_diags[0].location.end_column == 88
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<box>::position</implied_b>"
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied_a> to position<out>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "                it has the position</implied_a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<out> to position<verify_dest>.\n"
                "        create a particle in position<verify_dest>::position</secret>.\n"
                "        create a particle in position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied_a> to position<out>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "                it has the position</implied_a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<out> to position<fail_dest>.\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<my_secret_holder>::position</secret>.\n"
                "        create a particle in position<fail_dest>.\n"
                "        create a particle in position<fail_dest>::position</other>.\n"
                "        create a particle in position<box>::position</implied_a>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 27
    assert all_diags[0].location.column == 87
    assert all_diags[0].location.end_line == 27
    assert all_diags[0].location.end_column == 106
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in> to position<out>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<in>.\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<verify_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::action</implied_action>::position<in>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<out> to position<verify_dest>.\n"
                "        create a particle in position<verify_dest>::position</secret>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]


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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<in> to position<out>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<in>.\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "        destroy the particle in position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<my_secret_holder> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</secret>.\n"
                "            }\n"
                "        }\n"
                "        define the position<fail_dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "                it has the action</implied_action>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<box>.\n"
                "        move the particle in position<my_secret_holder> to position<box>::action</implied_action>::position<in>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<out> to position<fail_dest>.\n"
                "        create a particle in position<my_secret_holder>.\n"
                "        create a particle in position<my_secret_holder>::position</secret>.\n"
                "        create a particle in position<fail_dest>.\n"
                "        create a particle in position<fail_dest>::position</other>.\n"
                "        create a particle in position<box>::action</implier>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.line == 26
    assert all_diags[0].location.column == 87
    assert all_diags[0].location.end_line == 26
    assert all_diags[0].location.end_column == 106
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].source_position
        == "position<box>::action</implied_action>::position<out>"
    )
    assert all_diags[0].target_position == "position<fail_dest>"
    assert all_diags[0].missing_qualities == [
        "position<my.domain.com:my_lib:/other>",
    ]
    assert action_graph(result.operation_graphs) == [
        (_FORWARDER, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_TEST, _IMPLIED),
        (_TEST, _IMPLIER),
    ]
