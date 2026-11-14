"""The encodings config, .define/encodings/encodings.defcl, which holds the project's Value Encoding Associations."""

from __future__ import annotations

import types
import typing
from pathlib import PurePosixPath

from define.compiler.config import config_file
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.parsing import parser
from define.compiler.validator.structural import name_validators
from define.config.encodings import encodings_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from crates.source_rendering.python import rendering
    from defcl.python import validator as defcl_validator
    from define.compiler import ast
    from define.compiler.config import project_config

CONFIG_FILE = config_file.ConfigFile(
    path=define_path.DefinePathFromPosix(
        PurePosixPath(".define/encodings/encodings.defcl")
    ),
    message_type=encodings_pb2.EncodingsFile,
)

_EMPTY_VALUE_ENCODINGS: types.MappingProxyType[
    str, list[ast.ReferenceGlobalNameContent]
] = types.MappingProxyType({})


class EncodingsConfigReader(config_file.ConfigFileReader[encodings_pb2.EncodingsFile]):
    """Reads a project root's encodings config, which the project config says whether the project has."""

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root and the source map to register the file with."""
        super().__init__(root, source_map, CONFIG_FILE)

    def load(
        self, project: project_config.ProjectConfig
    ) -> tuple[
        types.MappingProxyType[str, list[ast.ReferenceGlobalNameContent]] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the project's Value Encoding Associations.

        Returns an immutable mapping from each value quality's short global
        name to the global names of its associated encodings, or None if a
        diagnostic keeps the associations from being used, with the
        associations' diagnostics. The mapping is empty when the project config
        does not say that the project has Value Encoding Associations.
        """
        # TODO: Once a library can be compiled, report each association whose
        # value quality the compile never validated. Until then, an association
        # is checked only when the program uses its value quality, so one that
        # names an unused or undefined value quality goes unreported.
        if project.has_encodings_location is None:
            return _EMPTY_VALUE_ENCODINGS, []
        # The project config says the file exists, so only then is it checked.
        if not self.exists():
            return None, [
                diagnostics.EncodingsConfigNotFoundDiagnostic(
                    location=project.has_encodings_location,
                    encodings_config_path=str(self.path()),
                )
            ]
        result, encodings_diagnostics = self.load_message()
        if result is None:
            return None, encodings_diagnostics
        value_encodings, association_diagnostics = _value_encodings(
            result.message.encodings.value_encodings, result.file, project.fqun
        )
        encodings_diagnostics.extend(association_diagnostics)
        return types.MappingProxyType(value_encodings), encodings_diagnostics


def _config_global_name(
    file: defcl_validator.ValidatedFile,
    field_path: diagnostics.FieldPath,
    name: str,
    fqun: str,
) -> tuple[ast.ReferenceGlobalNameContent | None, list[diagnostics.Diagnostic]]:
    """Parse and validate the global name in the config file's field at field_path.

    Returns the name's content, located at its value in the file, or None if
    the name is not valid, with the name's diagnostics. fqun is the project's
    universe, whose names must be in short form.
    """
    # Each field's value is a string, so it is located at its opening quote,
    # and the name starts after it.
    # TODO: This is only right when the string has no escapes. Locate the
    # name by its value's text once defcl gives that location.
    quote = file.location_of(field_path)
    name_content = parser.parse_global_name(
        name.encode(), quote.file_path, quote.line, quote.column + 1
    )
    if isinstance(name_content, syntax_errors.DefineSyntaxError):
        return None, [name_content]
    content_diagnostics = name_validators.validate_global_name(
        name_content, must_use_short_form=fqun
    )
    return (None if content_diagnostics else name_content), content_diagnostics


def _check_global_name_in_this_universe(
    field_name: str, content: ast.ReferenceGlobalNameContent, fqun: str
) -> diagnostics.Diagnostic | None:
    """Return a diagnostic if the name in the field named field_name is not in the same universe as the project, whose FQUN is fqun."""
    # A short name is in the project's universe. `_config_global_name` rejects
    # a name with the project's own FQUN, so any other name with an FQUN is
    # in another universe.
    if content.fqun is None:
        return None
    return diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=content.location,
        field_name=field_name,
        name=content.source_name,
        fqun=fqun,
    )


def _value_encoding(
    file: defcl_validator.ValidatedFile,
    field_path: diagnostics.FieldPath,
    association: encodings_pb2.ValueEncoding,
    fqun: str,
) -> tuple[
    tuple[ast.ReferenceGlobalNameContent, ast.ReferenceGlobalNameContent] | None,
    list[diagnostics.Diagnostic],
]:
    """Parse and validate the value quality and encoding of the association at field_path.

    Returns them, or None if either one cannot be used, with their
    diagnostics. fqun is the project's universe.
    """
    value, association_diagnostics = _config_global_name(
        file, (*field_path, "value"), association.value, fqun
    )
    universe_diagnostic = (
        None
        if value is None
        else _check_global_name_in_this_universe("value", value, fqun)
    )
    if universe_diagnostic is not None:
        association_diagnostics.append(universe_diagnostic)
    encoding, encoding_diagnostics = _config_global_name(
        file, (*field_path, "encoding"), association.encoding, fqun
    )
    association_diagnostics.extend(encoding_diagnostics)
    if value is None or encoding is None or universe_diagnostic is not None:
        return None, association_diagnostics
    return (value, encoding), association_diagnostics


def _value_encodings(
    associations: Sequence[encodings_pb2.ValueEncoding],
    file: defcl_validator.ValidatedFile,
    fqun: str,
) -> tuple[
    dict[str, list[ast.ReferenceGlobalNameContent]],
    list[diagnostics.FormattableDiagnostic],
]:
    """Return each value quality's encodings from the Value Encoding Associations, with the diagnostics about the associations.

    An association repeated later, or whose value quality or encoding is not a
    valid name for it, is ignored. fqun is the project's universe.
    """
    value_encodings: dict[str, list[ast.ReferenceGlobalNameContent]] = {}
    association_diagnostics: list[diagnostics.FormattableDiagnostic] = []
    # The index of the first association of each value quality and encoding.
    first_indexes: dict[tuple[str, str], int] = {}
    previous_value = ""
    for index, association in enumerate(associations):
        field_path = ("encodings", "value_encodings", index)
        names, name_diagnostics = _value_encoding(file, field_path, association, fqun)
        association_diagnostics.extend(name_diagnostics)
        if association.value < previous_value:
            association_diagnostics.append(
                diagnostics.UnsortedValueEncodingDiagnostic(
                    location=file.location_of((*field_path, "value")),
                    value=association.value,
                    previous_value=previous_value,
                )
            )
        previous_value = association.value
        pair = (association.value, association.encoding)
        first_index = first_indexes.get(pair)
        if first_index is not None:
            association_diagnostics.append(
                diagnostics.DuplicateValueEncodingDiagnostic(
                    location=file.location_of(field_path),
                    value=association.value,
                    encoding=association.encoding,
                    first_location=file.location_of(
                        ("encodings", "value_encodings", first_index)
                    ),
                )
            )
            continue
        first_indexes[pair] = index
        if names is not None:
            value, encoding = names
            value_encodings.setdefault(value.path.name, []).append(encoding)
    return value_encodings, association_diagnostics
