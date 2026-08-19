"""Unit tests for isolated Empty and Move Rule calculation contracts.

This file is intentionally narrow. Tests belong here only when the behavior
under test is independent of how a valid Define program produces an Operation
Graph. Appropriate examples are path selection, reduction, ordering, and
scaling behavior over an already-collected child-operation snapshot.

Dependency semantics do not belong here. Move Correction, Fill Dependency
removal, caller Collection, guarantees, Binding Holes, and partial rule
application must be tested with valid Define source in an existing
operation-graph integration test module. Those tests exercise the validator,
particle tracker, Operation Graph, and action resolver together, so they protect
the actual propagation path that production uses.

In particular, do not construct a graph state that the compiler cannot produce
in order to reach a branch. Do not omit requirements, preceding operations, or
particle state that valid Define source would necessarily provide. Do not add a
unit test merely to preserve defensive behavior or increase line or branch
coverage. If a production branch can be reached here but cannot be reached by a
valid integration fixture, first determine whether the branch is unreachable
and should be deleted.

Minimal node setup is acceptable when it is only incidental to a narrow
calculation contract, such as ordering a child-operation snapshot. Assertions
must not use that setup to specify dependency edges.
"""

import functools

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    operation_graph_model,
    operation_graph_rules,
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


def test_excludes_operations_on_the_same_paths():
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            (
                (("position<a>",), _operation_node(2)),
                (("position<b>",), _operation_node(3)),
                (("position<c>",), _operation_node(4)),
            )
        )
    )

    assert operation_graph_rules.operations_not_on_same_paths_as(
        child_operations,
        frozenset(
            {
                ("position<a>", "position<deep>"),
                ("position<d>",),
                ("position<e>",),
                ("position<f>",),
                ("position<g>",),
            }
        ),
    ) == [
        operation_graph_model.ChildOperation(("position<c>",), _operation_node(4)),
        operation_graph_model.ChildOperation(("position<b>",), _operation_node(3)),
    ]
    assert (
        operation_graph_rules.operations_not_on_same_paths_as(
            child_operations, frozenset({()})
        )
        == []
    )


def test_excludes_one_operation_known_on_multiple_positions():
    operation = _operation_node(2)
    remaining_operation = _operation_node(3)
    child_operations = operation_graph_model.ParticleChildOperations(
        (
            operation_graph_model.ChildOperation(("position<b>",), operation),
            operation_graph_model.ChildOperation(("position<a>",), operation),
            operation_graph_model.ChildOperation(("position<c>",), remaining_operation),
        )
    )

    assert operation_graph_rules.operations_not_on_same_paths_as(
        child_operations, frozenset({("position<a>", "position<deep>")})
    ) == [operation_graph_model.ChildOperation(("position<c>",), remaining_operation)]


def test_path_exclusion_scales_to_wide_child_and_relative_position_sets():
    child_count = 10_000
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            ((f"position<c{index}>",), _operation_node(index))
            for index in range(child_count)
        )
    )

    operations = operation_graph_rules.operations_not_on_same_paths_as(
        child_operations,
        frozenset((f"position<other{index}>",) for index in range(child_count)),
    )

    assert len(operations) == child_count
    assert operations[0] == operation_graph_model.ChildOperation(
        ("position<c9999>",), _operation_node(9999)
    )
    assert operations[-1] == operation_graph_model.ChildOperation(
        ("position<c0>",), _operation_node(0)
    )


def test_empty_rule_dependencies_match_parent_and_child_paths():
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

    assert operation_graph_rules.empty_rule_dependencies_for(
        child_operations, ("position<a>", "position<child>")
    ) == (operation_a.operation,)
    assert operation_graph_rules.empty_rule_dependencies_for(
        child_operations, ("position<b>",)
    ) == (operation_b_deep.operation,)
    assert set(
        operation_graph_rules.empty_rule_dependencies_for(
            child_operations, ("position<c>",)
        )
    ) == {
        operation_c_first.operation,
        operation_c_second.operation,
    }
    assert (
        operation_graph_rules.empty_rule_dependencies_for(
            child_operations, ("position<missing>",)
        )
        == ()
    )


def test_empty_rule_dependencies_reduce_matching_operations():
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

    assert operation_graph_rules.empty_rule_dependencies_for(
        child_operations, ("position<a>",)
    ) == (newer_operation,)


def test_empty_rule_dependencies_return_a_shared_operation_once():
    operation = _operation_node(1)
    child_operations = operation_graph_model.ParticleChildOperations(
        (
            operation_graph_model.ChildOperation(("position<a>",), operation),
            operation_graph_model.ChildOperation(
                ("position<a>", "position<child>"), operation
            ),
        )
    )

    assert operation_graph_rules.empty_rule_dependencies_for(
        child_operations, ("position<a>",)
    ) == (operation,)
