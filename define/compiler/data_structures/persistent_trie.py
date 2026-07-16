"""An immutable trie that preserves earlier versions after every update.

"Persistent" is the data-structure term for returning a new value from an
update while leaving the old value usable. It does not mean that the trie is
stored on disk. The new and old versions share the portions that did not change,
so retaining many snapshots costs much less memory than copying the complete
trie for each update.

Use this trie when keys form prefix paths, updates must not alter snapshots that
other objects already retain, and copying every key for every snapshot would be
too expensive. A mutable trie is simpler when callers need only the latest
version.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

type TrieKey = tuple[str, ...]


class _Missing:
    pass


_MISSING = _Missing()

# Compiler profiling showed that updates dominate traversal: operation-graph
# construction can perform millions of updates, while many retained versions
# are never passed to maximal_items(). An update therefore copies only the
# immediate-child dictionaries on its key's prefix path. Unchanged trie nodes
# remain shared, and Python dictionaries make the common small-child-map case
# substantially faster than a persistent balanced tree.
#
# We also measured these alternatives:
#
# - Persistent AVL child maps used much less memory when thousands of
#   progressively wider versions remained live, but made generated
#   full-compiler workloads 15-37% slower. They became faster only around
#   1,500-2,000 immediate children on one trie node when every version was
#   retained, a situation that should almost never happen in a compiler run.
# - One copied dictionary containing all complete key-value pairs made every
#   update scan and copy the complete collection. It was slightly faster for a
#   50,000-line single-action workload, but 58% slower for a wide, dense
#   action graph and used up to 54 times as much retained memory in isolated
#   benchmarks.
# - One copied tuple containing all complete key-value pairs had the same
#   whole-collection update cost and was about twice as slow as the flat
#   dictionary while using still more retained memory.
# - Maintaining maximal_items as another persistent structure would add work
#   and retained state to every update, and its traversal was not a measured
#   bottleneck.
#
# This implementation deliberately favors compiler throughput over the AVL
# representation's worst-case memory bound for extremely wide, heavily retained
# child maps.


@dataclass(frozen=True, slots=True)
class _TrieNode[V]:
    value: V | _Missing = _MISSING
    children: dict[str, _TrieNode[V]] | None = None


@dataclass(frozen=True, slots=True)
class PersistentTrie[V]:
    """A trie whose updates return structurally shared immutable values."""

    _root: _TrieNode[V] = field(default_factory=_TrieNode)

    def replace_subtree(self, key: TrieKey, value: V) -> PersistentTrie[V]:
        """Return a trie with a non-empty ``key`` set and its descendants removed."""
        path: list[tuple[_TrieNode[V], str]] = []
        trie_node = self._root
        for name in key:
            path.append((trie_node, name))
            child = None if trie_node.children is None else trie_node.children.get(name)
            trie_node = _TrieNode[V]() if child is None else child

        updated = _TrieNode(value)
        for parent, name in reversed(path):
            children = {} if parent.children is None else parent.children.copy()
            children[name] = updated
            updated = _TrieNode(parent.value, children)
        return PersistentTrie(updated)

    def maximal_items(self) -> Iterator[tuple[TrieKey, V]]:
        """Yield valued keys that have no valued descendant, in no guaranteed order."""
        work: list[tuple[TrieKey, _TrieNode[V]]] = [((), self._root)]
        while work:
            key, trie_node = work.pop()
            if not trie_node.children:
                if trie_node.value is not _MISSING:
                    yield key, typing.cast("V", trie_node.value)
                continue
            # Dictionary insertion order makes traversal repeatable for the same
            # update sequence. Callers either treat these items as unordered or
            # impose the operation-node order they require, so canonical key
            # ordering would add sorting work without affecting graph semantics.
            for name, child in trie_node.children.items():
                work.append(((*key, name), child))
