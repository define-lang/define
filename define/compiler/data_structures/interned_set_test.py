from __future__ import annotations

import typing

from hypothesis import given
from hypothesis import strategies as st

from define.compiler.data_structures import interned_set

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

# These tests cover only what the compiler relies on: membership, size and
# iteration, and that equal sets are the same object, which keeps unions
# cheap. They do not pin anything else about how sets are built.

_NAMES = st.sets(st.text(alphabet="abcdef", max_size=4), max_size=40)


# The hash each test name has, to place it in the tree.
_CHOSEN_HASHES = {
    "a": 0b0000,
    "b": 0b0100,
    "c": 0b0010,
    "d": 0b0110,
    "e": 0b0001,
    "f": 0b0101,
    "g": -0b1101,
    "h": -0b1001,
    "same_a": 7,
    "same_b": 7,
    "same_c": 7,
    "other": 5,
}


@typing.final
class _Name(str):  # noqa: FURB189 - The sets take str, and only the hash differs.
    __slots__ = ()

    @typing.override
    def __hash__(self) -> int:
        return _CHOSEN_HASHES[str.__str__(self)]


def _set_of(
    sets: interned_set.InternedSets, names: Iterable[str]
) -> interned_set.InternedSet:
    result = interned_set.EMPTY
    for name in names:
        result = sets.with_name(result, name)
    return result


@given(_NAMES, _NAMES)
def test_operations_match_built_in_sets(first: set[str], second: set[str]):
    sets = interned_set.InternedSets()
    union = sets.union(_set_of(sets, first), _set_of(sets, second))
    assert sorted(union) == sorted(first | second)
    assert len(union) == len(first | second)
    for name in first | second | {"absent"}:
        assert (name in union) == (name in first | second)


@given(_NAMES, _NAMES)
def test_equal_sets_are_the_same_object(first: set[str], second: set[str]):
    sets = interned_set.InternedSets()
    union = sets.union(_set_of(sets, first), _set_of(sets, second))
    assert union is _set_of(sets, sorted(first | second, reverse=True))


def test_unions_of_branches_at_every_relative_position():
    a, b, c, d, e, f, g, h = (_Name(name) for name in "abcdefgh")
    sets = interned_set.InternedSets()
    first_low = _set_of(sets, [a, b])
    second_low = _set_of(sets, [c, d])
    first_high = _set_of(sets, [e, f])
    second_high = _set_of(sets, [g, h])
    everything = _set_of(sets, [a, b, c, d, e, f, g, h])
    lows = sets.union(first_low, second_low)
    highs = sets.union(first_high, second_high)
    assert sets.union(lows, highs) is everything
    assert sets.union(sets.union(first_high, first_low), second_low) is sets.union(
        lows, first_high
    )
    assert sets.union(sets.union(first_low, first_high), second_high) is sets.union(
        first_low, highs
    )
    assert sets.union(lows, _set_of(sets, [a, c])) is lows
    low_and_high = sets.union(first_low, first_high)
    assert sets.union(low_and_high, first_low) is low_and_high
    assert sets.union(low_and_high, first_high) is low_and_high
    assert sorted(everything) == ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert e not in lows
    assert c not in first_low


def test_names_whose_hashes_are_identical():
    a, b, c, d = (_Name(name) for name in ["same_a", "same_b", "same_c", "other"])
    sets = interned_set.InternedSets()
    pair = _set_of(sets, [b, a])
    assert sorted(pair) == ["same_a", "same_b"]
    assert len(pair) == 2
    assert c not in pair
    assert d not in pair
    triple = sets.with_name(pair, c)
    assert sets.with_name(triple, a) is triple
    assert sets.union(pair, _set_of(sets, [c, b])) is triple
    assert sorted(sets.with_name(triple, d)) == ["other", "same_a", "same_b", "same_c"]
