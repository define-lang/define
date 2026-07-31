"""A hash-indexed trie supporting subtree reparenting and prefix scans.

Keys are sequences of string segments (tuples) that form a prefix hierarchy.
Every point operation (get/set/contains/delete) is a single tuple hash
plus one dict probe; there is no walking the segments like a traditional trie
data structure. A parallel ``children``index records each parent's immediate
child segments so that subtree moves, subtree deletes, and prefix scans are
cheap dictionary operations.

The root's children live under the empty-tuple key ``()`` so that
single-element keys have a parent entry to attach to.
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable, ItemsView, Iterable, Iterator

type TrieKey = tuple[str, ...]

_MISSING: typing.Final = object()


class TrieError(Exception):
    """Base exception for trie operations."""


class EmptyKeyError(TrieError):
    """Raised when an operation receives an empty key."""


class TargetExistsError(TrieError):
    """Raised when a move or graft target key already exists."""


class StrictReparentingTrie[V]:
    """A trie keyed by string sequences, supporting subtree reparenting.

    Every node must have an existing parent (except single-element keys, whose
    parent is the root). Deleting a key deletes all of its descendants.

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    def __init__(self):
        """Initialize an empty trie."""
        # This used to be a more traditional trie data structure where we had
        # a dictionary of dictionaries that we would walk through for each item.
        # However, that made lookups (our most common use case in the compiler)
        # very expensive and a fairly large hotspot in large compiles. Our new
        # structure optimizes for making lookups cheap, at the expense of making
        # moves more expensive.
        self._values: dict[TrieKey, V] = {}
        self._children: dict[TrieKey, set[str]] = {}

    def get(self, key: TrieKey, default: V | None = None) -> V | None:
        """Get value at key, or default if missing."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        return self._values.get(key, default)

    def __getitem__(self, key: TrieKey) -> V:
        """Get value at key. Raises KeyError if missing."""
        return self._values[key]

    def __contains__(self, key: TrieKey) -> bool:
        """Check if key has a value."""
        return key in self._values

    def _ensure_parent(self, key: TrieKey):
        """Verify the parent path for a write; strict tries require it to exist."""
        parent = key[:-1]
        if parent and parent not in self._values:
            raise KeyError(key)

    def __setitem__(self, key: TrieKey, value: V):
        """Set value at key. Parent must already exist (KeyError if not)."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        self._ensure_parent(key)
        self._values[key] = value
        parent = key[:-1]
        siblings = self._children.get(parent)
        if siblings is None:
            self._children[parent] = {key[-1]}
        else:
            siblings.add(key[-1])

    def _collect_subtree(self, root: TrieKey) -> list[TrieKey]:
        """Return root and all of its descendant keys."""
        result = [root]
        stack = [root]
        while stack:
            node = stack.pop()
            for segment in self._children.get(node, ()):
                child = (*node, segment)
                result.append(child)
                stack.append(child)
        return result

    def _unlink_from_parent(self, key: TrieKey):
        """Remove key's last segment from its parent's child set."""
        parent = key[:-1]
        siblings = self._children.get(parent)
        if siblings is not None:
            siblings.discard(key[-1])
            if not siblings:
                del self._children[parent]

    def __delitem__(self, key: TrieKey):
        """Remove key and all descendants. Raises KeyError if missing."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        if key not in self._values:
            raise KeyError(key)
        for node in self._collect_subtree(key):
            del self._values[node]
            _ = self._children.pop(node, None)
        self._unlink_from_parent(key)

    def move_subtree(self, source: TrieKey, target: TrieKey):
        """Detach the subtree at source and reattach it at target.

        The source key must exist. The target key must not already exist.
        The target's parent must exist (strict tries) or be auto-created
        (lenient tries). All descendants of source become descendants of target.

        Raises KeyError if source doesn't exist or target's parent doesn't exist.
        Raises TargetExistsError if target already exists.
        """
        if not source:
            raise EmptyKeyError("key must not be empty")
        if not target:
            raise EmptyKeyError("key must not be empty")
        if source not in self._values:
            raise KeyError(source)
        self._ensure_parent(target)
        if target in self._values:
            raise TargetExistsError(f"target key already exists: {target}")

        source_len = len(source)
        moved: list[tuple[TrieKey, V, set[str] | None]] = []
        for old in self._collect_subtree(source):
            value = self._values.pop(old)
            child_segments = self._children.pop(old, None)
            new = target + old[source_len:]
            moved.append((new, value, child_segments))
        for new, value, child_segments in moved:
            self._values[new] = value
            if child_segments is not None:
                self._children[new] = child_segments

        self._unlink_from_parent(source)
        self._children.setdefault(target[:-1], set()).add(target[-1])

    def pop_subtree(self, key: TrieKey) -> StrictReparentingTrie[V]:
        """Detach the subtree at key and return it as a new trie.

        The returned trie has a single root entry keyed by the last element of
        key, containing the popped value and all its descendants.

        Raises KeyError if key doesn't exist.
        """
        if not key:
            raise EmptyKeyError("key must not be empty")
        if key not in self._values:
            raise KeyError(key)
        return self._detach_subtree(key)

    def pop_subtrees(
        self, keys: Iterable[TrieKey]
    ) -> dict[TrieKey, StrictReparentingTrie[V]]:
        """Detach each present key's subtree, returning a map from key to its popped trie.

        Keys not present in the trie are skipped. When one key is a descendant
        of another, the descendant is popped first (deepest key first) so it is
        returned as its own trie instead of only as part of its ancestor's
        subtree.
        """
        result: dict[TrieKey, StrictReparentingTrie[V]] = {}
        for key in sorted(keys, key=len, reverse=True):
            if key in self._values:
                result[key] = self._detach_subtree(key)
        return result

    def _detach_subtree(self, key: TrieKey) -> StrictReparentingTrie[V]:
        """Detach the subtree at key, which must already exist, and return it as a new trie."""
        result: StrictReparentingTrie[V] = StrictReparentingTrie()
        key_len = len(key)
        root_segment = key[-1]
        for old in self._collect_subtree(key):
            value = self._values.pop(old)
            child_segments = self._children.pop(old, None)
            new = (root_segment, *old[key_len:])
            result._values[new] = value
            if child_segments is not None:
                result._children[new] = child_segments
        result._children.setdefault((), set()).add(root_segment)
        self._unlink_from_parent(key)
        return result

    def restore_subtree(
        self, target: TrieKey, subtree: StrictReparentingTrie[V], root_value: V
    ):
        """Consume a popped subtree and restore it at target with a new root value.

        The target key must not already exist. Its parent must exist (strict
        tries) or is auto-created (lenient tries). The subtree must not be used
        after this operation.

        Raises KeyError if the target's parent doesn't exist.
        Raises TargetExistsError if the target already exists.
        """
        if not target:
            raise EmptyKeyError("key must not be empty")
        self._ensure_parent(target)
        if target in self._values:
            raise TargetExistsError(f"target key already exists: {target}")

        subtree_values = subtree._values
        subtree_children = subtree._children
        subtree_root = (next(iter(subtree_children[()])),)
        del subtree_values[subtree_root]
        self._values[target] = root_value
        if not subtree_values:
            self._children.setdefault(target[:-1], set()).add(target[-1])
            return

        # Flat dictionary passes avoid the traversal bookkeeping that synthetic
        # benchmarks showed was substantially slower for consumed subtrees.
        for old, value in subtree_values.items():
            self._values[target + old[1:]] = value

        root_children = subtree_children.pop(subtree_root, None)
        if root_children is not None:
            self._children[target] = root_children
        del subtree_children[()]
        for old, child_segments in subtree_children.items():
            self._children[target + old[1:]] = child_segments
        self._children.setdefault(target[:-1], set()).add(target[-1])

    def items(self) -> ItemsView[TrieKey, V]:
        """Yield all (key, value) pairs in the trie."""
        return self._values.items()

    def subtree_items(self, key: TrieKey) -> list[tuple[TrieKey, V]]:
        """Return (relative_key, value) for every descendant of key.

        relative_key is the descendant's path below key; key itself is excluded.
        Relative keys are built during the walk so callers can index without
        re-slicing the shared prefix off every result.
        """
        if not key:
            raise EmptyKeyError("key must not be empty")
        result: list[tuple[TrieKey, V]] = []
        stack: list[tuple[TrieKey, TrieKey]] = [(key, ())]
        while stack:
            full_node, relative_node = stack.pop()
            for segment in self._children.get(full_node, ()):
                full_child = (*full_node, segment)
                relative_child = (*relative_node, segment)
                result.append((relative_child, self._values[full_child]))
                stack.append((full_child, relative_child))
        return result

    def selected_subtree_items[Selected](
        self, key: TrieKey, select: Callable[[V], Selected | None]
    ) -> Iterator[tuple[TrieKey, Selected]]:
        """Yield selected descendant values with keys relative to ``key``."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        stack: list[tuple[TrieKey, TrieKey]] = [(key, ())]
        while stack:
            full_node, relative_node = stack.pop()
            for segment in self._children.get(full_node, ()):
                full_child = (*full_node, segment)
                relative_child = (*relative_node, segment)
                value = self._values[full_child]
                selected = select(value)
                if selected is not None:
                    yield relative_child, selected
                stack.append((full_child, relative_child))

    def subtree_keys(self, key: TrieKey) -> list[TrieKey]:
        """Return the full key of every descendant of key; key itself is excluded."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        result: list[TrieKey] = []
        stack = [key]
        while stack:
            node = stack.pop()
            for segment in self._children.get(node, ()):
                child = (*node, segment)
                result.append(child)
                stack.append(child)
        return result

    def existing_prefix(self, key: TrieKey) -> TrieKey:
        """Return the longest prefix of key whose nodes all exist in the trie."""
        if not key:
            raise EmptyKeyError("key must not be empty")
        # Walking down from the full key lets us stop at the first hit, which is
        # the most common case inside of the compiler.
        for length in range(len(key), 0, -1):
            prefix = key[:length]
            if prefix in self._values:
                return prefix
        return ()

    def find_shortest_prefix_where(
        self, key: TrieKey, predicate: Callable[[V], bool]
    ) -> TrieKey | None:
        """Return the shortest prefix of key whose value satisfies predicate.

        Walks from the root toward the full key. Returns the first prefix whose
        value satisfies predicate, or None if no prefix matches. Stops early and
        returns None if a node along the path doesn't exist.
        """
        if not key:
            raise EmptyKeyError("key must not be empty")
        for length in range(1, len(key) + 1):
            prefix = key[:length]
            value = self._values.get(prefix, _MISSING)
            if value is _MISSING:
                return None
            if predicate(typing.cast("V", value)):
                return prefix
        return None

    def find_longest_prefix_where(
        self, key: TrieKey, predicate: Callable[[V], bool]
    ) -> TrieKey | None:
        """Return the longest prefix of key whose value satisfies predicate.

        Walks from the full key toward the root, skipping nodes that don't
        exist. Returns the first prefix whose value satisfies predicate, or None
        if no prefix matches.
        """
        if not key:
            raise EmptyKeyError("key must not be empty")
        for length in range(len(key), 0, -1):
            prefix = key[:length]
            value = self._values.get(prefix, _MISSING)
            if value is not _MISSING and predicate(typing.cast("V", value)):
                return prefix
        return None

    def find_longest_prefixes_where(
        self, keys: Iterable[TrieKey], predicate: Callable[[V], bool]
    ) -> dict[TrieKey, TrieKey | None]:
        """Return the longest matching prefix for each distinct key."""
        sorted_keys = sorted(keys)
        if sorted_keys and not sorted_keys[0]:
            raise EmptyKeyError("key must not be empty")
        results: dict[TrieKey, TrieKey | None] = {}
        previous_key: TrieKey = ()
        matches_by_depth: list[TrieKey | None] = [None]
        for key in sorted_keys:
            if key == previous_key:
                continue
            common_depth = 0
            for previous_segment, segment in zip(previous_key, key, strict=False):
                if previous_segment != segment:
                    break
                common_depth += 1
            del matches_by_depth[common_depth + 1 :]
            nearest_match = matches_by_depth[common_depth]
            for depth in range(common_depth + 1, len(key) + 1):
                prefix = key[:depth]
                value = self._values.get(prefix, _MISSING)
                if value is not _MISSING and predicate(typing.cast("V", value)):
                    nearest_match = prefix
                matches_by_depth.append(nearest_match)
            results[key] = nearest_match
            previous_key = key
        return results


class LenientReparentingTrie[V](StrictReparentingTrie[V]):
    """A trie that auto-creates intermediate nodes on write operations.

    When setting a value or moving a subtree to a target, missing intermediate
    nodes are created with ``default_factory()`` values. Reads, deletes, and
    move-source lookups remain strict.
    """

    _default_factory: typing.Callable[[], V]

    def __init__(self, default_factory: typing.Callable[[], V]):
        """Initialize with a factory for auto-created intermediate node values."""
        super().__init__()
        self._default_factory = default_factory

    @typing.override
    def _ensure_parent(self, key: TrieKey):
        """Auto-create any missing ancestors with default values."""
        for length in range(len(key) - 1, 0, -1):
            ancestor = key[:length]
            if ancestor in self._values:
                break
            self._values[ancestor] = self._default_factory()
            self._children.setdefault(ancestor[:-1], set()).add(ancestor[-1])
