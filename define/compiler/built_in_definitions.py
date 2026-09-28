"""Definitions the compiler provides until the Define Standard Library exists."""

from __future__ import annotations

import functools
import typing
from pathlib import Path

from define.compiler import ast, parser

if typing.TYPE_CHECKING:
    from collections.abc import Collection

_SOURCE_PATH = Path(__file__).parent / "built_in_definitions.dfn"


@functools.cache
def _definitions_by_name() -> dict[str, ast.GlobalDefinition]:
    parse_result = parser.Parser().parse_and_transform(
        _SOURCE_PATH.read_text(encoding="utf-8")
    )
    if parse_result.exception is not None:
        raise parse_result.exception
    if parse_result.program is None:
        raise ValueError("parse produced no program despite reporting no exception")
    definitions: dict[str, ast.GlobalDefinition] = {}
    for definition in parse_result.program.definitions:
        definitions[definition.typed_name.full_typed_name] = definition
    return definitions


def definitions() -> Collection[ast.GlobalDefinition]:
    """Return every built-in definition."""
    return _definitions_by_name().values()


def get_definition(full_typed_name: str) -> ast.GlobalDefinition | None:
    """Return the built-in definition with this full typed name, if there is one."""
    return _definitions_by_name().get(full_typed_name)
