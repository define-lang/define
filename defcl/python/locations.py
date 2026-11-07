"""Locations in DCL files."""

from __future__ import annotations

import msgspec


class SourceLocation(msgspec.Struct, frozen=True, gc=False):
    """The part of a DCL file that an error or a field covers.

    Lines and columns are 1-based, and columns count characters. ``end_line``
    and ``end_column`` are the position of the last character that the
    location covers.
    """

    line: int
    column: int
    end_line: int
    end_column: int


class FieldPathLocation(msgspec.Struct, frozen=True):
    """Where a DCL file writes the field that a field path names, or, if the file does not write it, the nearest field on the path that it does write."""

    # None for an element of a repeated field, which has no name.
    name: SourceLocation | None
    value: SourceLocation
    # Whether the location is of the whole path, rather than of the nearest
    # field on it that the file writes.
    is_whole_path: bool
