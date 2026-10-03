# pyright: reportUnusedCallResult=false

from __future__ import annotations

import pytest

from define.compiler import chained_name
from define.compiler.data_structures import trie


def _key(*names: str) -> chained_name.ChainedNameTuple:
    return chained_name.ChainedNameTuple(names)


class TestPointOps:
    def test_setitem_and_contains(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        assert _key("a") in t

    def test_not_contains_initially(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert _key("a") not in t

    def test_getitem(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 42
        assert t[_key("a", "b")] == 42

    def test_getitem_missing_raises(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        with pytest.raises(KeyError):
            _ = t[_key("a")]

    def test_overwrite_existing(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a")] = 2
        assert t[_key("a")] == 2

    def test_get_missing(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert t.get(_key("a")) is None

    def test_get_existing(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        assert t.get(_key("a")) == 1

    def test_root_has_default_value_initially(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert _key() in t
        assert t[_key()] == 0
        assert t.get(_key()) == 0


class TestDeleteSubtree:
    def test_deletes_item(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t.delete_subtree(_key("a"))
        assert _key("a") not in t

    def test_cascades_to_children(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t.delete_subtree(_key("a"))
        assert _key("a") not in t
        assert _key("a", "b") not in t
        assert _key("a", "b", "c") not in t

    def test_preserves_siblings(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "c")] = 3
        t.delete_subtree(_key("a", "b"))
        assert _key("a") in t
        assert _key("a", "c") in t

    def test_delete_then_reinsert_child(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t.delete_subtree(_key("a", "b"))
        t[_key("a", "b")] = 3
        assert t[_key("a", "b")] == 3


class TestMoveSubtree:
    def test_move_leaf(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t.move_subtree(_key("a"), _key("b"))
        assert _key("a") not in t
        assert t[_key("b")] == 1

    def test_move_with_children(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t[_key("a", "y")] = 3
        t.move_subtree(_key("a"), _key("b"))
        assert _key("a") not in t
        assert _key("a", "x") not in t
        assert _key("a", "y") not in t
        assert t[_key("b")] == 1
        assert t[_key("b", "x")] == 2
        assert t[_key("b", "y")] == 3

    def test_move_deeply_nested_children(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t.move_subtree(_key("a"), _key("z"))
        assert _key("a") not in t
        assert t[_key("z")] == 1
        assert t[_key("z", "b", "c")] == 3

    def test_move_preserves_sibling(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("c")] = 3
        t.move_subtree(_key("a"), _key("b"))
        assert t[_key("c")] == 3

    def test_move_into_deeper_path(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "child")] = 2
        t[_key("x")] = 10
        t.move_subtree(_key("a"), _key("x", "y"))
        assert _key("a") not in t
        assert t[_key("x", "y")] == 1
        assert t[_key("x", "y", "child")] == 2

    def test_move_from_deeper_path(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("x")] = 10
        t[_key("x", "y")] = 1
        t[_key("x", "y", "child")] = 2
        t.move_subtree(_key("x", "y"), _key("a"))
        assert _key("x", "y") not in t
        assert t[_key("x")] == 10
        assert t[_key("a")] == 1
        assert t[_key("a", "child")] == 2


class TestIteration:
    def test_items_of_new_trie_are_only_the_root(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert list(t.items()) == [(_key(), 0)]

    def test_items(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("b")] = 2
        t[_key("a", "c")] = 3
        result = sorted((tuple(k), v) for k, v in t.items())
        assert result == [
            (_key(), 0),
            (_key("a"), 1),
            (_key("a", "c"), 3),
            (_key("b"), 2),
        ]


class TestDirectChildItems:
    def test_empty_key_yields_keys_of_one_name(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert list(t.direct_child_items(_key())) == [(_key("a"), 1)]


class TestPrunedSubtreeItems:
    def test_prefixed_keys_exclude_entire_subtrees_but_not_starting_key(self):
        values: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        values[_key("a")] = 0
        values[_key("a", "b")] = 1
        values[_key("a", "b", "c")] = 2
        values[_key("a", "d")] = 3
        values[_key("a", "d", "e")] = 4
        values[_key("a", "d", "f")] = 5
        values[_key("z")] = 6
        excluded = {_key("p", "q"), _key("p", "q", "b"), _key("p", "q", "d", "e")}
        assert dict(
            values.pruned_subtree_items(
                _key("a"), key_prefix=_key("p", "q"), excluded_keys=excluded
            )
        ) == {_key("p", "q", "d"): 3, _key("p", "q", "d", "f"): 5}

    def test_empty_prefix_and_no_exclusions(self):
        values: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        values[_key("a")] = 0
        values[_key("a", "b")] = 1
        values[_key("a", "b", "c")] = 2
        assert dict(
            values.pruned_subtree_items(
                _key("a"), key_prefix=_key(), excluded_keys=set()
            )
        ) == {_key("b"): 1, _key("b", "c"): 2}

    def test_leaf_and_missing_key_yield_nothing(self):
        values: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        values[_key("a")] = 0
        assert (
            list(
                values.pruned_subtree_items(
                    _key("a"), key_prefix=_key(), excluded_keys=set()
                )
            )
            == []
        )
        assert (
            list(
                values.pruned_subtree_items(
                    _key("missing"), key_prefix=_key(), excluded_keys=set()
                )
            )
            == []
        )

    def test_empty_key_yields_every_key_but_the_root(self):
        values: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        values[_key("a")] = 1
        values[_key("a", "b")] = 2
        assert sorted(
            values.pruned_subtree_items(_key(), key_prefix=_key(), excluded_keys=set())
        ) == [(_key("a"), 1), (_key("a", "b"), 2)]


class TestSubtreeValuesWithParents:
    def test_yields_each_descendant_with_its_parent_after_the_parent(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t[_key("a", "d")] = 4
        t[_key("z")] = 9
        pairs = list(t.subtree_values_with_parents(_key("a")))
        assert sorted(pairs) == [(1, 2), (1, 4), (2, 3)]
        assert pairs.index((1, 2)) < pairs.index((2, 3))

    def test_empty_for_leaf(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        assert list(t.subtree_values_with_parents(_key("a"))) == []


class TestPopSubtree:
    def test_keeps_keys_values_and_children(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t[_key("a", "y")] = 3
        popped = t.pop_subtree(_key("a"))
        assert popped.key == _key("a")
        assert popped.values == {("a",): 1, ("a", "x"): 2, ("a", "y"): 3}
        assert popped.children == {("a",): {("a", "x"), ("a", "y")}}

    def test_removes_from_source(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t[_key("b")] = 3
        _ = t.pop_subtree(_key("a"))
        assert _key("a") not in t
        assert _key("a", "x") not in t
        assert list(t.direct_child_items(_key())) == [(_key("b"), 3)]


class TestRestoreSubtree:
    def test_restores_entries_at_target(self):
        source: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        source[_key("a")] = 1
        source[_key("a", "x")] = 2
        source[_key("a", "x", "deep")] = 3
        source[_key("a", "y")] = 4
        subtree = source.pop_subtree(_key("a"))
        target: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        target[_key("b")] = 99
        target.restore_subtree(_key("b", "restored"), subtree)
        assert target[_key("b", "restored")] == 1
        assert target[_key("b", "restored", "x")] == 2
        assert target[_key("b", "restored", "x", "deep")] == 3
        assert target[_key("b", "restored", "y")] == 4

    def test_restored_child_can_be_moved(self):
        source: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        source[_key("a")] = 1
        source[_key("a", "x")] = 2
        subtree = source.pop_subtree(_key("a"))
        target: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        target[_key("b")] = 99
        target.restore_subtree(_key("b", "restored"), subtree)
        target.move_subtree(_key("b", "restored", "x"), _key("b", "restored", "z"))
        assert _key("b", "restored", "x") not in target
        assert target[_key("b", "restored", "z")] == 2


class TestExistingPrefix:
    def test_full_path_exists(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        assert t.existing_prefix(_key("a", "b", "c")) == _key("a", "b", "c")

    def test_partial_path(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t.existing_prefix(_key("a", "b", "c", "d")) == _key("a", "b")

    def test_no_path(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert t.existing_prefix(_key("a", "b")) == ()

    def test_single_element_exists(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        assert t.existing_prefix(_key("a")) == _key("a")

    def test_single_element_missing(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert t.existing_prefix(_key("a")) == ()

    def test_empty_key_is_its_own_prefix(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        assert t.existing_prefix(_key()) == _key()


class TestFindLongestPrefixWhere:
    def test_no_match(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t.find_longest_prefix_where(_key("a", "b"), lambda v: v > 10) is None

    def test_match_at_leaf(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        t[_key("a", "b")] = 50
        assert t.find_longest_prefix_where(_key("a", "b"), lambda v: v > 10) == _key(
            "a", "b"
        )

    def test_match_at_intermediate(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        t[_key("a", "b")] = 50
        t[_key("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(_key("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
        )

    def test_match_at_root_element(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(
            _key("a", "b", "c"), lambda v: v > 10
        ) == _key("a")

    def test_missing_leaf_is_skipped(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        assert t.find_longest_prefix_where(
            _key("a", "b", "c"), lambda v: v > 10
        ) == _key("a")

    def test_key_not_in_trie(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        assert t.find_longest_prefix_where(_key("x", "y"), lambda v: v > 10) is None

    def test_empty_key_has_no_match(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=lambda: 1)
        assert t.find_longest_prefix_where(_key(), lambda v: v > 0) is None
        assert t.find_longest_prefixes_where((_key(), _key("a")), lambda v: v > 0) == {
            _key(): None,
            _key("a"): None,
        }

    def test_multiple_keys_are_deduplicated(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        t[_key("a", "b")] = 2
        t[_key("x")] = 3
        assert t.find_longest_prefixes_where(
            (_key("a", "b"), _key("x"), _key("a", "b")), lambda value: value > 10
        ) == {
            _key("a", "b"): _key("a"),
            _key("x"): None,
        }

    def test_multiple_branches_reuse_common_prefixes(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 99
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 50
        t[_key("a", "d")] = 3
        assert t.find_longest_prefixes_where(
            (_key("a", "d"), _key("a", "b", "x"), _key("a", "b", "c")),
            lambda value: value > 10,
        ) == {
            _key("a", "b", "c"): _key("a", "b", "c"),
            _key("a", "b", "x"): _key("a"),
            _key("a", "d"): _key("a"),
        }


class TestIndependence:
    def test_parent_and_child_are_independent_values(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t[_key("a")] == 1
        assert t[_key("a", "b")] == 2

    def test_siblings_are_independent(self):
        t: trie.ReparentingTrie[int] = trie.ReparentingTrie(default_factory=int)
        t[_key("a")] = 0
        t[_key("a", "b")] = 1
        t[_key("a", "c")] = 2
        t.delete_subtree(_key("a", "b"))
        assert _key("a", "b") not in t
        assert t[_key("a", "c")] == 2


def _make_trie() -> trie.ReparentingTrie[int]:
    return trie.ReparentingTrie(default_factory=int)


class TestSetitemCreatesParents:
    def test_auto_creates_intermediates(self):
        t = _make_trie()
        t[_key("a", "b", "c")] = 42
        assert t[_key("a", "b", "c")] == 42
        assert t[_key("a")] == 0
        assert t[_key("a", "b")] == 0

    def test_auto_created_intermediate_links_into_child_index(self):
        t = _make_trie()
        t[_key("a", "b", "c")] = 42
        t.delete_subtree(_key("a"))
        assert _key("a", "b", "c") not in t
        assert _key("a", "b") not in t

    def test_does_not_overwrite_existing_intermediate(self):
        t = _make_trie()
        t[_key("a")] = 10
        t[_key("a", "b")] = 42
        assert t[_key("a")] == 10
        assert t[_key("a", "b")] == 42

    def test_overwrite_existing_value(self):
        t = _make_trie()
        t[_key("a", "b")] = 1
        t[_key("a", "b")] = 2
        assert t[_key("a", "b")] == 2


class TestMoveSubtreeCreatesParents:
    def test_move_target_auto_creates_intermediates(self):
        t = _make_trie()
        t[_key("a")] = 1
        t.move_subtree(_key("a"), _key("x", "y"))
        assert t[_key("x")] == 0
        assert t[_key("x", "y")] == 1

    def test_move_target_auto_creates_preserves_existing(self):
        t = _make_trie()
        t[_key("a")] = 1
        t[_key("x")] = 10
        t.move_subtree(_key("a"), _key("x", "y"))
        assert t[_key("x")] == 10
        assert t[_key("x", "y")] == 1


class TestRestoreCreatesParents:
    def test_restore_auto_creates_intermediates(self):
        source = _make_trie()
        source[_key("child")] = 2
        subtree = source.pop_subtree(_key("child"))
        target = _make_trie()
        target.restore_subtree(_key("x", "y"), subtree)
        assert target[_key("x")] == 0
        assert target[_key("x", "y")] == 2
