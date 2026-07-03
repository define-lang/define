from define.compiler import ast
from define.compiler.validator.reference_graph import operation_graph

_LOC = ast.start_of_file_location()


def _ref(*names: str) -> ast.PositionReference:
    return ast.PositionReference(
        typed_names=tuple(
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name=name, location=_LOC),
                location=_LOC,
            )
            for name in names
        ),
        location=_LOC,
    )


def _key(*names: str) -> tuple[str, ...]:
    return _ref(*names).canonical_chained_name_tuple


def _deps(graph: operation_graph.OperationGraph, identifier: int) -> set[int]:
    return set(graph.dependency_identifiers(identifier))


def test_same_key_chain():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    assert _deps(graph, 0) == set()
    assert _deps(graph, 1) == {0}


def test_independent_positions_do_not_depend():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("two"))  # 2
    graph.record_destroy(_ref("two"), [])  # 3
    assert _deps(graph, 0) == set()
    assert _deps(graph, 1) == {0}
    assert _deps(graph, 2) == set()
    assert _deps(graph, 3) == {2}


def test_child_depends_on_nearest_ancestor():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    assert _deps(graph, 1) == {0}
    assert _deps(graph, 2) == {1}


def test_move_depends_on_both_ends():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("two"), [])  # 1
    graph.record_move(_ref("one"), _ref("two"), [])  # 2
    assert _deps(graph, 2) == {0, 1}
    assert graph.last_operation_identifier_for_key(_key("two")) == 2


def test_move_carries_child_transitively():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    # The move's source subtree still holds box::inner.
    graph.record_move(_ref("box"), _ref("basket"), [_key("box", "inner")])  # 2
    # box::inner keeps its pre-move key, so a destroy of the moved-to parent
    # misses it directly but reaches it through the move node.
    graph.record_destroy(_ref("basket"), [_key("basket", "inner")])  # 3
    assert 1 in _deps(graph, 2)
    assert _deps(graph, 3) == {2}


def test_destroy_depends_on_touched_children():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 2
    assert _deps(graph, 2) == {0, 1}


def test_destroy_depends_on_emptied_child():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box", "inner"), [])  # 2
    # The child is now known-empty but still touched in the parent's subtree.
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 3
    assert 2 in _deps(graph, 3)


def test_recreate_after_direct_destroy_depends_on_destroy():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("one"))  # 2
    assert _deps(graph, 2) == {1}


def test_destroy_depends_on_grandchild_not_only_child():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    graph.record_destroy(
        _ref("box"), [_key("box", "inner"), _key("box", "inner", "deep")]
    )  # 3
    # The child's create (1) precedes the grandchild's (2), so depending only on
    # the child would not cover the grandchild; the destroy needs both directly.
    assert _deps(graph, 3) == {0, 1, 2}


def test_move_depends_on_carried_grandchild_subtree():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    graph.record_move(
        _ref("box"),
        _ref("basket"),
        [_key("box", "inner"), _key("box", "inner", "deep")],
    )  # 3
    assert _deps(graph, 3) == {0, 1, 2}


def test_join_moving_into_emptied_position():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("two"))  # 2
    graph.record_move(_ref("two"), _ref("one"), [])  # 3
    # A join: the move waits on the particle it carries (2) and on the destroy
    # that emptied its target (1).
    assert _deps(graph, 3) == {1, 2}


def test_rebranch_after_join():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("two"))  # 2
    graph.record_move(_ref("two"), _ref("one"), [])  # 3
    graph.record_create(_ref("two"))  # 4
    graph.record_destroy(_ref("two"), [])  # 5
    graph.record_destroy(_ref("one"), [])  # 6
    assert _deps(graph, 3) == {1, 2}
    assert _deps(graph, 4) == {3}
    assert _deps(graph, 5) == {4}
    assert _deps(graph, 6) == {3}


def test_child_refill_after_parent_destroy():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 2
    graph.record_create(_ref("box"))  # 3
    graph.record_create(_ref("surprise"))  # 4
    graph.record_move(_ref("surprise"), _ref("box", "inner"), [])  # 5
    graph.record_create(_ref("box", "other"))  # 6
    assert _deps(graph, 2) == {0, 1}
    # The move fills the new box's inner: create surprise (4) and, via parent,
    # the new box (3). The edge to the old inner create (1) is a stale same-name
    # rule-1 dependency, redundant with the path through 3.
    assert _deps(graph, 5) == {1, 3, 4}
    assert _deps(graph, 6) == {3}


def test_deep_grandchild_carried_through_two_moves():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("a"))  # 0
    graph.record_create(_ref("a", "b"))  # 1
    graph.record_create(_ref("a", "b", "c"))  # 2
    graph.record_move(_ref("a"), _ref("d"), [_key("a", "b"), _key("a", "b", "c")])  # 3
    graph.record_move(_ref("d"), _ref("e"), [_key("d", "b"), _key("d", "b", "c")])  # 4
    graph.record_destroy(_ref("e", "b", "c"), [])  # 5
    graph.record_destroy(_ref("e"), [_key("e", "b"), _key("e", "b", "c")])  # 6
    assert _deps(graph, 3) == {0, 1, 2}
    # d's children keep their pre-move (a::) keys, so rule 3 on the second move
    # misses them and reaches them through the first move (3).
    assert _deps(graph, 4) == {3}
    # e::b::c has no entry under that name, so this destroy hangs off e's move.
    assert _deps(graph, 5) == {4}
    # The parent destroy sees the explicit destroy of e::b::c (5) directly.
    assert _deps(graph, 6) == {4, 5}
