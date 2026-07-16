from define.compiler.data_structures import persistent_trie

type Key = tuple[str, ...]


def _items[V](
    values: persistent_trie.PersistentTrie[V],
) -> set[tuple[Key, V]]:
    return set(values.maximal_items())


def test_empty_trie_has_no_maximal_items():
    assert tuple(persistent_trie.PersistentTrie[int]().maximal_items()) == ()


def test_independent_keys_are_all_maximal():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a",), 1)
        .replace_subtree(("b",), 2)
        .replace_subtree(("c",), 3)
    )

    assert _items(values) == {
        (("a",), 1),
        (("b",), 2),
        (("c",), 3),
    }


def test_descendant_suppresses_valued_ancestors():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a",), 1)
        .replace_subtree(("a", "b"), 2)
        .replace_subtree(("a", "b", "c"), 3)
    )

    assert _items(values) == {(("a", "b", "c"), 3)}


def test_independent_descendants_are_all_maximal():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a",), 1)
        .replace_subtree(("a", "left"), 2)
        .replace_subtree(("a", "right"), 3)
        .replace_subtree(("a", "left", "deep"), 4)
    )

    assert _items(values) == {
        (("a", "left", "deep"), 4),
        (("a", "right"), 3),
    }


def test_replacing_subtree_removes_all_descendant_values():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a", "left"), 1)
        .replace_subtree(("a", "right", "deep"), 2)
        .replace_subtree(("outside",), 3)
        .replace_subtree(("a",), 4)
    )

    assert _items(values) == {
        (("a",), 4),
        (("outside",), 3),
    }


def test_replacing_one_subtree_preserves_siblings_and_ancestors():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a",), 1)
        .replace_subtree(("a", "left", "deep"), 2)
        .replace_subtree(("a", "right"), 3)
        .replace_subtree(("a", "left"), 4)
    )

    assert _items(values) == {
        (("a", "left"), 4),
        (("a", "right"), 3),
    }


def test_replacing_same_key_changes_value_and_removes_descendants():
    values = (
        persistent_trie.PersistentTrie[int]()
        .replace_subtree(("a",), 1)
        .replace_subtree(("a", "child"), 2)
        .replace_subtree(("a",), 3)
    )

    assert _items(values) == {(("a",), 3)}


def test_none_is_a_value():
    values = persistent_trie.PersistentTrie[None]().replace_subtree(("a",), None)

    assert _items(values) == {(("a",), None)}


def test_retained_versions_do_not_change_after_later_updates():
    first = persistent_trie.PersistentTrie[int]().replace_subtree(("a",), 1)
    second = first.replace_subtree(("a", "child"), 2)
    third = second.replace_subtree(("b",), 3)
    fourth = third.replace_subtree(("a",), 4)

    assert _items(first) == {(("a",), 1)}
    assert _items(second) == {(("a", "child"), 2)}
    assert _items(third) == {
        (("a", "child"), 2),
        (("b",), 3),
    }
    assert _items(fourth) == {
        (("a",), 4),
        (("b",), 3),
    }


def test_updates_from_same_version_are_independent():
    original = persistent_trie.PersistentTrie[int]().replace_subtree(("a",), 1)
    with_left = original.replace_subtree(("left",), 2)
    with_right = original.replace_subtree(("right",), 3)

    assert _items(original) == {(("a",), 1)}
    assert _items(with_left) == {
        (("a",), 1),
        (("left",), 2),
    }
    assert _items(with_right) == {
        (("a",), 1),
        (("right",), 3),
    }


def test_maximal_items_are_complete_after_varied_insertion_orders():
    for names in (
        ("m", "a", "z", "b", "y", "c", "x"),
        ("c", "a", "b"),
        ("a", "c", "b"),
    ):
        keys = tuple((name,) for name in names)
        values = persistent_trie.PersistentTrie[str]()
        for key in keys:
            values = values.replace_subtree(key, key[0])

        assert _items(values) == {(key, key[0]) for key in keys}


def test_deep_keys_do_not_depend_on_python_recursion():
    depth = 2_000
    key = tuple(f"name{index}" for index in range(depth))
    values = persistent_trie.PersistentTrie[int]().replace_subtree(key, 1)

    assert _items(values) == {(key, 1)}


def test_wide_subtree_remains_complete_after_one_key_is_replaced():
    width = 2_000
    values = persistent_trie.PersistentTrie[int]()
    for index in range(width):
        values = values.replace_subtree(("a", f"child{index}"), index)
    values = values.replace_subtree(("a", "child1000"), width)

    expected = {
        (("a", f"child{index}"), width if index == 1_000 else index)
        for index in range(width)
    }
    assert _items(values) == expected
