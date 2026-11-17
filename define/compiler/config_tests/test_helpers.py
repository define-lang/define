"""Helpers shared by the project configuration tests."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from crates.source_rendering.python import rendering
from defcl.python import loader as defcl_loader
from define.compiler import constants
from define.compiler.config import (
    association_config,
    config_loader,
    encoding_operations_config,
    encodings_config,
    local_deps_config,
    project_config,
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


def load_association_table(
    root: define_path.DefinePath = constants.PROJECT_ROOT,
) -> tuple[
    association_config.AssociationTable, list[diagnostics.FormattableDiagnostic]
]:
    """Load the associations of the project at root, whose config must load without diagnostics."""
    source_map = rendering.SourceMap()
    result = config_loader.ConfigLoader(root, source_map).load_project_root_config(None)
    assert result.diagnostics == []
    assert result.config is not None
    return association_config.load_association_table(root, source_map, result.config)


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


def loaded_fqun(
    config: config_loader.Config | None,
    canonical: str,
    root: define_path.DefinePath = constants.PROJECT_ROOT,
) -> ast.Fqun:
    """Return the FQUN of a loaded config, after checking that it is canonical and located at the universe name in the project config of the project at root."""
    assert config is not None
    assert config.fqun.canonical == canonical
    assert config.fqun.location == universe_name_location(canonical, root)
    return config.fqun


def universe_name_location(
    universe_name: str, root: define_path.DefinePath = constants.PROJECT_ROOT
) -> rendering.SourceLocation:
    """Return the location of universe_name, the universe name in the project config of the project at root."""
    quote = config_field_location(
        project_config.CONFIG_FILE, ("project", "universe_name"), root
    )
    # The name starts after the opening quote of its string.
    return rendering.SourceLocation(
        line=quote.line,
        column=quote.column + 1,
        end_line=quote.line,
        end_column=quote.column + len(universe_name),
        file_path=quote.file_path,
    )


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


def declared_sub_root(
    universe: str, path: str, index: int = 0
) -> local_deps_config.LocalDependencyEntry:
    """Return the sub-root that entry index of the local dependencies config of the project at the project root declares."""
    return local_deps_config.LocalDependencyEntry(
        universe=universe,
        path=define_path.DefinePathFromPosix(PurePosixPath(path)),
        universe_location=config_field_location(
            local_deps_config.CONFIG_FILE, ("deps", "local", index, "universe_name")
        ),
        path_location=config_field_location(
            local_deps_config.CONFIG_FILE, ("deps", "local", index, "path")
        ),
    )


def associated_names(
    associations: Mapping[str, list[ast.GlobalTypedNameReference]] | None,
) -> dict[str, list[tuple[str, rendering.SourceLocation]]]:
    """Return the names associated with each key, as the text the config writes and their locations, from associations that can be used."""
    assert associations is not None
    result: dict[str, list[tuple[str, rendering.SourceLocation]]] = {}
    for key, references in associations.items():
        result[key] = [
            (reference.name_content.source_name, reference.location)
            for reference in references
        ]
    return result


def encoding_name(name: str, line: int) -> tuple[str, rendering.SourceLocation]:
    """Return an encoding name that the project's encodings config writes on line, as `associated_names` returns it."""
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


def associated_encoding_operations(
    associations: Mapping[
        str, list[encoding_operations_config.AssociatedEncodingOperation]
    ]
    | None,
) -> dict[str, list[tuple[str, rendering.SourceLocation, list[tuple[str, str]]]]]:
    """Return the Encoding Operations associated with each logical operation, as their names' text and locations, and their views' names and encodings' text, from associations that can be used."""
    assert associations is not None
    result: dict[
        str, list[tuple[str, rendering.SourceLocation, list[tuple[str, str]]]]
    ] = {}
    for logical_operation, encoding_operations in associations.items():
        result[logical_operation] = []
        for encoding_operation in encoding_operations:
            views: list[tuple[str, str]] = []
            for view in encoding_operation.views:
                views.append((view.name, view.encoding.name_content.source_name))
            result[logical_operation].append(
                (
                    encoding_operation.reference.name_content.source_name,
                    encoding_operation.reference.location,
                    views,
                )
            )
    return result


def encoding_operation_name_location(name: str, line: int) -> rendering.SourceLocation:
    """Return where the project's encoding operations config writes an Encoding Operation's name on line."""
    # Each test's config writes `name: "` at the same indentation, so the
    # name always starts at the same column.
    return rendering.SourceLocation(
        line=line,
        column=16,
        end_line=line,
        end_column=15 + len(name),
        file_path=str(encoding_operations_config.CONFIG_FILE.path),
    )
