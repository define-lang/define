"""Values that are each computed once, even when several threads need the same value at the same time."""

from __future__ import annotations

import threading
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable, ItemsView, ValuesView


class ComputedOnce[K, V]:
    """Values by key, each computed the first time a thread needs it.

    A thread that needs a value while another thread computes the same value
    waits for that thread and gets its value. Threads that need different
    values do not wait for each other.
    """

    def __init__(self):
        """Hold no values."""
        self._values: dict[K, V] = {}
        # The lock that one thread holds while it computes the value of each
        # key, so that each value is computed only once. A key's lock is
        # removed once its value is stored.
        self._locks: dict[K, threading.Lock] = {}

    def get(self, key: K, compute: Callable[[], V]) -> V:
        """Return the value of ``key``, calling ``compute`` for it if no thread has."""
        # A value is never replaced or removed, so reading it needs no lock.
        # A value can be None, so presence is checked by key.
        if key in self._values:
            return self._values[key]
        # CPython's dict.setdefault is atomic, with or without the GIL, so
        # every thread that needs this key gets the same lock.
        with self._locks.setdefault(key, threading.Lock()):
            # Another thread may have computed the value while this one waited.
            if key not in self._values:
                self._values[key] = compute()
            # The value is stored, so a thread that gets a new lock for this
            # key finds the value and does not compute it. A thread that found
            # no value can insert a new lock after another thread removed the
            # first one, so every thread that gets a lock removes the key's
            # lock, and another thread may already have removed it.
            _ = self._locks.pop(key, None)
        return self._values[key]

    def values(self) -> ValuesView[V]:
        """Return every value computed so far."""
        return self._values.values()

    def items(self) -> ItemsView[K, V]:
        """Return every key whose value was computed so far, with its value."""
        return self._values.items()
