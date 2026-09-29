"""Operations on canonical chained names that tag each result as a position or an action."""

from __future__ import annotations

import typing

from define.compiler import name_types

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

# A position's canonical chained name, as stored in tries and contracts.
# TODO: Compute with these tuples instead of building ChainedName objects
# wherever the code does not need a SourceLocation.
# TODO: Also, use this everywhere appropriate.
type ChainedNameTuple = tuple[str, ...]

# A chained name's kind is the kind of its last typed name, so a
# PositionReferenceTuple can still contain actions, as in
# position<p>::action<a>::position<q>.
PositionReferenceTuple = typing.NewType("PositionReferenceTuple", tuple[str, ...])
ActionReferenceTuple = typing.NewType("ActionReferenceTuple", tuple[str, ...])

_ACTION_TYPED_NAME_PREFIX: typing.Final = f"{name_types.NameType.ACTION.value}<"


def is_action_key(typed_name: str) -> bool:
    """Return whether a canonical typed name in a chained-name key is an action."""
    return typed_name.startswith(_ACTION_TYPED_NAME_PREFIX)


def starts_with_global(chain: ChainedNameTuple) -> bool:
    """Return whether the leftmost element of a chained-name key is a global."""
    return "/" in chain[0]


def with_prefix[T: ChainedNameTuple](chain: T, prefix: ChainedNameTuple) -> T:
    """Return ``chain`` with ``prefix`` as its parent names."""
    return typing.cast("T", prefix + chain)


def without_prefix(
    chain: ChainedNameTuple, prefix: ChainedNameTuple
) -> ChainedNameTuple:
    """Return the names of ``chain`` after ``prefix``, which must be a prefix of it."""
    return chain[len(prefix) :]


def replace_prefix[T: ChainedNameTuple](
    chain: T, old_prefix: ChainedNameTuple, new_prefix: ChainedNameTuple
) -> T:
    """Return ``chain`` with ``old_prefix``, which must be a prefix of it, replaced by ``new_prefix``."""
    return typing.cast("T", new_prefix + chain[len(old_prefix) :])


def prefixes(chain: ChainedNameTuple) -> Iterator[ChainedNameTuple]:
    """Yield each nonempty prefix of the chain, shortest first."""
    for length in range(1, len(chain) + 1):
        yield chain[:length]


def in_caller[T: ChainedNameTuple](
    caller_chain: ActionReferenceTuple, local_chain: T
) -> T:
    """Return a callee-local chain from the perspective of a caller that triggers it via ``caller_chain``."""
    if starts_with_global(local_chain):
        return typing.cast("T", caller_chain[:-1] + local_chain)
    return typing.cast("T", caller_chain + local_chain)


def last_action_index(chain: ChainedNameTuple) -> int | None:
    """Return the index of the chain's last action, or None if it has none."""
    for index in range(len(chain) - 1, -1, -1):
        if is_action_key(chain[index]):
            return index
    return None


def chain_to_last_action(chain: ChainedNameTuple) -> ActionReferenceTuple | None:
    """Return the chain up to and including its last action, or None if it has none."""
    index = last_action_index(chain)
    return None if index is None else ActionReferenceTuple(chain[: index + 1])


def position_prefix(chain: ChainedNameTuple, name_count: int) -> PositionReferenceTuple:
    """Return the chain's first ``name_count`` typed names, which must end in a position."""
    return PositionReferenceTuple(chain[:name_count])


def position_prefixes_before_first_action(
    chain: ChainedNameTuple,
) -> list[PositionReferenceTuple]:
    """Return every prefix of the chain that ends before its first action, shortest first."""
    prefixes: list[PositionReferenceTuple] = []
    for index, typed_name in enumerate(chain):
        if is_action_key(typed_name):
            break
        prefixes.append(position_prefix(chain, index + 1))
    return prefixes


def parent_position_index(chain: ChainedNameTuple) -> int | None:
    """Return the index of the chain's nearest parent position, or None if it has none."""
    for index in range(len(chain) - 2, -1, -1):
        if not is_action_key(chain[index]):
            return index
    return None


def parent_position(chain: ChainedNameTuple) -> PositionReferenceTuple | None:
    """Return the nearest parent position, or None if the chain has no parent position."""
    index = parent_position_index(chain)
    return None if index is None else PositionReferenceTuple(chain[: index + 1])
