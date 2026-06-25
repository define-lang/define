# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors


def _edge_pairs(
    result: conftest.FullValidationResult,
) -> set[tuple[str, str]]:
    return result.action_call_graph.unique_edges()


_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_POS_TEST = "position<my.domain.com:my_lib:/test>"
_POS_P = "position<my.domain.com:my_lib:/p>"


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
        assert _edge_pairs(result) == {(_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _TEST, _OTHER)

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
        assert _edge_pairs(result) == {(_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _TEST, _OTHER)

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
        assert result.action_call_graph.edges() == [(_TEST, _OTHER)]

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
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == set()

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
        assert _edge_pairs(result) == {(_TEST, _ACT_B)}
        assert_action_calls(result.action_call_graph, _TEST, _ACT_B)

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
        assert _edge_pairs(result) == {(_TEST, _ACT_B), (_ACT_B, _ACT_C)}
        assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _ACT_C)

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
        assert _edge_pairs(result) == set()

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
        assert _edge_pairs(result) == set()

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
        assert _edge_pairs(result) == {(_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _TEST, _OTHER)

    def test_no_body_effect_when_create_target_has_unknown_state(
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

    def test_no_body_effect_when_move_target_has_unknown_state(
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
        assert _edge_pairs(result) == set()


_OTHER_ACTION = (
    "define the potential action<my.domain.com:my_lib:/other> {\n"
    "    define the position<trigger_pos>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        define the position<_noop>.\n"
    "        create a particle in position<_noop>.\n"
    "    }\n"
    "}\n"
)


class TestPositionInitTriggering:
    def test_position_init_create_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a particle in position</test>.\n"
                    "        create a particle in position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_POS_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)

    def test_position_init_move_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        define the position<tmp>.\n"
                    "        create a particle in position<tmp>.\n"
                    "        create a particle in position</test>.\n"
                    "        move the particle in position<tmp> to position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_POS_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)

    def test_position_init_self_reference_no_trigger_edge(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    after it is assigned {\n"
                    "        create a particle in position</test>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == set()

    def test_position_init_no_edge_when_non_trigger_position(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a particle in position</test>.\n"
                    "        create a particle in position</test>::action</other>::position<non_trigger>.\n"
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
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == set()

    def test_position_init_and_action_both_trigger_same_target(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a particle in position</test>.\n"
                    "        create a particle in position</test>::action</other>::position<trigger_pos>.\n"
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
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {
            (_POS_TEST, _OTHER),
            (_TEST, _OTHER),
        }
        assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)
        assert_action_calls(result.action_call_graph, _TEST, _OTHER)

    def test_position_init_chained_through_self_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        define the position<local>.\n"
                    "        create a particle in position<local>.\n"
                    "        create a particle in position</test>.\n"
                    "        move the particle in position<local> to position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_POS_TEST, _OTHER)}
        assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)

    def test_constrained_position_init_block_records_edge(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "p.dfn": (
                    "define the potential position<my.domain.com:my_lib:/p> {\n"
                    "    after it is assigned {\n"
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
                    "                it has the position</p>.\n"
                    "            }\n"
                    "        }\n"
                    "        create a particle in position<box>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_TEST, _POS_P)}
        assert_action_calls(result.action_call_graph, _TEST, _POS_P)


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
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos> {\n"
                    "    it may only contain particles where {\n"
                    "        it has the action</test>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a particle in position</pos>.\n"
                    "        create a particle in position</pos>::action</test>::position<run>.\n"
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
