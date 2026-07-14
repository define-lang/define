# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph.operation_graph_renderer_new import (
    action_graph,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_P = "action<my.domain.com:my_lib:/p>"


class TestActionTriggering:
    def test_basic_cross_action_trigger(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_create_and_move_trigger_other_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<tmp>.\n"
                    "        create a particle in position<tmp>.\n"
                    "        create a particle in position<gateway>.\n"
                    "        move the particle in position<tmp> to position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_refilling_destroyed_trigger_position_retriggers(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        destroy the particle in position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_TEST, _OTHER),
            (_TEST, _OTHER),
        ]

    def test_moving_between_two_trigger_positions_fires_both(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway_other> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<gateway_b> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway_other>.\n"
                    "        create a particle in position<gateway_b>.\n"
                    "        create a particle in position<gateway_other>::action</other>::position<trigger_pos>.\n"
                    "        move the particle in position<gateway_other>::action</other>::position<trigger_pos> to position<gateway_b>::action</act_b>::position<trigger_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_b>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_b> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_TEST, _OTHER),
            (_TEST, _ACT_B),
        ]

    def test_move_from_trigger_position_to_itself_does_not_retrigger(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "        move the particle in position<gateway>::action</other>::position<trigger_pos> to position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.MoveToSamePositionDiagnostic)
        assert all_diags[0].location.line == 13
        assert all_diags[0].location.column == 125
        assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
        assert (
            all_diags[0].position_name
            == "position<gateway>::action</other>::position<trigger_pos>"
        )
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_no_trigger_when_writing_to_non_trigger_position(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<non_trigger>.\n"
                    "    define the position<actual_trigger>.\n"
                    "    it happens when {\n"
                    "        the position<actual_trigger> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "        create a particle in position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == []

    def test_assumed_occupied_trigger_position_does_not_fire_the_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
                "inner.dfn": (
                    "define the potential action<my.domain.com:my_lib:/inner> {\n"
                    "    define the position<run> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<start>.\n"
                    "    define the position<box> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</inner>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<start> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<box>::action</inner>::position<run>::position</a>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        # position<box>::action</inner>::position<run> is only assumed occupied,
        # as a requirement of the deep create, never filled by a body operation.
        # An assumed occupancy does not fire a trigger, so /inner never runs.
        assert action_graph(result.operation_graphs) == []
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        untriggered = all_diags[0]
        assert isinstance(untriggered, diagnostics.UntriggeredActionDiagnostic)
        assert untriggered.constraint_name == "action</inner>"
        assert untriggered.position_name == "position<box>"
        assert untriggered.location.line == 5
        assert untriggered.location.column == 24
        assert untriggered.location.end_line == 5
        assert untriggered.location.end_column == 38
        assert untriggered.location.file_path == PurePosixPath("test.dfn")
        dead_child = all_diags[1]
        assert isinstance(dead_child, diagnostics.DeadChildPositionDiagnostic)
        assert dead_child.constraint_name == "position</a>"
        assert dead_child.position_name == "position<run>"
        assert dead_child.location.line == 4
        assert dead_child.location.column == 24
        assert dead_child.location.end_line == 4
        assert dead_child.location.end_column == 36
        assert dead_child.location.file_path == PurePosixPath("inner.dfn")

    def test_cross_file_triggering(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</act_b>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _ACT_B)]

    def test_trigger_chain(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</act_b>::position<trigger_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_b>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_c>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<trigger_b> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</act_c>::position<trigger_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_c.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                    "    define the position<trigger_c>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_c> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [
            (_ACT_B, _ACT_C),
            (_TEST, _ACT_B),
        ]

    def test_self_trigger(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<my_pos>.\n"
                    "    define the position<other>.\n"
                    "    it happens when {\n"
                    "        the position<my_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        move the particle in position<my_pos> to position<other>.\n"
                    "        create a particle in position<my_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.ActionSelfTriggerDiagnostic,
        )
        assert action_graph(result.operation_graphs) == []

    def test_duplicate_action_does_not_add_trigger_edges(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.DuplicateDefinitionDiagnostic,
        )
        assert result.program_result.all_diagnostics[0].definition_type == "action"
        assert result.program_result.all_diagnostics[0].path == "/test"
        assert result.program_result.all_diagnostics[0].first_definition_line == 1
        assert result.program_result.all_diagnostics[0].location.line == 10
        assert result.program_result.all_diagnostics[0].location.column == 1
        assert action_graph(result.operation_graphs) == []

    def test_local_prefix_before_action_trigger(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<local> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<local>.\n"
                    "        create a particle in position<local>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_no_body_effect_when_create_target_has_error_state(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<a>.\n"
                    "        define the position<b>.\n"
                    "        move the particle in position<a> to position<b>.\n"
                    "        create a particle in position<b>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.MoveFromEmptyPositionDiagnostic,
        )
        assert result.program_result.all_diagnostics[0].position_name == "position<a>"
        assert result.program_result.all_diagnostics[0].location.line == 8
        assert result.program_result.all_diagnostics[0].location.column == 30

    def test_no_body_effect_when_move_target_has_error_state(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<a>.\n"
                    "        define the position<b>.\n"
                    "        move the particle in position<a> to position<b>.\n"
                    "        move the particle in position<a> to position<b>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.MoveFromEmptyPositionDiagnostic,
        )
        assert result.program_result.all_diagnostics[0].position_name == "position<a>"
        assert result.program_result.all_diagnostics[0].location.line == 8
        assert result.program_result.all_diagnostics[0].location.column == 30


class TestUnknownGlobalNoTrigger:
    def test_no_trigger_edge_on_unknown_global_chain_start(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
        assert all_diags[0].source_global_name == "action</other>"
        assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
        assert action_graph(result.operation_graphs) == []


class TestConstructorTriggering:
    def test_constructor_create_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        this particle is created.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_constructor_move_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        this particle is created.\n"
                    "    } and it does {\n"
                    "        define the position<tmp>.\n"
                    "        create a particle in position<tmp>.\n"
                    "        create a particle in position<gateway>.\n"
                    "        move the particle in position<tmp> to position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _OTHER)]

    def test_constructor_no_edge_when_non_trigger_position(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        this particle is created.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<non_trigger>.\n"
                    "    define the position<actual_trigger>.\n"
                    "    it happens when {\n"
                    "        the position<actual_trigger> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "        create a particle in position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == []

    def test_constructor_fired_via_constraint_records_edge(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "p.dfn": (
                    "define the potential action<my.domain.com:my_lib:/p> {\n"
                    "    it happens when {\n"
                    "        this particle is created.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
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
                    "                it has the action</p>.\n"
                    "            }\n"
                    "        }\n"
                    "        create a particle in position<box>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert action_graph(result.operation_graphs) == [(_TEST, _P)]


class TestCircularDependencyTriggering:
    def test_circular_dependency_skips_trigger_check(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the position</pos>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<run>::position</pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</test>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 1
        assert isinstance(all_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
        assert all_diags[0].location.line == 3
        assert all_diags[0].location.column == 20
