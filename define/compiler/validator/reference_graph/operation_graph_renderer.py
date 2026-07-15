"""Renders an action's operation graph as a readable map of dependencies, for tests."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import action_contract, operation_graph

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

# Every operation graph test names the action it validates /test.
_ENTRY_POINT_ACTION_PATH = "/test"

type _OperationGraphs = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, operation_graph.OperationGraph
]
type _ActionOperationLabels = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, _OperationLabels
]
# One triggering of one action, by the operation that fired it and the action it
# fires. An action names each of its own triggerings, and one operation can fire
# more than one of them.
type _TriggerKey = tuple[int, str]


def _trigger_key(trigger: operation_graph.ActionTrigger) -> _TriggerKey:
    """Return the key that tells one triggering an action performs from the next."""
    return (trigger.trigger_node_id, trigger.callee_action_name.full_typed_name)


def _action_name(action: ast.GlobalTypedName) -> str:
    """Return an action's name without its universe or path, such as ``test``."""
    return action.name_content.path.name.removeprefix("/")


def operation_dependencies(
    operation_graphs: _OperationGraphs,
) -> dict[str, list[str]]:
    """Return a label for each operation the entry-point action performs or triggers, mapped to the labels it depends on."""
    for typed_name in operation_graphs:
        if typed_name.name_content.path.name == _ENTRY_POINT_ACTION_PATH:
            return _Program(operation_graphs).to_scheduling_table(typed_name)
    raise KeyError(_ENTRY_POINT_ACTION_PATH)


def action_graph(operation_graphs: _OperationGraphs) -> list[tuple[str, str]]:
    """Return each action's directly-triggered actions as (source, target) name pairs.

    An action that triggers the same action twice yields two edges. Actions appear
    in reference-graph post-order and their triggerings in the order they perform
    them, so the result is deterministic. A reference-graph diamond can still make
    two sibling actions' relative order nondeterministic; assertions spanning such
    actions should compare ``action_graph_set``.
    """
    edges: list[tuple[str, str]] = []
    for action, graph in operation_graphs.items():
        for trigger in graph.triggers:
            edges.append(
                (action.source_typed_name, trigger.callee_action_name.full_typed_name)
            )
    return edges


def action_graph_set(operation_graphs: _OperationGraphs) -> set[tuple[str, str]]:
    """Return ``action_graph`` as a set, for assertions whose edge order is nondeterministic."""
    return set(action_graph(operation_graphs))


class _OperationLabels:
    """The label of every operation of one graph, by node id."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Label every operation in ``graph``."""
        self._labels: dict[int, str] = {}
        times_seen: dict[str, int] = {}
        for node in graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._operation_label(node)
            # An action can perform the same operation on the same position more
            # than once, which every operation after the first says in its label.
            count = times_seen.get(label, 0) + 1
            times_seen[label] = count
            self._labels[node.node_id] = label if count == 1 else f"{label}#{count}"

    def __getitem__(self, node_id: int) -> str:
        """Return the label of the operation at ``node_id``."""
        return self._labels[node_id]

    @classmethod
    def _operation_label(cls, node: operation_graph.PositionOperationNode) -> str:
        """Return the label of one operation, such as ``move(item, dest)``."""
        target = cls._position_name(node.target)
        match node:
            case operation_graph.CreateNode():
                return f"create({target})"
            case operation_graph.MoveNode():
                source = cls._position_name(node.source)
                return f"move({source}, {target})"
            case operation_graph.DestroyNode():
                return f"destroy({target})"
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    @staticmethod
    def _position_name(position: ast.PositionReference) -> str:
        """Return a position's name as the action that operates on it names it."""
        return "::".join(
            typed_name.name_content.source_name for typed_name in position.typed_names
        )


class _InvocationLabels:
    """The name one action gives each action it triggers, by the triggering."""

    def __init__(self, graph: operation_graph.OperationGraph):
        """Name every action ``graph`` triggers."""
        self._names: dict[_TriggerKey, str] = {}
        self._callees: list[ast.GlobalTypedNameReference] = []
        times_invoked: dict[str, int] = {}
        for trigger in graph.triggers:
            action_name = _action_name(trigger.callee_action_name)
            # An action can trigger the same action more than once, which every
            # triggering after the first says in its name.
            count = times_invoked.get(action_name, 0) + 1
            times_invoked[action_name] = count
            self._names[_trigger_key(trigger)] = (
                action_name if count == 1 else f"{action_name}#{count}"
            )
            self._callees.append(trigger.callee_action_name)

    def __getitem__(self, trigger: operation_graph.ActionTrigger) -> str:
        """Return the name of the action ``trigger`` fires."""
        return self._names[_trigger_key(trigger)]

    def names(self) -> Iterable[str]:
        """Return the name of every action this action triggers."""
        return self._names.values()

    def callees(self) -> Iterable[ast.GlobalTypedNameReference]:
        """Return the action every triggering of this action fires."""
        return self._callees


class _ActionInvocationLabels:
    """The name of every triggering in the program, by the action that performs it.

    Each action names its own triggerings, knowing nothing of the rest of the
    program, so a name can fail to stand for one triggering in two ways: two
    actions that trigger the same callee both name their first triggering of it
    ``worker``, and an action triggered more than once hands out every one of its
    names again in each copy of itself. Either way, the name carries the name of
    the triggering it was spliced in by: ``first:worker``, ``first#2:worker``.
    """

    def __init__(self, graphs: _OperationGraphs):
        """Name every triggering the actions in ``graphs`` perform."""
        self._labels: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, _InvocationLabels
        ] = typed_name_dict.TypedNameDict()
        # How many actions give out each name, and how many times each action is
        # triggered. A name stands for one triggering only when one action gives it
        # and that action is itself triggered only once.
        callers_naming: dict[str, int] = {}
        times_invoked: typed_name_dict.TypedNameDict[ast.GlobalTypedName, int] = (
            typed_name_dict.TypedNameDict()
        )
        for caller, graph in graphs.items():
            labels = _InvocationLabels(graph)
            self._labels[caller] = labels
            for name in labels.names():
                callers_naming[name] = callers_naming.get(name, 0) + 1
            for callee in labels.callees():
                times_invoked[callee] = times_invoked.get(callee, 0) + 1
        self._ambiguous: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, set[str]
        ] = typed_name_dict.TypedNameDict()
        for caller, labels in self._labels.items():
            caller_invoked_repeatedly = times_invoked.get(caller, 0) > 1
            self._ambiguous[caller] = {
                name
                for name in labels.names()
                if callers_naming[name] > 1 or caller_invoked_repeatedly
            }

    def name(
        self,
        action: ast.GlobalTypedName,
        spliced_name: str,
        trigger: operation_graph.ActionTrigger,
    ) -> str:
        """Return the name of the action ``trigger`` fires, triggered from the copy of ``action`` named ``spliced_name``."""
        name = self._labels[action][trigger]
        if name in self._ambiguous[action]:
            return f"{spliced_name}:{name}"
        return name


class _NameResolver:
    """The name every operation and every triggering in the program goes by.

    Both are decided across the whole program at once: an action's operations are
    labeled with its own name for them wherever it is spliced in, and whether a
    triggering's name says which triggering spliced it in depends on what the
    other actions call theirs.
    """

    def __init__(self, graphs: _OperationGraphs):
        """Name the operations and triggerings of every action in ``graphs``."""
        self._operation_labels: _ActionOperationLabels = typed_name_dict.TypedNameDict()
        for action, graph in graphs.items():
            self._operation_labels[action] = _OperationLabels(graph)
        self._invocation_labels: _ActionInvocationLabels = _ActionInvocationLabels(
            graphs
        )

    def operation_name(
        self, action: ast.GlobalTypedName, node: operation_graph.PositionOperationNode
    ) -> str:
        """Return what ``action`` calls the operation at ``node``, such as ``move(item, dest)``."""
        return self._operation_labels[action][node.node_id]

    def triggering_name(
        self,
        action: ast.GlobalTypedName,
        spliced_name: str,
        trigger: operation_graph.ActionTrigger,
    ) -> str:
        """Return the name of the action ``trigger`` fires, triggered from the copy of ``action`` named ``spliced_name``."""
        return self._invocation_labels.name(action, spliced_name, trigger)


class _Program:
    """Every action's operation graph, and the names everything in them goes by."""

    def __init__(self, graphs: _OperationGraphs):
        """Prepare to render the actions in ``graphs``."""
        self._graphs: _OperationGraphs = graphs
        self._names: _NameResolver = _NameResolver(graphs)

    def to_scheduling_table(self, action: ast.GlobalTypedName) -> dict[str, list[str]]:
        """Return a label for each operation ``action`` performs or triggers, mapped to the labels it depends on."""
        table: dict[str, list[str]] = {}
        # Nothing triggered the entry-point action, so nothing spliced it in.
        entry_point = _SplicedAction(
            self._graphs,
            self._names,
            action,
            _action_name(action),
            trigger=None,
            spliced_by=None,
        )
        entry_point.render(table)
        return table


@dataclass(frozen=True, slots=True)
class _SplicedAction:
    """One copy of an action's operations, spliced into the graph by a triggering.

    Triggering an action does not "call" it in the traditional sense. Logically,
    what it actually does is it splices the operations of the callee into the
    caller's graph. (The callee's operations wait on the caller's operations.)

    An action is spliced separately every time it is triggered.
    """

    graphs: _OperationGraphs
    names: _NameResolver
    action: ast.GlobalTypedName
    # What every operation of this copy is labeled with, such as ``middle``.
    name: str
    # The triggering that spliced this copy in, and the copy whose operation fired
    # it. Both are absent for the entry point, which nothing spliced in.
    trigger: operation_graph.ActionTrigger | None
    spliced_by: _SplicedAction | None

    @property
    def _graph(self) -> operation_graph.OperationGraph:
        """The operation graph of the action this is a copy of."""
        return self.graphs[self.action]

    def render(self, table: dict[str, list[str]]):
        """Add every operation of this copy, and of the actions it triggers, to ``table``."""
        for node in self._graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            label = self._label(node)
            if label in table:
                raise ValueError(f"two operations are labeled {label}")
            table[label] = self._operation_dependency_labels(node)
        # Triggering an action splices the operations of that action in here.
        for trigger in self._graph.triggers:
            self._spliced_callee(trigger).render(table)

    def _operation_dependency_labels(
        self, node: operation_graph.PositionOperationNode
    ) -> list[str]:
        """Return the labels of the operations ``node`` waits on."""
        dependency_labels = self._dependency_labels(node.depends_on)
        if dependency_labels or self.trigger is None or self.spliced_by is None:
            return dependency_labels
        # An operation with nothing else to wait on still only happens because the
        # action was triggered, so it waits on the operation that triggered it.
        return self.spliced_by._node_labels(
            self.spliced_by._graph.nodes[self.trigger.trigger_node_id]
        )

    def _spliced_callee(self, trigger: operation_graph.ActionTrigger) -> _SplicedAction:
        """Return the copy of the action ``trigger`` fires, which this copy splices in."""
        return _SplicedAction(
            self.graphs,
            self.names,
            trigger.callee_action_name,
            self.names.triggering_name(self.action, self.name, trigger),
            trigger=trigger,
            spliced_by=self,
        )

    def _label(self, node: operation_graph.PositionOperationNode) -> str:
        """Return the label of ``node``, an operation this copy performs, such as ``test.move(item, dest)``."""
        return f"{self.name}.{self.names.operation_name(self.action, node)}"

    def _dependency_labels(self, depends_on: Iterable[int]) -> list[str]:
        """Return the labels of the operations this copy waits on at the ids in ``depends_on``."""
        dependency_labels: list[str] = []
        for depends_on_node_id in depends_on:
            dependency_labels.extend(
                self._node_labels(self._graph.nodes[depends_on_node_id])
            )
        return dependency_labels

    def _node_labels(self, node: operation_graph.OperationNode) -> list[str]:
        """Return the labels of the operations this copy waits on at ``node``."""
        match node:
            case operation_graph.PositionOperationNode():
                return [self._label(node)]
            case operation_graph.RequirementNode():
                return self._requirement_labels(node)
            case operation_graph.RequirementChildrenNode():
                return self._resolve_requirement_children(node, frozenset())
            case operation_graph.GuaranteeNode():
                return self._guarantee_labels(node)
            case _:
                raise TypeError(f"unknown node type: {type(node).__name__}")

    def _guarantee_labels(self, guarantee: operation_graph.GuaranteeNode) -> list[str]:
        """Return the labels of the operations that leave the guaranteed position as the triggered action guarantees it."""
        # The triggered action guarantees the position, so what puts it in that
        # state is the last operation that action performs on it, in the copy of it
        # the triggering the guarantee hangs off spliced in.
        spliced_callee = self._spliced_callee(guarantee.trigger)
        return spliced_callee._guaranteed_position_labels(guarantee.guaranteed_position)

    def _guaranteed_position_labels(self, position: tuple[str, ...]) -> list[str]:
        """Resolve the final operation on a guaranteed position through pass-through actions."""
        last_operation = self._graph.last_operation_on_position(position)
        node = self._graph.nodes[last_operation]
        # A non-requirement node is this graph's recorded final operation on the
        # position. If only its initial RequirementNode remains, this action
        # passed a nested guarantee outward without recording it on the position.
        if not isinstance(node, operation_graph.RequirementNode):
            return self._node_labels(node)

        trigger = self._graph.last_trigger_using_requirement(node.node_id)
        callee_position = ast.chain_in_callee(trigger.action_chain, position)
        return self._spliced_callee(trigger)._guaranteed_position_labels(
            callee_position
        )

    def _requirement_labels(
        self, requirement: operation_graph.RequirementNode
    ) -> list[str]:
        """Return the labels of the operations that put the position of ``requirement`` in the state this copy needs it in."""
        if self.trigger is None or self.spliced_by is None:
            # Nothing spliced the entry-point action in, so nothing in this program
            # satisfies its requirements.
            return []
        binding = self.trigger.bindings.get(requirement.requirement_position)
        if binding is not None:
            # The action that triggered this copy says what satisfies the
            # requirement. That is one of its own operations, or a requirement of
            # its own, which whatever spliced it in satisfies in turn.
            return self.spliced_by._node_labels(
                self.spliced_by._graph.nodes[binding.node_id]
            )
        if (
            requirement.required_state
            is action_contract.PositionOccupancyState.OCCUPIED
        ):
            raise ValueError(
                f"nothing fills the position {requirement.requirement_position}"
            )
        # Nothing the caller did made the position empty: it is empty because
        # nothing was ever put in it. What left it that way is the fill of the
        # position above it, which is the requirement this one waits on. With no
        # position above it, no operation made it empty and it waits on nothing.
        return self._dependency_labels(requirement.depends_on)

    def _resolve_requirement_children(
        self,
        requirement: operation_graph.RequirementChildrenNode,
        depends_on_child_operations: frozenset[tuple[str, ...]],
    ) -> list[str]:
        """Resolve the caller contribution for emptying a required particle.

        For example, suppose /middle passes <source> from /test to /inner, and
        /inner operates on <source>::</a>::</deep> before emptying <source>.
        The renderer examines /middle and then /test for operations that the
        emptying operation must depend on. By the time it examines /test,
        ``depends_on_child_operations`` contains the relative position
        </a>::</deep>. If /test operated on <source>::</a>, that operation is
        omitted because /inner's operation already depends on it.
        """
        if self.trigger is None or self.spliced_by is None:
            # Skipped for the entry-point action.
            return []
        depends_on_child_operations = (
            requirement.depends_on_child_operations | depends_on_child_operations
        )
        binding = self.trigger.bindings[requirement.requirement_position]
        operations = binding.child_operations_not_on_same_paths_as(
            depends_on_child_operations
        )
        labels: list[str] = []
        for operation in sorted(operations, key=lambda operation: operation.node_id):
            operation_labels = self.spliced_by._node_labels(
                self.spliced_by._graph.nodes[operation.node_id]
            )
            if not operation_labels:
                raise ValueError(
                    f"child operation at {operation.child_position} has no label"
                )
            labels.extend(operation_labels)
        if binding.requirement_children_node is not None:
            labels.extend(
                self.spliced_by._resolve_requirement_children(
                    binding.requirement_children_node,
                    depends_on_child_operations,
                )
            )
        if labels or depends_on_child_operations:
            return labels
        return self.spliced_by._node_labels(
            self.spliced_by._graph.nodes[binding.node_id]
        )
