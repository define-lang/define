"""Operations on canonical chained names that tag each result as a position or an action."""

from __future__ import annotations

import typing

from define.compiler import ast

# A chained name's kind is the kind of its last typed name, so a
# PositionReferenceTuple can still contain actions, as in
# position<p>::action<a>::position<q>.
PositionReferenceTuple = typing.NewType("PositionReferenceTuple", tuple[str, ...])
ActionReferenceTuple = typing.NewType("ActionReferenceTuple", tuple[str, ...])

_ACTION_PREFIX = f"{ast.NameType.ACTION}<"


def chain_to_last_action(chain: ast.ChainedNameTuple) -> ActionReferenceTuple | None:
    """Return the chain up to and including its last action, or None if it has none."""
    for index in range(len(chain) - 1, -1, -1):
        if chain[index].startswith(_ACTION_PREFIX):
            return ActionReferenceTuple(chain[: index + 1])
    return None


def parent_position(chain: ast.ChainedNameTuple) -> PositionReferenceTuple | None:
    """Return the nearest parent position, or None if the chain has no parent position."""
    for index in range(len(chain) - 2, -1, -1):
        if not chain[index].startswith(_ACTION_PREFIX):
            return PositionReferenceTuple(chain[: index + 1])
    return None
