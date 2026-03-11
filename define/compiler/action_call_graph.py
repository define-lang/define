"""Action call graph for tracking trigger relationships between actions."""

from __future__ import annotations

import collections
import typing
from dataclasses import dataclass
from functools import cached_property

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class TriggerPositionInfo:
    """An action's trigger condition, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    checked_position: ast.ChainedName

    @cached_property
    def checked_position_name_with_prefix(self) -> str:
        """Return the full chained name of the position the trigger condition is checking, prefixed with the action name."""
        fqun = self.enclosing_typed_name.name_content.fqun
        chain_str = self.checked_position.canonical_chained_name(in_universe=fqun)
        return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"


@dataclass(frozen=True)
class ActionBodyEffect:
    """A body statement that writes a DP into a position, for cross-action matching."""

    enclosing_typed_name: ast.GlobalTypedNameInDefinition
    statement: ast.CreateDimensionPointStatement | ast.MoveDimensionPointStatement

    @property
    def modified_position(self) -> ast.ChainedName:
        """Return the position chain that this statement writes into."""
        match self.statement:
            case ast.CreateDimensionPointStatement():
                return self.statement.position_reference.chain
            case ast.MoveDimensionPointStatement():
                return self.statement.to_position.chain

    @cached_property
    def _action_boundary(self) -> tuple[int, str] | None:
        """Find the last action reference in the chain.

        Returns (index, full_typed_name) or None if no action ref exists.
        """
        fqun = self.enclosing_typed_name.name_content.fqun
        for i in range(len(self.modified_position.typed_names) - 1, -1, -1):
            elem = self.modified_position.typed_names[i]
            if elem.name_type == ast.NameType.ACTION:
                return (i, elem.full_typed_name(in_universe=fqun))
        return None

    @cached_property
    def target_action_name(self) -> str:
        """Return the action whose position is being modified.

        When the chain contains an explicit action reference, that action is
        the target. Otherwise, the enclosing action is the implicit target
        (the write is to a local position).
        """
        if self._action_boundary is not None:
            return self._action_boundary[1]
        return self.enclosing_typed_name.full_typed_name()

    @cached_property
    def affected_position_qualified_chained_name(self) -> str:
        """Return the globally-unique position key of the position that was affected (got a dimension point)."""
        fqun = self.enclosing_typed_name.name_content.fqun
        boundary = self._action_boundary
        if boundary is None:
            chain_str = self.modified_position.canonical_chained_name(in_universe=fqun)
            return f"{self.enclosing_typed_name.full_typed_name()}::{chain_str}"
        idx = boundary[0]
        return "::".join(
            elem.full_typed_name(in_universe=fqun)
            for elem in self.modified_position.typed_names[idx:]
        )


@dataclass(frozen=True)
class ActionTriggerEdge:
    """A directed edge from a source action to a target action it triggers."""

    source_action: str
    """Full typed name of the action (not chained) that performs the triggering effect."""
    target_action: str
    """Full typed name of the action (not chained) that gets triggered."""
    statement: ast.CreateDimensionPointStatement | ast.MoveDimensionPointStatement

    @property
    def source_line(self) -> int:
        """The source line of the statement that produced this edge."""
        return self.statement.position.line


class ActionCallGraph:
    """Tracks which actions can trigger which other actions.

    Built incrementally as definition results arrive from validation.
    """

    # Qualified name (prefixed with the action name) of the position a
    # trigger condition is on (e.g. "action<d:u:/alarm>::position<triggered>")
    # --> the full typed name of the action whose Trigger Conditions Block
    # checks that position.
    _trigger_position_to_action_name: dict[str, str]
    # Action names that have at least one trigger position registered.
    _actions_with_triggers: set[str]
    # Target action name --> effects whose target's triggers haven't been
    # registered yet. Drained as action definitions are processed.
    _effects_waiting_for_target: collections.defaultdict[str, list[ActionBodyEffect]]
    # Source action full typed name --> resolved trigger edges originating from that action.
    _edges: collections.defaultdict[str, list[ActionTriggerEdge]]

    def __init__(self):
        """Initialize an empty call graph."""
        self._trigger_position_to_action_name = {}
        self._actions_with_triggers = set()
        self._effects_waiting_for_target = collections.defaultdict(list)
        self._edges = collections.defaultdict(list)

    def process_definition_result(
        self,
        trigger_positions: Sequence[TriggerPositionInfo],
        action_body_effects: Sequence[ActionBodyEffect],
    ):
        """Register triggers and effects from a completed definition's validation."""
        self._register_triggers(trigger_positions)
        self._register_effects(action_body_effects)

    def all_edges(self) -> list[ActionTriggerEdge]:
        """Return all resolved trigger edges."""
        return [edge for edges in self._edges.values() for edge in edges]

    def _register_triggers(self, trigger_positions: Sequence[TriggerPositionInfo]):
        for tp in trigger_positions:
            action_name = tp.enclosing_typed_name.full_typed_name()
            self._trigger_position_to_action_name[
                tp.checked_position_name_with_prefix
            ] = action_name
            self._actions_with_triggers.add(action_name)

        # Resolve deferred effects whose target action now has triggers.
        newly_registered_actions = {
            tp.enclosing_typed_name.full_typed_name() for tp in trigger_positions
        }
        for action_name in newly_registered_actions:
            for effect in self._effects_waiting_for_target.pop(action_name, []):
                self._resolve_effect(effect)

    def _register_effects(self, body_effects: Sequence[ActionBodyEffect]):
        for effect in body_effects:
            target = effect.target_action_name
            if self._action_has_triggers(target):
                self._resolve_effect(effect)
            else:
                self._effects_waiting_for_target[target].append(effect)

    def _resolve_effect(self, effect: ActionBodyEffect):
        """Resolve an effect against the trigger index."""
        source_action = effect.enclosing_typed_name.full_typed_name()
        target_action = self._trigger_position_to_action_name.get(
            effect.affected_position_qualified_chained_name
        )
        if target_action is None:
            return
        edge = ActionTriggerEdge(
            source_action=source_action,
            target_action=target_action,
            statement=effect.statement,
        )
        self._edges[source_action].append(edge)

    def _action_has_triggers(self, action_name: str) -> bool:
        """Check if any trigger position is registered for the given action."""
        return action_name in self._actions_with_triggers
