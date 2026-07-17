# pyright: reportUnusedCallResult=false

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
    particle_tracker,
)

_LOC = ast.start_of_file_location()


_NO_REQUIREMENTS: dict[tuple[str, ...], action_contract.PositionRequirement] = {}

_CREATE = operation_graph.CreateNode
_MOVE = operation_graph.MoveNode
_DESTROY = operation_graph.DestroyNode
_GUARANTEE = operation_graph.GuaranteeNode
_ACTION_PARENT_LAST_OPERATION = operation_graph.ActionParentLastOperationNode

_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOC),
    universe=ast.Universe(name="my_lib", location=_LOC),
    location=_LOC,
)


def _local(name: str) -> ast.LocalTypedNameReference:
    return ast.LocalTypedNameReference(
        name_type=ast.NameType.POSITION,
        name_content=ast.LocalNameContent(name=name, location=_LOC),
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
        typed_names=tuple(_local(name) for name in names),
        location=_LOC,
    )


def _chain(*elements: ast.TypedNameReference) -> ast.PositionReference:
    return ast.PositionReference(typed_names=elements, location=_LOC)


def _action_chain(*elements: ast.TypedNameReference) -> ast.ActionReference:
    return ast.ActionReference(typed_names=elements, location=_LOC)


def _occupied_by_new() -> action_contract.OccupiedByNewGuarantee:
    cause = _ref("cause")
    return action_contract.OccupiedByNewGuarantee(
        qualities=(),
        caused_by=cause,
        operation_positions=(cause.canonical_chained_name_tuple,),
    )


def _last_operation(
    tracker: particle_tracker.ParticleTracker, position: ast.PositionReference
) -> int:
    return tracker.operation_graph.last_operation_on_position(
        position.canonical_chained_name_tuple
    )


def _kinds(
    tracker: particle_tracker.ParticleTracker,
) -> list[type[operation_graph.OperationNode]]:
    return [type(node) for node in tracker.operation_graph.nodes]


def _deps(tracker: particle_tracker.ParticleTracker, node_id: int) -> list[int]:
    return list(tracker.operation_graph.nodes[node_id].depends_on)


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
            ast.PositionPresenceStatement(typed_name=_local("dummy"), location=_LOC),
        ),
        location=_LOC,
    ),
    action_statements=ast.ActionStatementsBlock(statements=(), location=_LOC),
)


def _make_requirement(
    state: action_contract.PositionOccupancyState,
    position: ast.PositionReference,
) -> action_contract.PositionRequirement:
    return action_contract.PositionRequirement(
        required_state=state,
        position=position,
        inferred_at=position.location,
        enclosing_action=_DUMMY_ACTION,
    )


def test_body_chain_depends_in_order():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("one"), ())
    tracker.destroy(_ref("one"))
    # Node 0 is the trigger-position RequirementNode the first create waits on.
    assert _kinds(tracker) == [_ACTION_PARENT_LAST_OPERATION, _CREATE, _DESTROY]
    assert _deps(tracker, 1) == [0]
    assert _deps(tracker, 2) == [1]


def test_child_create_depends_on_parent():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    assert [
        node.target.canonical_chained_name_tuple
        for node in tracker.operation_graph.nodes
        if isinstance(node, operation_graph.PositionOperationNode)
    ] == [("position<box>",), ("position<box>", "position<inner>")]
    assert _deps(tracker, 1) == [0]
    assert _deps(tracker, 2) == [1]


def test_destroy_depends_on_touched_children():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.destroy(_ref("box"))
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _DESTROY,
    ]
    # The destroy waits on the child (2), which already reaches create box (1).
    assert _deps(tracker, 3) == [2]


def test_destroy_depends_on_grandchildren():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.create(_ref("box", "inner", "deep"), ())
    tracker.destroy(_ref("box"))
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _CREATE,
        _DESTROY,
    ]
    # subtree_keys hands the destroy the child (2) and the grandchild (3); the
    # grandchild is the deepest and reaches the rest, so only it survives.
    assert _deps(tracker, 4) == [3]


def test_move_carries_child_transitively():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.move(_ref("box"), _ref("basket"))
    tracker.destroy(_ref("basket"))
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _MOVE,
        _DESTROY,
    ]
    # The move pulls in box::inner via the Child Rule; box::inner already reaches
    # create box (1), so that is not repeated.
    assert _deps(tracker, 3) == [2]
    # basket::inner is recorded under its pre-move name, so the destroy reaches
    # it only transitively through the move node.
    assert _deps(tracker, 4) == [3]


def test_move_carries_grandchild_subtree():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.create(_ref("box"), ())
    tracker.create(_ref("box", "inner"), ())
    tracker.create(_ref("box", "inner", "deep"), ())
    tracker.move(_ref("box"), _ref("basket"))
    tracker.destroy(_ref("basket"))
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _CREATE,
        _MOVE,
        _DESTROY,
    ]
    # The move pulls in the carried subtree; the grandchild (3) is deepest and
    # reaches the child (2) and the box (1), so only it survives.
    assert _deps(tracker, 4) == [3]
    # The carried subtree keeps its pre-move keys, so the destroy of the
    # moved-to parent reaches it only through the move node.
    assert _deps(tracker, 5) == [4]


def test_from_caller_create_records_no_operation():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    iface = _ref("iface")
    tracker.create(iface, (), from_caller=iface)
    tracker.destroy(iface)
    # The from-caller create is not a body operation, so the destroy has
    # nothing of its own to wait on and waits on the trigger-position
    # requirement.
    assert _kinds(tracker) == [_ACTION_PARENT_LAST_OPERATION, _DESTROY]
    assert _deps(tracker, 1) == [0]


def test_mark_empty_records_nothing():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    tracker.mark_empty(_ref("slot"))
    tracker.create(_ref("slot"), ())
    assert _kinds(tracker) == [_ACTION_PARENT_LAST_OPERATION, _CREATE]
    assert _deps(tracker, 1) == [0]


def test_triggered_guarantee_output_becomes_a_guarantee_node():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    box = _action("/b")
    run = _chain(_local("box"), box, _local("run"))
    out = _chain(_local("box"), box, _local("out"))
    tracker.create(_ref("box"), ())  # requirement 0, create 1
    tracker.create(run, ())  # 2: the caller fill that fires the trigger
    tracker.apply_guarantees(
        _action_chain(_local("box"), box),
        action_contract.Guarantees(
            own=[(("position<out>",), _occupied_by_new())], nested=()
        ),
        run,
        [],
        [],
    )
    # The triggered action's output becomes a guarantee node hanging off the
    # trigger; that node is the output's last operation.
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _GUARANTEE,
    ]
    assert _last_operation(tracker, out) == 3
    # A caller operation on the output chains to the guarantee node, the most
    # recent operation on its ancestor chain, which already waits on the box
    # that holds it.
    tracker.destroy(out)  # 4
    assert _deps(tracker, 4) == [3]


def test_triggered_guarantee_parent_and_child_become_guarantee_nodes():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    box = _action("/b")
    run = _chain(_local("box"), box, _local("run"))
    tracker.create(_ref("box"), ())  # requirement 0, create 1
    tracker.create(run, ())  # 2: the trigger fill
    tracker.apply_guarantees(
        _action_chain(_local("box"), box),
        action_contract.Guarantees(
            own=[
                (("position<parent>",), _occupied_by_new()),
                (("position<parent>", "position<child>"), _occupied_by_new()),
            ],
            nested=(),
        ),
        run,
        [],
        [],
    )
    # Each of the callee's outputs becomes its own guarantee node.
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _GUARANTEE,
        _GUARANTEE,
    ]
    parent = _chain(_local("box"), box, _local("parent"))
    child = _chain(_local("box"), box, _local("parent"), _local("child"))
    assert _last_operation(tracker, parent) == 3
    assert _last_operation(tracker, child) == 4


def test_nested_triggered_guarantee_becomes_a_guarantee_node():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    outer = _action("/outer")
    inner = _action("/inner")
    run = _chain(_local("box"), outer, _local("run"))
    # A globally-named triggered action re-roots at its parent position (the box),
    # so a nested action fires on the box directly rather than under its trigger.
    # The sibling ensures that inner-action trie node exists before the deferred
    # guarantee's target is drained.
    sibling = _chain(_local("box"), inner, _local("sibling"))
    item = _chain(_local("box"), inner, _local("item"))
    tracker.create(_ref("box"), ())  # requirement 0, create 1
    tracker.create(run, ())  # 2: the trigger fill
    tracker.create(sibling, ())  # 3
    nested = action_contract.NestedGuarantees(
        triggered_action=("action<my.domain.com:my_lib:/inner>",),
        guarantees=action_contract.Guarantees(
            own=[(("position<item>",), _occupied_by_new())], nested=()
        ),
    )
    tracker.apply_guarantees(
        _action_chain(_local("box"), outer),
        action_contract.Guarantees(own=[], nested=(nested,)),
        run,
        [],
        [],
    )
    # The nested guarantee is deferred; a query on its output drains it, adding a
    # guarantee node (hanging off the trigger it inherited) that becomes the
    # output's last operation.
    assert tracker.is_occupied(item)
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _CREATE,
        _GUARANTEE,
    ]
    assert _last_operation(tracker, item) == 4


def test_stale_nested_guarantee_keeps_the_later_last_operation():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    earlier = _action("/earlier")
    later = _action("/later")
    inner = _action("/inner")
    earlier_run = _chain(_local("box"), earlier, _local("run"))
    later_run = _chain(_local("box"), later, _local("run"))
    sibling = _chain(_local("box"), inner, _local("sibling"))
    item = _chain(_local("box"), inner, _local("item"))
    inner_item = ("action<my.domain.com:my_lib:/inner>", "position<item>")
    tracker.create(_ref("box"), ())  # requirement 0, create 1
    tracker.create(earlier_run, ())  # 2: the earlier trigger fill
    tracker.create(sibling, ())  # 3
    tracker.create(later_run, ())  # 4: the later trigger fill
    # The earlier trigger defers a nested guarantee for box::action</inner>::item.
    nested = action_contract.NestedGuarantees(
        triggered_action=("action<my.domain.com:my_lib:/inner>",),
        guarantees=action_contract.Guarantees(
            own=[(("position<item>",), _occupied_by_new())], nested=()
        ),
    )
    tracker.apply_guarantees(
        _action_chain(_local("box"), earlier),
        action_contract.Guarantees(own=[], nested=(nested,)),
        earlier_run,
        [],
        [],
    )
    # The later trigger writes the same position eagerly, becoming its last
    # operation.
    tracker.apply_guarantees(
        _action_chain(_local("box"), later),
        action_contract.Guarantees(own=[(inner_item, _occupied_by_new())], nested=()),
        later_run,
        [],
        [],
    )
    assert _last_operation(tracker, item) == 5
    # Draining the earlier trigger's stale guarantee finds the position already
    # decided by the later write, so it adds no node and does not change the last
    # operation.
    assert tracker.is_occupied(item)
    assert _kinds(tracker) == [
        _ACTION_PARENT_LAST_OPERATION,
        _CREATE,
        _CREATE,
        _CREATE,
        _CREATE,
        _GUARANTEE,
    ]
    assert _last_operation(tracker, item) == 5


def test_apply_guarantees_tags_the_trigger_with_its_action():
    tracker = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    box = _action("/b")
    run = _chain(_local("box"), box, _local("run"))
    action_chain = _action_chain(_local("box"), box)
    tracker.create(_ref("box"), ())  # requirement 0, create 1
    tracker.create(run, ())  # 2: the trigger fill
    tracker.apply_guarantees(
        action_chain,
        action_contract.Guarantees(
            own=[(("position<out>",), _occupied_by_new())], nested=()
        ),
        run,
        [],
        [],
    )
    # The fill of the trigger position is the operation that fires the callee, and
    # is what satisfies the callee's requirement on that position; the box that
    # merely holds it fires nothing.
    assert list(tracker.operation_graph.triggers) == [
        operation_graph.ActionTrigger(
            action_chain,
            2,
            {
                ("position<run>",): operation_graph.RequirementBinding(
                    2, operation_graph.ParticleChildOperations(), None
                )
            },
            action_parent_last_operation_node_id=1,
        )
    ]


def test_apply_guarantees_records_ordering_edge_for_touched_unchanged_position():
    # A callee creates and destroys its own required-empty position: it touches
    # the position but ends it empty, so its contract carries an
    # UnchangedGuarantee -- unchanged, but operated on.
    callee = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    x = _local("x")
    x_ref = _ref("x")
    callee.create(x_ref, ())
    callee.destroy(x_ref)
    requirements = {
        ("position<x>",): _make_requirement(
            action_contract.PositionOccupancyState.EMPTY, x_ref
        )
    }
    callee_guarantees = callee.generate_own_guarantees((x,), (), requirements)
    assert len(callee_guarantees) == 1
    key, guarantee = callee_guarantees[0]
    assert key == ("position<x>",)
    assert isinstance(guarantee, action_contract.UnchangedGuarantee)
    assert _last_operation(callee, x_ref) == 2

    # A caller triggers that action, then fills the position the callee touched.
    caller = particle_tracker.ParticleTracker(_NO_REQUIREMENTS, _ref("run"))
    box = _local("box")
    b = _action("/b")
    caller.create(_ref("box"), ())  # requirement node 0, box create node 1
    run = _chain(box, b, _local("run"))
    caller.create(run, ())  # node 2: the fill that fires the trigger
    caller.apply_guarantees(
        _action_chain(box, b),
        action_contract.Guarantees(own=callee_guarantees, nested=()),
        run,
        [],
        [],
    )
    caller.create(_chain(box, b, x), ())  # node 4

    # The caller's fill of x waits for the guarantee node (node 3) that
    # transiently occupied x: the UnchangedGuarantee carried the ordering the
    # caller must respect. That node already reaches the enclosing box (node 1),
    # so the fill needs no separate edge to it.
    assert _deps(caller, 4) == [3]
