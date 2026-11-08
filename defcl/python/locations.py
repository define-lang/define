"""Locations in DCL files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from source_rendering.python import rendering


class FieldPathLocation(msgspec.Struct, frozen=True):
    """Where a DCL file writes the field that a field path names, or, if the file does not write it, the nearest field on the path that it does write."""

    # None for an element of a repeated field, which has no name.
    name: rendering.SourceLocation | None
    value: rendering.SourceLocation
    # Whether the location is of the whole path, rather than of the nearest
    # field on it that the file writes.
    is_whole_path: bool
