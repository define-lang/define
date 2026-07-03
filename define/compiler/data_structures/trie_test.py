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


class TestRootChildren:
    def test_returns_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t[("a", "x", "deep")] = 3
        t[("a", "y")] = 4
        children = t.root_children()
        assert children[("x",)] == 2
        assert children[("x", "deep")] == 3
        assert children[("y",)] == 4

    def test_no_children(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        children = t.root_children()
        assert list(children.items()) == []

    def test_multiple_roots(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t[("b",)] = 3
        t[("b", "y")] = 4
        children = t.root_children()
        assert children[("x",)] == 2
        assert children[("y",)] == 4


class TestGraftSubtree:
    def test_attaches_entries(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("x",)] = 2
        source[("x", "deep")] = 3
        source[("y",)] = 4
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target.graft_subtree(("b",), source)
        assert target[("b",)] == 99
        assert target[("b", "x")] == 2
        assert target[("b", "x", "deep")] == 3
        assert target[("b", "y")] == 4

    def test_grafted_child_can_be_moved(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("x",)] = 2
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target.graft_subtree(("b",), source)
        target.move_subtree(("b", "x"), ("b", "z"))
        assert ("b", "x") not in target
        assert target[("b", "z")] == 2

    def test_existing_child_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("x",)] = 2
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target[("b", "x")] = 50
        with pytest.raises(trie.TargetExistsError):
            target.graft_subtree(("b",), source)

    def test_missing_key_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("x",)] = 1
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            target.graft_subtree(("b",), source)


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


class TestLenientPopAndGraft:
    def test_graft_auto_creates_intermediates(self):
        source = _make_lenient()
        source[("child",)] = 2
        target = _make_lenient()
        target[("x", "y")] = 99
        target.graft_subtree(("x", "y"), source)
        assert target[("x",)] == 0
        assert target[("x", "y")] == 99
        assert target[("x", "y", "child")] == 2
