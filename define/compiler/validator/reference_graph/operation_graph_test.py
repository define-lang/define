import pytest

from define.compiler import ast
from define.compiler.validator.reference_graph import action_contract, operation_graph

_LOC = ast.start_of_file_location()


def _callee(action_chain: ast.ActionReference) -> ast.GlobalTypedNameReference:
    typed_name = action_chain.get_last_action()
    assert typed_name is not None
    return typed_name


_NO_REQUIREMENTS: dict[tuple[str, ...], action_contract.PositionRequirement] = {}

_EMPTY = action_contract.PositionOccupancyState.EMPTY
_OCCUPIED = action_contract.PositionOccupancyState.OCCUPIED

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
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


def _action_chain_under(position_name: str, path: str) -> ast.ActionReference:
    """Return the chain of the action ``path`` on the particle in ``position_name``."""
    return ast.ActionReference(
        typed_names=(
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name=position_name, location=_LOC),
                location=_LOC,
            ),
            ast.GlobalTypedNameReference(
                name_type=ast.NameType.ACTION,
                name_content=ast.ReferenceGlobalNameContent(
                    fqun=None,
                    path=ast.GlobalPathName(name=path, location=_LOC),
                    location=_LOC,
                ),
                enclosing_fqun=_FQUN,
                location=_LOC,
            ),
        ),
        location=_LOC,
    )


def _interface_ref(
    action_chain: ast.ActionReference, name: str
) -> ast.PositionReference:
    """Return a reference to the interface position ``name`` of ``action_chain``."""
    return ast.PositionReference(
        typed_names=(
            *action_chain.typed_names,
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name=name, location=_LOC),
                location=_LOC,
            ),
        ),
        location=_LOC,
    )


def _implied_ref(position_name: str, path: str) -> ast.PositionReference:
    """Return a reference to the position ``path`` that an action implies on the particle in ``position_name``."""
    return ast.PositionReference(
        typed_names=(
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name=position_name, location=_LOC),
                location=_LOC,
            ),
            ast.GlobalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.ReferenceGlobalNameContent(
                    fqun=None,
                    path=ast.GlobalPathName(name=path, location=_LOC),
                    location=_LOC,
                ),
                enclosing_fqun=_FQUN,
                location=_LOC,
            ),
        ),
        location=_LOC,
    )


def _global_ref(*paths: str) -> ast.PositionReference:
    return ast.PositionReference(
        typed_names=tuple(
            ast.GlobalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.ReferenceGlobalNameContent(
                    fqun=None,
                    path=ast.GlobalPathName(name=path, location=_LOC),
                    location=_LOC,
                ),
                enclosing_fqun=_FQUN,
                location=_LOC,
            )
            for path in paths
        ),
        location=_LOC,
    )


def _key(*names: str) -> tuple[str, ...]:
    return _ref(*names).canonical_chained_name_tuple


def _global_key(*paths: str) -> tuple[str, ...]:
    return _global_ref(*paths).canonical_chained_name_tuple


_DUMMY_ACTION = ast.ActionDefinition(
    name=ast.DefinitionGlobalNameContent(
        fqun=_FQUN,
        path=ast.GlobalPathName(name="/dummy", location=_LOC),
        location=_LOC,
    ),
    location=_LOC,
    quality_implications=(),
    interface_positions=(),
    trigger_conditions=ast.TriggerConditionsBlock(
        conditions=(
            ast.PositionPresenceStatement(
                typed_name=ast.LocalTypedNameReference(
                    name_type=ast.NameType.POSITION,
                    name_content=ast.LocalNameContent(name="dummy", location=_LOC),
                    location=_LOC,
                ),
                location=_LOC,
            ),
        ),
        location=_LOC,
    ),
    action_statements=ast.ActionStatementsBlock(statements=(), location=_LOC),
)


def _requirements(
    *requirements: tuple[ast.PositionReference, action_contract.PositionOccupancyState],
) -> dict[tuple[str, ...], action_contract.PositionRequirement]:
    """Return an inferred-requirements map holding a requirement on each position."""
    return {
        position.canonical_chained_name_tuple: action_contract.PositionRequirement(
            required_state=state,
            position=position,
            inferred_at=_LOC,
            enclosing_action=_DUMMY_ACTION,
        )
        for position, state in requirements
    }


def _trigger(
    graph: operation_graph.OperationGraph,
    action_chain: ast.ActionReference,
    acting_on_position: ast.PositionReference,
    *guaranteed_keys: tuple[str, ...],
) -> None:
    """Fire ``action_chain`` from the operation on ``acting_on_position``, guaranteeing ``guaranteed_keys``.

    ``guaranteed_keys`` are absolute keys, so each is either an interface position
    of the triggered action or a position it implies on the particle the action
    is assigned to.
    """
    trigger_node_id = graph.record_action_trigger(
        action_chain, acting_on_position, [], []
    )
    graph.record_guarantees(
        trigger_node_id, action_chain.canonical_chained_name_tuple, guaranteed_keys
    )


# Every graph below is an action triggered by position<run>, so its first node
# stands in for the caller operation that filled that position: the operations
# with nothing else to wait on depend on it.
_TRIGGER_POSITION = operation_graph.RequirementNode(
    node_id=0, depends_on=[], required_state=_OCCUPIED
)


def test_same_key_chain():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    graph.record_create(one)
    graph.record_destroy(one, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=one, depends_on=[1]),
    ]


def test_independent_positions_do_not_depend():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)
    graph.record_destroy(one, [])
    graph.record_create(two)
    graph.record_destroy(two, [])
    # The two chains share the trigger-position RequirementNode, never each
    # other.
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=one, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=two, depends_on=[0]),
        operation_graph.DestroyNode(node_id=4, target=two, depends_on=[3]),
    ]


def test_child_depends_on_nearest_ancestor():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    deep = _ref("box", "inner", "deep")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_create(deep)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=deep, depends_on=[2]),
    ]


def test_move_depends_on_both_ends():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)
    graph.record_destroy(two, [])
    graph.record_move(one, two, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=two, depends_on=[0]),
        operation_graph.MoveNode(node_id=3, source=one, target=two, depends_on=[1, 2]),
    ]


def test_move_carries_child_transitively():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    basket = _ref("basket")
    graph.record_create(box)
    graph.record_create(inner)
    # The move's source subtree still holds box::inner, which already reaches
    # the create of box.
    graph.record_move(box, basket, [_key("box", "inner")])
    # box::inner keeps its pre-move key, so a destroy of the moved-to parent
    # misses it directly but reaches it through the move node.
    graph.record_destroy(basket, [_key("basket", "inner")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.MoveNode(node_id=3, source=box, target=basket, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=basket, depends_on=[3]),
    ]


def test_destroy_depends_on_touched_children():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    graph.record_create(box)
    graph.record_create(inner)
    # The destroy waits on the child; its own create is not repeated, since the
    # child already reaches it.
    graph.record_destroy(box, [_key("box", "inner")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=box, depends_on=[2]),
    ]


def test_destroy_depends_on_emptied_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_destroy(inner, [])
    # The child is now known-empty but still touched in the parent's subtree.
    graph.record_destroy(box, [_key("box", "inner")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=inner, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=box, depends_on=[3]),
    ]


def test_recreate_after_direct_destroy_depends_on_destroy():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    graph.record_create(one)
    graph.record_destroy(one, [])
    graph.record_create(one)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=one, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=one, depends_on=[2]),
    ]


def test_destroy_depends_on_deepest_touched_descendant_only():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    deep = _ref("box", "inner", "deep")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_create(deep)
    # The grandchild is the deepest touched descendant and reaches both the
    # child and the box, so the destroy needs only it.
    graph.record_destroy(box, [_key("box", "inner"), _key("box", "inner", "deep")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=deep, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=box, depends_on=[3]),
    ]


def test_move_depends_on_carried_grandchild_subtree():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    deep = _ref("box", "inner", "deep")
    basket = _ref("basket")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_create(deep)
    # The deepest carried descendant reaches the rest of the subtree, so the
    # move needs only it.
    graph.record_move(box, basket, [_key("box", "inner"), _key("box", "inner", "deep")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=deep, depends_on=[2]),
        operation_graph.MoveNode(node_id=4, source=box, target=basket, depends_on=[3]),
    ]


def test_join_moving_into_emptied_position():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)
    graph.record_destroy(one, [])
    graph.record_create(two)
    # A join: the move waits on the particle it carries and on the destroy that
    # emptied its target.
    graph.record_move(two, one, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=one, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=two, depends_on=[0]),
        operation_graph.MoveNode(node_id=4, source=two, target=one, depends_on=[2, 3]),
    ]


def test_rebranch_after_join():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)
    graph.record_destroy(one, [])
    graph.record_create(two)
    graph.record_move(two, one, [])
    # The move is the most recent operation on both its ends, so each end's
    # next operation branches from it.
    graph.record_create(two)
    graph.record_destroy(two, [])
    graph.record_destroy(one, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=one, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=two, depends_on=[0]),
        operation_graph.MoveNode(node_id=4, source=two, target=one, depends_on=[2, 3]),
        operation_graph.CreateNode(node_id=5, target=two, depends_on=[4]),
        operation_graph.DestroyNode(node_id=6, target=two, depends_on=[5]),
        operation_graph.DestroyNode(node_id=7, target=one, depends_on=[4]),
    ]


def test_child_refill_after_parent_destroy():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    other = _ref("box", "other")
    surprise = _ref("surprise")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_destroy(box, [_key("box", "inner")])
    graph.record_create(box)
    graph.record_create(surprise)
    # The move fills the new box's inner: it waits on the created surprise and
    # on the new box, the most recent operation on inner's ancestor chain. The
    # stale old inner create is not repeated -- the new box create already
    # reaches it.
    graph.record_move(surprise, inner, [])
    graph.record_create(other)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=box, depends_on=[2]),
        operation_graph.CreateNode(node_id=4, target=box, depends_on=[3]),
        operation_graph.CreateNode(node_id=5, target=surprise, depends_on=[0]),
        operation_graph.MoveNode(
            node_id=6, source=surprise, target=inner, depends_on=[4, 5]
        ),
        operation_graph.CreateNode(node_id=7, target=other, depends_on=[4]),
    ]


def test_empty_after_ancestor_move_refill_waits_on_the_move():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    box_child = _ref("box", "child")
    source = _ref("source")
    source_child = _ref("source", "child")
    graph.record_create(box)
    graph.record_create(box_child)
    graph.record_destroy(box_child, [])
    graph.record_destroy(box, [_key("box", "child")])
    graph.record_create(source)
    graph.record_create(source_child)
    graph.record_move(source, box, [_key("source", "child")])
    # The move refilled box::child without operating on that key directly. It
    # is the most recent operation on box::child's ancestor chain, so the new
    # destroy waits on it and cannot run before the particle arrives. The stale
    # earlier destroy is not repeated -- the move already reaches it.
    graph.record_destroy(box_child, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=box_child, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=box_child, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=box, depends_on=[3]),
        operation_graph.CreateNode(node_id=5, target=source, depends_on=[0]),
        operation_graph.CreateNode(node_id=6, target=source_child, depends_on=[5]),
        operation_graph.MoveNode(
            node_id=7, source=source, target=box, depends_on=[4, 6]
        ),
        operation_graph.DestroyNode(node_id=8, target=box_child, depends_on=[7]),
    ]


def test_deep_grandchild_carried_through_two_moves():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    a = _ref("a")
    a_b = _ref("a", "b")
    a_b_c = _ref("a", "b", "c")
    d = _ref("d")
    e = _ref("e")
    e_b_c = _ref("e", "b", "c")
    graph.record_create(a)
    graph.record_create(a_b)
    graph.record_create(a_b_c)
    # The deepest carried descendant reaches the rest of the subtree.
    graph.record_move(a, d, [_key("a", "b"), _key("a", "b", "c")])
    # d's children keep their pre-move (a::) keys, so the Child Rule on the
    # second move misses them and reaches them through the first move.
    graph.record_move(d, e, [_key("d", "b"), _key("d", "b", "c")])
    # e::b::c has no entry under that name, so this destroy hangs off e's move.
    graph.record_destroy(e_b_c, [])
    # The parent destroy waits on the explicit destroy of e::b::c, which already
    # reaches e's move.
    graph.record_destroy(e, [_key("e", "b"), _key("e", "b", "c")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=a, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=a_b, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=a_b_c, depends_on=[2]),
        operation_graph.MoveNode(node_id=4, source=a, target=d, depends_on=[3]),
        operation_graph.MoveNode(node_id=5, source=d, target=e, depends_on=[4]),
        operation_graph.DestroyNode(node_id=6, target=e_b_c, depends_on=[5]),
        operation_graph.DestroyNode(node_id=7, target=e, depends_on=[6]),
    ]


def test_operation_records_the_actions_it_triggers():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    basket = _ref("basket")
    graph.record_create(box)
    graph.record_create(basket)
    # Two constructors of the box's particle: creating it fires both.
    brew = _action_chain_under("box", "/brew")
    grind = _action_chain_under("box", "/grind")
    _ = graph.record_action_trigger(brew, box, [], [])
    _ = graph.record_action_trigger(grind, box, [], [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=box,
            depends_on=[0],
            satisfies=[
                operation_graph.RequirementSatisfaction(_callee(brew), (), 1),
                operation_graph.RequirementSatisfaction(_callee(grind), (), 1),
            ],
        ),
        operation_graph.CreateNode(node_id=2, target=basket, depends_on=[0]),
    ]


def test_trigger_records_the_firing_operation_as_the_trigger_position_satisfier():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(machine)
    graph.record_create(trigger_position)
    _ = graph.record_action_trigger(brew, trigger_position, [], [])
    assert list(graph.triggers) == [
        operation_graph.ActionTrigger(_callee(brew), 2, {("position<run>",): 2})
    ]


def test_trigger_records_the_operation_that_satisfies_a_callee_requirement():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(machine)
    # The caller fills the callee's <beans>, which is what satisfies the callee's
    # requirement that it be occupied.
    graph.record_create(_interface_ref(brew, "beans"))
    graph.record_create(trigger_position)
    _ = graph.record_action_trigger(
        brew, trigger_position, [_ref("beans")], [_interface_ref(brew, "beans")]
    )
    assert list(graph.triggers) == [
        operation_graph.ActionTrigger(
            _callee(brew), 3, {("position<run>",): 3, ("position<beans>",): 2}
        )
    ]


def test_trigger_records_a_requirement_node_for_a_requirement_it_passes_to_its_caller():
    # <beans> is a requirement of this action too, which it never operates on, so
    # what satisfies the callee's requirement is the RequirementNode standing in
    # for this action's own caller.
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    beans = _interface_ref(brew, "beans")
    graph = operation_graph.OperationGraph(
        _requirements((machine, _OCCUPIED), (beans, _OCCUPIED)), _ref("run")
    )
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(trigger_position)
    _ = graph.record_action_trigger(brew, trigger_position, [_ref("beans")], [beans])
    (trigger,) = graph.triggers
    satisfier = trigger.satisfiers[("position<beans>",)]
    assert isinstance(graph.nodes[satisfier], operation_graph.RequirementNode)
    assert (
        graph.requirement_node(beans.canonical_chained_name_tuple).node_id == satisfier
    )


def test_trigger_records_no_satisfier_for_a_requirement_nothing_satisfies():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(machine)
    graph.record_create(trigger_position)
    # The caller never touches <cup> and has no requirement on it, so nothing it
    # did satisfies the callee's requirement: the position is empty because the
    # create of the machine left it that way.
    _ = graph.record_action_trigger(
        brew, trigger_position, [_ref("cup")], [_interface_ref(brew, "cup")]
    )
    assert list(graph.triggers) == [
        operation_graph.ActionTrigger(_callee(brew), 2, {("position<run>",): 2})
    ]


def test_one_operation_records_a_trigger_for_each_action_it_fires():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    graph.record_create(box)
    # Two constructors of the box's particle: creating it fires both, and each
    # triggering is its own record.
    brew = _action_chain_under("box", "/brew")
    grind = _action_chain_under("box", "/grind")
    _ = graph.record_action_trigger(brew, box, [], [])
    _ = graph.record_action_trigger(grind, box, [], [])
    assert list(graph.triggers) == [
        operation_graph.ActionTrigger(_callee(brew), 1, {(): 1}),
        operation_graph.ActionTrigger(_callee(grind), 1, {(): 1}),
    ]


def test_each_operation_reports_only_its_own_triggers():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)
    graph.record_create(two)
    brew = _action_chain_under("one", "/brew")
    grind = _action_chain_under("two", "/grind")
    _ = graph.record_action_trigger(brew, one, [], [])
    _ = graph.record_action_trigger(grind, two, [], [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=one,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.CreateNode(
            node_id=2,
            target=two,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(grind), (), 2)],
        ),
    ]


def test_guarantee_adds_a_guarantee_node_hanging_off_the_trigger():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    coffee = _interface_ref(brew, "coffee")
    graph.record_create(machine)
    _trigger(graph, brew, machine, coffee.canonical_chained_name_tuple)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<coffee>",),
            depends_on=[1],
        ),
    ]


def test_guarantee_node_names_the_position_as_the_callee_does():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(machine)
    graph.record_create(trigger_position)
    # The callee's interface positions are child names of its action. The node
    # names the position as the callee's own graph does (``position<coffee>``),
    # not by where it lands in this caller (``machine::/brew::coffee``), so
    # codegen can find the last operation on it in that graph.
    trigger_node_id = graph.record_action_trigger(brew, trigger_position, [], [])
    graph.record_guarantees(
        trigger_node_id,
        brew.canonical_chained_name_tuple,
        [
            (*brew.canonical_chained_name_tuple, "position<coffee>"),
        ],
    )
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=machine, depends_on=[0]),
        operation_graph.CreateNode(
            node_id=2,
            target=trigger_position,
            depends_on=[1],
            satisfies=[
                operation_graph.RequirementSatisfaction(
                    _callee(brew), ("position<run>",), 2
                )
            ],
        ),
        operation_graph.GuaranteeNode(
            node_id=3,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<coffee>",),
            depends_on=[2],
        ),
    ]


def test_guarantee_node_names_an_implied_position_as_the_callee_does():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    # A position the callee implies is a child name of the particle its action
    # is assigned to -- the action's parent position -- and the callee names it
    # by the position's global name alone.
    grounds = _implied_ref("machine", "/grounds")
    graph.record_create(machine)
    _trigger(graph, brew, machine, grounds.canonical_chained_name_tuple)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<my.domain.com:my_lib:/grounds>",),
            depends_on=[1],
        ),
    ]


def test_guarantee_node_names_a_nested_guarantee_as_the_direct_callee_does():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    graph.record_create(machine)
    graph.record_create(trigger_position)
    # A position the callee itself took from an action it triggered still reaches
    # this caller through the callee's own guarantees, so the node names it the
    # way the callee does: by the action the caller actually triggered, with the
    # key the callee's own graph knows it as.
    grinder = ("position<grinder>", "action<my.domain.com:my_lib:/grind>")
    trigger_node_id = graph.record_action_trigger(brew, trigger_position, [], [])
    graph.record_guarantees(
        trigger_node_id,
        brew.canonical_chained_name_tuple,
        [
            (*brew.canonical_chained_name_tuple, *grinder, "position<grounds>"),
        ],
    )
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=machine, depends_on=[0]),
        operation_graph.CreateNode(
            node_id=2,
            target=trigger_position,
            depends_on=[1],
            satisfies=[
                operation_graph.RequirementSatisfaction(
                    _callee(brew), ("position<run>",), 2
                )
            ],
        ),
        operation_graph.GuaranteeNode(
            node_id=3,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=(*grinder, "position<grounds>"),
            depends_on=[2],
        ),
    ]


def test_operation_on_a_guaranteed_position_depends_on_the_guarantee_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    coffee = _interface_ref(brew, "coffee")
    graph.record_create(machine)
    _trigger(graph, brew, machine, coffee.canonical_chained_name_tuple)
    # The consumer chains to the guarantee node (the most recent operation on
    # its ancestor chain), not to the trigger directly. The guarantee node
    # already waits on the machine, so the consumer needs no separate ancestor
    # edge.
    graph.record_destroy(coffee, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<coffee>",),
            depends_on=[1],
        ),
        operation_graph.DestroyNode(node_id=3, target=coffee, depends_on=[2]),
    ]


def test_guarantee_overrides_an_earlier_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    # The caller fills a position the callee implies on the machine, and the
    # callee's guarantee re-fills it.
    grounds = _implied_ref("machine", "/grounds")
    graph.record_create(machine)
    graph.record_create(grounds)
    _trigger(graph, brew, machine, grounds.canonical_chained_name_tuple)
    # A later operation chains to the guarantee node, not the stale earlier
    # create.
    graph.record_destroy(grounds, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.CreateNode(node_id=2, target=grounds, depends_on=[1]),
        operation_graph.GuaranteeNode(
            node_id=3,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<my.domain.com:my_lib:/grounds>",),
            depends_on=[1],
        ),
        operation_graph.DestroyNode(node_id=4, target=grounds, depends_on=[3]),
    ]


def test_parent_destroy_reaches_a_triggered_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    brew = _action_chain_under("box", "/brew")
    out = _interface_ref(brew, "out")
    graph.record_create(box)
    _trigger(graph, brew, box, out.canonical_chained_name_tuple)
    # The destroy waits, via the Child Rule, on the guarantee node that filled
    # the box's child position; that node already reaches the box's create.
    graph.record_destroy(box, [out.canonical_chained_name_tuple])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=box,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<out>",),
            depends_on=[1],
        ),
        operation_graph.DestroyNode(node_id=3, target=box, depends_on=[2]),
    ]


def test_each_guaranteed_position_gets_its_own_guarantee_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    coffee = _interface_ref(brew, "coffee")
    puck = _interface_ref(brew, "puck")
    graph.record_create(machine)
    _trigger(
        graph,
        brew,
        machine,
        coffee.canonical_chained_name_tuple,
        puck.canonical_chained_name_tuple,
    )
    # Each consumer hangs off its own position's guarantee node, the most recent
    # operation on its ancestor chain, which already waits on the machine.
    graph.record_destroy(coffee, [])
    graph.record_destroy(puck, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<coffee>",),
            depends_on=[1],
        ),
        operation_graph.GuaranteeNode(
            node_id=3,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<puck>",),
            depends_on=[1],
        ),
        operation_graph.DestroyNode(node_id=4, target=coffee, depends_on=[2]),
        operation_graph.DestroyNode(node_id=5, target=puck, depends_on=[3]),
    ]


def test_a_move_can_be_the_trigger_fill():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    src = _ref("src")
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    trigger_position = _interface_ref(brew, "run")
    out = _interface_ref(brew, "out")
    graph.record_create(machine)
    graph.record_create(src)
    # The fill that fires the trigger is a move, so the move carries the
    # satisfaction and the create that only supplied the particle carries none.
    graph.record_move(src, trigger_position, [])
    _trigger(graph, brew, trigger_position, out.canonical_chained_name_tuple)
    graph.record_destroy(out, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=machine, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=src, depends_on=[0]),
        operation_graph.MoveNode(
            node_id=3,
            source=src,
            target=trigger_position,
            depends_on=[1, 2],
            satisfies=[
                operation_graph.RequirementSatisfaction(
                    _callee(brew), ("position<run>",), 3
                )
            ],
        ),
        operation_graph.GuaranteeNode(
            node_id=4,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<out>",),
            depends_on=[3],
        ),
        operation_graph.DestroyNode(node_id=5, target=out, depends_on=[4]),
    ]


def test_a_later_operation_overrides_a_guarantee():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    machine = _ref("machine")
    brew = _action_chain_under("machine", "/brew")
    cup = _interface_ref(brew, "cup")
    graph.record_create(machine)
    _trigger(graph, brew, machine, cup.canonical_chained_name_tuple)
    # The re-fill chains to the guarantee node; a later consumer chains to the
    # re-fill.
    graph.record_create(cup)
    graph.record_destroy(cup, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(
            node_id=1,
            target=machine,
            depends_on=[0],
            satisfies=[operation_graph.RequirementSatisfaction(_callee(brew), (), 1)],
        ),
        operation_graph.GuaranteeNode(
            node_id=2,
            action=brew.typed_names[-1].full_typed_name,
            guaranteed_position=("position<cup>",),
            depends_on=[1],
        ),
        operation_graph.CreateNode(node_id=3, target=cup, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=cup, depends_on=[3]),
    ]


def test_touched_list_order_does_not_change_edges():
    box = _ref("box")
    inner = _ref("box", "inner")
    deep = _ref("box", "inner", "deep")

    def build(touched: list[tuple[str, ...]]) -> list[operation_graph.OperationNode]:
        graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
        graph.record_create(box)
        graph.record_create(inner)
        graph.record_create(deep)
        graph.record_destroy(box, touched)
        return list(graph.nodes)

    touched = [_key("box", "inner"), _key("box", "inner", "deep")]
    expected = [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=box, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=inner, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=deep, depends_on=[2]),
        operation_graph.DestroyNode(node_id=4, target=box, depends_on=[3]),
    ]
    assert build(touched) == expected
    assert build(list(reversed(touched))) == expected


def test_gap_in_touched_list_still_drops_the_shallower_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    outer = _ref("outer")
    box = _ref("outer", "box")
    mid = _ref("outer", "box", "mid")
    deep = _ref("outer", "box", "mid", "deep")
    graph.record_create(outer)
    graph.record_create(box)
    graph.record_create(mid)
    graph.record_create(deep)
    # The touched list skips the mid position, but the deep one still supersedes
    # the shallower box.
    graph.record_destroy(
        outer, [_key("outer", "box"), _key("outer", "box", "mid", "deep")]
    )
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=outer, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=box, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=mid, depends_on=[2]),
        operation_graph.CreateNode(node_id=4, target=deep, depends_on=[3]),
        operation_graph.DestroyNode(node_id=5, target=outer, depends_on=[4]),
    ]


def test_child_create_records_no_operation_for_other_keys():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    inner = _ref("box", "inner")
    box = _ref("box")
    other = _ref("other")
    graph.record_create(inner)
    # Nothing was recorded for the ancestor or an unrelated position, so creates
    # in them wait only on the trigger-position requirement.
    graph.record_create(other)
    graph.record_create(box)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=inner, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=other, depends_on=[0]),
        operation_graph.CreateNode(node_id=3, target=box, depends_on=[0]),
    ]


def test_duplicate_touched_keys_and_shared_move_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    one = _ref("one")
    two = _ref("two")
    holder = _ref("holder")
    graph.record_create(one)
    graph.record_move(one, two, [])
    # The move is recorded for both its ends, and the destroy's duplicate
    # touched keys all resolve to that one move.
    graph.record_destroy(holder, [_key("one"), _key("one"), _key("two")])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=one, depends_on=[0]),
        operation_graph.MoveNode(node_id=2, source=one, target=two, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=holder, depends_on=[2]),
    ]


def test_wide_touched_subtree_drops_every_superseded_shallow_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    root = _ref("root")
    graph.record_create(root)
    child_count = 40
    children = [_ref("root", f"c{index}") for index in range(child_count)]
    grandchildren = [_ref("root", f"c{index}", "deep") for index in range(child_count)]
    touched: list[tuple[str, ...]] = []
    for index in range(child_count):
        graph.record_create(children[index])
        graph.record_create(grandchildren[index])
        touched.append(_key("root", f"c{index}"))
        touched.append(_key("root", f"c{index}", "deep"))
    graph.record_destroy(root, touched)
    # Every shallow child is superseded by its later, deeper child, so the
    # destroy waits on the deep children alone.
    expected: list[operation_graph.OperationNode] = [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=root, depends_on=[0]),
    ]
    for index in range(child_count):
        child_id = 2 + 2 * index
        expected.append(
            operation_graph.CreateNode(
                node_id=child_id, target=children[index], depends_on=[1]
            )
        )
        expected.append(
            operation_graph.CreateNode(
                node_id=child_id + 1,
                target=grandchildren[index],
                depends_on=[child_id],
            )
        )
    expected.append(
        operation_graph.DestroyNode(
            node_id=2 + 2 * child_count,
            target=root,
            depends_on=[3 + 2 * index for index in range(child_count)],
        )
    )
    assert list(graph.nodes) == expected


def test_last_operation_affecting_position_resolves_a_move_of_an_ancestor():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    inner = _ref("box", "inner")
    basket = _ref("basket")
    graph.record_create(box)
    graph.record_create(inner)
    graph.record_move(box, basket, [_key("box", "inner")])
    # The move relocated the child without operating on its key, so the child's
    # last operation is that move; the move's own ends resolve to it directly.
    assert graph.last_operation_affecting_position(_key("basket", "inner")) == 3
    assert graph.last_operation_affecting_position(_key("basket")) == 3
    assert graph.last_operation_affecting_position(_key("box")) == 3


def test_last_operation_affecting_position_raises_for_an_unaffected_position():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    box = _ref("box")
    graph.record_create(box)
    assert graph.last_operation_affecting_position(_key("box")) == 1
    with pytest.raises(KeyError):
        _ = graph.last_operation_affecting_position(_key("other"))
    # A create makes exactly one particle; that particle's child positions start
    # empty.
    with pytest.raises(KeyError):
        _ = graph.last_operation_affecting_position(_key("box", "inner"))


def test_read_of_occupied_requirement_waits_on_a_lower_id_requirement_node():
    graph = operation_graph.OperationGraph(
        _requirements((_ref("input"), _OCCUPIED)), _ref("run")
    )
    input_position = _ref("input")
    # The destroy reads a caller-filled position that no earlier body operation
    # acted on, so it waits on a RequirementNode minted at the lower id -- it
    # stands in for the earlier caller op that filled the position.
    graph.record_destroy(input_position, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.DestroyNode(node_id=2, target=input_position, depends_on=[1]),
    ]
    assert graph.requirement_node(_key("input")).node_id == 1


def test_fill_of_empty_requirement_waits_on_a_requirement_node():
    graph = operation_graph.OperationGraph(
        _requirements((_ref("slot"), _EMPTY)), _ref("run")
    )
    slot = _ref("slot")
    graph.record_create(slot)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=2, target=slot, depends_on=[1]),
    ]
    assert graph.requirement_node(_key("slot")).node_id == 1


def test_local_fill_with_no_requirement_waits_on_the_trigger_position_requirement():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    item = _ref("item")
    # No position requirement applies, so the create waits on the
    # trigger-position requirement alone -- the empty key, since this graph has
    # no trigger position.
    graph.record_create(item)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=item, depends_on=[0]),
    ]


def test_operations_with_nothing_else_to_wait_on_share_the_trigger_position_requirement_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    scratch = _ref("scratch")
    note = _ref("note")
    graph.record_create(scratch)
    graph.record_create(note)
    assert list(graph.nodes) == [
        operation_graph.RequirementNode(
            node_id=0, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.CreateNode(node_id=1, target=scratch, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=note, depends_on=[0]),
    ]
    assert graph.requirement_node(graph.trigger_position_key).node_id == 0


def test_a_trigger_position_read_shares_the_trigger_position_requirement_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS, _ref("run"))
    run = _ref("run")
    scratch = _ref("scratch")
    # The read of the trigger position mints the RequirementNode; the create
    # with nothing else to wait on then depends on that same node.
    graph.record_destroy(run, [])
    graph.record_create(scratch)
    assert list(graph.nodes) == [
        operation_graph.RequirementNode(
            node_id=0, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.DestroyNode(node_id=1, target=run, depends_on=[0]),
        operation_graph.CreateNode(node_id=2, target=scratch, depends_on=[0]),
    ]
    assert graph.requirement_node(graph.trigger_position_key).node_id == 0


def test_a_constructor_gets_a_requirement_node_for_the_position_it_is_assigned_to():
    # A constructor has no trigger position: it is triggered by the filling of
    # the position it is assigned to, which is the position above all the ones it
    # can name, so its trigger requirement carries the empty key. The create of
    # the global /marker it assigns waits on that position's own requirement,
    # while the create with nothing else to wait on waits on the trigger.
    graph = operation_graph.OperationGraph(
        _requirements((_global_ref("/marker"), _EMPTY))
    )
    marker = _global_ref("/marker")
    scratch = _ref("scratch")
    graph.record_create(marker)
    graph.record_create(scratch)
    assert list(graph.nodes) == [
        operation_graph.RequirementNode(
            node_id=0, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=2, target=marker, depends_on=[1]),
        operation_graph.CreateNode(node_id=3, target=scratch, depends_on=[0]),
    ]
    assert graph.trigger_position_key == ()
    assert graph.requirement_node(()).node_id == 0
    assert graph.requirement_node(_global_key("/marker")).node_id == 1


def test_earlier_body_operation_takes_precedence_over_a_requirement_node():
    graph = operation_graph.OperationGraph(
        _requirements((_ref("slot"), _EMPTY)), _ref("run")
    )
    slot = _ref("slot")
    graph.record_create(slot)
    # The destroy follows an earlier body operation on the position (the
    # create), so it waits on that rather than minting a fresh requirement node.
    graph.record_destroy(slot, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=2, target=slot, depends_on=[1]),
        operation_graph.DestroyNode(node_id=3, target=slot, depends_on=[2]),
    ]
    assert graph.requirement_node(_key("slot")).node_id == 1


def test_requirement_node_attaches_to_the_nearest_requirement_ancestor():
    graph = operation_graph.OperationGraph(
        _requirements((_ref("box"), _OCCUPIED)), _ref("run")
    )
    deep = _ref("box", "mid", "deep")
    # Only box is a requirement, so the intermediate positions mint no nodes of
    # their own and the create waits on box's RequirementNode.
    graph.record_create(deep)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.CreateNode(node_id=2, target=deep, depends_on=[1]),
    ]
    assert graph.requirement_node(_key("box")).node_id == 1


def test_two_children_of_required_parent_share_the_parent_requirement_node():
    # The callee-graph shape behind the empty-by-default-children integration
    # case: box is a caller-provided occupied requirement and box::/a, box::/b
    # are its empty-by-default children the body fills. box's RequirementNode is
    # shared: each child's own RequirementNode depends on it, so the two creates
    # transitively wait on whatever fills box.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_ref("box"), _OCCUPIED),
            (_ref("box", "a"), _EMPTY),
            (_ref("box", "b"), _EMPTY),
        ),
        _ref("run"),
    )
    box_a = _ref("box", "a")
    box_b = _ref("box", "b")
    graph.record_create(box_a)
    graph.record_create(box_b)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=3, target=box_a, depends_on=[2]),
        operation_graph.RequirementNode(
            node_id=4, depends_on=[1], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=5, target=box_b, depends_on=[4]),
    ]
    assert graph.requirement_node(_key("box")).node_id == 1
    assert graph.requirement_node(_key("box", "a")).node_id == 2
    assert graph.requirement_node(_key("box", "b")).node_id == 4


def test_grandchild_fill_builds_the_full_requirement_ancestor_chain():
    # The grandchild integration case: filling a caller-provided grandchild
    # builds a RequirementNode per contracted ancestor, each depending on the
    # next shallower one, and the create waits on the leaf.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_ref("box"), _OCCUPIED),
            (_ref("box", "child"), _OCCUPIED),
            (_ref("box", "child", "grandchild"), _EMPTY),
        ),
        _ref("run"),
    )
    grandchild = _ref("box", "child", "grandchild")
    graph.record_create(grandchild)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=3, depends_on=[2], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=4, target=grandchild, depends_on=[3]),
    ]
    assert graph.requirement_node(_key("box")).node_id == 1
    assert graph.requirement_node(_key("box", "child")).node_id == 2
    assert graph.requirement_node(_key("box", "child", "grandchild")).node_id == 3


def test_grandchild_read_builds_the_full_requirement_ancestor_chain():
    # The occupied-grandchild integration case: reading a caller-provided
    # grandchild builds the same ancestor chain, and the destroy waits on the
    # leaf.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_ref("box"), _OCCUPIED),
            (_ref("box", "child"), _OCCUPIED),
            (_ref("box", "child", "grandchild"), _OCCUPIED),
        ),
        _ref("run"),
    )
    grandchild = _ref("box", "child", "grandchild")
    graph.record_destroy(grandchild, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=3, depends_on=[2], required_state=_OCCUPIED
        ),
        operation_graph.DestroyNode(node_id=4, target=grandchild, depends_on=[3]),
    ]
    assert graph.requirement_node(_key("box")).node_id == 1
    assert graph.requirement_node(_key("box", "child")).node_id == 2
    assert graph.requirement_node(_key("box", "child", "grandchild")).node_id == 3


def test_read_of_a_carried_in_parent_child_builds_the_requirement_chain():
    # The callee-graph shape behind the moved-in-parent integration case: inner
    # reads input::/parent (provided by a caller move that carries the child), so
    # the destroy waits on the input::/parent requirement, which waits on input.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_ref("input"), _OCCUPIED),
            (_ref("input", "parent"), _OCCUPIED),
        ),
        _ref("run"),
    )
    parent = _ref("input", "parent")
    graph.record_destroy(parent, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_OCCUPIED
        ),
        operation_graph.DestroyNode(node_id=3, target=parent, depends_on=[2]),
    ]
    assert graph.requirement_node(_key("input")).node_id == 1
    assert graph.requirement_node(_key("input", "parent")).node_id == 2


def test_implied_position_children_share_the_global_parent_requirement_node():
    # The implied-position integration cases: /inner assigns the global /parent
    # and fills its children. The chain is built from global keys verbatim; the
    # /parent RequirementNode is shared by both children's requirements.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_global_ref("/parent"), _OCCUPIED),
            (_global_ref("/parent", "/child1"), _EMPTY),
            (_global_ref("/parent", "/child2"), _EMPTY),
        ),
        _ref("run"),
    )
    child1 = _global_ref("/parent", "/child1")
    child2 = _global_ref("/parent", "/child2")
    graph.record_create(child1)
    graph.record_create(child2)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=3, target=child1, depends_on=[2]),
        operation_graph.RequirementNode(
            node_id=4, depends_on=[1], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=5, target=child2, depends_on=[4]),
    ]
    assert graph.requirement_node(_global_key("/parent")).node_id == 1
    assert graph.requirement_node(_global_key("/parent", "/child1")).node_id == 2
    assert graph.requirement_node(_global_key("/parent", "/child2")).node_id == 4


def test_move_joins_an_in_body_source_with_a_requirement_target():
    # A move is the one operation with both a fill and an empty side, so it can
    # depend on a RequirementNode and a PositionOperationNode at once: it empties
    # the in-body-created <src> (Empty Rule -> the create) and fills the
    # caller-controlled empty-requirement <dest> (Fill Rule, no in-body op -> a
    # RequirementNode). This is the shape a real /test produces for
    # `create <src>; move <src> to <dest>` with <dest> an empty-by-default guarantee.
    graph = operation_graph.OperationGraph(
        _requirements((_ref("dest"), _EMPTY)), _ref("run")
    )
    src = _ref("src")
    dest = _ref("dest")
    graph.record_create(src)
    graph.record_move(src, dest, [])
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.CreateNode(node_id=1, target=src, depends_on=[0]),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[], required_state=_EMPTY
        ),
        operation_graph.MoveNode(node_id=3, source=src, target=dest, depends_on=[1, 2]),
    ]
    assert graph.requirement_node(_key("dest")).node_id == 2


def test_implied_position_grandchild_builds_the_global_requirement_chain():
    # The implied grandchild integration case: the full global
    # /parent::/child::/grandchild chain is built from global keys, each
    # RequirementNode depending on the next shallower one.
    graph = operation_graph.OperationGraph(
        _requirements(
            (_global_ref("/parent"), _OCCUPIED),
            (_global_ref("/parent", "/child"), _OCCUPIED),
            (_global_ref("/parent", "/child", "/grandchild1"), _EMPTY),
        ),
        _ref("run"),
    )
    grandchild = _global_ref("/parent", "/child", "/grandchild1")
    graph.record_create(grandchild)
    assert list(graph.nodes) == [
        _TRIGGER_POSITION,
        operation_graph.RequirementNode(
            node_id=1, depends_on=[], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=2, depends_on=[1], required_state=_OCCUPIED
        ),
        operation_graph.RequirementNode(
            node_id=3, depends_on=[2], required_state=_EMPTY
        ),
        operation_graph.CreateNode(node_id=4, target=grandchild, depends_on=[3]),
    ]
    assert graph.requirement_node(_global_key("/parent")).node_id == 1
    assert graph.requirement_node(_global_key("/parent", "/child")).node_id == 2
    assert (
        graph.requirement_node(_global_key("/parent", "/child", "/grandchild1")).node_id
        == 3
    )
