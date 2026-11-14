"""The encoding operations config, .define/encodings/encoding_operations.defcl, which associates the project's logical operations with Encoding Operations."""

from __future__ import annotations

import types
import typing
from pathlib import PurePosixPath

from define.compiler.config import config_file, global_names
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.config.encodings import encoding_operations_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from crates.source_rendering.python import rendering
    from defcl.python import validator as defcl_validator
    from define.compiler import ast
    from define.compiler.config import project_config

CONFIG_FILE = config_file.ConfigFile(
    path=define_path.DefinePathFromPosix(
        PurePosixPath(".define/encodings/encoding_operations.defcl")
    ),
    message_type=encoding_operations_pb2.EncodingOperationsFile,
)

_EMPTY_ENCODING_OPERATIONS: types.MappingProxyType[
    str, list[ast.ReferenceGlobalNameContent]
] = types.MappingProxyType({})


class EncodingOperationsConfigReader(
    config_file.ConfigFileReader[encoding_operations_pb2.EncodingOperationsFile]
):
    """Reads a project root's encoding operations config, which the project config says whether the project has."""

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root and the source map to register the file with."""
        super().__init__(root, source_map, CONFIG_FILE)

    def load(
        self, project: project_config.ProjectConfig
    ) -> tuple[
        types.MappingProxyType[str, list[ast.ReferenceGlobalNameContent]] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the project's Encoding Operation associations with its logical operations.

        Returns an immutable mapping from each logical operation's short global
        name to the global names of its associated Encoding Operations, or None
        if a diagnostic keeps the associations from being used, with the
        associations' diagnostics. The mapping is empty when the project config
        does not say that the project has Encoding Operation associations.
        """
        # TODO: Once a library can be compiled, report each association whose
        # logical operation the compile never validated. Until then, an
        # association is checked only when the program uses its logical
        # operation, so one that names an unused or undefined logical operation
        # goes unreported.
        if project.has_encoding_operations_location is None:
            return _EMPTY_ENCODING_OPERATIONS, []
        # The project config says the file exists, so only then is it checked.
        if not self.exists():
            return None, [
                diagnostics.EncodingOperationsConfigNotFoundDiagnostic(
                    location=project.has_encoding_operations_location,
                    encoding_operations_config_path=str(self.path()),
                )
            ]
        result, encoding_operations_diagnostics = self.load_message()
        if result is None:
            return None, encoding_operations_diagnostics
        encoding_operations, association_diagnostics = _encoding_operations(
            result.message.encoding_operations.operation_encodings,
            result.file,
            project.fqun,
        )
        encoding_operations_diagnostics.extend(association_diagnostics)
        return (
            types.MappingProxyType(encoding_operations),
            encoding_operations_diagnostics,
        )


def _encoding_operation(
    file: defcl_validator.ValidatedFile,
    field_path: diagnostics.FieldPath,
    association: encoding_operations_pb2.OperationEncoding,
    fqun: str,
) -> tuple[
    tuple[ast.ReferenceGlobalNameContent, ast.ReferenceGlobalNameContent] | None,
    list[diagnostics.Diagnostic],
]:
    """Parse and validate the logical operation and Encoding Operation of the association at field_path.

    Returns them, or None if either one cannot be used, with their
    diagnostics. fqun is the project's universe.
    """
    # TODO: Allow a logical operation in another universe when the project
    # defines an encoding that the Encoding Operation's views require, as DLP
    # 58 allows.
    logical_operation, association_diagnostics = global_names.config_global_name(
        file, (*field_path, "logical_operation"), association.logical_operation, fqun
    )
    universe_diagnostic = (
        None
        if logical_operation is None
        else global_names.check_global_name_in_this_universe(
            "logical_operation", logical_operation, fqun
        )
    )
    if universe_diagnostic is not None:
        association_diagnostics.append(universe_diagnostic)
    encoding_operation, encoding_operation_diagnostics = (
        global_names.config_global_name(
            file,
            (*field_path, "encoding_operation"),
            association.encoding_operation,
            fqun,
        )
    )
    association_diagnostics.extend(encoding_operation_diagnostics)
    if (
        logical_operation is None
        or encoding_operation is None
        or universe_diagnostic is not None
    ):
        return None, association_diagnostics
    return (logical_operation, encoding_operation), association_diagnostics


def _encoding_operations(
    associations: Sequence[encoding_operations_pb2.OperationEncoding],
    file: defcl_validator.ValidatedFile,
    fqun: str,
) -> tuple[
    dict[str, list[ast.ReferenceGlobalNameContent]],
    list[diagnostics.FormattableDiagnostic],
]:
    """Return each logical operation's Encoding Operations from the associations, with the diagnostics about the associations.

    An association repeated later, or whose logical operation or Encoding
    Operation is not a valid name for it, is ignored. fqun is the project's
    universe.
    """
    encoding_operations: dict[str, list[ast.ReferenceGlobalNameContent]] = {}
    association_diagnostics: list[diagnostics.FormattableDiagnostic] = []
    # The index of the first association of each logical operation and
    # Encoding Operation.
    first_indexes: dict[tuple[str, str], int] = {}
    previous_logical_operation = ""
    for index, association in enumerate(associations):
        field_path = ("encoding_operations", "operation_encodings", index)
        names, name_diagnostics = _encoding_operation(
            file, field_path, association, fqun
        )
        association_diagnostics.extend(name_diagnostics)
        if association.logical_operation < previous_logical_operation:
            association_diagnostics.append(
                diagnostics.UnsortedEncodingOperationDiagnostic(
                    location=file.location_of((*field_path, "logical_operation")),
                    logical_operation=association.logical_operation,
                    previous_logical_operation=previous_logical_operation,
                )
            )
        previous_logical_operation = association.logical_operation
        pair = (association.logical_operation, association.encoding_operation)
        first_index = first_indexes.get(pair)
        if first_index is not None:
            association_diagnostics.append(
                diagnostics.DuplicateEncodingOperationDiagnostic(
                    location=file.location_of(field_path),
                    logical_operation=association.logical_operation,
                    encoding_operation=association.encoding_operation,
                    first_location=file.location_of(
                        ("encoding_operations", "operation_encodings", first_index)
                    ),
                )
            )
            continue
        first_indexes[pair] = index
        if names is not None:
            logical_operation, encoding_operation = names
            encoding_operations.setdefault(logical_operation.path.name, []).append(
                encoding_operation
            )
    return encoding_operations, association_diagnostics
