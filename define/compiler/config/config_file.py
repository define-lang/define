"""What every config file has: where it is, the message that it holds, and how it is loaded and checked against its schema's rules."""

from __future__ import annotations

import typing
from pathlib import Path

import msgspec
import protovalidate
from google.protobuf import message

from defcl.python import loader as defcl_loader
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import PurePosixPath

    from crates.source_rendering.python import rendering
    from define.compiler.data_structures import define_path


class ConfigFile[M: message.Message](msgspec.Struct, frozen=True):
    """A config file's path, relative to a project root, and the message type that it holds."""

    path: define_path.DefinePath
    message_type: type[M]


class ConfigFileReader[M: message.Message]:
    """Reads one config file of a project root."""

    _root: define_path.DefinePath
    _source_map: rendering.SourceMap
    _config_file: ConfigFile[M]

    def __init__(
        self,
        root: define_path.DefinePath,
        source_map: rendering.SourceMap,
        config_file: ConfigFile[M],
    ):
        """Initialize with the project root, the source map to register the file with, and the config file."""
        self._root = root
        self._source_map = source_map
        self._config_file = config_file

    def path(self) -> PurePosixPath:
        """Return the config file's path."""
        return (self._root / self._config_file.path).as_posix_path()

    def exists(self) -> bool:
        """Whether the config file exists."""
        return Path(self.path()).exists()

    def load_message(
        self,
    ) -> tuple[
        defcl_loader.LoadedMessage[M] | None, list[diagnostics.FormattableDiagnostic]
    ]:
        """Load the config file and check it against its schema's rules.

        Returns its message with the file, or None if a diagnostic keeps it
        from being used, with its diagnostics.
        """
        result = defcl_loader.load_file(
            str(self.path()), self._config_file.message_type, self._source_map
        )
        config_diagnostics: list[diagnostics.FormattableDiagnostic] = list(
            result.diagnostics
        )
        if result.loaded is None:
            return None, config_diagnostics
        try:
            protovalidate.validate(result.loaded.message)
        except protovalidate.ValidationError as e:
            # TODO: Move this block into a helper function.
            for violation in e.violations:
                field = violation.proto.field
                # The config schemas have rules only on fields.
                if field is None:
                    raise ValueError(
                        f"config rule violation without a field: {violation.proto.message}"
                    ) from e
                field_path: list[str | int] = []
                for element in field.elements:
                    field_path.append(element.field_name)
                    subscript = element.subscript
                    if subscript is not None and subscript.field == "index":
                        field_path.append(subscript.value)
                config_diagnostics.append(
                    diagnostics.ConfigViolationDiagnostic(
                        location=result.loaded.file.location_of(tuple(field_path)),
                        field_path=tuple(field_path),
                        violation_message=violation.proto.message,
                    )
                )
            return None, config_diagnostics
        return result.loaded, config_diagnostics
