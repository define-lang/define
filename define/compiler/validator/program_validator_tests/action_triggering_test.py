# pyright: reportUnusedCallResult=false
from define.compiler import diagnostics
from define.compiler.validator.program_validator_tests import conftest


def _edge_keys(result: conftest.ProjectResult) -> set[tuple[str, str, int]]:
    return {
        (e.source_action, e.target_action, e.source_line)
        for e in result.graph.all_edges()
    }


_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"


class TestActionTriggering:
    def test_basic_cross_action_trigger(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _OTHER, 6)}

    def test_create_and_move_trigger_other_action(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        define the position<tmp>.\n"
                    "        create a dimension point in position<tmp>.\n"
                    "        move the dimension point in position<tmp> to action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _OTHER, 8)}

    def test_no_trigger_when_writing_to_non_trigger_position(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</other>::position<non_trigger>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == set()

    def test_cross_file_triggering(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</act_b>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _ACT_B, 6)}

    def test_trigger_chain(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</act_b>::position<trigger_b>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.def": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<trigger_b>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_b> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</act_c>::position<trigger_c>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_c.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _ACT_B, 6), (_ACT_B, _ACT_C, 6)}

    def test_self_trigger(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _TEST, 8)}

    def test_duplicate_action_does_not_add_trigger_edges(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert len(result.all_diagnostics) == 1
        assert isinstance(
            result.all_diagnostics[0], diagnostics.DuplicateDefinitionDiagnostic
        )
        assert result.all_diagnostics[0].definition_type == "action"
        assert result.all_diagnostics[0].path == "/test"
        assert result.all_diagnostics[0].first_definition_line == 1
        assert result.all_diagnostics[0].position.line == 10
        assert result.all_diagnostics[0].position.column == 1
        assert _edge_keys(result) == set()

    def test_trigger_positions_recorded(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
        assert result.all_diagnostics == []
        test_result = result.result_for("test.def")
        assert len(test_result.definition_results[0].trigger_positions) == 1
        tp = test_result.definition_results[0].trigger_positions[0]
        assert (
            tp.enclosing_typed_name.full_typed_name()
            == "action<my.domain.com:my_lib:/test>"
        )
        assert len(tp.checked_position.typed_names) == 1
        assert (
            tp.checked_position.typed_names[0].full_typed_name() == "position<my_pos>"
        )

    def test_action_body_effects_recorded(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
                    "define the potential action<my.domain.com:my_lib:/test> {\n"
                    "    define the position<run>.\n"
                    "    it happens when {\n"
                    "        the position<run> has a dimension point.\n"
                    "    } and it does {\n"
                    "        create a dimension point in action</other>::position<pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert result.all_diagnostics == []
        test_result = result.result_for("test.def")
        assert len(test_result.definition_results[0].action_body_effects) == 1
        effect = test_result.definition_results[0].action_body_effects[0]
        assert (
            effect.enclosing_typed_name.full_typed_name()
            == "action<my.domain.com:my_lib:/test>"
        )
        assert len(effect.modified_position.typed_names) == 2
        fqun = effect.enclosing_typed_name.name_content.fqun
        assert (
            effect.modified_position.typed_names[0].full_typed_name(in_universe=fqun)
            == "action<my.domain.com:my_lib:/other>"
        )
        assert (
            effect.modified_position.typed_names[1].full_typed_name() == "position<pos>"
        )

    def test_local_prefix_before_action_trigger(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
                    "        create a dimension point in position<local>::action</other>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "other.def": (
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
        assert result.all_diagnostics == []
        assert _edge_keys(result) == {(_TEST, _OTHER, 11)}

    def test_no_body_effect_when_create_target_has_unknown_state(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
        test_result = result.result_for("test.def")
        assert len(result.all_diagnostics) == 1
        assert isinstance(
            result.all_diagnostics[0], diagnostics.MoveFromEmptyPositionDiagnostic
        )
        assert result.all_diagnostics[0].position_name == "position<a>"
        assert result.all_diagnostics[0].position.line == 8
        assert result.all_diagnostics[0].position.column == 37
        assert test_result.definition_results[0].action_body_effects == []

    def test_no_body_effect_when_move_target_has_unknown_state(
        self,
        validate_project_with_graph: conftest.ValidateProjectWithGraph,
    ):
        result = validate_project_with_graph(
            {
                "test.def": (
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
        test_result = result.result_for("test.def")
        assert len(result.all_diagnostics) == 1
        assert isinstance(
            result.all_diagnostics[0], diagnostics.MoveFromEmptyPositionDiagnostic
        )
        assert result.all_diagnostics[0].position_name == "position<a>"
        assert result.all_diagnostics[0].position.line == 8
        assert result.all_diagnostics[0].position.column == 37
        assert test_result.definition_results[0].action_body_effects == []
