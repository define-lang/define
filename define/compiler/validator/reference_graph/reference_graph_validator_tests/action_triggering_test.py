# pyright: reportUnusedCallResult=false
from define.compiler import conftest, diagnostics


def _edge_keys(
    result: conftest.FullValidationResult,
) -> set[tuple[str, str, int]]:
    return {
        (e.source, e.target, e.statement.position.line)
        for e in result.action_call_graph.edges()
    }


_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_POS_TEST = "position<my.domain.com:my_lib:/test>"


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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _OTHER, 12)}

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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<tmp>.\n"
                    "        create a dimension point in position<tmp>.\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        move the dimension point in position<tmp> to position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _OTHER, 14)}

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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</other>::position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<non_trigger>.\n"
                    "    define the position<actual_trigger>.\n"
                    "    it happens when {\n"
                    "        the position<actual_trigger> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == set()

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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</act_b>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _ACT_B, 12)}

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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</act_b>::position<trigger_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_b>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</act_c>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<trigger_b> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</act_c>::position<trigger_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_c.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                    "    define the position<trigger_c>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_c> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _ACT_B, 12), (_ACT_B, _ACT_C, 12)}

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
                    "        the position<my_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        move the dimension point in position<my_pos> to position<other>.\n"
                    "        create a dimension point in position<my_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _TEST, 8)}

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
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
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
        assert _edge_keys(result) == set()

    def test_trigger_positions_recorded(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<my_pos>.\n"
                    "    it happens when {\n"
                    "        the position<my_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        all_trigger_positions = [
            tp
            for r in result.program_result.file_results
            for dr in r.definition_results
            for tp in dr.trigger_positions
        ]
        assert len(all_trigger_positions) == 1
        tp = all_trigger_positions[0]
        assert (
            tp.enclosing_typed_name.source_typed_name
            == "action<my.domain.com:my_lib:/test>"
        )
        assert tp.checked_position.source_chained_name == "position<my_pos>"

    def test_action_body_effects_recorded(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</other>::position<pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<pos>.\n"
                    "    it happens when {\n"
                    "        the position<pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        all_body_effects = [
            effect
            for r in result.program_result.file_results
            for dr in r.definition_results
            for effect in dr.action_body_effects
        ]
        assert len(all_body_effects) == 3
        effect_names = {
            e.enclosing_typed_name.source_typed_name for e in all_body_effects
        }
        assert effect_names == {
            "action<my.domain.com:my_lib:/test>",
            "action<my.domain.com:my_lib:/other>",
        }
        test_effects = [
            e
            for e in all_body_effects
            if e.enclosing_typed_name.source_typed_name
            == "action<my.domain.com:my_lib:/test>"
        ]
        assert len(test_effects) == 2
        modified_positions = {
            e.modified_position.source_chained_name for e in test_effects
        }
        assert modified_positions == {
            "position<gateway>",
            "position<gateway>::action</other>::position<pos>",
        }

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
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<local>.\n"
                    "        create a dimension point in position<local>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_TEST, _OTHER, 12)}

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
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<a>.\n"
                    "        define the position<b>.\n"
                    "        move the dimension point in position<a> to position<b>.\n"
                    "        create a dimension point in position<b>.\n"
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
        assert result.program_result.all_diagnostics[0].location.column == 37
        all_body_effects = [
            effect
            for r in result.program_result.file_results
            for dr in r.definition_results
            for effect in dr.action_body_effects
        ]
        assert all_body_effects == []

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
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<a>.\n"
                    "        define the position<b>.\n"
                    "        move the dimension point in position<a> to position<b>.\n"
                    "        move the dimension point in position<a> to position<b>.\n"
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
        assert result.program_result.all_diagnostics[0].location.column == 37
        all_body_effects = [
            effect
            for r in result.program_result.file_results
            for dr in r.definition_results
            for effect in dr.action_body_effects
        ]
        assert all_body_effects == []


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
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
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
        assert _edge_keys(result) == set()


_OTHER_ACTION = (
    "define the potential action<my.domain.com:my_lib:/other> {\n"
    "    define the position<trigger_pos>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a dimension point.\n"
    "    } and it does {\n"
    "        define the position<_noop>.\n"
    "        create a dimension point in position<_noop>.\n"
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
                    "    it may only contain dimension points where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a dimension point in position</test>.\n"
                    "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_POS_TEST, _OTHER, 7)}

    def test_position_init_move_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        define the position<tmp>.\n"
                    "        create a dimension point in position<tmp>.\n"
                    "        create a dimension point in position</test>.\n"
                    "        move the dimension point in position<tmp> to position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_POS_TEST, _OTHER, 9)}

    def test_position_init_self_reference_no_trigger_edge(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    after it is assigned {\n"
                    "        create a dimension point in position</test>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == set()

    def test_position_init_no_edge_when_non_trigger_position(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a dimension point in position</test>.\n"
                    "        create a dimension point in position</test>::action</other>::position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": (
                    "define the potential action<my.domain.com:my_lib:/other> {\n"
                    "    define the position<non_trigger>.\n"
                    "    define the position<actual_trigger>.\n"
                    "    it happens when {\n"
                    "        the position<actual_trigger> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == set()

    def test_position_init_and_action_both_trigger_same_target(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a dimension point in position</test>.\n"
                    "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain dimension points where {\n"
                    "            it has the action</other>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in position<gateway>.\n"
                    "        create a dimension point in position<gateway>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {
            (_POS_TEST, _OTHER, 7),
            (_TEST, _OTHER, 21),
        }

    def test_position_init_chained_through_self_triggers_action(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": (
                    "define the potential position<my.domain.com:my_lib:/test> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the action</other>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        define the position<local>.\n"
                    "        create a dimension point in position<local>.\n"
                    "        create a dimension point in position</test>.\n"
                    "        move the dimension point in position<local> to position</test>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.dfn": _OTHER_ACTION,
            },
        )
        assert not result.program_result.has_errors()
        assert _edge_keys(result) == {(_POS_TEST, _OTHER, 9)}


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
                    "        it may only contain dimension points where {\n"
                    "            it has the position</pos>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a dimension point in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "pos.dfn": (
                    "define the potential position<my.domain.com:my_lib:/pos> {\n"
                    "    it may only contain dimension points where {\n"
                    "        it has the action</test>.\n"
                    "    }\n"
                    "    after it is assigned {\n"
                    "        create a dimension point in position</pos>.\n"
                    "        create a dimension point in position</pos>::action</test>::position<run>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        all_diags = result.program_result.all_diagnostics
        assert len(all_diags) == 2
        assert isinstance(all_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
        assert all_diags[0].location.line == 3
        assert all_diags[0].location.column == 20
        assert isinstance(all_diags[1], diagnostics.CircularGlobalReferenceDiagnostic)
        assert all_diags[1].location.line == 7
        assert all_diags[1].location.column == 53
