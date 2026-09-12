"""Semantic identities for destruction and Destruction Contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler import ast


@dataclass(frozen=True, slots=True, eq=False)
class SimultaneousDestruction:
    """The directly destroyed particle and its Simultaneous Transitive Destruction."""

    directly_destroyed_position: ast.PositionReference
    destroying_action: ast.GlobalTypedName
    is_automatic: bool


@dataclass(frozen=True, slots=True, eq=False)
class DestructionFact:
    """Identifies the destruction of one specific particle."""

    destruction: SimultaneousDestruction
    destroyed_position_in_destroyer: ast.PositionReference
