# pyright: reportUnusedCallResult=false

import pytest

from define.compiler.data_structures import trie


class TestPointOps:
    def test_setitem_and_contains(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert ("a",) in t

    def test_not_contains_initially(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert ("a",) not in t

    def test_getitem(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 42
        assert t[("a", "b")] == 42

    def test_getitem_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            _ = t[("a",)]

    def test_overwrite_existing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a",)] = 2
        assert t[("a",)] == 2

    def test_get_with_default(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.get(("a",), 99) == 99

    def test_get_existing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.get(("a",), 99) == 1

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t[()] = 1

    def test_set_child_without_parent_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t[("a", "b")] = 1


class TestDelete:
    def test_delitem(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        del t[("a",)]
        assert ("a",) not in t

    def test_delitem_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            del t[("a",)]

    def test_delitem_cascades_to_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        del t[("a",)]
        assert ("a",) not in t
        assert ("a", "b") not in t
        assert ("a", "b", "c") not in t

    def test_delitem_preserves_siblings(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "c")] = 3
        del t[("a", "b")]
        assert ("a",) in t
        assert ("a", "c") in t

    def test_delitem_then_reinsert_child(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        del t[("a", "b")]
        t[("a", "b")] = 3
        assert t[("a", "b")] == 3


class TestMoveSubtree:
    def test_move_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t.move_subtree(("a",), ("b",))
        assert ("a",) not in t
        assert t[("b",)] == 1

    def test_move_with_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t[("a", "y")] = 3
        t.move_subtree(("a",), ("b",))
        assert ("a",) not in t
        assert ("a", "x") not in t
        assert ("a", "y") not in t
        assert t[("b",)] == 1
        assert t[("b", "x")] == 2
        assert t[("b", "y")] == 3

    def test_move_deeply_nested_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        t.move_subtree(("a",), ("z",))
        assert ("a",) not in t
        assert t[("z",)] == 1
        assert t[("z", "b", "c")] == 3

    def test_move_missing_source_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t.move_subtree(("a",), ("b",))

    def test_move_to_existing_target_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("b",)] = 2
        with pytest.raises(trie.TargetExistsError):
            t.move_subtree(("a",), ("b",))

    def test_move_to_existing_target_preserves_source(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("b",)] = 2
        with pytest.raises(trie.TargetExistsError):
            t.move_subtree(("a",), ("b",))
        assert t[("a",)] == 1

    def test_move_preserves_sibling(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("c",)] = 3
        t.move_subtree(("a",), ("b",))
        assert t[("c",)] == 3

    def test_move_into_deeper_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "child")] = 2
        t[("x",)] = 10
        t.move_subtree(("a",), ("x", "y"))
        assert ("a",) not in t
        assert t[("x", "y")] == 1
        assert t[("x", "y", "child")] == 2

    def test_move_from_deeper_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("x",)] = 10
        t[("x", "y")] = 1
        t[("x", "y", "child")] = 2
        t.move_subtree(("x", "y"), ("a",))
        assert ("x", "y") not in t
        assert t[("x",)] == 10
        assert t[("a",)] == 1
        assert t[("a", "child")] == 2

    def test_move_target_parent_must_exist(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        with pytest.raises(KeyError):
            t.move_subtree(("a",), ("x", "y"))


class TestIteration:
    def test_items_empty(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert list(t.items()) == []

    def test_items(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("b",)] = 2
        t[("a", "c")] = 3
        result = sorted((tuple(k), v) for k, v in t.items())
        assert result == [(("a",), 1), (("a", "c"), 3), (("b",), 2)]


class TestSubtreeItems:
    def test_returns_relative_keys_excluding_root_and_unrelated_branches(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        t[("z",)] = 9
        assert sorted(t.subtree_items(("a",))) == [
            (("b",), 2),
            (("b", "c"), 3),
        ]

    def test_empty_for_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.subtree_items(("a",)) == []

    def test_missing_key_returns_empty(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.subtree_items(("missing",)) == []

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.subtree_items(())


class TestSelectedSubtreeItems:
    def test_yields_selected_relative_keys_across_unselected_nodes(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        t[("a", "d")] = 4
        t[("z",)] = 6
        assert sorted(
            t.selected_subtree_items(
                ("a",), lambda value: str(value) if value % 2 == 0 else None
            )
        ) == [
            (("b",), "2"),
            (("d",), "4"),
        ]

    def test_missing_key_yields_nothing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert list(t.selected_subtree_items(("missing",), lambda value: value)) == []

    def test_empty_key_raises_when_iterated(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            list(t.selected_subtree_items((), lambda value: value))


class TestSubtreeKeys:
    def test_returns_full_keys_excluding_root_and_unrelated_branches(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        t[("z",)] = 9
        assert sorted(t.subtree_keys(("a",))) == [("a", "b"), ("a", "b", "c")]

    def test_empty_for_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.subtree_keys(("a",)) == []

    def test_missing_key_returns_empty(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.subtree_keys(("missing",)) == []

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.subtree_keys(())


class TestPopSubtree:
    def test_returns_standalone_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t[("a", "y")] = 3
        popped = t.pop_subtree(("a",))
        assert popped[("a",)] == 1
        assert popped[("a", "x")] == 2
        assert popped[("a", "y")] == 3

    def test_removes_from_source(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t.pop_subtree(("a",))
        assert ("a",) not in t
        assert ("a", "x") not in t

    def test_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t.pop_subtree(("a",))


class TestPopSubtrees:
    def test_pops_each_key_and_skips_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("b",)] = 2
        result = t.pop_subtrees([("a",), ("b",), ("missing",)])
        assert set(result) == {("a",), ("b",)}
        assert result[("a",)][("a",)] == 1
        assert result[("b",)][("b",)] == 2
        assert ("a",) not in t
        assert ("b",) not in t

    def test_descendant_saved_separately_from_ancestor(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        result = t.pop_subtrees([("a",), ("a", "x")])
        assert result[("a", "x")][("x",)] == 2
        assert ("x",) not in result[("a",)]


class TestRestoreSubtree:
    def test_restores_entries_at_target(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        source[("a", "x")] = 2
        source[("a", "x", "deep")] = 3
        source[("a", "y")] = 4
        subtree = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target.restore_subtree(("b", "restored"), subtree, 10)
        assert target[("b", "restored")] == 10
        assert target[("b", "restored", "x")] == 2
        assert target[("b", "restored", "x", "deep")] == 3
        assert target[("b", "restored", "y")] == 4

    def test_restored_child_can_be_moved(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        source[("a", "x")] = 2
        subtree = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target.restore_subtree(("b", "restored"), subtree, 10)
        target.move_subtree(("b", "restored", "x"), ("b", "restored", "z"))
        assert ("b", "restored", "x") not in target
        assert target[("b", "restored", "z")] == 2

    def test_existing_target_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        subtree = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        with pytest.raises(trie.TargetExistsError):
            target.restore_subtree(("b",), subtree, 10)

    def test_missing_parent_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        subtree = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            target.restore_subtree(("b", "restored"), subtree, 10)


class TestExistingPrefix:
    def test_full_path_exists(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        assert t.existing_prefix(("a", "b", "c")) == ("a", "b", "c")

    def test_partial_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        assert t.existing_prefix(("a", "b", "c", "d")) == ("a", "b")

    def test_no_path(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.existing_prefix(("a", "b")) == ()

    def test_single_element_exists(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.existing_prefix(("a",)) == ("a",)

    def test_single_element_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        assert t.existing_prefix(("a",)) == ()

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.existing_prefix(())


class TestFindShortestPrefixWhere:
    def test_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        assert t.find_shortest_prefix_where(("a", "b"), lambda v: v > 10) is None

    def test_match_at_root_element(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 2
        assert t.find_shortest_prefix_where(("a", "b"), lambda v: v > 10) == ("a",)

    def test_match_at_intermediate(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 50
        t[("a", "b", "c")] = 3
        assert t.find_shortest_prefix_where(("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
        )

    def test_match_at_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 99
        assert t.find_shortest_prefix_where(("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
            "c",
        )

    def test_key_not_in_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        assert t.find_shortest_prefix_where(("x", "y"), lambda v: v > 10) is None

    def test_partial_path_match_before_missing(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        assert t.find_shortest_prefix_where(("a", "b"), lambda v: v > 10) == ("a",)

    def test_partial_path_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        assert t.find_shortest_prefix_where(("a", "b"), lambda v: v > 10) is None

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.find_shortest_prefix_where((), lambda v: v > 0)


class TestFindLongestPrefixWhere:
    def test_no_match(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        assert t.find_longest_prefix_where(("a", "b"), lambda v: v > 10) is None

    def test_match_at_leaf(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 50
        assert t.find_longest_prefix_where(("a", "b"), lambda v: v > 10) == ("a", "b")

    def test_match_at_intermediate(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 50
        t[("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(("a", "b", "c"), lambda v: v > 10) == (
            "a",
            "b",
        )

    def test_match_at_root_element(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        assert t.find_longest_prefix_where(("a", "b", "c"), lambda v: v > 10) == ("a",)

    def test_missing_leaf_is_skipped(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        assert t.find_longest_prefix_where(("a", "b", "c"), lambda v: v > 10) == ("a",)

    def test_key_not_in_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        assert t.find_longest_prefix_where(("x", "y"), lambda v: v > 10) is None

    def test_empty_key_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(trie.EmptyKeyError):
            t.find_longest_prefix_where((), lambda v: v > 0)

    def test_multiple_keys_are_deduplicated(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 2
        t[("x",)] = 3
        assert t.find_longest_prefixes_where(
            (("a", "b"), ("x",), ("a", "b")), lambda value: value > 10
        ) == {
            ("a", "b"): ("a",),
            ("x",): None,
        }

    def test_multiple_branches_reuse_common_prefixes(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 99
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 50
        t[("a", "d")] = 3
        assert t.find_longest_prefixes_where(
            (("a", "d"), ("a", "b", "x"), ("a", "b", "c")),
            lambda value: value > 10,
        ) == {
            ("a", "b", "c"): ("a", "b", "c"),
            ("a", "b", "x"): ("a",),
            ("a", "d"): ("a",),
        }


class TestIndependence:
    def test_parent_and_child_are_independent_values(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        assert t[("a",)] == 1
        assert t[("a", "b")] == 2

    def test_siblings_are_independent(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 0
        t[("a", "b")] = 1
        t[("a", "c")] = 2
        del t[("a", "b")]
        assert ("a", "b") not in t
        assert t[("a", "c")] == 2


def _make_lenient() -> trie.LenientReparentingTrie[int]:
    return trie.LenientReparentingTrie(default_factory=int)


class TestLenientSetitem:
    def test_auto_creates_intermediates(self):
        t = _make_lenient()
        t[("a", "b", "c")] = 42
        assert t[("a", "b", "c")] == 42
        assert t[("a",)] == 0
        assert t[("a", "b")] == 0

    def test_auto_created_intermediate_links_into_child_index(self):
        t = _make_lenient()
        t[("a", "b", "c")] = 42
        del t[("a",)]
        assert ("a", "b", "c") not in t
        assert ("a", "b") not in t

    def test_does_not_overwrite_existing_intermediate(self):
        t = _make_lenient()
        t[("a",)] = 10
        t[("a", "b")] = 42
        assert t[("a",)] == 10
        assert t[("a", "b")] == 42

    def test_overwrite_existing_value(self):
        t = _make_lenient()
        t[("a", "b")] = 1
        t[("a", "b")] = 2
        assert t[("a", "b")] == 2


class TestLenientDelete:
    def test_delete_does_not_auto_create(self):
        t = _make_lenient()
        with pytest.raises(KeyError):
            del t[("a", "b")]


class TestLenientMoveSubtree:
    def test_move_source_does_not_auto_create(self):
        t = _make_lenient()
        t[("b",)] = 1
        with pytest.raises(KeyError):
            t.move_subtree(("a",), ("b", "c"))

    def test_move_target_auto_creates_intermediates(self):
        t = _make_lenient()
        t[("a",)] = 1
        t.move_subtree(("a",), ("x", "y"))
        assert t[("x",)] == 0
        assert t[("x", "y")] == 1

    def test_move_target_auto_creates_preserves_existing(self):
        t = _make_lenient()
        t[("a",)] = 1
        t[("x",)] = 10
        t.move_subtree(("a",), ("x", "y"))
        assert t[("x",)] == 10
        assert t[("x", "y")] == 1


class TestLenientPopAndRestore:
    def test_restore_auto_creates_intermediates(self):
        source = _make_lenient()
        source[("child",)] = 2
        subtree = source.pop_subtree(("child",))
        target = _make_lenient()
        target.restore_subtree(("x", "y"), subtree, 99)
        assert target[("x",)] == 0
        assert target[("x", "y")] == 99
