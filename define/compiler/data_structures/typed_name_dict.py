"""A mapping keyed by a typed name's canonical name."""

from __future__ import annotations

import collections.abc
import typing

from define.compiler import ast


class _ItemsView[K: ast.TypedName, V](collections.abc.ItemsView[K, V]):
    """An items view that reads stored pairs directly, without a re-lookup per item."""

    def __init__(self, mapping: TypedNameDict[K, V], data: dict[str, tuple[K, V]]):
        super().__init__(mapping)
        self._data: dict[str, tuple[K, V]] = data

    @typing.override
    def __iter__(self) -> collections.abc.Iterator[tuple[K, V]]:
        return iter(self._data.values())


class _ValuesView[K: ast.TypedName, V](collections.abc.ValuesView[V]):
    """A values view that reads stored values directly, without a re-lookup per item."""

    def __init__(self, mapping: TypedNameDict[K, V], data: dict[str, tuple[K, V]]):
        super().__init__(mapping)
        self._data: dict[str, tuple[K, V]] = data

    @typing.override
    def __iter__(self) -> collections.abc.Iterator[V]:
        return (value for _, value in self._data.values())


class TypedNameDict[K: ast.TypedName, V](collections.abc.MutableMapping[K, V]):
    """A mapping whose keys are identified by their canonical typed name.

    Two typed names that share a ``full_typed_name`` refer to the same entry,
    even when they are distinct objects (for example, references at different
    source locations, or a global reference written in full versus short form).
    The most recently set key object is the one retained and iterated.

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    def __init__(self):
        """Initialize an empty mapping."""
        self._data: dict[str, tuple[K, V]] = {}

    @typing.override
    def __getitem__(self, key: K) -> V:
        return self._data[key.full_typed_name][1]

    @typing.override
    def __setitem__(self, key: K, value: V):
        self._data[key.full_typed_name] = (key, value)

    @typing.override
    def __delitem__(self, key: K):
        del self._data[key.full_typed_name]

    @typing.override
    def __contains__(self, key: object) -> bool:
        if not isinstance(key, ast.TypedName):
            raise TypeError(f"key must be a TypedName, not {type(key).__name__}")
        return key.full_typed_name in self._data

    @typing.override
    def __iter__(self) -> collections.abc.Iterator[K]:
        return (stored_key for stored_key, _ in self._data.values())

    @typing.override
    def __len__(self) -> int:
        return len(self._data)

    @typing.override
    def items(self) -> collections.abc.ItemsView[K, V]:
        return _ItemsView(self, self._data)

    @typing.override
    def values(self) -> collections.abc.ValuesView[V]:
        return _ValuesView(self, self._data)

    def _value_map(self) -> dict[str, V]:
        return {canonical: value for canonical, (_, value) in self._data.items()}

    @typing.override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypedNameDict):
            return self._value_map() == other._value_map()
        return NotImplemented

    @typing.override
    def __repr__(self) -> str:
        return f"TypedNameDict({dict(self.items())!r})"
