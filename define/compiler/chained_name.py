"""Operations on canonical chained names that tag each result as a position or an action."""

from __future__ import annotations

import typing

from define.compiler import name_types

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

# A canonical chained name of any kind, including a relative or partial one.
# TODO: Compute with these tuples instead of building ChainedName objects
# wherever the code does not need a SourceLocation.
ChainedNameTuple = typing.NewType("ChainedNameTuple", tuple[str, ...])

# A chained name's kind is the kind of its last typed name, so a
# PositionReferenceTuple can still contain actions, as in
# position<p>::action<a>::position<q>.
# TODO: Allow a PositionReferenceTuple to be empty, naming the particle that
# relative names start from, and then change the ChainedNameTuples that are
# only ChainedNameTuples because they can be empty to PositionReferenceTuples:
# ACTION_PARENT_PARTICLE, and Child State positions such as
# DestructionContract.position_in_child_state and the Child State keys.
PositionReferenceTuple = typing.NewType("PositionReferenceTuple", ChainedNameTuple)
ActionReferenceTuple = typing.NewType("ActionReferenceTuple", ChainedNameTuple)

# The chain of the particle an action is assigned to, from that action's
# perspective: no name precedes the names of that particle's children.
ACTION_PARENT_PARTICLE: typing.Final = ChainedNameTuple(())


def position(names: tuple[str, ...]) -> PositionReferenceTuple:
    """Tag canonical typed names that end in a position."""
    return typing.cast("PositionReferenceTuple", names)


def action(names: tuple[str, ...]) -> ActionReferenceTuple:
    """Tag canonical typed names that end in an action."""
    return typing.cast("ActionReferenceTuple", names)


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
    return names_after(chain, len(prefix))


def names_after(chain: ChainedNameTuple, name_count: int) -> ChainedNameTuple:
    """Return the names of ``chain`` after its first ``name_count`` names."""
    return ChainedNameTuple(chain[name_count:])


def with_suffix(chain: ChainedNameTuple, *typed_names: str) -> ChainedNameTuple:
    """Return ``chain`` with ``typed_names`` appended as child names."""
    return ChainedNameTuple((*chain, *typed_names))


def parent(chain: ChainedNameTuple) -> ChainedNameTuple:
    """Return ``chain`` without its last name."""
    return ChainedNameTuple(chain[:-1])


def last_name(chain: ChainedNameTuple) -> ChainedNameTuple:
    """Return the last name of ``chain`` as a chain of one name."""
    return ChainedNameTuple(chain[-1:])


def replace_prefix[T: ChainedNameTuple](
    chain: T, old_prefix: ChainedNameTuple, new_prefix: ChainedNameTuple
) -> T:
    """Return ``chain`` with ``old_prefix``, which must be a prefix of it, replaced by ``new_prefix``."""
    return typing.cast("T", new_prefix + chain[len(old_prefix) :])


def proper_prefixes(chain: ChainedNameTuple) -> Iterator[ChainedNameTuple]:
    """Yield each proper prefix of the chain, shortest first, starting with the empty chain."""
    for length in range(len(chain)):
        yield ChainedNameTuple(chain[:length])


def in_caller[T: ChainedNameTuple](
    callee_chain: ActionReferenceTuple, chain_from_callee: T
) -> T:
    """Return ``chain_from_callee``, a chain from a callee's perspective, from the perspective of the caller that triggers that callee through ``callee_chain``."""
    if starts_with_global(chain_from_callee):
        return typing.cast("T", callee_chain[:-1] + chain_from_callee)
    return typing.cast("T", callee_chain + chain_from_callee)


def last_action_index(chain: ChainedNameTuple) -> int | None:
    """Return the index of the chain's last action, or None if it has none."""
    for index in range(len(chain) - 1, -1, -1):
        if is_action_key(chain[index]):
            return index
    return None


def chain_to_last_action(chain: ChainedNameTuple) -> ActionReferenceTuple | None:
    """Return the chain up to and including its last action, or None if it has none."""
    index = last_action_index(chain)
    return None if index is None else action(chain[: index + 1])


def position_prefix(chain: ChainedNameTuple, name_count: int) -> PositionReferenceTuple:
    """Return the chain's first ``name_count`` typed names, which must end in a position."""
    return position(chain[:name_count])


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
    return None if index is None else position(chain[: index + 1])
