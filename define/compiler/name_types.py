"""The types of names in Define."""

from __future__ import annotations

import enum


class NameType(enum.StrEnum):
    """The type of a name."""

    POSITION = "position"
    ACTION = "action"
    VALUE = "value"
    ENCODING = "encoding"
    LITERAL = "literal"
    OPERATION = "operation"
    ENCODING_OPERATION = "encoding_operation"
    VIEW = "view"
