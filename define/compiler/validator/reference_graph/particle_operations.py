"""Particle statements and Action Executions in execution order."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from define.compiler import ast


@dataclass(frozen=True, slots=True, eq=False)
class ActionExecution:
    """One execution of an action triggered by a particle arrival."""

    callee: ast.ActionReference
    acting_on_position: ast.PositionReference


type ParticleOperations = list[ast.ParticleStatement | ActionExecution]
