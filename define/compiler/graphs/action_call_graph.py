"""Action call graph for tracking trigger relationships between actions."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import cached_property
from typing import cast

import networkx as nx

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


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
    statement: ast.DimensionPointStatement

    @property
    def modified_position(self) -> ast.ChainedName:
        """Return the position chain that this statement writes into."""
        return self.statement.target_position.chain

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
class ActionGraphEdge:
    """A directed edge from a source action to a target action it triggers."""

    source: str
    target: str
    statement: ast.DimensionPointStatement


class ActionCallGraph:
    """Tracks which actions can trigger which other actions.

    Built during the DFS post-order walk of the reference graph, which
    guarantees that a target action's triggers are registered before any
    effect referencing that action arrives.
    """

    # Qualified name (prefixed with the action name) of the position a
    # trigger condition is on (e.g. "action<d:u:/alarm>::position<triggered>")
    # --> the full typed name of the action whose Trigger Conditions Block
    # checks that position.
    _trigger_position_to_action_name: dict[str, str]
    _graph: nx.MultiDiGraph[str]

    def __init__(self):
        """Initialize an empty call graph."""
        self._trigger_position_to_action_name = {}
        self._graph = nx.MultiDiGraph()

    def register_triggers(self, trigger_positions: Sequence[TriggerPositionInfo]):
        """Register trigger positions from a completed definition's validation."""
        for tp in trigger_positions:
            self._trigger_position_to_action_name[
                tp.checked_position_name_with_prefix
            ] = tp.enclosing_typed_name.full_typed_name()

    def register_effects(self, body_effects: Sequence[ActionBodyEffect]):
        """Register action body effects, resolving them against known triggers."""
        for effect in body_effects:
            target_action = self._trigger_position_to_action_name.get(
                effect.affected_position_qualified_chained_name
            )
            if target_action is None:
                continue
            source_action = effect.enclosing_typed_name.full_typed_name()
            _ = self._graph.add_edge(
                source_action, target_action, statement=effect.statement
            )

    def edges(self) -> Iterator[ActionGraphEdge]:
        """Yield an ``ActionGraphEdge`` for every resolved trigger edge."""
        for source, target, data in self._graph.edges(data=True):
            yield ActionGraphEdge(
                source=source,
                target=target,
                statement=cast(
                    "ast.DimensionPointStatement",
                    data["statement"],
                ),
            )

    def unique_edges(self) -> set[tuple[str, str]]:
        """Return the set of distinct ``(source, target)`` pairs."""
        return {(source, target) for source, target in self._graph.edges()}
