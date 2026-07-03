"""Mappings keyed by a typed name's or chained name's canonical name."""

from __future__ import annotations

import abc
import collections.abc
import typing

from define.compiler import ast


class _ItemsView[K: ast.ASTNode, V](collections.abc.ItemsView[K, V]):
    """An items view that reads stored pairs directly, without a re-lookup per item."""

    def __init__(self, mapping: _AstNodeDict[K, V], data: dict[str, tuple[K, V]]):
        super().__init__(mapping)
        self._data: dict[str, tuple[K, V]] = data

    @typing.override
    def __iter__(self) -> collections.abc.Iterator[tuple[K, V]]:
        return iter(self._data.values())


class _ValuesView[K: ast.ASTNode, V](collections.abc.ValuesView[V]):
    """A values view that reads stored values directly, without a re-lookup per item."""

    def __init__(self, mapping: _AstNodeDict[K, V], data: dict[str, tuple[K, V]]):
        super().__init__(mapping)
        self._data: dict[str, tuple[K, V]] = data

    @typing.override
    def __iter__(self) -> collections.abc.Iterator[V]:
        return (value for _, value in self._data.values())


class _AstNodeDict[K: ast.ASTNode, V](collections.abc.MutableMapping[K, V], abc.ABC):
    """A mapping whose keys are identified by a canonical string derived from the key.

    Two keys that share a canonical name refer to the same entry, even when they
    are distinct objects. The most recently set key object is the one retained
    and iterated. Subclasses define the accepted key type and how a key's
    canonical name is computed.

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    _key_type: typing.ClassVar[type[ast.ASTNode]]

    def __init__(self):
        """Initialize an empty mapping."""
        self._data: dict[str, tuple[K, V]] = {}

    @abc.abstractmethod
    def _canonical_name(self, key: K) -> str:
        """Return the canonical string that identifies ``key``'s entry."""

    @typing.override
    def __getitem__(self, key: K) -> V:
        return self._data[self._canonical_name(key)][1]

    @typing.override
    def __setitem__(self, key: K, value: V):
        self._data[self._canonical_name(key)] = (key, value)

    @typing.override
    def __delitem__(self, key: K):
        del self._data[self._canonical_name(key)]

    @typing.override
    def __contains__(self, key: object) -> bool:
        if not isinstance(key, self._key_type):
            raise TypeError(
                f"key must be a {self._key_type.__name__}, not {type(key).__name__}"
            )
        return self._canonical_name(typing.cast("K", key)) in self._data

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
        if type(self) is not type(other):
            return NotImplemented
        return (
            self._value_map() == typing.cast("_AstNodeDict[K, V]", other)._value_map()
        )

    @typing.override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self.items())!r})"


class TypedNameDict[K: ast.TypedName, V](_AstNodeDict[K, V]):
    """A mapping whose keys are identified by their canonical typed name.

    Two typed names that share a ``full_typed_name`` refer to the same entry,
    even when they are distinct objects (for example, references at different
    source locations, or a global reference written in full versus short form).

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    _key_type: typing.ClassVar[type[ast.ASTNode]] = ast.TypedName

    @typing.override
    def _canonical_name(self, key: K) -> str:
        return key.full_typed_name


class ChainedNameDict[K: ast.ChainedName, V](_AstNodeDict[K, V]):
    """A mapping whose keys are identified by their canonical chained name.

    Two chained names that share a ``canonical_chained_name`` refer to the same
    entry, even when they are distinct objects (for example, chains at different
    source locations, or a chain whose elements are written in full versus short
    form).

    Not thread-safe. Concurrent reads and writes will produce undefined
    behavior.
    """

    _key_type: typing.ClassVar[type[ast.ASTNode]] = ast.ChainedName

    @typing.override
    def _canonical_name(self, key: K) -> str:
        return key.canonical_chained_name
