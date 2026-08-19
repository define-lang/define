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
            )
        )
    )

    assert operation_graph_rules.operations_not_on_same_paths_as(
        child_operations, frozenset({("position<a>", "position<deep>")})
    ) == [operation_graph_model.ChildOperation(("position<b>",), _operation_node(3))]


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


def test_path_exclusion_scales_to_wide_particles():
    child_count = 10_000
    child_operations = (
        operation_graph_model.ParticleChildOperations.from_preceding_operations(
            ((f"position<c{index}>",), _operation_node(index))
            for index in range(child_count)
        )
    )

    operations = operation_graph_rules.operations_not_on_same_paths_as(
        child_operations, frozenset()
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
