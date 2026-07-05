from define.compiler import ast
from define.compiler.validator.reference_graph import operation_graph

_LOC = ast.start_of_file_location()

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


def _key(*names: str) -> tuple[str, ...]:
    return _ref(*names).canonical_chained_name_tuple


def _deps(graph: operation_graph.OperationGraph, node_id: int) -> set[int]:
    return set(graph.nodes[node_id].depends_on)


def _trigger(
    graph: operation_graph.OperationGraph,
    node_id: int,
    action_path: str,
    *output_keys: tuple[str, ...],
):
    """Fire ``action_path`` from operation ``node_id``, guaranteeing ``output_keys``.

    Each output's callee-local key is taken to equal its absolute key, which is
    all these synthetic graphs (no real callee) need.
    """
    action_chain = _action_chain(action_path)
    graph.record_action_trigger(node_id, action_chain)
    graph.record_guarantees(
        node_id,
        action_chain.typed_names[-1].full_typed_name,
        [(key, key) for key in output_keys],
    )


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
    assert graph.last_operation_node_id_for_key(_key("two")) == 2


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


def test_operation_records_the_actions_it_triggers():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("basket"))  # 1
    brew = _action_chain("/brew")
    grind = _action_chain("/grind")
    graph.record_action_trigger(0, brew)
    graph.record_action_trigger(0, grind)
    assert list(graph.triggered_actions(0)) == [brew, grind]
    # An operation that fires nothing has no triggered actions.
    assert graph.triggered_actions(1) == ()


def test_each_operation_reports_only_its_own_triggers():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("one"))  # 0
    graph.record_create(_ref("two"))  # 1
    brew = _action_chain("/brew")
    grind = _action_chain("/grind")
    graph.record_action_trigger(0, brew)
    graph.record_action_trigger(1, grind)
    assert list(graph.triggered_actions(0)) == [brew]
    assert list(graph.triggered_actions(1)) == [grind]


def test_guarantee_adds_a_guarantee_node_hanging_off_the_trigger():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    _trigger(graph, 0, "/brew", _key("machine", "coffee"))  # 1: the guarantee node
    # The output becomes a guarantee node whose last operation is that node, and
    # the guarantee node itself waits on the trigger.
    assert len(graph.nodes) == 2
    assert graph.last_operation_node_id_for_key(_key("machine", "coffee")) == 1
    assert _deps(graph, 1) == {0}


def test_guarantee_node_carries_the_callee_action_and_output_position():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    brew = _action_chain("/brew")
    graph.record_action_trigger(0, brew)
    # The callee's own key for the output (``position<coffee>``) differs from
    # where it lands in the caller (``machine::coffee``); the node keeps the
    # callee's key so codegen can find the split point in the callee's graph.
    graph.record_guarantees(
        0,
        brew.typed_names[-1].full_typed_name,
        [(_key("machine", "coffee"), ("position<coffee>",))],
    )
    node = graph.nodes[1]
    assert isinstance(node, operation_graph.GuaranteeNode)
    assert node.action == brew.typed_names[-1].full_typed_name
    assert node.output_position == ("position<coffee>",)
    assert node.depends_on == [0]
    assert graph.last_operation_node_id_for_key(_key("machine", "coffee")) == 1


def test_operation_on_a_guaranteed_position_depends_on_the_guarantee_node():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    _trigger(graph, 0, "/brew", _key("machine", "coffee"))  # 1: the guarantee node
    graph.record_destroy(_ref("machine", "coffee"), [])  # 2
    # The consumer chains to the guarantee node (rule 1) and to the machine
    # (rule 2), not to the trigger directly.
    assert _deps(graph, 2) == {0, 1}


def test_guarantee_overrides_an_earlier_operation():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("cup"))  # 0: the caller already filled cup
    graph.record_create(_ref("machine"))  # 1: the trigger fill
    _trigger(graph, 1, "/brew", _key("cup"))  # 2: guarantee node re-fills cup
    graph.record_destroy(_ref("cup"), [])  # 3
    # A later operation chains to the guarantee node, not the stale earlier create.
    assert _deps(graph, 3) == {2}


def test_parent_destroy_reaches_a_triggered_child():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("box"))  # 0
    graph.record_create(_ref("gadget"))  # 1: the trigger fill
    _trigger(graph, 1, "/brew", _key("box", "out"))  # 2: guarantee node fills box::out
    graph.record_destroy(_ref("box"), [_key("box", "out")])  # 3
    # The destroy waits on its own create (0) and, via rule 3, on the guarantee
    # node that filled its child (2).
    assert _deps(graph, 3) == {0, 2}


def test_triggered_outputs_get_separate_guarantee_nodes():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    # 1: guarantee node for coffee, 2: guarantee node for puck
    _trigger(graph, 0, "/brew", _key("machine", "coffee"), _key("machine", "puck"))
    graph.record_destroy(_ref("machine", "coffee"), [])  # 3
    graph.record_destroy(_ref("machine", "puck"), [])  # 4
    # Each consumer hangs off its own output's guarantee node (rule 1) and the
    # machine (rule 2).
    assert _deps(graph, 3) == {0, 1}
    assert _deps(graph, 4) == {0, 2}


def test_a_move_can_be_the_trigger_fill():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("src"))  # 0
    graph.record_move(_ref("src"), _ref("slot"), [])  # 1: the fill is a move
    _trigger(graph, 1, "/brew", _key("slot", "out"))  # 2: the guarantee node
    graph.record_destroy(_ref("slot", "out"), [])  # 3
    assert list(graph.triggered_actions(1)) == [_action_chain("/brew")]
    assert graph.triggered_actions(0) == ()
    # The destroy chains to the guarantee node (rule 1) and the slot (rule 2).
    assert _deps(graph, 3) == {1, 2}


def test_a_later_operation_overrides_a_guarantee():
    graph = operation_graph.OperationGraph()
    graph.record_create(_ref("machine"))  # 0: the trigger fill
    _trigger(graph, 0, "/brew", _key("cup"))  # 1: guarantee node fills cup
    graph.record_create(_ref("cup"))  # 2: the body re-fills cup after the guarantee
    graph.record_destroy(_ref("cup"), [])  # 3
    # The re-fill chains to the guarantee node; a later consumer chains to the re-fill.
    assert _deps(graph, 2) == {1}
    assert _deps(graph, 3) == {2}
