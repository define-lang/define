# pyright: reportUnusedCallResult=false
"""Tests for ReferenceGraph incremental cycle detection."""

from define.compiler.validator import reference_graph


def _add(graph: reference_graph.ReferenceGraph, *edges: tuple[str, str]):
    for source, target in edges:
        assert graph.try_add_edge(source, target) is None


class TestReferenceGraphNoCycles:
    def test_single_edge(self):
        graph = reference_graph.ReferenceGraph()
        assert graph.try_add_edge("A", "B") is None

    def test_chain(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"), ("B", "C"), ("C", "D"))

    def test_dag_diamond(self):
        graph = reference_graph.ReferenceGraph()
        _add(
            graph,
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
        )

    def test_multiple_roots(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "C"), ("B", "C"))


class TestReferenceGraphSelfCycles:
    def test_self_cycle(self):
        graph = reference_graph.ReferenceGraph()
        detected = graph.try_add_edge("A", "A")
        assert detected == reference_graph.DetectedCycle(path=["A", "A"])


class TestReferenceGraphTwoNodeCycles:
    def test_two_node_cycle(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"))
        detected = graph.try_add_edge("B", "A")
        assert detected == reference_graph.DetectedCycle(path=["A", "B", "A"])

    def test_two_node_cycle_same_batch(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"))
        detected = graph.try_add_edge("B", "A")
        assert detected is not None
        assert detected.path == ["A", "B", "A"]


class TestReferenceGraphThreeNodeCycles:
    def test_three_node_cycle(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"), ("B", "C"))
        detected = graph.try_add_edge("C", "A")
        assert detected == reference_graph.DetectedCycle(path=["A", "B", "C", "A"])


class TestReferenceGraphMultipleCycles:
    def test_two_separate_cycles(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"), ("C", "D"))
        assert graph.try_add_edge("B", "A") == reference_graph.DetectedCycle(
            path=["A", "B", "A"]
        )
        assert graph.try_add_edge("D", "C") == reference_graph.DetectedCycle(
            path=["C", "D", "C"]
        )

    def test_rejected_edge_not_added(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"), ("B", "C"))
        assert graph.try_add_edge("C", "A") is not None
        # C->A was rejected, so adding A->C should not create a cycle
        assert graph.try_add_edge("A", "C") is None


class TestReferenceGraphIncremental:
    def test_incremental_additions(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"), ("B", "C"))
        detected = graph.try_add_edge("C", "A")
        assert detected is not None
        assert detected.path == ["A", "B", "C", "A"]

    def test_non_cycle_edge_after_rejection(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"))
        graph.try_add_edge("B", "A")  # rejected
        assert graph.try_add_edge("B", "C") is None

    def test_accept_then_reject_in_sequence(self):
        graph = reference_graph.ReferenceGraph()
        _add(graph, ("A", "B"))
        assert graph.try_add_edge("B", "C") is None
        detected = graph.try_add_edge("C", "A")
        assert detected is not None
        assert detected.path == ["A", "B", "C", "A"]
