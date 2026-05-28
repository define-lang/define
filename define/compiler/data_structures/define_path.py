"""A POSIX-style path used in the compiler's internal data structures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import override


# We used to use pathlib.PurePosixPath but it represented a significant amount
# of our memory allocations and a significant amount of the CPU during
# compilation, all for functionality that we don't need in the compiler.
@dataclass(frozen=True, slots=True)
class DefinePath:
    """A POSIX-shaped path used in the compiler's internal data structures."""

    _path: str

    @override
    def __str__(self) -> str:
        return self._path

    def __truediv__(self, other: DefinePath) -> DefinePath:
        """Return a new DefinePath joining self with other.

        If left ends with / and right starts with /, one slash is dropped
        and the strings are concatenated. If only one side has a slash at
        the join point, the strings are concatenated literally. Otherwise
        a / is inserted between them.
        """
        if not self._path:
            return other
        if not other._path:
            return self
        left_ends_slash = self._path.endswith("/")
        right_starts_slash = other._path.startswith("/")
        if left_ends_slash and right_starts_slash:
            return DefinePath(self._path + other._path[1:])
        if left_ends_slash or right_starts_slash:
            return DefinePath(self._path + other._path)
        return DefinePath(f"{self._path}/{other._path}")

    @property
    def parts(self) -> list[str]:
        """Return the path's segments as split on '/'."""
        if not self._path:
            return []
        return self._path.split("/")

    @property
    def name(self) -> str:
        """Return the path's last component."""
        idx = self._path.rfind("/")
        return self._path[idx + 1 :] if idx >= 0 else self._path

    def with_suffix(self, suffix: str) -> DefinePath:
        """Return a new DefinePath with suffix appended to the path."""
        return DefinePath(self._path + suffix)

    def as_relative_path(self) -> DefinePath:
        """Return a DefinePath with the leading / removed, or self if absent."""
        if self._path.startswith("/"):
            return DefinePath(self._path[1:])
        return self

    def as_posix_path(self) -> PurePosixPath:
        """Return a PurePosixPath for interop with code that takes one."""
        return PurePosixPath(self._path)


@dataclass(frozen=True, slots=True, init=False)
class DefinePathFromPosix(DefinePath):
    """A DefinePath that caches the PurePosixPath it was built from."""

    _path_obj: PurePosixPath

    def __init__(self, path_obj: PurePosixPath):
        """Initialize with a PurePosixPath, caching it for as_posix_path."""
        # PurePosixPath uses "." as its relative-root identity element;
        # DefinePath uses "". The bridge maps between them so the join
        # operator behaves the same way in either representation.
        path_str = "" if path_obj == PurePosixPath(".") else str(path_obj)
        super().__init__(path_str)
        object.__setattr__(self, "_path_obj", path_obj)

    @override
    def as_posix_path(self) -> PurePosixPath:
        return self._path_obj


class InvalidPathError(Exception):
    """Raised when a path operation is invoked on an InvalidDefinePath."""


@dataclass(frozen=True, slots=True)
class InvalidDefinePath(DefinePath):
    """A DefinePath sentinel that rejects path operations.

    Supports __str__ and name; every other path operation raises
    InvalidPathError.
    """

    @override
    def __truediv__(self, other: DefinePath) -> DefinePath:
        raise InvalidPathError(f"cannot join invalid path: {self._path}")

    @property
    @override
    def parts(self) -> list[str]:
        raise InvalidPathError(f"cannot split invalid path: {self._path}")

    @override
    def with_suffix(self, suffix: str) -> DefinePath:
        raise InvalidPathError(f"cannot add suffix to invalid path: {self._path}")

    @override
    def as_relative_path(self) -> DefinePath:
        raise InvalidPathError(
            f"cannot take relative form of invalid path: {self._path}"
        )

    @override
    def as_posix_path(self) -> PurePosixPath:
        raise InvalidPathError(
            f"cannot convert invalid path to PurePosixPath: {self._path}"
        )


EMPTY = DefinePath("")
