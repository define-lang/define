from __future__ import annotations

from define.compiler import chained_name

_FQUN = "my.domain.com:my_lib"


def test_chain_to_last_action_ends_at_last_action():
    chain = ("position<p>", "action<a>", "position<q>", "action<b>", "position<r>")
    assert chained_name.chain_to_last_action(chain) == (
        "position<p>",
        "action<a>",
        "position<q>",
        "action<b>",
    )


def test_chain_to_last_action_without_action_is_none():
    assert chained_name.chain_to_last_action(("position<p>", "position<q>")) is None


def test_parent_position_skips_actions():
    chain = ("position<p>", "action<a>", "position<q>")
    assert chained_name.parent_position(chain) == ("position<p>",)


def test_parent_position_of_action_chain_is_its_parent_position():
    chain = ("position<p>", "position<q>", "action<a>")
    assert chained_name.parent_position(chain) == ("position<p>", "position<q>")


def test_parent_position_of_single_name_is_none():
    assert chained_name.parent_position(("position<p>",)) is None


def test_parent_position_with_only_actions_before_is_none():
    assert chained_name.parent_position(("action<a>", "position<q>")) is None


def test_parent_position_of_two_positions():
    chain = ("position<local>", f"position<{_FQUN}:/x>")
    assert chained_name.parent_position(chain) == ("position<local>",)
