"""Definitions the compiler provides until the Define Standard Library exists."""

from __future__ import annotations

import functools
import typing
from pathlib import Path

from define.compiler import ast, parser

_SOURCE_PATH = Path(__file__).parent / "built_in_definitions.dfn"


@functools.cache
def _operations() -> dict[str, ast.OperationDefinition]:
    parse_result = parser.Parser().parse_and_transform(
        _SOURCE_PATH.read_text(encoding="utf-8")
    )
    if parse_result.exception is not None:
        raise parse_result.exception
    if parse_result.program is None:
        raise ValueError("parse produced no program despite reporting no exception")
    operations: dict[str, ast.OperationDefinition] = {}
    # The built-in source defines only operations.
    for definition in parse_result.program.definitions:
        operations[definition.typed_name.full_typed_name] = typing.cast(
            "ast.OperationDefinition", definition
        )
    return operations


def get_operation(full_typed_name: str) -> ast.OperationDefinition | None:
    """Return the built-in operation with this full typed name, if there is one."""
    return _operations().get(full_typed_name)
