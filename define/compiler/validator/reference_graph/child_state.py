"""Separate shared stores for destruction-time occupancy and value state."""

from __future__ import annotations

import abc
import typing

import msgspec

if typing.TYPE_CHECKING:
    from define.compiler.validator.reference_graph import (
        particle_info,
        position_occupancy,
    )

# In our initial experiments, we saw that memory starts to grow quite a bit
# with _very_ large child states (more than 255 tracked positions, over thousands
# of actions). The solution to this was a partitioned representation that maintains
# more constant memory at large sizes. However, those large sizes should be extremely
# rare, so the partitioning implementation seemed like unnecessary complexity.
# If we need it, a full description of it is in the research repo, in
# destruction_contract_benchmarks/TUNING.md.

# Comparing limits of 8, 16, 32, and 256 on three Define programs with initially
# 8, 16, and 32 tracked child positions found similar reference-graph CPU times:
# about 10, 17, and 31 ms, respectively (three timed runs per setting). In the
# 32-position program, lowering the limit from 256 to 16 reduced retained snapshot
# dictionary and state-object storage from 5.79 to 3.96 KiB. We choose 16 to retain
# single-dictionary lookups for the smallest states while sharing larger states;
# these small benchmarks do not establish a unique optimum between 8 and 16.
_FLAT_LIMIT = 16


class ChildStateStore[State](abc.ABC):
    """Known state that remains unchanged when shared with another caller."""

    __slots__: tuple[str, ...] = ()

    @abc.abstractmethod
    def get(self, position: tuple[str, ...]) -> State | None:
        """Return known state, or None when the position's state is unknown."""
        raise NotImplementedError

    @abc.abstractmethod
    def with_caller(
        self,
        caller: dict[tuple[str, ...], State],
    ) -> ChildStateStore[State]:
        """Take ownership of caller knowledge for previously unknown positions.

        The caller must not mutate the supplied dictionary afterward.
        """
        raise NotImplementedError


@typing.final
class FlatChildStateStore[State](ChildStateStore[State]):
    """A small or newly captured destruction-time snapshot."""

    __slots__: tuple[str, ...] = ("_values",)

    def __init__(self, values: dict[tuple[str, ...], State]):
        """Take ownership of values that will no longer be mutated."""
        self._values = values

    @typing.override
    def get(self, position: tuple[str, ...]) -> State | None:
        return self._values.get(position)

    @typing.override
    def with_caller(
        self,
        caller: dict[tuple[str, ...], State],
    ) -> ChildStateStore[State]:
        if not caller:
            return self
        if len(self._values) < _FLAT_LIMIT:
            caller.update(self._values)
            return FlatChildStateStore(caller)
        return _extended_state(self._values, caller)


@typing.final
class ExtendedChildStateStore[State](ChildStateStore[State]):
    """Destruction-time state sharing original knowledge across callers."""

    __slots__: tuple[str, ...] = ("_additions", "_base")

    def __init__(
        self,
        base: dict[tuple[str, ...], State],
        additions: dict[tuple[str, ...], State],
    ):
        """Take ownership of dictionaries that will no longer be mutated."""
        self._base = base
        self._additions = additions

    @typing.override
    def get(self, position: tuple[str, ...]) -> State | None:
        state = self._base.get(position)
        if state is not None:
            return state
        return self._additions.get(position)

    @typing.override
    def with_caller(
        self,
        caller: dict[tuple[str, ...], State],
    ) -> ChildStateStore[State]:
        if not caller:
            return self
        caller.update(self._additions)
        return _extended_state(self._base, caller)


def _extended_state[State](
    base: dict[tuple[str, ...], State],
    additions: dict[tuple[str, ...], State],
) -> ChildStateStore[State]:
    if len(additions) >= len(base):
        additions.update(base)
        return FlatChildStateStore(additions)
    return ExtendedChildStateStore(base, additions)


type ChildOccupancyMap = dict[tuple[str, ...], position_occupancy.ChildOccupancy]
type ChildValueMap = dict[tuple[str, ...], particle_info.ParticleValueState]


class ChildState(msgspec.Struct, frozen=True):
    """Independent occupancy and value knowledge at destruction time."""

    occupancy: ChildStateStore[position_occupancy.ChildOccupancy]
    # Unknown values have no entry, so resolving a value only adds knowledge.
    values: ChildStateStore[particle_info.ParticleValueState]

    def with_caller(
        self,
        occupancy: ChildOccupancyMap,
        values: ChildValueMap,
    ) -> ChildState:
        """Take ownership of additional caller knowledge without changing earlier facts."""
        if not occupancy and not values:
            return self
        return ChildState(
            self.occupancy.with_caller(occupancy),
            self.values.with_caller(values),
        )
