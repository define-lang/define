from define.compiler import ast
from define.compiler.validator.reference_graph import operation_graph

_LOC = ast.start_of_file_location()

_NO_REQUIREMENTS: frozenset[tuple[str, ...]] = frozenset()

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


def _action_chain(path: str) -> ast.ActionReference:
    return ast.ActionReference(
        typed_names=(
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


def _deps(graph: operation_graph.OperationGraph, node_id: int) -> set[int]:
    return set(graph.nodes[node_id].depends_on)


def _trigger(
    graph: operation_graph.OperationGraph,
    acting_on_position: ast.PositionReference,
    action_path: str,
    *output_keys: tuple[str, ...],
) -> ast.ActionReference:
    """Fire ``action_path`` from the operation on ``acting_on_position``, guaranteeing ``output_keys``.

    Each output's callee-local key is taken to equal its absolute key, which is
    all these synthetic graphs (no real callee) need. Returns the action chain
    the trigger was recorded with.
    """
    action_chain = _action_chain(action_path)
    trigger_node_id = graph.record_action_trigger(
        action_chain, acting_on_position, [], []
    )
    assert trigger_node_id is not None
    graph.record_guarantees(
        trigger_node_id,
        action_chain.typed_names[-1].full_typed_name,
        [(key, key) for key in output_keys],
    )
    return action_chain


def test_same_key_chain():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    assert _deps(graph, 0) == set()
    assert _deps(graph, 1) == {0}


def test_independent_positions_do_not_depend():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("two"))  # 2
    graph.record_destroy(_ref("two"), [])  # 3
    assert _deps(graph, 0) == set()
    assert _deps(graph, 1) == {0}
    assert _deps(graph, 2) == set()
    assert _deps(graph, 3) == {2}


def test_child_depends_on_nearest_ancestor():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    assert _deps(graph, 1) == {0}
    assert _deps(graph, 2) == {1}


def test_move_depends_on_both_ends():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    one = _ref("one")
    two = _ref("two")
    graph.record_create(one)  # 0
    graph.record_destroy(two, [])  # 1
    graph.record_move(one, two, [])  # 2
    assert list(graph.nodes) == [
        operation_graph.CreateNode(node_id=0, target=one, depends_on=[]),
        operation_graph.DestroyNode(node_id=1, target=two, depends_on=[]),
        operation_graph.MoveNode(node_id=2, source=one, target=two, depends_on=[0, 1]),
    ]


def test_move_carries_child_transitively():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
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
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 2
    # The destroy waits on the child (1); its own create (0) is not repeated,
    # since the child already reaches it.
    assert _deps(graph, 2) == {1}


def test_destroy_depends_on_emptied_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box", "inner"), [])  # 2
    # The child is now known-empty but still touched in the parent's subtree.
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 3
    assert 2 in _deps(graph, 3)


def test_recreate_after_direct_destroy_depends_on_destroy():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("one"))  # 2
    assert _deps(graph, 2) == {1}


def test_destroy_depends_on_deepest_touched_descendant_only():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    graph.record_destroy(
        _ref("box"), [_key("box", "inner"), _key("box", "inner", "deep")]
    )  # 3
    # The grandchild (2) is the deepest touched descendant and reaches both the
    # child (1) and the box (0), so the destroy needs only it.
    assert _deps(graph, 3) == {2}


def test_move_depends_on_carried_grandchild_subtree():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_create(_ref("box", "inner", "deep"))  # 2
    graph.record_move(
        _ref("box"),
        _ref("basket"),
        [_key("box", "inner"), _key("box", "inner", "deep")],
    )  # 3
    # The deepest carried descendant (2) reaches the rest of the subtree, so the
    # move needs only it.
    assert _deps(graph, 3) == {2}


def test_join_moving_into_emptied_position():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("one"))  # 0
    graph.record_destroy(_ref("one"), [])  # 1
    graph.record_create(_ref("two"))  # 2
    graph.record_move(_ref("two"), _ref("one"), [])  # 3
    # A join: the move waits on the particle it carries (2) and on the destroy
    # that emptied its target (1).
    assert _deps(graph, 3) == {1, 2}


def test_rebranch_after_join():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
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
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "inner"))  # 1
    graph.record_destroy(_ref("box"), [_key("box", "inner")])  # 2
    graph.record_create(_ref("box"))  # 3
    graph.record_create(_ref("surprise"))  # 4
    graph.record_move(_ref("surprise"), _ref("box", "inner"), [])  # 5
    graph.record_create(_ref("box", "other"))  # 6
    # The destroy waits on the child (1), which already reaches create box (0).
    assert _deps(graph, 2) == {1}
    # The move fills the new box's inner: create surprise (4) and the new box (3),
    # the most recent operation on inner's ancestor chain. The stale old inner
    # create (1) is not repeated -- the new box create already reaches it.
    assert _deps(graph, 5) == {3, 4}
    assert _deps(graph, 6) == {3}


def test_empty_after_ancestor_move_refill_waits_on_the_move():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("box", "child"))  # 1
    graph.record_destroy(_ref("box", "child"), [])  # 2
    graph.record_destroy(_ref("box"), [_key("box", "child")])  # 3
    graph.record_create(_ref("source"))  # 4
    graph.record_create(_ref("source", "child"))  # 5
    graph.record_move(_ref("source"), _ref("box"), [_key("source", "child")])  # 6
    graph.record_destroy(_ref("box", "child"), [])  # 7
    # The move (6) refilled box::child without operating on that key directly. It
    # is the most recent operation on box::child's ancestor chain, so the new
    # destroy waits on it and cannot run before the particle arrives. The stale
    # earlier destroy (2) is not repeated -- the move already reaches it.
    assert _deps(graph, 7) == {6}


def test_deep_grandchild_carried_through_two_moves():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("a"))  # 0
    graph.record_create(_ref("a", "b"))  # 1
    graph.record_create(_ref("a", "b", "c"))  # 2
    graph.record_move(_ref("a"), _ref("d"), [_key("a", "b"), _key("a", "b", "c")])  # 3
    graph.record_move(_ref("d"), _ref("e"), [_key("d", "b"), _key("d", "b", "c")])  # 4
    graph.record_destroy(_ref("e", "b", "c"), [])  # 5
    graph.record_destroy(_ref("e"), [_key("e", "b"), _key("e", "b", "c")])  # 6
    # The deepest carried descendant (2) reaches the rest of the subtree.
    assert _deps(graph, 3) == {2}
    # d's children keep their pre-move (a::) keys, so the Child Rule on the
    # second move misses them and reaches them through the first move (3).
    assert _deps(graph, 4) == {3}
    # e::b::c has no entry under that name, so this destroy hangs off e's move.
    assert _deps(graph, 5) == {4}
    # The parent destroy waits on the explicit destroy of e::b::c (5), which
    # already reaches e's move (4).
    assert _deps(graph, 6) == {5}


def test_operation_records_the_actions_it_triggers():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("basket"))  # 1
    brew = _action_chain("/brew")
    grind = _action_chain("/grind")
    _ = graph.record_action_trigger(brew, _ref("box"), [], [])
    _ = graph.record_action_trigger(grind, _ref("box"), [], [])
    assert graph.nodes[0].satisfies == [
        operation_graph.RequirementSatisfaction(brew, ()),
        operation_graph.RequirementSatisfaction(grind, ()),
    ]
    # An operation that fires nothing satisfies nothing.
    assert graph.nodes[1].satisfies == []


def test_each_operation_reports_only_its_own_triggers():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("one"))  # 0
    graph.record_create(_ref("two"))  # 1
    brew = _action_chain("/brew")
    grind = _action_chain("/grind")
    _ = graph.record_action_trigger(brew, _ref("one"), [], [])
    _ = graph.record_action_trigger(grind, _ref("two"), [], [])
    assert graph.nodes[0].satisfies == [
        operation_graph.RequirementSatisfaction(brew, ())
    ]
    assert graph.nodes[1].satisfies == [
        operation_graph.RequirementSatisfaction(grind, ())
    ]


def test_guarantee_adds_a_guarantee_node_hanging_off_the_trigger():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    machine = _ref("machine")
    graph.record_create(machine)  # 0: the trigger fill
    # 1: the guarantee node
    brew = _trigger(graph, machine, "/brew", _key("machine", "coffee"))
    assert list(graph.nodes) == [
        operation_graph.CreateNode(
            node_id=0,
            target=machine,
            depends_on=[],
            satisfies=[operation_graph.RequirementSatisfaction(brew, ())],
        ),
        operation_graph.GuaranteeNode(
            node_id=1,
            action=brew.typed_names[-1].full_typed_name,
            output_position=_key("machine", "coffee"),
            depends_on=[0],
        ),
    ]


def test_guarantee_node_carries_the_callee_action_and_output_position():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    machine = _ref("machine")
    graph.record_create(machine)  # 0: the trigger fill
    brew = _action_chain("/brew")
    _ = graph.record_action_trigger(brew, machine, [], [])
    # The callee's own key for the output (``position<coffee>``) differs from
    # where it lands in the caller (``machine::coffee``); the node keeps the
    # callee's key so codegen can find the last operation on it in the callee's
    # graph.
    graph.record_guarantees(
        0,
        brew.typed_names[-1].full_typed_name,
        [(_key("machine", "coffee"), ("position<coffee>",))],
    )
    assert list(graph.nodes) == [
        operation_graph.CreateNode(
            node_id=0,
            target=machine,
            depends_on=[],
            satisfies=[operation_graph.RequirementSatisfaction(brew, ())],
        ),
        operation_graph.GuaranteeNode(
            node_id=1,
            action=brew.typed_names[-1].full_typed_name,
            output_position=("position<coffee>",),
            depends_on=[0],
        ),
    ]


def test_operation_on_a_guaranteed_position_depends_on_the_guarantee_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    # 1: the guarantee node
    _ = _trigger(graph, _ref("machine"), "/brew", _key("machine", "coffee"))
    graph.record_destroy(_ref("machine", "coffee"), [])  # 2
    # The consumer chains to the guarantee node (the most recent operation on its
    # ancestor chain), not to the trigger directly. The guarantee node already
    # waits on the machine, so the consumer needs no separate ancestor edge.
    assert _deps(graph, 2) == {1}


def test_guarantee_overrides_an_earlier_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("cup"))  # 0: the caller already filled cup
    graph.record_create(_ref("machine"))  # 1: the trigger fill
    # 2: guarantee node re-fills cup
    _ = _trigger(graph, _ref("machine"), "/brew", _key("cup"))
    graph.record_destroy(_ref("cup"), [])  # 3
    # A later operation chains to the guarantee node, not the stale earlier create.
    assert _deps(graph, 3) == {2}


def test_parent_destroy_reaches_a_triggered_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("gadget"))  # 1: the trigger fill
    # 2: guarantee node fills box::out
    _ = _trigger(graph, _ref("gadget"), "/brew", _key("box", "out"))
    graph.record_destroy(_ref("box"), [_key("box", "out")])  # 3
    # The destroy waits, via the Child Rule, on the guarantee node that filled its
    # child (2); that node already reaches the box's create (0).
    assert _deps(graph, 3) == {2}


def test_triggered_outputs_get_separate_guarantee_nodes():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    # 1: guarantee node for coffee, 2: guarantee node for puck
    _ = _trigger(
        graph,
        _ref("machine"),
        "/brew",
        _key("machine", "coffee"),
        _key("machine", "puck"),
    )
    graph.record_destroy(_ref("machine", "coffee"), [])  # 3
    graph.record_destroy(_ref("machine", "puck"), [])  # 4
    # Each consumer hangs off its own output's guarantee node, the most recent
    # operation on its ancestor chain, which already waits on the machine.
    assert _deps(graph, 3) == {1}
    assert _deps(graph, 4) == {2}


def test_a_move_can_be_the_trigger_fill():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("src"))  # 0
    graph.record_move(_ref("src"), _ref("slot"), [])  # 1: the fill is a move
    # 2: the guarantee node
    _ = _trigger(graph, _ref("slot"), "/brew", _key("slot", "out"))
    graph.record_destroy(_ref("slot", "out"), [])  # 3
    assert graph.nodes[1].satisfies == [
        operation_graph.RequirementSatisfaction(_action_chain("/brew"), ())
    ]
    assert graph.nodes[0].satisfies == []
    # The destroy chains to the guarantee node, the most recent operation on its
    # ancestor chain, which already waits on the slot.
    assert _deps(graph, 3) == {2}


def test_a_later_operation_overrides_a_guarantee():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    # 1: guarantee node fills cup
    _ = _trigger(graph, _ref("machine"), "/brew", _key("cup"))
    graph.record_create(_ref("cup"))  # 2: the body re-fills cup after the guarantee
    graph.record_destroy(_ref("cup"), [])  # 3
    # The re-fill chains to the guarantee node; a later consumer chains to the re-fill.
    assert _deps(graph, 2) == {1}
    assert _deps(graph, 3) == {2}


def test_touched_list_order_does_not_change_edges():
    def build(touched: list[tuple[str, ...]]) -> operation_graph.OperationGraph:
        graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
        graph.record_create(_ref("box"))  # 0
        graph.record_create(_ref("box", "inner"))  # 1
        graph.record_create(_ref("box", "inner", "deep"))  # 2
        graph.record_destroy(_ref("box"), touched)  # 3
        return graph

    touched = [_key("box", "inner"), _key("box", "inner", "deep")]
    assert _deps(build(touched), 3) == _deps(build(list(reversed(touched))), 3) == {2}


def test_gap_in_touched_list_still_drops_the_shallower_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("outer"))  # 0
    graph.record_create(_ref("outer", "box"))  # 1
    graph.record_create(_ref("outer", "box", "mid"))  # 2
    graph.record_create(_ref("outer", "box", "mid", "deep"))  # 3
    graph.record_destroy(
        _ref("outer"), [_key("outer", "box"), _key("outer", "box", "mid", "deep")]
    )  # 4
    assert _deps(graph, 4) == {3}


def test_child_create_records_no_operation_for_other_keys():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    inner = _ref("box", "inner")
    box = _ref("box")
    other = _ref("other")
    graph.record_create(inner)  # 0
    # Nothing was recorded for the ancestor or an unrelated position, so
    # creates in them have no dependencies.
    graph.record_create(other)  # 1
    graph.record_create(box)  # 2
    assert list(graph.nodes) == [
        operation_graph.CreateNode(node_id=0, target=inner, depends_on=[]),
        operation_graph.CreateNode(node_id=1, target=other, depends_on=[]),
        operation_graph.CreateNode(node_id=2, target=box, depends_on=[]),
    ]


def test_duplicate_touched_keys_and_shared_move_operation():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    one = _ref("one")
    two = _ref("two")
    holder = _ref("holder")
    graph.record_create(one)  # 0
    graph.record_move(one, two, [])  # 1
    # The move is recorded for both its ends, and the destroy's duplicate
    # touched keys all resolve to that one move.
    graph.record_destroy(holder, [_key("one"), _key("one"), _key("two")])  # 2
    assert list(graph.nodes) == [
        operation_graph.CreateNode(node_id=0, target=one, depends_on=[]),
        operation_graph.MoveNode(node_id=1, source=one, target=two, depends_on=[0]),
        operation_graph.DestroyNode(node_id=2, target=holder, depends_on=[1]),
    ]


def test_wide_touched_subtree_drops_every_superseded_shallow_child():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("root"))  # 0
    child_count = 40
    touched: list[tuple[str, ...]] = []
    surviving_deep_children: set[int] = set()
    for index in range(child_count):
        child = f"c{index}"
        graph.record_create(_ref("root", child))
        graph.record_create(_ref("root", child, "deep"))
        touched.append(_key("root", child))
        touched.append(_key("root", child, "deep"))
        surviving_deep_children.add(graph.nodes[-1].node_id)
    graph.record_destroy(_ref("root"), touched)
    # Every shallow child is superseded by its later, deeper child, so only the
    # deep children survive.
    assert _deps(graph, graph.nodes[-1].node_id) == surviving_deep_children


def _requirement_node(
    graph: operation_graph.OperationGraph, node_id: int
) -> operation_graph.RequirementNode:
    node = graph.nodes[node_id]
    assert isinstance(node, operation_graph.RequirementNode)
    return node


def test_read_of_occupied_requirement_waits_on_a_lower_id_requirement_node():
    graph = operation_graph.OperationGraph({_key("input")})
    graph.record_destroy(_ref("input"), [])  # 1
    # The destroy reads a caller-filled position that no earlier body operation
    # acted on, so it waits on a RequirementNode minted at the lower id 0 -- it
    # stands in for the earlier caller op that filled the position.
    assert _deps(graph, 1) == {0}
    assert _requirement_node(graph, 0).requirement_position == _key("input")


def test_fill_of_empty_requirement_waits_on_a_requirement_node():
    graph = operation_graph.OperationGraph({_key("slot")})
    graph.record_create(_ref("slot"))  # 1
    assert _deps(graph, 1) == {0}
    assert _requirement_node(graph, 0).requirement_position == _key("slot")


def test_local_fill_with_no_requirement_gets_no_requirement_node():
    graph = operation_graph.OperationGraph(_NO_REQUIREMENTS)
    graph.record_create(_ref("item"))  # 0
    assert _deps(graph, 0) == set()
    assert len(graph.nodes) == 1


def test_earlier_body_operation_takes_precedence_over_a_requirement_node():
    graph = operation_graph.OperationGraph({_key("slot")})
    graph.record_create(_ref("slot"))  # 1 (waits on requirement node 0)
    graph.record_destroy(_ref("slot"), [])  # 2
    # The destroy follows an earlier body operation on the position (the create),
    # so it waits on that rather than minting a fresh requirement node.
    assert _deps(graph, 2) == {1}
    assert len(graph.nodes) == 3


def test_requirement_node_attaches_to_the_nearest_requirement_ancestor():
    graph = operation_graph.OperationGraph({_key("box")})
    graph.record_create(_ref("box", "mid", "deep"))  # 1
    assert _deps(graph, 1) == {0}
    assert _requirement_node(graph, 0).requirement_position == _key("box")


def test_two_children_of_required_parent_share_the_parent_requirement_node():
    # The callee-graph shape behind the empty-by-default-children integration
    # case: box is a caller-provided occupied requirement and box::/a, box::/b are
    # its empty-by-default children the body fills. box's RequirementNode (0) is
    # shared: each child's own RequirementNode depends on it, so the two creates
    # transitively wait on whatever establishes box.
    graph = operation_graph.OperationGraph(
        {_key("box"), _key("box", "a"), _key("box", "b")}
    )
    graph.record_create(_ref("box", "a"))  # req box 0, req box/a 1, create 2
    graph.record_create(_ref("box", "b"))  # req box/b 3, create 4
    nodes = graph.nodes
    assert len(nodes) == 5
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _key("box")
    assert nodes[0].depends_on == []
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _key("box", "a")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.CreateNode)
    assert nodes[2].depends_on == [1]
    assert isinstance(nodes[3], operation_graph.RequirementNode)
    assert nodes[3].requirement_position == _key("box", "b")
    assert nodes[3].depends_on == [0]
    assert isinstance(nodes[4], operation_graph.CreateNode)
    assert nodes[4].depends_on == [3]


def test_grandchild_fill_builds_the_full_requirement_ancestor_chain():
    # The grandchild integration case: filling a caller-provided grandchild builds
    # a RequirementNode per contracted ancestor (box, box::/child, grandchild),
    # each depending on the next shallower one, and the create waits on the leaf.
    graph = operation_graph.OperationGraph(
        {
            _key("box"),
            _key("box", "child"),
            _key("box", "child", "grandchild"),
        }
    )
    graph.record_create(_ref("box", "child", "grandchild"))  # reqs 0,1,2, create 3
    nodes = graph.nodes
    assert len(nodes) == 4
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _key("box")
    assert nodes[0].depends_on == []
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _key("box", "child")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.RequirementNode)
    assert nodes[2].requirement_position == _key("box", "child", "grandchild")
    assert nodes[2].depends_on == [1]
    assert isinstance(nodes[3], operation_graph.CreateNode)
    assert nodes[3].depends_on == [2]


def test_grandchild_read_builds_the_full_requirement_ancestor_chain():
    # The occupied-grandchild integration case: reading a caller-provided
    # grandchild builds the same ancestor chain, and the destroy waits on the leaf.
    graph = operation_graph.OperationGraph(
        {
            _key("box"),
            _key("box", "child"),
            _key("box", "child", "grandchild"),
        }
    )
    graph.record_destroy(
        _ref("box", "child", "grandchild"), []
    )  # reqs 0,1,2, destroy 3
    nodes = graph.nodes
    assert len(nodes) == 4
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _key("box")
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _key("box", "child")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.RequirementNode)
    assert nodes[2].requirement_position == _key("box", "child", "grandchild")
    assert nodes[2].depends_on == [1]
    assert isinstance(nodes[3], operation_graph.DestroyNode)
    assert nodes[3].depends_on == [2]


def test_read_of_a_carried_in_parent_child_builds_the_requirement_chain():
    # The callee-graph shape behind the moved-in-parent integration case: inner
    # reads input::/parent (provided by a caller move that carries the child), so
    # the destroy waits on the input::/parent requirement, which waits on input.
    graph = operation_graph.OperationGraph({_key("input"), _key("input", "parent")})
    graph.record_destroy(_ref("input", "parent"), [])  # reqs 0,1, destroy 2
    nodes = graph.nodes
    assert len(nodes) == 3
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _key("input")
    assert nodes[0].depends_on == []
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _key("input", "parent")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.DestroyNode)
    assert nodes[2].depends_on == [1]


def test_implied_position_children_share_the_global_parent_requirement_node():
    # The implied-position integration cases: /inner assigns the global /parent
    # and fills its children. The chain is built from global keys verbatim; the
    # /parent RequirementNode (0) is shared by both children's requirements.
    graph = operation_graph.OperationGraph(
        {
            _global_key("/parent"),
            _global_key("/parent", "/child1"),
            _global_key("/parent", "/child2"),
        }
    )
    graph.record_create(_global_ref("/parent", "/child1"))  # reqs 0,1, create 2
    graph.record_create(_global_ref("/parent", "/child2"))  # req 3, create 4
    nodes = graph.nodes
    assert len(nodes) == 5
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _global_key("/parent")
    assert nodes[0].depends_on == []
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _global_key("/parent", "/child1")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.CreateNode)
    assert nodes[2].depends_on == [1]
    assert isinstance(nodes[3], operation_graph.RequirementNode)
    assert nodes[3].requirement_position == _global_key("/parent", "/child2")
    assert nodes[3].depends_on == [0]
    assert isinstance(nodes[4], operation_graph.CreateNode)
    assert nodes[4].depends_on == [3]


def test_move_joins_an_in_body_source_with_a_requirement_target():
    # A move is the one operation with both a fill and an empty side, so it can
    # depend on a RequirementNode and a PositionOperationNode at once: it empties
    # the in-body-created <src> (Empty Rule -> the create) and fills the
    # caller-controlled empty-requirement <dest> (Fill Rule, no in-body op -> a
    # RequirementNode). This is the shape a real /test produces for
    # `create <src>; move <src> to <dest>` with <dest> an empty-by-default output.
    graph = operation_graph.OperationGraph({_key("dest")})
    graph.record_create(_ref("src"))  # 0
    graph.record_move(_ref("src"), _ref("dest"), [])  # req 1, move 2
    assert isinstance(graph.nodes[0], operation_graph.CreateNode)
    assert isinstance(graph.nodes[1], operation_graph.RequirementNode)
    assert graph.nodes[1].requirement_position == _key("dest")
    assert isinstance(graph.nodes[2], operation_graph.MoveNode)
    assert _deps(graph, 2) == {0, 1}


def test_implied_position_grandchild_builds_the_global_requirement_chain():
    # The implied grandchild integration case: the full global
    # /parent::/child::/grandchild chain is built from global keys, each
    # RequirementNode depending on the next shallower one.
    graph = operation_graph.OperationGraph(
        {
            _global_key("/parent"),
            _global_key("/parent", "/child"),
            _global_key("/parent", "/child", "/grandchild1"),
        }
    )
    graph.record_create(_global_ref("/parent", "/child", "/grandchild1"))
    nodes = graph.nodes
    assert len(nodes) == 4
    assert isinstance(nodes[0], operation_graph.RequirementNode)
    assert nodes[0].requirement_position == _global_key("/parent")
    assert isinstance(nodes[1], operation_graph.RequirementNode)
    assert nodes[1].requirement_position == _global_key("/parent", "/child")
    assert nodes[1].depends_on == [0]
    assert isinstance(nodes[2], operation_graph.RequirementNode)
    assert nodes[2].requirement_position == _global_key(
        "/parent", "/child", "/grandchild1"
    )
    assert nodes[2].depends_on == [1]
    assert isinstance(nodes[3], operation_graph.CreateNode)
    assert nodes[3].depends_on == [2]
