"""A hash-indexed trie supporting subtree reparenting and prefix scans.

Keys are chained names, whose typed names form a prefix hierarchy.
Every point operation (get/set/contains/delete) is a single tuple hash
plus one dict probe; there is no walking the segments like a traditional trie
data structure. A parallel ``children`` index records each parent's immediate
child keys so that subtree moves, subtree deletes, and prefix scans are cheap
dictionary operations. Retaining the keys already held by the value dictionary
also avoids rebuilding every absolute key during descendant walks.

The root's children live under the empty-tuple key ``()`` so that
single-element keys have a parent entry to attach to.
"""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name

if typing.TYPE_CHECKING:
    from collections.abc import (
        Callable,
        Collection,
        ItemsView,
        Iterable,
        Iterator,
    )
    from collections.abc import Set as AbstractSet

type TrieKey = chained_name.ChainedNameTuple

_MISSING: typing.Final = object()


class DetachedSubtree[V](msgspec.Struct):
    """A subtree detached from a trie, whose entries keep the keys they had there."""

    key: TrieKey
    values: dict[tuple[str, ...], V]
    children: dict[tuple[str, ...], set[tuple[str, ...]]]


class ReparentingTrie[V]:
    """A trie keyed by chained names, supporting subtree reparenting.

    The empty key is the root, which always has its ``default_factory()``
    value. It must never be passed to a method that changes the trie. Every
    other node has a parent. Setting a value, or moving or restoring a
    subtree to a target, creates any missing parent with a
    ``default_factory()`` value. Reads, deletes, and move-source lookups do
    not. Deleting a key deletes all of its descendants.

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    _default_factory: typing.Callable[[], V]

    def __init__(self, default_factory: typing.Callable[[], V]):
        """Initialize a trie that holds only its root, with a factory for the values of the root and of parents it creates."""
        self._default_factory = default_factory
        # This used to be a more traditional trie data structure where we had
        # a dictionary of dictionaries that we would walk through for each item.
        # However, that made lookups (our most common use case in the compiler)
        # very expensive and a fairly large hotspot in large compiles. Our new
        # structure optimizes for making lookups cheap, at the expense of making
        # moves more expensive.
        # Internal keys are plain tuples so that parent names and prefixes can
        # be sliced without tagging each one; keys leave the trie as TrieKey.
        self._values: dict[tuple[str, ...], V] = {(): default_factory()}
        self._children: dict[tuple[str, ...], set[tuple[str, ...]]] = {}

    def get(self, key: TrieKey) -> V | None:
        """Get the value at key, or None if it is missing."""
        return self._values.get(key)

    def __getitem__(self, key: TrieKey) -> V:
        """Get value at key. Raises KeyError if missing."""
        return self._values[key]

    def __contains__(self, key: TrieKey) -> bool:
        """Check if key has a value."""
        return key in self._values

    def _ensure_parent(self, key: tuple[str, ...]):
        """Create any missing ancestors with default values."""
        for length in range(len(key) - 1, 0, -1):
            ancestor = key[:length]
            if ancestor in self._values:
                break
            self._values[ancestor] = self._default_factory()
            self._children.setdefault(ancestor[:-1], set()).add(ancestor)

    def __setitem__(self, key: TrieKey, value: V):
        """Set value at key, creating any missing parent."""
        self._values[key] = value
        self._ensure_parent(key)
        parent = key[:-1]
        siblings = self._children.get(parent)
        if siblings is None:
            self._children[parent] = {key}
        else:
            siblings.add(key)

    def _collect_subtree(self, root: tuple[str, ...]) -> list[tuple[str, ...]]:
        """Return root and all of its descendant keys."""
        result = [root]
        stack = [root]
        while stack:
            node = stack.pop()
            for child in self._children.get(node, ()):
                result.append(child)
                stack.append(child)
        return result

    def _unlink_from_parent(self, key: tuple[str, ...]):
        """Remove key from its parent's child set."""
        parent = key[:-1]
        siblings = self._children[parent]
        siblings.discard(key)
        if not siblings:
            del self._children[parent]

    def delete_subtree(self, key: TrieKey):
        """Remove a key, which must exist, and its descendants."""
        for node in self._collect_subtree(key):
            del self._values[node]
            _ = self._children.pop(node, None)
        self._unlink_from_parent(key)

    def move_subtree(self, source: TrieKey, target: TrieKey):
        """Detach the subtree at source and reattach it at target.

        The source key must exist. The target key must not already exist.
        A missing parent of the target is created. All descendants of source
        become descendants of target.
        """
        self._ensure_parent(target)

        source_len = len(source)
        old_keys = self._collect_subtree(source)
        new_keys = {old: target + old[source_len:] for old in old_keys}
        moved: list[tuple[tuple[str, ...], V, set[tuple[str, ...]] | None]] = []
        for old in old_keys:
            value = self._values.pop(old)
            old_children = self._children.pop(old, None)
            new_children = (
                {new_keys[child] for child in old_children}
                if old_children is not None
                else None
            )
            moved.append((new_keys[old], value, new_children))
        for new, value, new_children in moved:
            self._values[new] = value
            if new_children is not None:
                self._children[new] = new_children

        self._unlink_from_parent(source)
        self._children.setdefault(target[:-1], set()).add(target)

    def pop_subtree(self, key: TrieKey) -> DetachedSubtree[V]:
        """Detach the subtree at key, which must already exist, keeping its keys."""
        values: dict[tuple[str, ...], V] = {}
        children: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
        for old in self._collect_subtree(key):
            values[old] = self._values.pop(old)
            old_children = self._children.pop(old, None)
            if old_children is not None:
                children[old] = old_children
        self._unlink_from_parent(key)
        return DetachedSubtree(key, values, children)

    def restore_subtree(self, target: TrieKey, subtree: DetachedSubtree[V]):
        """Consume a detached subtree and restore it at target.

        The target key must not already exist. A missing parent of the target
        is created. The subtree must not be used after this operation.
        """
        self._ensure_parent(target)
        key_length = len(subtree.key)
        new_keys = {old: target + old[key_length:] for old in subtree.values}
        for old, value in subtree.values.items():
            self._values[new_keys[old]] = value
        for old, old_children in subtree.children.items():
            self._children[new_keys[old]] = {new_keys[child] for child in old_children}
        self._children.setdefault(target[:-1], set()).add(target)

    def items(self) -> ItemsView[TrieKey, V]:
        """Yield all (key, value) pairs in the trie."""
        return typing.cast("ItemsView[TrieKey, V]", self._values.items())

    def direct_child_items(self, key: TrieKey) -> Iterator[tuple[TrieKey, V]]:
        """Yield each direct child's full key and value in key order."""
        for child in sorted(self._children.get(key, ())):
            yield chained_name.ChainedNameTuple(child), self._values[child]

    def child_keys(self, key: TrieKey) -> Collection[TrieKey]:
        """Return the full key of each direct child of ``key``.

        The result must not be iterated while the trie is changed.
        """
        return typing.cast("Collection[TrieKey]", self._children.get(key, ()))

    def pruned_subtree_items(
        self,
        key: TrieKey,
        *,
        key_prefix: TrieKey,
        excluded_keys: AbstractSet[TrieKey],
    ) -> Iterator[tuple[TrieKey, V]]:
        """Yield descendants with prefixed relative keys, in unspecified order.

        Each returned key is key_prefix followed by its path relative to key.
        Exclusions use those returned keys and omit both the matching node and
        its descendants. The starting key itself is never yielded or excluded.
        """
        pending: list[tuple[tuple[str, ...], tuple[str, ...]]] = [(key, key_prefix)]
        while pending:
            full_node, result_node = pending.pop()
            for full_child in self._children.get(full_node, ()):
                result_child = (*result_node, full_child[-1])
                if result_child in excluded_keys:
                    continue
                yield (
                    chained_name.ChainedNameTuple(result_child),
                    self._values[full_child],
                )
                pending.append((full_child, result_child))

    def subtree_values_with_parents(self, key: TrieKey) -> Iterator[tuple[V, V]]:
        """Yield the value of each descendant of key, which must exist, after its parent's value, with its parent's value.

        Each parent is yielded before its children. The trie's structure must
        not change during iteration.
        """
        stack: list[tuple[str, ...]] = [key]
        while stack:
            node = stack.pop()
            parent_value = self._values[node]
            for child in self._children.get(node, ()):
                yield parent_value, self._values[child]
                stack.append(child)

    def existing_prefix(self, key: TrieKey) -> TrieKey:
        """Return the longest prefix of key whose nodes all exist in the trie."""
        # Walking down from the full key lets us stop at the first hit, which is
        # the most common case inside of the compiler.
        for length in range(len(key), 0, -1):
            prefix = key[:length]
            if prefix in self._values:
                return chained_name.ChainedNameTuple(prefix)
        return chained_name.ChainedNameTuple(())

    def find_longest_prefix_where(
        self, key: TrieKey, predicate: Callable[[V], bool]
    ) -> TrieKey | None:
        """Return the longest prefix of key whose value satisfies predicate.

        Walks from the full key toward the root, skipping nodes that don't
        exist. Returns the first prefix whose value satisfies predicate, or None
        if no prefix matches.
        """
        for length in range(len(key), 0, -1):
            prefix = key[:length]
            value = self._values.get(prefix, _MISSING)
            if value is not _MISSING and predicate(typing.cast("V", value)):
                return chained_name.ChainedNameTuple(prefix)
        return None

    def find_longest_prefixes_where(
        self, keys: Iterable[TrieKey], predicate: Callable[[V], bool]
    ) -> dict[TrieKey, TrieKey | None]:
        """Return the longest matching prefix for each distinct key."""
        sorted_keys = sorted(keys)
        results: dict[TrieKey, tuple[str, ...] | None] = {}
        previous_key: tuple[str, ...] = ()
        matches_by_depth: list[tuple[str, ...] | None] = [None]
        for key in sorted_keys:
            if key in results:
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
        return typing.cast("dict[TrieKey, TrieKey | None]", results)
