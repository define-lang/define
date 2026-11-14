"""Helpers shared by the project configuration tests."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from crates.source_rendering.python import rendering
from defcl.python import loader as defcl_loader
from define.compiler import constants
from define.compiler.config import (
    config_loader,
    encodings_config,
    local_deps_config,
)
from define.compiler.data_structures import define_path

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from google.protobuf import message

    from define.compiler import ast
    from define.compiler.config import (
        config_file,
    )
    from define.compiler.errors import diagnostics


def load_config(
    root: define_path.DefinePath = constants.PROJECT_ROOT,
    declaring_entry: local_deps_config.LocalDependencyEntry | None = None,
) -> config_loader.ConfigLoadResult:
    """Load the configuration of the project at root."""
    return config_loader.ConfigLoader(
        root, rendering.SourceMap()
    ).load_project_root_config(declaring_entry)


def config_field_location[M: message.Message](
    config_file: config_file.ConfigFile[M],
    field_path: diagnostics.FieldPath,
    root: define_path.DefinePath = constants.PROJECT_ROOT,
) -> rendering.SourceLocation:
    """Return the location of the field at field_path in config_file of the project at root, relative to the current directory."""
    path = (root / config_file.path).as_posix_path()
    result = defcl_loader.load_file(
        str(path), config_file.message_type, rendering.SourceMap()
    )
    assert result.loaded is not None
    return result.loaded.file.location_of(field_path)


def declaring_entry(universe: str, path: str) -> local_deps_config.LocalDependencyEntry:
    """Return a local dependency entry that declares a sub-root, as the declaring project's local deps config would."""
    # The tests have no declaring project, so the entry's locations are only
    # somewhere for diagnostics about it to point.
    location = rendering.SourceLocation(
        line=1,
        column=1,
        end_line=1,
        end_column=1,
        file_path=str(local_deps_config.CONFIG_FILE.path),
    )
    return local_deps_config.LocalDependencyEntry(
        universe=universe,
        path=define_path.DefinePathFromPosix(PurePosixPath(path)),
        universe_location=location,
        path_location=location,
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
            file_path=str(encodings_config.CONFIG_FILE.path),
        ),
    )
