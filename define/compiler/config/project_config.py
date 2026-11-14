"""The project config, .define/project/config.defcl, which makes a directory a project root."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

import msgspec

from defcl.schema.core import boolean_pb2
from define.compiler.config import config_file
from define.compiler.data_structures import define_path
from define.config.project import config_pb2

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from defcl.python import loader as defcl_loader
    from define.compiler.errors import diagnostics

CONFIG_FILE = config_file.ConfigFile(
    path=define_path.DefinePathFromPosix(PurePosixPath(".define/project/config.defcl")),
    message_type=config_pb2.ProjectConfigFile,
)


class ProjectConfig(msgspec.Struct, frozen=True):
    """What a project config says about its project."""

    fqun: str
    # The location of the universe_name value, for diagnostics about the
    # universe that are found after the config is loaded.
    fqun_location: rendering.SourceLocation
    # Where the config says that the project has Value Encoding Associations,
    # or None if it does not say so.
    has_encodings_location: rendering.SourceLocation | None
    # Where the config says that the project has Encoding Operation
    # associations, or None if it does not say so.
    has_encoding_operations_location: rendering.SourceLocation | None


class ProjectConfigReader(config_file.ConfigFileReader[config_pb2.ProjectConfigFile]):
    """Reads a project root's project config."""

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root and the source map to register the file with."""
        super().__init__(root, source_map, CONFIG_FILE)

    def load(
        self,
    ) -> tuple[ProjectConfig | None, list[diagnostics.FormattableDiagnostic]]:
        """Load and validate the project config.

        Returns what it says, or None if a diagnostic keeps it from being used,
        with its diagnostics.
        """
        loaded, config_diagnostics = self.load_message()
        if loaded is None:
            return None, config_diagnostics
        project = loaded.message.project
        return ProjectConfig(
            fqun=project.universe_name or "",
            fqun_location=loaded.file.location_of(("project", "universe_name")),
            has_encodings_location=_true_association_location(
                loaded, "has_encodings", project.associations.has_encodings
            ),
            has_encoding_operations_location=_true_association_location(
                loaded,
                "has_encoding_operations",
                project.associations.has_encoding_operations,
            ),
        ), config_diagnostics


def _true_association_location(
    loaded: defcl_loader.LoadedMessage[config_pb2.ProjectConfigFile],
    field_name: str,
    value: boolean_pb2.Defcl.Boolean.ValueType,
) -> rendering.SourceLocation | None:
    """Return the location of the project config's association field named field_name, whose value is value, if it is TRUE, or None."""
    if value != boolean_pb2.Defcl.Boolean.TRUE:
        return None
    return loaded.file.location_of(("project", "associations", field_name))
