"""Helpers shared by the project configuration tests."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from crates.source_rendering.python import rendering
from define.compiler import config, constants
from define.compiler.data_structures import define_path

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler import ast


def load_project_root_config(
    root: define_path.DefinePath = constants.PROJECT_ROOT,
    declaring_entry: config.LocalDependencyEntry | None = None,
) -> config.RootConfigResult:
    """Load the configuration of the project at root."""
    return config.ConfigLoader(root, rendering.SourceMap()).load_project_root_config(
        declaring_entry
    )


def declaring_entry(universe: str, path: str) -> config.LocalDependencyEntry:
    """Return the first local dependency entry of the project's local deps config."""
    return config.LocalDependencyEntry(
        deps_path=str(config.LOCAL_DEPS_PATH),
        index=0,
        universe=universe,
        path=define_path.DefinePathFromPosix(PurePosixPath(path)),
    )


def encoding_names(
    value_encodings: Mapping[str, list[ast.ReferenceGlobalNameContent]],
) -> dict[str, list[tuple[str, rendering.SourceLocation]]]:
    """Return each value quality's encoding names as their text and locations."""
    result: dict[str, list[tuple[str, rendering.SourceLocation]]] = {}
    for value, names in value_encodings.items():
        result[value] = [(name.source_name, name.location) for name in names]
    return result


def encoding_name(name: str, line: int) -> tuple[str, rendering.SourceLocation]:
    """Return an encoding name that the project's encodings config writes on line, as `encoding_names` returns it."""
    # Each test's encodings config writes `encoding: "` at the same
    # indentation, so the name always starts at the same column.
    return (
        name,
        rendering.SourceLocation(
            line=line,
            column=18,
            end_line=line,
            end_column=17 + len(name),
            file_path=str(config.ENCODINGS_PATH),
        ),
    )
