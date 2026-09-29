# pyright: reportUnusedCallResult=false

from __future__ import annotations

import pytest

from define.compiler import chained_name
from define.compiler.data_structures import trie


def _key(*names: str) -> chained_name.ChainedNameTuple:
    return chained_name.ChainedNameTuple(names)


class TestPointOps:
    def test_setitem_and_contains(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert _key("a") in t

    def test_not_contains_initially(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert _key("a") not in t

    def test_getitem(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 42
        assert t[_key("a", "b")] == 42

    def test_getitem_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            _ = t[_key("a")]

    def test_overwrite_existing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a")] = 2
        assert t[_key("a")] == 2

    def test_get_with_default(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.get(_key("a"), 99) == 99

    def test_get_existing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert t.get(_key("a"), 99) == 1

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t[_key()] = 1

    def test_set_child_without_parent_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t[_key("a", "b")] = 1


class TestDeleteSubtree:
    def test_deletes_item(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t.delete_subtree(_key("a"))
        assert _key("a") not in t

    def test_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t.delete_subtree(_key("a"))

    def test_cascades_to_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        removed_values: list[int] = []
        t.delete_subtree(_key("a"), removed_value_callback=removed_values.append)
        assert _key("a") not in t
        assert _key("a", "b") not in t
        assert _key("a", "b", "c") not in t
        assert set(removed_values) == {1, 2, 3}

    def test_preserves_siblings(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "c")] = 3
        t.delete_subtree(_key("a", "b"))
        assert _key("a") in t
        assert _key("a", "c") in t

    def test_delete_then_reinsert_child(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t.delete_subtree(_key("a", "b"))
        t[_key("a", "b")] = 3
        assert t[_key("a", "b")] == 3


class TestMoveSubtree:
    def test_move_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t.move_subtree(_key("a"), _key("b"))
        assert _key("a") not in t
        assert t[_key("b")] == 1

    def test_move_with_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t[_key("a", "y")] = 3
        moved_values: list[int] = []
        t.move_subtree(
            _key("a"),
            _key("b"),
            moved_value_callback=lambda _key, value: moved_values.append(value),
        )
        assert _key("a") not in t
        assert _key("a", "x") not in t
        assert _key("a", "y") not in t
        assert t[_key("b")] == 1
        assert t[_key("b", "x")] == 2
        assert t[_key("b", "y")] == 3
        assert set(moved_values) == {1, 2, 3}

    def test_move_deeply_nested_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t.move_subtree(_key("a"), _key("z"))
        assert _key("a") not in t
        assert t[_key("z")] == 1
        assert t[_key("z", "b", "c")] == 3

    def test_move_missing_source_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t.move_subtree(_key("a"), _key("b"))

    def test_move_to_existing_target_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("b")] = 2
        with pytest.raises(trie.TargetExistsError):
            t.move_subtree(_key("a"), _key("b"))

    def test_move_to_existing_target_preserves_source(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("b")] = 2
        with pytest.raises(trie.TargetExistsError):
            t.move_subtree(_key("a"), _key("b"))
        assert t[_key("a")] == 1

    def test_move_preserves_sibling(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("c")] = 3
        t.move_subtree(_key("a"), _key("b"))
        assert t[_key("c")] == 3

    def test_move_into_deeper_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "child")] = 2
        t[_key("x")] = 10
        t.move_subtree(_key("a"), _key("x", "y"))
        assert _key("a") not in t
        assert t[_key("x", "y")] == 1
        assert t[_key("x", "y", "child")] == 2

    def test_move_from_deeper_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("x")] = 10
        t[_key("x", "y")] = 1
        t[_key("x", "y", "child")] = 2
        t.move_subtree(_key("x", "y"), _key("a"))
        assert _key("x", "y") not in t
        assert t[_key("x")] == 10
        assert t[_key("a")] == 1
        assert t[_key("a", "child")] == 2

    def test_move_target_parent_must_exist(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        with pytest.raises(KeyError):
            t.move_subtree(_key("a"), _key("x", "y"))


class TestIteration:
    def test_items_empty(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert list(t.items()) == []

    def test_items(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("b")] = 2
        t[_key("a", "c")] = 3
        result = sorted((tuple(k), v) for k, v in t.items())
        assert result == [(_key("a"), 1), (_key("a", "c"), 3), (_key("b"), 2)]


class TestPrunedSubtreeItems:
    def test_prefixed_keys_exclude_entire_subtrees_but_not_starting_key(self):
        values: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
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
        values: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        values[_key("a")] = 0
        values[_key("a", "b")] = 1
        values[_key("a", "b", "c")] = 2
        assert dict(
            values.pruned_subtree_items(
                _key("a"), key_prefix=_key(), excluded_keys=set()
            )
        ) == {_key("b"): 1, _key("b", "c"): 2}

    def test_leaf_and_missing_key_yield_nothing(self):
        values: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
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

    def test_empty_key_raises_when_iterated(self):
        values: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            list(
                values.pruned_subtree_items(
                    _key(), key_prefix=_key(), excluded_keys=set()
                )
            )


class TestSelectedSubtreeItems:
    def test_yields_selected_relative_keys_across_unselected_nodes(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t[_key("a", "d")] = 4
        t[_key("z")] = 6
        assert sorted(
            t.selected_subtree_items(
                _key("a"), lambda value: str(value) if value % 2 == 0 else None
            )
        ) == [
            (_key("b"), "2"),
            (_key("d"), "4"),
        ]

    def test_missing_key_yields_nothing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert (
            list(t.selected_subtree_items(_key("missing"), lambda value: value)) == []
        )

    def test_empty_key_raises_when_iterated(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            list(t.selected_subtree_items(_key(), lambda value: value))


class TestSubtreeKeys:
    def test_returns_full_keys_excluding_root_and_unrelated_branches(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        t[_key("z")] = 9
        assert sorted(t.subtree_keys(_key("a"))) == [
            _key("a", "b"),
            _key("a", "b", "c"),
        ]

    def test_empty_for_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert t.subtree_keys(_key("a")) == []

    def test_missing_key_returns_empty(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert t.subtree_keys(_key("missing")) == []

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.subtree_keys(_key())


class TestPopSubtrees:
    def test_returns_standalone_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t[_key("a", "y")] = 3
        popped = t.pop_subtrees([_key("a")])[_key("a")]
        assert popped[_key("a")] == 1
        assert popped[_key("a", "x")] == 2
        assert popped[_key("a", "y")] == 3

    def test_removes_from_source(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        t.pop_subtrees([_key("a")])
        assert _key("a") not in t
        assert _key("a", "x") not in t

    def test_pops_each_key_and_skips_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("b")] = 2
        result = t.pop_subtrees([_key("a"), _key("b"), _key("missing")])
        assert set(result) == {_key("a"), _key("b")}
        assert result[_key("a")][_key("a")] == 1
        assert result[_key("b")][_key("b")] == 2
        assert _key("a") not in t
        assert _key("b") not in t

    def test_descendant_saved_separately_from_ancestor(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "x")] = 2
        result = t.pop_subtrees([_key("a"), _key("a", "x")])
        assert result[_key("a", "x")][_key("x")] == 2
        assert _key("x") not in result[_key("a")]


class TestRestoreSubtree:
    def test_restores_entries_at_target(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[_key("a")] = 1
        source[_key("a", "x")] = 2
        source[_key("a", "x", "deep")] = 3
        source[_key("a", "y")] = 4
        subtree = source.pop_subtrees([_key("a")])[_key("a")]
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[_key("b")] = 99
        target.restore_subtree(_key("b", "restored"), subtree, 10)
        assert target[_key("b", "restored")] == 10
        assert target[_key("b", "restored", "x")] == 2
        assert target[_key("b", "restored", "x", "deep")] == 3
        assert target[_key("b", "restored", "y")] == 4

    def test_restored_child_can_be_moved(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[_key("a")] = 1
        source[_key("a", "x")] = 2
        subtree = source.pop_subtrees([_key("a")])[_key("a")]
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[_key("b")] = 99
        target.restore_subtree(_key("b", "restored"), subtree, 10)
        target.move_subtree(_key("b", "restored", "x"), _key("b", "restored", "z"))
        assert _key("b", "restored", "x") not in target
        assert target[_key("b", "restored", "z")] == 2

    def test_existing_target_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[_key("a")] = 1
        subtree = source.pop_subtrees([_key("a")])[_key("a")]
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[_key("b")] = 99
        with pytest.raises(trie.TargetExistsError):
            target.restore_subtree(_key("b"), subtree, 10)

    def test_missing_parent_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[_key("a")] = 1
        subtree = source.pop_subtrees([_key("a")])[_key("a")]
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            target.restore_subtree(_key("b", "restored"), subtree, 10)


class TestExistingPrefix:
    def test_full_path_exists(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        assert t.existing_prefix(_key("a", "b", "c")) == _key("a", "b", "c")

    def test_partial_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t.existing_prefix(_key("a", "b", "c", "d")) == _key("a", "b")

    def test_no_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.existing_prefix(_key("a", "b")) == ()

    def test_single_element_exists(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert t.existing_prefix(_key("a")) == _key("a")

    def test_single_element_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.existing_prefix(_key("a")) == ()

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.existing_prefix(_key())


class TestFindShortestPrefixWhere:
    def test_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t.find_shortest_prefix_where(_key("a", "b"), lambda v: v > 10) is None

    def test_match_at_root_element(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        t[_key("a", "b")] = 2
        assert t.find_shortest_prefix_where(_key("a", "b"), lambda v: v > 10) == _key(
            "a"
        )

    def test_match_at_intermediate(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 50
        t[_key("a", "b", "c")] = 3
        assert t.find_shortest_prefix_where(_key("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
        )

    def test_match_at_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 99
        assert t.find_shortest_prefix_where(_key("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
            "c",
        )

    def test_key_not_in_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        assert t.find_shortest_prefix_where(_key("x", "y"), lambda v: v > 10) is None

    def test_partial_path_match_before_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        assert t.find_shortest_prefix_where(_key("a", "b"), lambda v: v > 10) == _key(
            "a"
        )

    def test_partial_path_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        assert t.find_shortest_prefix_where(_key("a", "b"), lambda v: v > 10) is None

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.find_shortest_prefix_where(_key(), lambda v: v > 0)


class TestFindLongestPrefixWhere:
    def test_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t.find_longest_prefix_where(_key("a", "b"), lambda v: v > 10) is None

    def test_match_at_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        t[_key("a", "b")] = 50
        assert t.find_longest_prefix_where(_key("a", "b"), lambda v: v > 10) == _key(
            "a", "b"
        )

    def test_match_at_intermediate(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        t[_key("a", "b")] = 50
        t[_key("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(_key("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
        )

    def test_match_at_root_element(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        t[_key("a", "b")] = 2
        t[_key("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(
            _key("a", "b", "c"), lambda v: v > 10
        ) == _key("a")

    def test_missing_leaf_is_skipped(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        assert t.find_longest_prefix_where(
            _key("a", "b", "c"), lambda v: v > 10
        ) == _key("a")

    def test_key_not_in_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 99
        assert t.find_longest_prefix_where(_key("x", "y"), lambda v: v > 10) is None

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.find_longest_prefix_where(_key(), lambda v: v > 0)

    def test_multiple_keys_are_deduplicated(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
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
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
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
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 1
        t[_key("a", "b")] = 2
        assert t[_key("a")] == 1
        assert t[_key("a", "b")] == 2

    def test_siblings_are_independent(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[_key("a")] = 0
        t[_key("a", "b")] = 1
        t[_key("a", "c")] = 2
        t.delete_subtree(_key("a", "b"))
        assert _key("a", "b") not in t
        assert t[_key("a", "c")] == 2


def _make_lenient() -> trie.LenientReparentingTrie[int]:
    return trie.LenientReparentingTrie(default_factory=int)


class TestLenientSetitem:
    def test_auto_creates_intermediates(self):
        t = _make_lenient()
        t[_key("a", "b", "c")] = 42
        assert t[_key("a", "b", "c")] == 42
        assert t[_key("a")] == 0
        assert t[_key("a", "b")] == 0

    def test_auto_created_intermediate_links_into_child_index(self):
        t = _make_lenient()
        t[_key("a", "b", "c")] = 42
        t.delete_subtree(_key("a"))
        assert _key("a", "b", "c") not in t
        assert _key("a", "b") not in t

    def test_does_not_overwrite_existing_intermediate(self):
        t = _make_lenient()
        t[_key("a")] = 10
        t[_key("a", "b")] = 42
        assert t[_key("a")] == 10
        assert t[_key("a", "b")] == 42

    def test_overwrite_existing_value(self):
        t = _make_lenient()
        t[_key("a", "b")] = 1
        t[_key("a", "b")] = 2
        assert t[_key("a", "b")] == 2


class TestLenientDelete:
    def test_delete_does_not_auto_create(self):
        t = _make_lenient()
        with pytest.raises(KeyError):
            t.delete_subtree(_key("a", "b"))


class TestLenientMoveSubtree:
    def test_move_source_does_not_auto_create(self):
        t = _make_lenient()
        t[_key("b")] = 1
        with pytest.raises(KeyError):
            t.move_subtree(_key("a"), _key("b", "c"))

    def test_move_target_auto_creates_intermediates(self):
        t = _make_lenient()
        t[_key("a")] = 1
        t.move_subtree(_key("a"), _key("x", "y"))
        assert t[_key("x")] == 0
        assert t[_key("x", "y")] == 1

    def test_move_target_auto_creates_preserves_existing(self):
        t = _make_lenient()
        t[_key("a")] = 1
        t[_key("x")] = 10
        t.move_subtree(_key("a"), _key("x", "y"))
        assert t[_key("x")] == 10
        assert t[_key("x", "y")] == 1


class TestLenientPopAndRestore:
    def test_restore_auto_creates_intermediates(self):
        source = _make_lenient()
        source[_key("child")] = 2
        subtree = source.pop_subtrees([_key("child")])[_key("child")]
        target = _make_lenient()
        target.restore_subtree(_key("x", "y"), subtree, 99)
        assert target[_key("x")] == 0
        assert target[_key("x", "y")] == 99
