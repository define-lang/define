# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.graphs import reference_graph

_LOC = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="a.com", location=_LOC),
    universe=ast.Universe(name="lib", location=_LOC),
    location=_LOC,
)


def _p(path: str) -> str:
    return f"position<a.com:lib:{path}>"


def _make_position(path_name: str) -> ast.PositionDefinition:
    return ast.PositionDefinition(
        name=ast.DefinitionGlobalNameContent(
            path=ast.GlobalPathName(name=path_name, location=_LOC),
            fqun=_FQUN,
            location=_LOC,
        ),
        location=_LOC,
    )


_TRIGGER_REF = ast.LocalTypedNameReference(
    name_type=ast.NameType.POSITION,
    name_content=ast.LocalNameContent(name="pp", location=_LOC),
    location=_LOC,
)


def _make_action(path_name: str) -> ast.ActionDefinition:
    return ast.ActionDefinition(
        name=ast.DefinitionGlobalNameContent(
            path=ast.GlobalPathName(name=path_name, location=_LOC),
            fqun=_FQUN,
            location=_LOC,
        ),
        quality_implications=[],
        interface_positions=[],
        trigger_conditions=ast.TriggerConditionsBlock(
            conditions=[
                ast.PositionPresenceStatement(typed_name=_TRIGGER_REF, location=_LOC)
            ],
            location=_LOC,
        ),
        action_statements=ast.ActionStatementsBlock(statements=[], location=_LOC),
        location=_LOC,
    )


def _make_edge(
    source: ast.QualityDefinition,
    target_path: str,
    target_type: ast.NameType = ast.NameType.POSITION,
) -> reference_graph.ReferenceEdge:
    return reference_graph.ReferenceEdge(
        enclosing_definition=source,
        global_name_reference=ast.GlobalTypedNameReference(
            name_type=target_type,
            name_content=ast.ReferenceGlobalNameContent(
                fqun=None,
                path=ast.GlobalPathName(name=target_path, location=_LOC),
                location=_LOC,
            ),
            enclosing_fqun=_FQUN,
            location=_LOC,
        ),
        is_same_file=False,
    )


def _add(
    graph: reference_graph.ReferenceGraph,
    *edges: reference_graph.ReferenceEdge,
):
    for edge in edges:
        assert graph.try_add_edge(edge) is None


class TestReferenceGraphNoCycles:
    def test_single_edge(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        graph.add_definition(a)
        b = _make_position("/b")
        graph.add_definition(b)
        assert graph.try_add_edge(_make_edge(a, "/b")) is None

    def test_chain(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        d = _make_position("/d")
        for defn in (a, b, c, d):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"), _make_edge(b, "/c"), _make_edge(c, "/d"))

    def test_dag_diamond(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        d = _make_position("/d")
        for defn in (a, b, c, d):
            graph.add_definition(defn)
        _add(
            graph,
            _make_edge(a, "/b"),
            _make_edge(a, "/c"),
            _make_edge(b, "/d"),
            _make_edge(c, "/d"),
        )

    def test_multiple_roots(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/c"), _make_edge(b, "/c"))


class TestReferenceGraphSelfCycles:
    def test_self_cycle(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        graph.add_definition(a)
        detected = graph.try_add_edge(_make_edge(a, "/a"))
        assert detected == reference_graph.DetectedCycle(path=[_p("/a"), _p("/a")])


class TestReferenceGraphTwoNodeCycles:
    def test_two_node_cycle(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        for defn in (a, b):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"))
        detected = graph.try_add_edge(_make_edge(b, "/a"))
        assert detected == reference_graph.DetectedCycle(
            path=[_p("/a"), _p("/b"), _p("/a")]
        )


class TestReferenceGraphThreeNodeCycles:
    def test_three_node_cycle(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"), _make_edge(b, "/c"))
        detected = graph.try_add_edge(_make_edge(c, "/a"))
        assert detected == reference_graph.DetectedCycle(
            path=[_p("/a"), _p("/b"), _p("/c"), _p("/a")]
        )


class TestReferenceGraphMultipleCycles:
    def test_two_separate_cycles(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        d = _make_position("/d")
        for defn in (a, b, c, d):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"), _make_edge(c, "/d"))
        assert graph.try_add_edge(_make_edge(b, "/a")) == reference_graph.DetectedCycle(
            path=[_p("/a"), _p("/b"), _p("/a")]
        )
        assert graph.try_add_edge(_make_edge(d, "/c")) == reference_graph.DetectedCycle(
            path=[_p("/c"), _p("/d"), _p("/c")]
        )

    def test_rejected_edge_not_added(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"), _make_edge(b, "/c"))
        assert graph.try_add_edge(_make_edge(c, "/a")) is not None
        assert graph.try_add_edge(_make_edge(a, "/c")) is None


class TestReferenceGraphIncremental:
    def test_incremental_additions(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"), _make_edge(b, "/c"))
        detected = graph.try_add_edge(_make_edge(c, "/a"))
        assert detected == reference_graph.DetectedCycle(
            path=[_p("/a"), _p("/b"), _p("/c"), _p("/a")]
        )

    def test_non_cycle_edge_after_rejection(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"))
        graph.try_add_edge(_make_edge(b, "/a"))
        assert graph.try_add_edge(_make_edge(b, "/c")) is None

    def test_accept_then_reject_in_sequence(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_position("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(graph, _make_edge(a, "/b"))
        assert graph.try_add_edge(_make_edge(b, "/c")) is None
        detected = graph.try_add_edge(_make_edge(c, "/a"))
        assert detected == reference_graph.DetectedCycle(
            path=[_p("/a"), _p("/b"), _p("/c"), _p("/a")]
        )


class TestDfsPostorder:
    def test_single_node(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        graph.add_definition(a)
        result = list(graph.dfs_postorder_from(a))
        assert result == [a]

    def test_chain_yields_leaf_first(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_action("/b")
        c = _make_position("/c")
        for defn in (a, b, c):
            graph.add_definition(defn)
        _add(
            graph,
            _make_edge(a, "/b", ast.NameType.ACTION),
            _make_edge(b, "/c"),
        )
        result = list(graph.dfs_postorder_from(a))
        assert result == [c, b, a]

    def test_diamond_yields_shared_dep_once(self):
        graph = reference_graph.ReferenceGraph()
        a = _make_position("/a")
        b = _make_action("/b")
        c = _make_action("/c")
        d = _make_position("/d")
        for defn in (a, b, c, d):
            graph.add_definition(defn)
        _add(
            graph,
            _make_edge(a, "/b", ast.NameType.ACTION),
            _make_edge(a, "/c", ast.NameType.ACTION),
            _make_edge(b, "/d"),
            _make_edge(c, "/d"),
        )
        result = list(graph.dfs_postorder_from(a))
        assert len(result) == 4
        assert result[-1] is a
        assert result.index(d) < result.index(b)
        assert result.index(d) < result.index(c)
