"""Unit tests for isolated operation-graph data structures and API contracts.

This file is intentionally narrow. Tests belong here only when the behavior
under test is independent of how a valid Define program produces an operation
graph. Appropriate examples are identity equality, the documented failure
behavior of a direct lookup API, and the ordering, path-selection, reduction,
or scaling behavior of ``ParticleChildOperations`` as a data structure.

Dependency semantics do not belong here. Create, move, destroy, Action
Triggering, requirement, guarantee, Empty Rule, and destruction-cascade edges
must be tested with valid Define source in an existing operation-graph
integration test module. Those tests exercise the validator, particle tracker,
and operation graph together, so they protect the actual propagation path that
production uses.

In particular, do not construct a graph state that the compiler cannot produce
in order to reach a branch. Do not omit requirements, preceding operations, or
particle state that valid Define source would necessarily provide. Do not add a
unit test merely to preserve defensive behavior or increase line or branch
coverage. If a production branch can be reached here but cannot be reached by a
valid integration fixture, first determine whether the branch is unreachable
and should be deleted.

Minimal graph setup is acceptable when it is only incidental to a narrow API
contract, such as recording one operation before testing a lookup. Assertions
must not use that setup to specify dependency edges. Tests of communication
between ``ParticleTracker`` and ``OperationGraph`` also do not belong here;
observable behavior at that boundary belongs in operation-graph integration
tests, while tracker state behavior belongs in ``particle_tracker_test.py``.
"""

import functools

import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
)

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


@functools.cache
def _operation_node(node_index: int) -> operation_graph_model.MoveNode:
    return operation_graph_model.MoveNode(
        node_id=node_index,
        source=_ref(f"source{node_index}"),
        target=_ref(f"target{node_index}"),
        depends_on=(),
    )


def test_operation_nodes_use_identity_equality():
    one = operation_graph_model.CreateNode(node_id=1, target=_ref("one"), depends_on=())
    equivalent = operation_graph_model.CreateNode(
        node_id=1, target=_ref("one"), depends_on=()
    )

    assert one != equivalent
    assert len({one, equivalent}) == 2


def test_inserted_destroy_if_occupied_orders_before_existing_destruction():
    preceding = operation_graph_model.CreateNode(
        node_id=1, target=_ref("preceding"), depends_on=()
    )
    destruction = operation_graph_model.DestroyNode(
        node_id=2, target=_ref("particle"), depends_on=(preceding,)
    )
    following = operation_graph_model.CreateNode(
        node_id=3, target=_ref("following"), depends_on=(destruction,)
    )
    inserted = operation_graph_model.DestroyIfOccupiedNode(
        node_id=4,
        target=_ref("particle", "child"),
        depends_on=(preceding,),
        inserted_before=destruction,
    )

    assert preceding.operation_order < inserted.operation_order
    assert inserted.operation_order < destruction.operation_order
    assert destruction.operation_order < following.operation_order


def test_last_operation_on_position_raises_for_an_untouched_position():
    graph = operation_graph.OperationGraph()
    box = _ref("box")
    operation = graph.record_create(box)

    assert (
        graph.last_operation_on_position(box.canonical_chained_name_tuple) is operation
    )
    with pytest.raises(KeyError):
        _ = graph.last_operation_on_position(_ref("other").canonical_chained_name_tuple)


def test_last_operation_on_position_or_parents_includes_parent_names():
    graph = operation_graph.OperationGraph()
    parent = _ref("parent")
    operation = graph.record_create(parent)

    descendant_positions = (
        _ref("parent", "child"),
        _ref("parent", "child", "grandchild"),
        _ref("parent", "child", "grandchild", "great_grandchild"),
    )
    for position in descendant_positions:
        assert (
            graph.last_operation_on_position_or_parents(
                position.canonical_chained_name_tuple
            )
            is operation
        )


def test_last_operation_on_position_or_parents_uses_newest_operation():
    graph = operation_graph.OperationGraph()
    child = _ref("parent", "child")
    _ = graph.record_create(child)
    parent_operation = graph.record_create(_ref("parent"))

    assert (
        graph.last_operation_on_position_or_parents(
            _ref(
                "parent", "child", "grandchild", "great_grandchild"
            ).canonical_chained_name_tuple
        )
        is parent_operation
    )


def test_last_operation_on_position_or_parents_prefers_newer_child_over_parent():
    graph = operation_graph.OperationGraph()
    _ = graph.record_create(_ref("parent"))
    child_operation = graph.record_create(_ref("parent", "child"))

    assert (
        graph.last_operation_on_position_or_parents(
            _ref(
                "parent", "child", "grandchild", "great_grandchild"
            ).canonical_chained_name_tuple
        )
        is child_operation
    )


def test_particle_child_operations_excludes_operations_on_the_same_paths():
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            (
                (("position<a>",), _operation_node(2)),
                (("position<b>",), _operation_node(3)),
            )
        )
    )

    assert child_operations.operations_not_on_same_paths_as(
        frozenset({("position<a>", "position<deep>")})
    ) == [operation_graph_model.ChildOperation(("position<b>",), _operation_node(3))]


def test_particle_child_operations_scales_to_wide_particles():
    child_count = 10_000
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            ((f"position<c{index}>",), _operation_node(index))
            for index in range(child_count)
        )
    )

    operations = child_operations.operations_not_on_same_paths_as(frozenset())

    assert len(operations) == child_count
    assert operations[0] == operation_graph_model.ChildOperation(
        ("position<c9999>",), _operation_node(9999)
    )
    assert operations[-1] == operation_graph_model.ChildOperation(
        ("position<c0>",), _operation_node(0)
    )


@pytest.mark.parametrize(
    ("preceding_operations", "expected_operations"),
    [
        (
            (
                (("position<a>",), _operation_node(2)),
                (("position<a>", "position<deep>"), _operation_node(4)),
                (("position<b>",), _operation_node(3)),
            ),
            {
                operation_graph_model.ChildOperation(
                    ("position<a>", "position<deep>"), _operation_node(4)
                ),
                operation_graph_model.ChildOperation(
                    ("position<b>",), _operation_node(3)
                ),
            },
        ),
        (
            (
                (("position<a>", "position<deep>"), _operation_node(2)),
                (("position<a>",), _operation_node(4)),
                (("position<b>",), _operation_node(3)),
            ),
            {
                operation_graph_model.ChildOperation(
                    ("position<a>",), _operation_node(4)
                ),
                operation_graph_model.ChildOperation(
                    ("position<b>",), _operation_node(3)
                ),
            },
        ),
        (
            (
                (("position<a>",), _operation_node(2)),
                (("position<a>",), _operation_node(4)),
            ),
            {
                operation_graph_model.ChildOperation(
                    ("position<a>",), _operation_node(4)
                )
            },
        ),
    ],
)
def test_particle_child_operations_keeps_only_newest_comparable_operations(
    preceding_operations: tuple[
        tuple[tuple[str, ...], operation_graph_model.PrecedingChildOperationNode], ...
    ],
    expected_operations: set[operation_graph_model.ChildOperation],
):
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            preceding_operations
        )
    )

    assert (
        set(child_operations.operations_not_on_same_paths_as(frozenset()))
        == expected_operations
    )


def test_particle_child_operations_matches_parent_and_child_paths():
    operation_a = operation_graph_model.ChildOperation(
        ("position<a>",), _operation_node(1)
    )
    operation_b_deep = operation_graph_model.ChildOperation(
        ("position<b>", "position<deep>"), _operation_node(2)
    )
    operation_c_first = operation_graph_model.ChildOperation(
        ("position<c>", "position<first>"), _operation_node(3)
    )
    operation_c_second = operation_graph_model.ChildOperation(
        ("position<c>", "position<second>"), _operation_node(4)
    )
    child_operations = operation_graph_model.ParticleChildOperations(
        (
            operation_c_second,
            operation_c_first,
            operation_b_deep,
            operation_a,
        )
    )

    assert child_operations.empty_rule_dependencies_for(
        ("position<a>", "position<child>")
    ) == (operation_a.operation,)
    assert child_operations.empty_rule_dependencies_for(("position<b>",)) == (
        operation_b_deep.operation,
    )
    assert set(child_operations.empty_rule_dependencies_for(("position<c>",))) == {
        operation_c_first.operation,
        operation_c_second.operation,
    }
    assert child_operations.empty_rule_dependencies_for(("position<missing>",)) == ()


def test_particle_child_operations_reduces_matching_dependencies():
    older_operation = operation_graph_model.MoveNode(
        node_id=1,
        source=_ref("box", "a", "child"),
        target=_ref("older_target"),
        depends_on=(),
    )
    newer_operation = operation_graph_model.MoveNode(
        node_id=2,
        source=_ref("box", "a"),
        target=_ref("newer_target"),
        depends_on=(),
    )
    child_operations = operation_graph_model.ParticleChildOperations(
        (
            operation_graph_model.ChildOperation(("position<a>",), newer_operation),
            operation_graph_model.ChildOperation(
                ("position<a>", "position<child>"), older_operation
            ),
        )
    )

    assert child_operations.empty_rule_dependencies_for(("position<a>",)) == (
        newer_operation,
    )


def test_particle_child_operations_returns_a_shared_dependency_once():
    operation = _operation_node(1)
    child_operations = operation_graph_model.ParticleChildOperations(
        (
            operation_graph_model.ChildOperation(("position<a>",), operation),
            operation_graph_model.ChildOperation(
                ("position<a>", "position<child>"), operation
            ),
        )
    )

    assert child_operations.empty_rule_dependencies_for(("position<a>",)) == (
        operation,
    )


def test_particle_child_operations_all_precede():
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            (
                (("position<a>",), _operation_node(2)),
                (("position<b>",), _operation_node(4)),
            )
        )
    )

    assert child_operations.all_precede(_operation_node(5))
    assert not child_operations.all_precede(_operation_node(4))
    assert operation_graph_model.ParticleChildOperations().all_precede(
        _operation_node(0)
    )
