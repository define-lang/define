"""Project configuration loading and validation."""

from __future__ import annotations

import types
import typing
from pathlib import Path, PurePosixPath

import msgspec
import protovalidate
from google.protobuf import message

from defcl.python import loader as defcl_loader
from defcl.schema.core import boolean_pb2
from define.compiler import constants
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.parsing import parser
from define.compiler.validator.structural import name_validators
from define.config.deps import local_pb2
from define.config.encodings import encodings_pb2
from define.config.project import config_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from crates.source_rendering.python import rendering
    from defcl.python import validator as defcl_validator
    from define.compiler import ast


CONFIG_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/project/config.defcl")
)
LOCAL_DEPS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/deps/local.defcl")
)
ENCODINGS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/encodings/encodings.defcl")
)


class ConfigFile[M: message.Message](msgspec.Struct, frozen=True):
    """A config file's path, relative to a project root, and the message type that it holds."""

    path: define_path.DefinePath
    message_type: type[M]


PROJECT_CONFIG = ConfigFile(path=CONFIG_PATH, message_type=config_pb2.ProjectConfigFile)
LOCAL_DEPS_CONFIG = ConfigFile(
    path=LOCAL_DEPS_PATH, message_type=local_pb2.LocalDepsFile
)
ENCODINGS_CONFIG = ConfigFile(
    path=ENCODINGS_PATH, message_type=encodings_pb2.EncodingsFile
)

_EMPTY_DEPS: types.MappingProxyType[str, LocalDependencyEntry] = types.MappingProxyType(
    {}
)
_EMPTY_VALUE_ENCODINGS: types.MappingProxyType[
    str, list[ast.ReferenceGlobalNameContent]
] = types.MappingProxyType({})


def universe_needs_configuration(fqun: str) -> bool:
    """Whether a project must configure a universe as a sub-root before referencing it."""
    # TODO: Remove this once the Define Standard Library exists.
    return fqun != constants.STANDARD_UNIVERSE


class LocalDependencyEntry(msgspec.Struct, frozen=True):
    """One entry in a project's local dependencies config."""

    universe: str
    # The sub-root's path, relative to the project that declares it.
    path: define_path.DefinePathFromPosix
    # The locations of the entry's universe_name and path values in
    # local_deps.defcl, for diagnostics about the entry that are found after the
    # config is loaded.
    universe_location: rendering.SourceLocation
    path_location: rendering.SourceLocation


class ProjectRootConfig(msgspec.Struct):
    """Resolved project configuration for a project root."""

    fqun: str
    # The location of the universe_name value in project.defcl, for
    # diagnostics about the universe that are found after the config is loaded.
    fqun_location: rendering.SourceLocation
    # The local dependency entry for each universe that the project configures
    # as a sub-root.
    sub_roots: Mapping[str, LocalDependencyEntry]
    # The global names of the encodings associated with each of the project's
    # value qualities, located inside encodings.defcl, keyed by the value
    # quality's short global name.
    value_encodings: Mapping[str, list[ast.ReferenceGlobalNameContent]] = (
        _EMPTY_VALUE_ENCODINGS
    )


class RootConfigResult(msgspec.Struct, frozen=True):
    """A project root's resolved configuration, if it can be resolved, and the diagnostics in its config files."""

    # None when a diagnostic leaves the configuration's meaning unclear.
    # Otherwise the configuration is used even if it has diagnostics, so that
    # the compiler can go on to find other errors in the program. The compile
    # still fails, since the diagnostics are reported.
    root_config: ProjectRootConfig | None
    diagnostics: list[diagnostics.FormattableDiagnostic]


class ConfigLoader:
    """Loads and validates Define project configuration files."""

    _root: define_path.DefinePath
    _source_map: rendering.SourceMap

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root path and the source map to register config files with."""
        self._root = root
        self._source_map = source_map

    def config_path(self) -> PurePosixPath:
        """Return the path of the root's project config file."""
        return (self._root / CONFIG_PATH).as_posix_path()

    def is_project_root(self) -> bool:
        """Whether the root has a project config file."""
        return Path(self.config_path()).exists()

    def load_project_root_config(
        self, declaring_entry: LocalDependencyEntry | None = None
    ) -> RootConfigResult:
        """Load and resolve this root's own configuration.

        declaring_entry is the local dependency entry that declares this root
        as a sub-root, or None for the project root. The universe name that a
        sub-root's own config declares must be the entry's.
        """
        config_path = self.config_path()
        if not self.is_project_root():
            if declaring_entry is None:
                return RootConfigResult(
                    root_config=None,
                    diagnostics=[
                        diagnostics.NotRunFromProjectRootDiagnostic(
                            config_path=str(config_path)
                        )
                    ],
                )
            return RootConfigResult(
                root_config=None,
                diagnostics=[
                    diagnostics.SubRootNotProjectRootDiagnostic(
                        location=declaring_entry.path_location,
                        sub_root_path=str(self._root),
                        sub_root_config_path=str(config_path),
                    )
                ],
            )
        # Every config file is loaded even when another has diagnostics that
        # keep the configuration from being used, so that all of their
        # diagnostics are reported at once.
        project_config, config_diagnostics = self._load_config(PROJECT_CONFIG)
        sub_roots, deps_diagnostics = self._local_deps_config()
        config_diagnostics.extend(deps_diagnostics)
        if project_config is None:
            return RootConfigResult(root_config=None, diagnostics=config_diagnostics)
        fqun = project_config.message.project.universe_name or ""
        fqun_location = project_config.file.location_of(("project", "universe_name"))
        fqun_matches = True
        if declaring_entry is not None and fqun != declaring_entry.universe:
            fqun_matches = False
            config_diagnostics.append(
                diagnostics.SubRootFqunMismatchDiagnostic(
                    location=fqun_location,
                    expected_fqun=declaring_entry.universe,
                    actual_fqun=fqun,
                    sub_root_path=str(self._root),
                )
            )
        value_encodings, encodings_diagnostics = self._value_encodings_config(
            project_config, fqun
        )
        config_diagnostics.extend(encodings_diagnostics)
        if not fqun_matches or sub_roots is None or value_encodings is None:
            return RootConfigResult(root_config=None, diagnostics=config_diagnostics)
        return RootConfigResult(
            root_config=ProjectRootConfig(
                fqun=fqun,
                fqun_location=fqun_location,
                sub_roots=sub_roots,
                value_encodings=value_encodings,
            ),
            diagnostics=config_diagnostics,
        )

    def _load_config[M: message.Message](
        self, config_file: ConfigFile[M]
    ) -> tuple[
        defcl_loader.LoadedMessage[M] | None, list[diagnostics.FormattableDiagnostic]
    ]:
        """Load and validate a defcl config file.

        Returns its message with the file, or None if a diagnostic keeps it
        from being used, with its diagnostics.
        """
        path = (self._root / config_file.path).as_posix_path()
        result = defcl_loader.load_file(
            str(path), config_file.message_type, self._source_map
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

    def _local_deps_config(
        self,
    ) -> tuple[
        types.MappingProxyType[str, LocalDependencyEntry] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the local dependency overrides.

        Returns an immutable mapping from universe name to its entry, or None
        if a diagnostic keeps the overrides from being used, with the
        overrides' diagnostics. When two entries declare the same universe,
        the first is used.
        """
        deps_path = (self._root / LOCAL_DEPS_PATH).as_posix_path()
        if not Path(deps_path).exists():
            return _EMPTY_DEPS, []
        result, deps_diagnostics = self._load_config(LOCAL_DEPS_CONFIG)
        if result is None:
            return None, deps_diagnostics
        deps: dict[str, LocalDependencyEntry] = {}
        for index, dep in enumerate(result.message.deps.local):
            universe_location = result.file.location_of(
                ("deps", "local", index, "universe_name")
            )
            first_entry = deps.get(dep.universe_name)
            if first_entry is not None:
                deps_diagnostics.append(
                    diagnostics.DuplicateLocalDependencyDiagnostic(
                        location=universe_location,
                        universe_name=dep.universe_name,
                        first_location=first_entry.universe_location,
                    )
                )
                continue
            deps[dep.universe_name] = LocalDependencyEntry(
                universe=dep.universe_name,
                # Parses the config's path string once, and keeps the parsed
                # path for joining onto the project later.
                path=define_path.DefinePathFromPosix(PurePosixPath(dep.path)),
                universe_location=universe_location,
                path_location=result.file.location_of(("deps", "local", index, "path")),
            )
        return types.MappingProxyType(deps), deps_diagnostics

    def _value_encodings_config(
        self,
        project_config: defcl_loader.LoadedMessage[config_pb2.ProjectConfigFile],
        fqun: str,
    ) -> tuple[
        types.MappingProxyType[str, list[ast.ReferenceGlobalNameContent]] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the Value Encoding Associations.

        Returns an immutable mapping from each value quality's short global name to the
        global names of its associated encodings, or None if a diagnostic keeps
        the associations from being used, with the associations' diagnostics. The
        mapping is empty when the project
        config's associations say the project has no Value Encoding
        Associations. An association repeated later, or whose encoding is not
        a valid global name, is ignored. fqun is the project's universe, whose
        encodings the config must name in short form.
        """
        # TODO: Once a library can be compiled, report each association whose
        # value quality the compile never validated. Until then, an association
        # is checked only when the program uses its value quality, so one that
        # names an unused or undefined value quality goes unreported.
        associations = project_config.message.project.associations
        if associations.has_encodings != boolean_pb2.Defcl.Boolean.TRUE:
            return _EMPTY_VALUE_ENCODINGS, []
        encodings_path = (self._root / ENCODINGS_PATH).as_posix_path()
        # The project config says the file exists, so only then is it checked.
        if not Path(encodings_path).exists():
            return None, [
                diagnostics.EncodingsConfigNotFoundDiagnostic(
                    location=project_config.file.location_of(
                        ("project", "associations", "has_encodings")
                    ),
                    encodings_config_path=str(encodings_path),
                )
            ]
        result, encodings_diagnostics = self._load_config(ENCODINGS_CONFIG)
        if result is None:
            return None, encodings_diagnostics
        associations_list = result.message.encodings.value_encodings
        names: list[tuple[diagnostics.FieldPath, str]] = []
        for index, association in enumerate(associations_list):
            names.append(
                (
                    ("encodings", "value_encodings", index, "encoding"),
                    association.encoding,
                )
            )
        encodings, name_diagnostics = _config_global_names(result.file, names, fqun)
        encodings_diagnostics.extend(name_diagnostics)
        value_encodings, association_diagnostics = _value_encodings(
            associations_list, encodings, result.file
        )
        encodings_diagnostics.extend(association_diagnostics)
        return types.MappingProxyType(value_encodings), encodings_diagnostics


def _config_global_names(
    file: defcl_validator.ValidatedFile,
    names: Sequence[tuple[diagnostics.FieldPath, str]],
    fqun: str,
) -> tuple[list[ast.ReferenceGlobalNameContent | None], list[diagnostics.Diagnostic]]:
    """Parse and validate the global names in the config file, each in the field at its field path.

    Returns each name's content, located at its value in the file, or None for
    a name that is not valid, with the names' diagnostics. fqun is the
    project's universe, whose names must be in short form.
    """
    contents: list[ast.ReferenceGlobalNameContent | None] = []
    name_diagnostics: list[diagnostics.Diagnostic] = []
    for field_path, name in names:
        # Each field's value is a string, so it is located at its opening
        # quote, and the name starts after it.
        quote = file.location_of(field_path)
        name_content = parser.parse_global_name(
            name.encode(), quote.file_path, quote.line, quote.column + 1
        )
        if isinstance(name_content, syntax_errors.DefineSyntaxError):
            name_diagnostics.append(name_content)
            contents.append(None)
            continue
        content_diagnostics = name_validators.validate_global_name(
            name_content, must_use_short_form=fqun
        )
        name_diagnostics.extend(content_diagnostics)
        contents.append(None if content_diagnostics else name_content)
    return contents, name_diagnostics


def _value_encodings(
    associations: Sequence[encodings_pb2.ValueEncoding],
    encodings: Sequence[ast.ReferenceGlobalNameContent | None],
    file: defcl_validator.ValidatedFile,
) -> tuple[
    dict[str, list[ast.ReferenceGlobalNameContent]],
    list[diagnostics.FormattableDiagnostic],
]:
    """Return each value quality's encodings from the Value Encoding Associations, whose encodings' parsed names are encodings, with the diagnostics about their order.

    An association repeated later, or whose encoding's name is None, is
    ignored.
    """
    value_encodings: dict[str, list[ast.ReferenceGlobalNameContent]] = {}
    association_diagnostics: list[diagnostics.FormattableDiagnostic] = []
    # The index of the first association of each value quality and encoding.
    first_indexes: dict[tuple[str, str], int] = {}
    previous_value = ""
    for index, (association, encoding) in enumerate(
        zip(associations, encodings, strict=True)
    ):
        field_path = ("encodings", "value_encodings", index)
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
        if encoding is not None:
            value_encodings.setdefault(association.value, []).append(encoding)
    return value_encodings, association_diagnostics
