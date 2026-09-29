"""Definitions the compiler provides until the Define Standard Library exists."""

from __future__ import annotations

import functools
import typing
from pathlib import Path, PurePosixPath

from define.compiler.errors import source_map
from define.compiler.parsing import parser

if typing.TYPE_CHECKING:
    from collections.abc import Collection

    from define.compiler import ast

_SOURCE_PATH = Path(__file__).parent / "built_in_definitions.dfn"
# Project file paths are relative, so this absolute path cannot collide with one.
SOURCE_FILE_PATH: typing.Final = PurePosixPath(_SOURCE_PATH.as_posix())


@functools.cache
def _source() -> bytes:
    return _SOURCE_PATH.read_bytes()


@functools.cache
def _definitions_by_name() -> dict[str, ast.GlobalDefinition]:
    parse_result = parser.Parser().parse_and_transform(
        _source().decode("utf-8"), file_path=SOURCE_FILE_PATH
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


def source_digest() -> bytes:
    """Return the digest of the built-in definitions' source file."""
    return source_map.source_digest(_source())
