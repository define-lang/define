"""Immutable sets of strings that share their structure, so a set made from others costs only what differs between them.

Each set is a Patricia tree keyed by the hashes of its names (Okasaki and
Gill, "Fast Mergeable Integer Maps"), and its nodes are hash-consed so that
equal sets are the same object (Filliâtre and Conchon, "Type-Safe Modular
Hash-Consing").
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


def _low_bits(key: int, bit: int) -> int:
    """Return the bits of ``key`` below ``bit``."""
    return key & (bit - 1)


class InternedSet:
    """An immutable set of strings.

    Sets are made only by ``InternedSets.with_name`` and
    ``InternedSets.union``, and each InternedSets remembers every set it has
    made. When one of them would make a set with the same names as a set it
    already made, it returns that existing set instead of a new copy. So two
    sets from the same InternedSets that hold the same names are always the
    same object, and ``first is second`` is enough to tell that they are
    equal. That is what lets a union skip whatever two sets have in common.
    """

    __slots__: typing.ClassVar[tuple[str, ...]] = ("size",)

    def __init__(self, size: int):
        """Hold ``size`` names; only this module makes these."""
        self.size: int = size

    def __contains__(self, name: str) -> bool:
        """Return whether ``name`` is in the set."""
        name_hash = hash(name)
        node = self
        while type(node) is _Branch:
            node = node.right if name_hash & node.bit else node.left
        return type(node) is _Leaf and node.key == name_hash and name in node.names

    def __len__(self) -> int:
        """Return the number of names in the set."""
        return self.size

    def __iter__(self) -> Iterator[str]:
        """Yield each name in the set, in an order that depends on the names' hashes."""
        pending: list[InternedSet] = [self]
        while pending:
            node = pending.pop()
            if type(node) is _Branch:
                pending.extend((node.right, node.left))
            elif type(node) is _Leaf:
                yield from node.names


@typing.final
class _Leaf(InternedSet):
    """The names whose hashes are ``key``, almost always one."""

    __slots__ = ("key", "names")

    def __init__(self, key: int, names: tuple[str, ...]):
        super().__init__(len(names))
        self.key = key
        self.names = names


@typing.final
class _Branch(InternedSet):
    """The names whose hashes all have ``low_bits`` below ``bit``, split by ``bit``, the lowest bit where their hashes differ."""

    __slots__ = ("bit", "left", "low_bits", "right")

    def __init__(self, low_bits: int, bit: int, left: InternedSet, right: InternedSet):
        super().__init__(left.size + right.size)
        self.low_bits = low_bits
        self.bit = bit
        self.left = left
        self.right = right


EMPTY: typing.Final = InternedSet(0)


@typing.final
class InternedSets:
    """Makes InternedSets, keeping one object for each distinct set it has made.

    Safe to use from several threads. When two threads make the same set at
    once, both get the one that was stored first.
    """

    def __init__(self):
        """Start with no sets made."""
        self._nodes: dict[tuple[object, ...], InternedSet] = {}

    def with_name(self, names: InternedSet, name: str) -> InternedSet:
        """Return ``names`` with ``name`` added."""
        return self.union(names, self._leaf(hash(name), (name,)))

    def union(self, first: InternedSet, second: InternedSet) -> InternedSet:
        """Return the names in either set."""
        if first is second or second is EMPTY:
            return first
        if first is EMPTY:
            return second
        if type(first) is _Leaf:
            return self._with_leaf(second, first)
        if type(second) is _Leaf:
            return self._with_leaf(first, second)
        return self._union_branches(
            typing.cast("_Branch", first), typing.cast("_Branch", second)
        )

    def _leaf(self, key: int, names: tuple[str, ...]) -> InternedSet:
        node_key = (key, names)
        existing = self._nodes.get(node_key)
        if existing is None:
            # setdefault, not assignment, is what makes this thread-safe:
            # when two threads make the same node at once, it hands both of
            # them whichever node was stored first.
            existing = self._nodes.setdefault(node_key, _Leaf(key, names))
        return existing

    def _branch(
        self, low_bits: int, bit: int, left: InternedSet, right: InternedSet
    ) -> InternedSet:
        # Every child is already the one object for its contents, so the
        # children's identities identify a node's contents.
        node_key = (low_bits, bit, left, right)
        existing = self._nodes.get(node_key)
        if existing is None:
            # setdefault, not assignment, is what makes this thread-safe:
            # when two threads make the same node at once, it hands both of
            # them whichever node was stored first.
            existing = self._nodes.setdefault(
                node_key, _Branch(low_bits, bit, left, right)
            )
        return existing

    def _with_leaf(self, node: InternedSet, leaf: _Leaf) -> InternedSet:
        if type(node) is _Leaf:
            if node.key != leaf.key:
                return self._join(node.key, node, leaf.key, leaf)
            names = {*node.names, *leaf.names}
            if len(names) == node.size:
                return node
            return self._leaf(node.key, tuple(sorted(names)))
        branch = typing.cast("_Branch", node)
        if _low_bits(leaf.key, branch.bit) != branch.low_bits:
            return self._join(branch.low_bits, branch, leaf.key, leaf)
        if leaf.key & branch.bit:
            right = self._with_leaf(branch.right, leaf)
            if right is branch.right:
                return branch
            return self._branch(branch.low_bits, branch.bit, branch.left, right)
        left = self._with_leaf(branch.left, leaf)
        if left is branch.left:
            return branch
        return self._branch(branch.low_bits, branch.bit, left, branch.right)

    def _union_branches(self, first: _Branch, second: _Branch) -> InternedSet:
        if first.bit == second.bit and first.low_bits == second.low_bits:
            left = self.union(first.left, second.left)
            right = self.union(first.right, second.right)
            if left is first.left and right is first.right:
                return first
            if left is second.left and right is second.right:
                return second
            return self._branch(first.low_bits, first.bit, left, right)
        # The branch on the lower bit is the one nearer the top of the tree.
        if first.bit > second.bit:
            first, second = second, first
        if _low_bits(second.low_bits, first.bit) != first.low_bits:
            return self._join(first.low_bits, first, second.low_bits, second)
        if second.low_bits & first.bit:
            right = self.union(first.right, second)
            if right is first.right:
                return first
            return self._branch(first.low_bits, first.bit, first.left, right)
        left = self.union(first.left, second)
        if left is first.left:
            return first
        return self._branch(first.low_bits, first.bit, left, first.right)

    def _join(
        self, first_key: int, first: InternedSet, second_key: int, second: InternedSet
    ) -> InternedSet:
        """Return the branch holding two nodes whose keys differ below both of them."""
        difference = first_key ^ second_key
        bit = difference & -difference
        if first_key & bit:
            first, second = second, first
        return self._branch(_low_bits(first_key, bit), bit, first, second)
