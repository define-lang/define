"""A project's associations, from its encodings and encoding operations configs, with every name in them fully qualified."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.config import encoding_operations_config, encodings_config

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.config import local_deps_config, project_config
    from define.compiler.data_structures import define_path
    from define.compiler.errors import diagnostics


class AssociationTable(msgspec.Struct, frozen=True):
    """A project's associations, whose names are references fully qualified in the project's universe."""

    # References to the encodings associated with each of the project's value
    # qualities, by the value quality's short global name. A value quality
    # whose associated encodings are all in universes that the project does
    # not configure has an empty list.
    value_encodings: Mapping[str, list[ast.GlobalTypedNameReference]]
    # The Encoding Operations associated with each of the project's logical
    # operations, by the logical operation's short global name.
    encoding_operations: Mapping[
        str, list[encoding_operations_config.AssociatedEncodingOperation]
    ]


def load_association_table(
    root: define_path.DefinePath,
    source_map: rendering.SourceMap,
    project: project_config.ProjectConfig,
    sub_roots: Mapping[str, local_deps_config.LocalDependencyEntry] | None,
) -> tuple[AssociationTable | None, list[diagnostics.FormattableDiagnostic]]:
    """Load the associations of the project at root, whose project config is project and which configures sub_roots.

    Returns them, or None if a diagnostic keeps them from being used, with
    the diagnostics in their config files. sub_roots is None when the
    project's local dependencies config cannot be used, which keeps the
    project's whole config from being used too; the association configs are
    still loaded so that their own diagnostics are reported at the same time,
    but which universes they name is not checked.
    """
    value_encodings, table_diagnostics = encodings_config.EncodingsConfigReader(
        root, source_map
    ).load(project, sub_roots)
    encoding_operations, encoding_operations_diagnostics = (
        encoding_operations_config.EncodingOperationsConfigReader(
            root, source_map
        ).load(project, sub_roots)
    )
    table_diagnostics.extend(encoding_operations_diagnostics)
    if value_encodings is None or encoding_operations is None:
        return None, table_diagnostics
    return AssociationTable(
        value_encodings=value_encodings, encoding_operations=encoding_operations
    ), table_diagnostics
