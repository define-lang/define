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

    def test_keys(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        result = sorted(tuple(k) for k, _ in t.items())
        assert result == [("a",), ("a", "b")]


class TestPopAndGraft:
    def test_pop_subtree_returns_standalone_trie(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t[("a", "y")] = 3
        popped = t.pop_subtree(("a",))
        assert popped[("a",)] == 1
        assert popped[("a", "x")] == 2
        assert popped[("a", "y")] == 3

    def test_pop_subtree_removes_from_source(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "x")] = 2
        t.pop_subtree(("a",))
        assert ("a",) not in t
        assert ("a", "x") not in t

    def test_pop_subtree_missing_raises(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            t.pop_subtree(("a",))

    def test_graft_subtree_inserts_children(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        source[("a", "x")] = 2
        popped = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("b",)] = 99
        target.graft_subtree(("b",), popped)
        assert target[("b",)] == 99
        assert target[("b", "a")] == 1
        assert target[("b", "a", "x")] == 2

    def test_graft_subtree_missing_parent_raises(self):
        source: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        source[("a",)] = 1
        popped = source.pop_subtree(("a",))
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        with pytest.raises(KeyError):
            target.graft_subtree(("b",), popped)

    def test_graft_subtree_multiple_roots(self):
        subtree: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        subtree[("a",)] = 1
        subtree[("a", "x")] = 2
        subtree[("b",)] = 3
        subtree[("b", "y")] = 4
        target: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        target[("root",)] = 0
        target.graft_subtree(("root",), subtree)
        assert target[("root",)] == 0
        assert target[("root", "a")] == 1
        assert target[("root", "a", "x")] == 2
        assert target[("root", "b")] == 3
        assert target[("root", "b", "y")] == 4

    def test_pop_and_graft_roundtrip(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "b")] = 2
        t[("a", "b", "c")] = 3
        popped = t.pop_subtree(("a",))
        t[("z",)] = 0
        t.graft_subtree(("z",), popped)
        assert ("a",) not in t
        assert t[("z",)] == 0
        assert t[("z", "a")] == 1
        assert t[("z", "a", "b")] == 2
        assert t[("z", "a", "b", "c")] == 3

    def test_pop_and_graft_swap(self):
        t: trie.StrictReparentingTrie[int] = trie.StrictReparentingTrie()
        t[("a",)] = 1
        t[("a", "child_a")] = 10
        t[("b",)] = 2
        t[("b", "child_b")] = 20
        popped_a = t.pop_subtree(("a",))
        popped_b = t.pop_subtree(("b",))
        t[("a",)] = 0
        t[("b",)] = 0
        t.graft_subtree(("a",), popped_b)
        t.graft_subtree(("b",), popped_a)
        assert t[("a", "b")] == 2
        assert t[("a", "b", "child_b")] == 20
        assert t[("b", "a")] == 1
        assert t[("b", "a", "child_a")] == 10


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
        source[("a",)] = 1
        source[("a", "child")] = 2
        popped = source.pop_subtree(("a",))
        target = _make_lenient()
        target[("x", "y")] = 99
        target.graft_subtree(("x", "y"), popped)
        assert target[("x",)] == 0
        assert target[("x", "y")] == 99
        assert target[("x", "y", "a")] == 1
        assert target[("x", "y", "a", "child")] == 2
