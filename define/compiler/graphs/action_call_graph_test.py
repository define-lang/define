# pyright: reportUnusedCallResult=false
from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_ACT_A = "action<my.domain.com:my_lib:/act_a>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_SHARED = "action<my.domain.com:my_lib:/shared>"

_NOOP_ACTION_ACT_A = (
    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
    "    define the position<my_pos>.\n"
    "    it happens when {\n"
    "        the position<my_pos> has a particle.\n"
    "    } and it does {\n"
    "        define the position<_noop>.\n"
    "        create a particle in position<_noop>.\n"
    "    }\n"
    "}\n"
)

_CALLER_ACT_B = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</act_a>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<gateway>.\n"
    "        create a particle in position<gateway>::action</act_a>::position<my_pos>.\n"
    "    }\n"
    "}\n"
)

_ENTRY_POS_REFS_B_C = (
    "define the potential position<my.domain.com:my_lib:/test> {\n"
    "    it may only contain particles where {\n"
    "        it has the action</act_b>.\n"
    "        it has the action</act_c>.\n"
    "    }\n"
    "}\n"
)


def _edge_pairs(
    result: conftest.FullValidationResult,
) -> set[tuple[str, str]]:
    return result.action_call_graph.unique_edges()


class TestActionCallGraph:
    def test_empty_graph(
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
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == set()

    def test_single_trigger_edge(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "act_b.dfn": _CALLER_ACT_B,
                "act_a.dfn": _NOOP_ACTION_ACT_A,
            },
            entry_file="act_b.dfn",
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_ACT_B, _ACT_A)}
        assert_action_calls(result.action_call_graph, _ACT_B, _ACT_A)

    def test_self_trigger(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "act_a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
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
            entry_file="act_a.dfn",
        )
        assert len(result.program_result.all_diagnostics) == 1
        assert isinstance(
            result.program_result.all_diagnostics[0],
            diagnostics.ActionSelfTriggerDiagnostic,
        )
        assert _edge_pairs(result) == set()

    def test_duplicates_not_targeted_twice(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": _ENTRY_POS_REFS_B_C,
                "act_a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
                    "    define the position<shared>.\n"
                    "    it happens when {\n"
                    "        the position<shared> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</act_a>::position<shared>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_c.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                    "    define the position<shared>.\n"
                    "    it happens when {\n"
                    "        the position<shared> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<_noop>.\n"
                    "        create a particle in position<_noop>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_ACT_B, _ACT_A)}
        assert_action_calls(result.action_call_graph, _ACT_B, _ACT_A)

    def test_multiple_effects_to_same_target(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "test.dfn": _ENTRY_POS_REFS_B_C,
                "act_a.dfn": _NOOP_ACTION_ACT_A,
                "act_b.dfn": _CALLER_ACT_B,
                "act_c.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        define the position<tmp>.\n"
                    "        create a particle in position<tmp>.\n"
                    "        create a particle in position<gateway>.\n"
                    "        move the particle in position<tmp> to position<gateway>::action</act_a>::position<my_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_ACT_B, _ACT_A), (_ACT_C, _ACT_A)}
        assert_action_calls(result.action_call_graph, _ACT_B, _ACT_A)
        assert_action_calls(result.action_call_graph, _ACT_C, _ACT_A)

    def test_local_prefix_before_action_reference(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<x> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<x>.\n"
                    "        create a particle in position<x>::action</act_a>::position<my_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_a.dfn": _NOOP_ACTION_ACT_A,
            },
            entry_file="act_b.dfn",
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {(_ACT_B, _ACT_A)}
        assert_action_calls(result.action_call_graph, _ACT_B, _ACT_A)

    def test_diamond_dependency(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "act_a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
                    "    define the position<my_pos>.\n"
                    "    define the position<box_b> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_b>.\n"
                    "        }\n"
                    "    }\n"
                    "    define the position<box_c> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_c>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<my_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<box_b>.\n"
                    "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                    "        create a particle in position<box_c>.\n"
                    "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</shared>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_c.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</shared>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "shared.dfn": (
                    "define the potential action<my.domain.com:my_lib:/shared> {\n"
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
            entry_file="act_a.dfn",
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == {
            (_ACT_A, _ACT_B),
            (_ACT_A, _ACT_C),
            (_ACT_B, _SHARED),
            (_ACT_C, _SHARED),
        }
        assert_action_calls(result.action_call_graph, _ACT_A, _ACT_B, _SHARED)
        assert_action_calls(result.action_call_graph, _ACT_A, _ACT_C, _SHARED)

    def test_no_edge_when_position_does_not_match(
        self,
        validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
    ):
        result = validate_project_with_reference_graph(
            {
                "act_b.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                    "    define the position<pp>.\n"
                    "    define the position<gateway> {\n"
                    "        it may only contain particles where {\n"
                    "            it has the action</act_a>.\n"
                    "        }\n"
                    "    }\n"
                    "    it happens when {\n"
                    "        the position<pp> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<gateway>.\n"
                    "        create a particle in position<gateway>::action</act_a>::position<other_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
                "act_a.dfn": (
                    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
                    "    define the position<trigger_pos>.\n"
                    "    define the position<other_pos>.\n"
                    "    it happens when {\n"
                    "        the position<trigger_pos> has a particle.\n"
                    "    } and it does {\n"
                    "        create a particle in position<other_pos>.\n"
                    "    }\n"
                    "}\n"
                ),
            },
            entry_file="act_b.dfn",
        )
        assert_no_errors(result.program_result)
        assert _edge_pairs(result) == set()
