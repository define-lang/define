# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph,
    particle_tracker,
)

_LOC = ast.start_of_file_location()

_CREATE = operation_graph.OperationKind.CREATE
_MOVE = operation_graph.OperationKind.MOVE
_DESTROY = operation_graph.OperationKind.DESTROY


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


def _kinds(
    tracker: particle_tracker.ParticleTracker,
) -> list[operation_graph.OperationKind]:
    return [node.kind for node in tracker.operation_graph.nodes]


def _deps(tracker: particle_tracker.ParticleTracker, node_id: int) -> list[int]:
    return list(tracker.operation_graph.nodes[node_id].depends_on)


def test_body_chain_depends_in_order():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("one"), ())
    tracker.destroy(_ref("one"))
    assert _kinds(tracker) == [_CREATE, _DESTROY]
    assert _deps(tracker, 0) == []
    assert _deps(tracker, 1) == [0]


def test_child_create_depends_on_parent():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    assert [
        node.target.canonical_chained_name_tuple
        for node in tracker.operation_graph.nodes
    ] == [("position<box>",), ("position<box>", "position<inner>")]
    assert _deps(tracker, 0) == []
    assert _deps(tracker, 1) == [0]


def test_destroy_depends_on_touched_children():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.destroy(_ref("box"))
    assert _kinds(tracker) == [_CREATE, _CREATE, _DESTROY]
    assert _deps(tracker, 2) == [0, 1]


def test_destroy_depends_on_grandchildren():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.create(_ref("box", "inner", "deep"), ())
    tracker.destroy(_ref("box"))
    assert _kinds(tracker) == [_CREATE, _CREATE, _CREATE, _DESTROY]
    # subtree_keys hands the destroy the child (1) and the grandchild (2).
    assert _deps(tracker, 3) == [0, 1, 2]


def test_move_carries_child_transitively():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.move(_ref("box"), _ref("basket"))
    tracker.destroy(_ref("basket"))
    assert _kinds(tracker) == [_CREATE, _CREATE, _MOVE, _DESTROY]
    # The move pulls in box::inner via rule 3.
    assert _deps(tracker, 2) == [0, 1]
    # basket::inner is recorded under its pre-move name, so the destroy reaches
    # it only transitively through the move node.
    assert _deps(tracker, 3) == [2]


def test_move_carries_grandchild_subtree():
    tracker = particle_tracker.ParticleTracker()
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.create(_ref("box", "inner", "deep"), ())
    tracker.move(_ref("box"), _ref("basket"))
    tracker.destroy(_ref("basket"))
    assert _kinds(tracker) == [_CREATE, _CREATE, _CREATE, _MOVE, _DESTROY]
    # The move pulls in the whole carried subtree: child (1) and grandchild (2).
    assert _deps(tracker, 3) == [0, 1, 2]
    # The carried subtree keeps its pre-move keys, so the destroy of the
    # moved-to parent reaches it only through the move node.
    assert _deps(tracker, 4) == [3]


def test_from_caller_create_is_a_graph_root():
    tracker = particle_tracker.ParticleTracker()
    iface = _ref("iface")
    tracker.create(iface, (), from_caller=iface)
    tracker.destroy(iface)
    assert _kinds(tracker) == [_DESTROY]
    assert _deps(tracker, 0) == []


def test_mark_empty_records_nothing():
    tracker = particle_tracker.ParticleTracker()
    tracker.mark_empty(_ref("slot"))
    tracker.create(_ref("slot"), ())
    assert _kinds(tracker) == [_CREATE]
    assert _deps(tracker, 0) == []
