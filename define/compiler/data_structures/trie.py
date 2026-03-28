"""A trie supporting O(k) point ops, subtree reparenting, and ancestor traversal."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Generator

type TrieKey = tuple[str, ...] | list[str]


class _Node[V]:
    """Internal trie node. Every non-root node always has a value."""

    __slots__: typing.ClassVar[tuple[str, ...]] = ("children", "value")

    def __init__(self, value: V):
        # Most nodes will have 1-2 children. If memory profiling shows trie
        # node count is high enough that per-dict overhead matters, this could
        # be replaced with adaptive storage: None for 0 children, a
        # (str, _Node) tuple for 1 child, upgrading to dict at 2+. That saves
        # ~48-64 bytes per single-child node at the cost of isinstance checks
        # on every access. My suspicion is that our current trade off (memory
        # in exchange for processing speed) is the right one, but future data
        # could convince me otherwise.
        self.children: dict[str, _Node[V]] = {}
        self.value: V = value


class StrictReparentingTrie[V]:
    """A trie keyed by string sequences, supporting subtree reparenting.

    Keys are tuples or lists of strings. Each element represents one level
    in the trie. Every node must have an existing parent (except
    single-element keys, whose parent is the root). Deleting a node
    deletes all of its descendants.

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.

    Key operations:
    - Point lookup/insert/delete: O(k) where k is key length
    - Subtree move: O(k) via node reparenting
    - Ancestor traversal: O(k), yielding each intermediate node's value
    """

    def __init__(self):
        """Initialize an empty trie."""
        self._root: dict[str, _Node[V]] = {}

    def _validate_key(self, key: TrieKey):
        if not key:
            raise ValueError("key must not be empty")

    def _walk(self, key: TrieKey) -> _Node[V] | None:
        """Walk to the node for key, returning None if the path doesn't exist."""
        children = self._root
        node: _Node[V] | None = None
        for element in key:
            node = children.get(element)
            if node is None:
                return None
            children = node.children
        return node

    def _walk_to_parent(self, key: TrieKey) -> dict[str, _Node[V]]:
        """Walk to the parent's children dict for key.

        For single-element keys, returns the root children dict.
        Raises KeyError if any intermediate node doesn't exist.
        """
        children = self._root
        for element in key[:-1]:
            node = children.get(element)
            if node is None:
                raise KeyError(key)
            children = node.children
        return children

    def __contains__(self, key: TrieKey) -> bool:
        """Check if key has a value."""
        self._validate_key(key)
        return self._walk(key) is not None

    def __getitem__(self, key: TrieKey) -> V:
        """Get value at key. Raises KeyError if missing."""
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result

    def __setitem__(self, key: TrieKey, value: V):
        """Set value at key. Parent must already exist (KeyError if not)."""
        self._validate_key(key)
        parent_children = self._walk_to_parent(key)
        last = key[-1]
        existing = parent_children.get(last)
        if existing is not None:
            existing.value = value
        else:
            parent_children[last] = _Node[V](value)

    def __delitem__(self, key: TrieKey):
        """Remove node and all descendants. Raises KeyError if missing."""
        self._validate_key(key)
        parent_children = self._walk_to_parent(key)
        last = key[-1]
        if last not in parent_children:
            raise KeyError(key)
        del parent_children[last]

    def get(self, key: TrieKey, default: V | None = None) -> V | None:
        """Get value at key, or default if missing."""
        self._validate_key(key)
        node = self._walk(key)
        if node is None:
            return default
        return node.value

    def move_subtree(self, source: TrieKey, target: TrieKey):
        """Detach the subtree at source and reattach it at target.

        The source key must exist. The target key must not already exist.
        The target's parent must exist. All descendants of source become
        descendants of target.

        Raises KeyError if source doesn't exist or target's parent doesn't exist.
        Raises ValueError if target already exists.
        """
        self._validate_key(source)
        self._validate_key(target)

        # Validate source and target before modifying anything.
        source_parent = self._walk_to_parent(source)
        source_last = source[-1]
        if source_last not in source_parent:
            raise KeyError(source)
        target_parent = self._walk_to_parent(target)
        target_last = target[-1]
        if target_last in target_parent:
            raise ValueError(f"target key already exists: {target}")

        # Both validated — perform the move.
        target_parent[target_last] = source_parent.pop(source_last)

    def items(self) -> Generator[tuple[list[str], V]]:
        """Yield all (key, value) pairs in the trie.

        The yielded key list is reused across iterations. Callers must copy
        it (e.g. ``tuple(key)``) if they need to keep it beyond the current
        iteration step. Callers must not modify the list key.
        """
        # CPython may shrink the list's internal array when it falls below
        # ~50% capacity after pops. In tries with widely varying branch depths
        # this could cause repeated reallocation.
        path: list[str] = []

        def recurse(node: _Node[V]) -> Generator[tuple[list[str], V]]:
            yield (path, node.value)
            for element, child in node.children.items():
                path.append(element)
                yield from recurse(child)
                _ = path.pop()

        for element, child in self._root.items():
            path.append(element)
            yield from recurse(child)
            _ = path.pop()

    def keys(self) -> Generator[list[str]]:
        """Yield all keys that have values.

        The yielded key list is reused across iterations. Callers must copy
        it if they need to keep it beyond the current iteration step. Callers
        must not modify the returned list.
        """
        for key, _ in self.items():
            yield key
