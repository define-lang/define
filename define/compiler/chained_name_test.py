from __future__ import annotations

from define.compiler import chained_name


def _chain(*names: str) -> chained_name.ChainedNameTuple:
    return chained_name.ChainedNameTuple(names)


_FQUN = "my.domain.com:my_lib"


def test_chain_to_last_action_ends_at_last_action():
    chain = _chain(
        "position<p>", "action<a>", "position<q>", "action<b>", "position<r>"
    )
    assert chained_name.chain_to_last_action(chain) == (
        "position<p>",
        "action<a>",
        "position<q>",
        "action<b>",
    )


def test_chain_to_last_action_without_action_is_none():
    assert (
        chained_name.chain_to_last_action(_chain("position<p>", "position<q>")) is None
    )


def test_parent_position_skips_actions():
    chain = _chain("position<p>", "action<a>", "position<q>")
    assert chained_name.parent_position(chain) == _chain("position<p>")


def test_parent_position_of_action_chain_is_its_parent_position():
    chain = _chain("position<p>", "position<q>", "action<a>")
    assert chained_name.parent_position(chain) == _chain("position<p>", "position<q>")


def test_parent_position_of_single_name_is_none():
    assert chained_name.parent_position(_chain("position<p>")) is None


def test_parent_position_with_only_actions_before_is_none():
    assert chained_name.parent_position(_chain("action<a>", "position<q>")) is None


def test_parent_position_of_two_positions():
    chain = _chain("position<local>", f"position<{_FQUN}:/x>")
    assert chained_name.parent_position(chain) == _chain("position<local>")


def test_with_prefix_places_chain_below_prefix():
    assert chained_name.with_prefix(
        _chain("position<c>"), _chain("position<a>", "position<b>")
    ) == (
        "position<a>",
        "position<b>",
        "position<c>",
    )


def test_without_prefix_returns_names_after_prefix():
    chain = _chain("position<a>", "position<b>", "position<c>")
    assert chained_name.without_prefix(chain, _chain("position<a>")) == (
        "position<b>",
        "position<c>",
    )


def test_without_whole_chain_is_empty():
    chain = _chain("position<a>", "position<b>")
    assert chained_name.without_prefix(chain, chain) == ()


def test_replace_prefix_moves_chain_to_new_prefix():
    chain = _chain("position<a>", "position<b>", "position<c>")
    assert chained_name.replace_prefix(
        chain, _chain("position<a>", "position<b>"), _chain("position<x>")
    ) == _chain("position<x>", "position<c>")


def test_prefixes_are_nonempty_and_shortest_first():
    chain = _chain("position<a>", "action<b>", "position<c>")
    assert list(chained_name.prefixes(chain)) == [
        _chain("position<a>"),
        _chain("position<a>", "action<b>"),
        _chain("position<a>", "action<b>", "position<c>"),
    ]


def test_names_after_skips_leading_names():
    chain = _chain("position<a>", "position<b>", "position<c>")
    assert chained_name.names_after(chain, 2) == ("position<c>",)


def test_with_suffix_appends_child_names():
    assert chained_name.with_suffix(
        _chain("position<a>"), "action<b>", "position<c>"
    ) == ("position<a>", "action<b>", "position<c>")


def test_parent_drops_last_name_even_when_it_leaves_an_action():
    chain = _chain("position<a>", "action<b>", "position<c>")
    assert chained_name.parent(chain) == ("position<a>", "action<b>")


def test_last_name_is_a_one_name_chain():
    chain = _chain("position<a>", "position<b>")
    assert chained_name.last_name(chain) == ("position<b>",)
