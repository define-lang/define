"""Unit tests for isolated operation-graph data structures and API contracts.

This file is intentionally narrow. Tests belong here only when the behavior
under test is independent of how a valid Define program produces an operation
graph. Appropriate examples are identity equality, the documented failure
behavior of a direct lookup API, and the ordering, path-selection, reduction,
or scaling behavior of ``ParticleChildOperations`` as a data structure.

Dependency semantics do not belong here. Create, move, destroy, Action
Action Execution, requirement, guarantee, Empty Rule, and destruction-cascade edges
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

from __future__ import annotations

import functools

import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
)

_LOC = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _action(path: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=path, location=_LOC),
            location=_LOC,
        ),
        enclosing_fqun=_FQUN,
        location=_LOC,
    )


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


def _destruction_contribution(
    action: ast.GlobalTypedNameReference,
    destruction_fact: operation_graph_model.DestructionFact,
    destruction_position: tuple[str, ...],
    node_id: int,
) -> operation_graph_model.DestructionContributionNode:
    action_parent_operation = _operation_node(0)
    execution = operation_graph_model.ActionExecution(
        ast.ActionReference(typed_names=(action,), location=_LOC),
        {},
        action_parent_last_operation=action_parent_operation,
    )
    return operation_graph_model.DestructionContributionNode(
        node_id=node_id,
        depends_on=(),
        callee_destroy=operation_graph_model.CalleeDestroy(
            direct_callee_execution=execution,
            destruction_fact=destruction_fact,
            callee_destroy_position=destruction_position,
        ),
    )


def test_repeated_destruction_at_one_position_retains_distinct_facts():
    action = _action("/test")
    builder = operation_graph.OperationGraphBuilder(action)
    destroyed_position = _ref("destroyed")
    first_fact = operation_graph_model.DestructionFact(destroyed_position, action)
    second_fact = operation_graph_model.DestructionFact(destroyed_position, action)
    _ = builder.record_create(destroyed_position)
    first_destroy = builder.record_destruction_fact_destroy(
        first_fact,
        destroyed_position,
        (),
        propagate_to_caller=True,
    )
    _ = builder.record_create(destroyed_position)
    second_destroy = builder.record_destruction_fact_destroy(
        second_fact,
        destroyed_position,
        (),
        propagate_to_caller=True,
    )
    graphs = operation_graph.OperationGraphs()
    graphs[action] = builder.finish()

    first_contribution = _destruction_contribution(action, first_fact, (), 1)
    second_contribution = _destruction_contribution(action, second_fact, (), 2)
    resolved_first_destroy = graphs.resolve_callee_destroy(
        first_contribution.callee_destroy
    ).callee_destroy
    resolved_second_destroy = graphs.resolve_callee_destroy(
        second_contribution.callee_destroy
    ).callee_destroy

    assert resolved_first_destroy.operation is first_destroy
    assert resolved_second_destroy.operation is second_destroy
    assert resolved_first_destroy.action is action
    assert resolved_second_destroy.action is action


def test_destruction_operations_distinguish_parent_and_child_destroys():
    action = _action("/test")
    builder = operation_graph.OperationGraphBuilder(action)
    parent = _ref("parent")
    child = _ref("parent", "child")
    destruction_fact = operation_graph_model.DestructionFact(parent, action)
    _ = builder.record_create(parent)
    _ = builder.record_create(child)
    child_destroy = builder.record_destruction_fact_destroy(
        destruction_fact,
        child,
        (),
        propagate_to_caller=True,
    )
    parent_destroy = builder.record_destruction_fact_destroy(
        destruction_fact,
        parent,
        (),
        propagate_to_caller=True,
    )
    graphs = operation_graph.OperationGraphs()
    graphs[action] = builder.finish()

    child_contribution = _destruction_contribution(
        action,
        destruction_fact,
        child.canonical_chained_name_tuple[len(parent.canonical_chained_name_tuple) :],
        1,
    )
    parent_contribution = _destruction_contribution(action, destruction_fact, (), 2)
    resolved_child_destroy = graphs.resolve_callee_destroy(
        child_contribution.callee_destroy
    ).callee_destroy
    resolved_parent_destroy = graphs.resolve_callee_destroy(
        parent_contribution.callee_destroy
    ).callee_destroy

    assert resolved_child_destroy.operation is child_destroy
    assert resolved_parent_destroy.operation is parent_destroy


def test_operation_nodes_use_identity_equality():
    one = operation_graph_model.CreateNode(node_id=1, target=_ref("one"), depends_on=())
    equivalent = operation_graph_model.CreateNode(
        node_id=1, target=_ref("one"), depends_on=()
    )

    assert one != equivalent
    assert len({one, equivalent}) == 2


def test_last_operation_on_position_or_parents_includes_parent_names():
    builder = operation_graph.OperationGraphBuilder(_action("/test"))
    parent = _ref("parent")
    operation = builder.record_create(parent)
    graph = builder.finish()

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
    builder = operation_graph.OperationGraphBuilder(_action("/test"))
    child = _ref("parent", "child")
    _ = builder.record_create(child)
    parent_operation = builder.record_create(_ref("parent"))
    graph = builder.finish()

    assert (
        graph.last_operation_on_position_or_parents(
            _ref(
                "parent", "child", "grandchild", "great_grandchild"
            ).canonical_chained_name_tuple
        )
        is parent_operation
    )


def test_last_operation_on_position_or_parents_prefers_newer_child_over_parent():
    builder = operation_graph.OperationGraphBuilder(_action("/test"))
    _ = builder.record_create(_ref("parent"))
    child_operation = builder.record_create(_ref("parent", "child"))
    graph = builder.finish()

    assert (
        graph.last_operation_on_position_or_parents(
            _ref(
                "parent", "child", "grandchild", "great_grandchild"
            ).canonical_chained_name_tuple
        )
        is child_operation
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
        tuple[tuple[str, ...], operation_graph_model.ConcreteOperationNode], ...
    ],
    expected_operations: set[operation_graph_model.ChildOperation],
):
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            preceding_operations
        )
    )

    assert set(child_operations.operations) == expected_operations


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
