# pyright: reportUnusedCallResult=false

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
    create = graph.record_create(_ref("one"))
    destroy = graph.record_destroy(_ref("one"), [])
    assert _deps(graph, create) == set()
    assert _deps(graph, destroy) == {create}


def test_independent_positions_do_not_depend():
    graph = operation_graph.OperationGraph()
    create_one = graph.record_create(_ref("one"))
    destroy_one = graph.record_destroy(_ref("one"), [])
    create_two = graph.record_create(_ref("two"))
    destroy_two = graph.record_destroy(_ref("two"), [])
    assert _deps(graph, create_one) == set()
    assert _deps(graph, destroy_one) == {create_one}
    assert _deps(graph, create_two) == set()
    assert _deps(graph, destroy_two) == {create_two}


def test_child_depends_on_nearest_ancestor():
    graph = operation_graph.OperationGraph()
    box = graph.record_create(_ref("box"))
    inner = graph.record_create(_ref("box", "inner"))
    deep = graph.record_create(_ref("box", "inner", "deep"))
    assert _deps(graph, inner) == {box}
    assert _deps(graph, deep) == {inner}


def test_move_depends_on_both_ends():
    graph = operation_graph.OperationGraph()
    create_source = graph.record_create(_ref("one"))
    graph.record_destroy(_ref("two"), [])
    empty_two = graph.last_operation_identifier_for_key(_key("two"))
    move = graph.record_move(_ref("one"), _ref("two"), [])
    assert _deps(graph, move) == {create_source, empty_two}


def test_move_carries_child_transitively():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))
    create_inner = graph.record_create(_ref("box", "inner"))
    # The move's source subtree still holds box::inner.
    move = graph.record_move(_ref("box"), _ref("basket"), [_key("box", "inner")])
    # box::inner keeps its pre-move key, so a destroy of the moved-to parent
    # misses it directly but reaches it through the move node.
    destroy = graph.record_destroy(_ref("basket"), [_key("basket", "inner")])
    assert create_inner in _deps(graph, move)
    assert _deps(graph, destroy) == {move}


def test_destroy_depends_on_touched_children():
    graph = operation_graph.OperationGraph()
    box = graph.record_create(_ref("box"))
    inner = graph.record_create(_ref("box", "inner"))
    destroy = graph.record_destroy(_ref("box"), [_key("box", "inner")])
    assert _deps(graph, destroy) == {box, inner}


def test_destroy_depends_on_emptied_child():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))
    graph.record_create(_ref("box", "inner"))
    destroy_inner = graph.record_destroy(_ref("box", "inner"), [])
    # The child is now known-empty but still touched in the parent's subtree.
    destroy_box = graph.record_destroy(_ref("box"), [_key("box", "inner")])
    assert destroy_inner in _deps(graph, destroy_box)


def test_recreate_after_direct_destroy_depends_on_destroy():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))
    destroy = graph.record_destroy(_ref("one"), [])
    recreate = graph.record_create(_ref("one"))
    assert _deps(graph, recreate) == {destroy}
