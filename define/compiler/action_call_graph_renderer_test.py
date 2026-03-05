# pyright: reportUnusedCallResult=false
import os
import subprocess

from define.compiler import action_call_graph, action_call_graph_renderer
from define.compiler.validator import program_validator


def _validate_mermaid(text: str):
    validator = os.environ.get("MERMAID_VALIDATOR")
    if not validator:
        return
    result = subprocess.run(
        [validator],
        input=text,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Invalid Mermaid syntax:\n{result.stderr}"


def _build_graph(*sources: str) -> action_call_graph.ActionCallGraph:
    """Parse Define sources and return the resulting call graph."""
    pv = program_validator.ProgramValidator()
    for source in sources:
        pv.validate_program_non_filesystem(source)
    return pv.action_call_graph


_ACTION_A = (
    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
    "    define the position<pp>.\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in action</act_b>::position<pp>.\n"
    "    }\n"
    "}\n"
)

_ACTION_B_TRIGGERED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "    }\n"
    "}\n"
)


class TestRenderMermaid:
    def test_empty_graph(self):
        graph = action_call_graph.ActionCallGraph()
        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == "flowchart LR\n"
        _validate_mermaid(result)

    def test_single_edge(self):
        graph = _build_graph(_ACTION_A, _ACTION_B_TRIGGERED)

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action-my.domain.com:my_lib:/act_a-["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action-my.domain.com:my_lib:/act_b-["action<my.domain.com:my_lib:/act_b>"]\n'
            "    action-my.domain.com:my_lib:/act_a- --> action-my.domain.com:my_lib:/act_b-\n"
        )
        _validate_mermaid(result)

    def test_duplicate_edges_deduplicated(self):
        source_a = (
            "define the potential action<my.domain.com:my_lib:/act_a> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</act_b>::position<pp>.\n"
            "        create a dimension point in action</act_b>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(source_a, _ACTION_B_TRIGGERED)

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action-my.domain.com:my_lib:/act_a-["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action-my.domain.com:my_lib:/act_b-["action<my.domain.com:my_lib:/act_b>"]\n'
            "    action-my.domain.com:my_lib:/act_a- --> action-my.domain.com:my_lib:/act_b-\n"
        )
        _validate_mermaid(result)

    def test_multiple_distinct_edges(self):
        action_b_chains = (
            "define the potential action<my.domain.com:my_lib:/act_b> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</act_c>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        action_c = (
            "define the potential action<my.domain.com:my_lib:/act_c> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(_ACTION_A, action_b_chains, action_c)

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action-my.domain.com:my_lib:/act_a-["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action-my.domain.com:my_lib:/act_b-["action<my.domain.com:my_lib:/act_b>"]\n'
            '    action-my.domain.com:my_lib:/act_c-["action<my.domain.com:my_lib:/act_c>"]\n'
            "    action-my.domain.com:my_lib:/act_a- --> action-my.domain.com:my_lib:/act_b-\n"
            "    action-my.domain.com:my_lib:/act_b- --> action-my.domain.com:my_lib:/act_c-\n"
        )
        _validate_mermaid(result)

    def test_node_ids_sanitized(self):
        source_foo = (
            "define the potential action<test.org:other_lib:/foo> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</bar>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        source_bar = (
            "define the potential action<test.org:other_lib:/bar> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(source_foo, source_bar)

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action-test.org:other_lib:/bar-["action<test.org:other_lib:/bar>"]\n'
            '    action-test.org:other_lib:/foo-["action<test.org:other_lib:/foo>"]\n'
            "    action-test.org:other_lib:/foo- --> action-test.org:other_lib:/bar-\n"
        )
        _validate_mermaid(result)
