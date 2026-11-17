"""A project's associations, from its encodings and encoding operations configs, with every name in them fully qualified."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.config import encoding_operations_config, encodings_config

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.config import config_loader
    from define.compiler.data_structures import define_path
    from define.compiler.errors import diagnostics


class AssociationTable(msgspec.Struct, frozen=True):
    """A project's associations, whose names are references fully qualified in the project's universe."""

    # References to the encodings associated with each of the project's value
    # qualities, by the value quality's short global name, or None if a
    # diagnostic in the encodings config keeps them from being used. A value
    # quality whose associated encodings are all in universes that the project
    # does not configure has an empty list.
    value_encodings: Mapping[str, list[ast.GlobalTypedNameReference]] | None
    # The Encoding Operations associated with each of the project's logical
    # operations, by the logical operation's short global name, or None if a
    # diagnostic in the encoding operations config keeps them from being used.
    encoding_operations: (
        Mapping[str, list[encoding_operations_config.AssociatedEncodingOperation]]
        | None
    )


def load_association_table(
    root: define_path.DefinePath,
    source_map: rendering.SourceMap,
    config: config_loader.Config,
) -> tuple[AssociationTable, list[diagnostics.FormattableDiagnostic]]:
    """Load the associations of the project at root, whose config is config, with the diagnostics in their config files."""
    value_encodings, table_diagnostics = encodings_config.EncodingsConfigReader(
        root, source_map
    ).load(config)
    encoding_operations, encoding_operations_diagnostics = (
        encoding_operations_config.EncodingOperationsConfigReader(
            root, source_map
        ).load(config)
    )
    table_diagnostics.extend(encoding_operations_diagnostics)
    return AssociationTable(
        value_encodings=value_encodings, encoding_operations=encoding_operations
    ), table_diagnostics
