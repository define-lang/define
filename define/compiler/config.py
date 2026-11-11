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
from define.compiler.errors import diagnostics
from define.config.deps import local_pb2
from define.config.encodings import encodings_pb2
from define.config.project import config_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from crates.source_rendering.python import rendering


CONFIG_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/project/config.defcl")
)
LOCAL_DEPS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/deps/local.defcl")
)
ENCODINGS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/encodings/encodings.defcl")
)

_EMPTY_DEPS: types.MappingProxyType[str, LocalDependencyEntry] = types.MappingProxyType(
    {}
)
_EMPTY_VALUE_ENCODINGS: types.MappingProxyType[str, list[str]] = types.MappingProxyType(
    {}
)


def universe_needs_configuration(fqun: str) -> bool:
    """Whether a project must configure a universe as a sub-root before referencing it."""
    # TODO: Remove this once the Define Standard Library exists.
    return fqun != constants.STANDARD_UNIVERSE


class LocalDependencyEntry(msgspec.Struct, frozen=True):
    """One entry in a project's local dependencies config."""

    # The path of the local dependencies config that holds the entry.
    deps_path: str
    # The entry's position in the config's list of local dependencies.
    index: int
    universe: str
    # The sub-root's path, relative to the project that declares it.
    path: define_path.DefinePathFromPosix


class ProjectRootConfig(msgspec.Struct):
    """Resolved project configuration for a project root."""

    fqun: str
    # The local dependency entry for each universe that the project configures
    # as a sub-root.
    sub_roots: Mapping[str, LocalDependencyEntry]
    # The paths of the encodings associated with each of the project's value
    # qualities, keyed by the value quality's path.
    value_encodings: Mapping[str, list[str]] = _EMPTY_VALUE_ENCODINGS


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
                        config_path=declaring_entry.deps_path,
                        field_path=("deps", "local", declaring_entry.index, "path"),
                        sub_root_path=str(self._root),
                        sub_root_config_path=str(config_path),
                    )
                ],
            )
        # Every config file is loaded even when another has diagnostics that
        # keep the configuration from being used, so that all of their
        # diagnostics are reported at once.
        project_config, config_diagnostics = self._load_config(
            CONFIG_PATH, config_pb2.ProjectConfigFile
        )
        sub_roots, deps_diagnostics = self._local_deps_config()
        config_diagnostics.extend(deps_diagnostics)
        if project_config is None:
            return RootConfigResult(root_config=None, diagnostics=config_diagnostics)
        fqun = project_config.project.universe_name or ""
        fqun_matches = True
        if declaring_entry is not None and fqun != declaring_entry.universe:
            fqun_matches = False
            config_diagnostics.append(
                diagnostics.SubRootFqunMismatchDiagnostic(
                    config_path=str(config_path),
                    field_path=("project", "universe_name"),
                    expected_fqun=declaring_entry.universe,
                    actual_fqun=fqun,
                    sub_root_path=str(self._root),
                )
            )
        value_encodings, encodings_diagnostics = self._value_encodings_config(
            project_config.project.associations
        )
        config_diagnostics.extend(encodings_diagnostics)
        if not fqun_matches or sub_roots is None or value_encodings is None:
            return RootConfigResult(root_config=None, diagnostics=config_diagnostics)
        return RootConfigResult(
            root_config=ProjectRootConfig(
                fqun=fqun,
                sub_roots=sub_roots,
                value_encodings=value_encodings,
            ),
            diagnostics=config_diagnostics,
        )

    def _load_config[M: message.Message](
        self,
        subpath: define_path.DefinePath,
        message_type: type[M],
    ) -> tuple[M | None, list[diagnostics.FormattableDiagnostic]]:
        """Load and validate a defcl config file.

        Returns its message, or None if a diagnostic keeps it from being used,
        with its diagnostics.
        """
        path = (self._root / subpath).as_posix_path()
        loaded = defcl_loader.load_file(str(path), message_type, self._source_map)
        config_diagnostics: list[diagnostics.FormattableDiagnostic] = list(
            loaded.diagnostics
        )
        if loaded.message is None:
            return None, config_diagnostics
        result = loaded.message
        try:
            protovalidate.validate(result)
        except protovalidate.ValidationError as e:
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
                        config_path=str(path),
                        field_path=tuple(field_path),
                        violation_message=violation.proto.message,
                    )
                )
            return None, config_diagnostics
        return result, config_diagnostics

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
        result, deps_diagnostics = self._load_config(
            LOCAL_DEPS_PATH, local_pb2.LocalDepsFile
        )
        if result is None:
            return None, deps_diagnostics
        deps: dict[str, LocalDependencyEntry] = {}
        for index, dep in enumerate(result.deps.local):
            first_entry = deps.get(dep.universe_name)
            if first_entry is not None:
                deps_diagnostics.append(
                    diagnostics.DuplicateLocalDependencyDiagnostic(
                        config_path=str(deps_path),
                        field_path=("deps", "local", index, "universe_name"),
                        universe_name=dep.universe_name,
                        first_field_path=(
                            "deps",
                            "local",
                            first_entry.index,
                            "universe_name",
                        ),
                    )
                )
                continue
            deps[dep.universe_name] = LocalDependencyEntry(
                deps_path=str(deps_path),
                index=index,
                universe=dep.universe_name,
                # Parses the config's path string once, and keeps the parsed
                # path for joining onto the project later.
                path=define_path.DefinePathFromPosix(PurePosixPath(dep.path)),
            )
        return types.MappingProxyType(deps), deps_diagnostics

    def _value_encodings_config(
        self,
        associations: config_pb2.Associations,
    ) -> tuple[
        types.MappingProxyType[str, list[str]] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the Value Encoding Associations.

        Returns an immutable mapping from each value quality's path to the
        paths of its associated encodings, or None if a diagnostic keeps the
        associations from being used, with the associations' diagnostics. The
        mapping is empty when the project
        config's associations say the project has no Value Encoding
        Associations. An association repeated later is ignored.
        """
        if associations.has_encodings != boolean_pb2.Defcl.Boolean.TRUE:
            return _EMPTY_VALUE_ENCODINGS, []
        encodings_path = (self._root / ENCODINGS_PATH).as_posix_path()
        # The project config says the file exists, so only then is it checked.
        if not Path(encodings_path).exists():
            return None, [
                diagnostics.EncodingsConfigNotFoundDiagnostic(
                    config_path=str(self.config_path()),
                    field_path=("project", "associations", "has_encodings"),
                    encodings_config_path=str(encodings_path),
                )
            ]
        result, encodings_diagnostics = self._load_config(
            ENCODINGS_PATH, encodings_pb2.EncodingsFile
        )
        if result is None:
            return None, encodings_diagnostics
        value_encodings: dict[str, list[str]] = {}
        # The index of the first association of each value quality and encoding.
        first_indexes: dict[tuple[str, str], int] = {}
        previous_value = ""
        for index, association in enumerate(result.encodings.value_encodings):
            field_path = ("encodings", "value_encodings", index)
            if association.value < previous_value:
                encodings_diagnostics.append(
                    diagnostics.UnsortedValueEncodingDiagnostic(
                        config_path=str(encodings_path),
                        field_path=(*field_path, "value"),
                        value=association.value,
                        previous_value=previous_value,
                    )
                )
            previous_value = association.value
            pair = (association.value, association.encoding)
            first_index = first_indexes.get(pair)
            if first_index is not None:
                encodings_diagnostics.append(
                    diagnostics.DuplicateValueEncodingDiagnostic(
                        config_path=str(encodings_path),
                        field_path=field_path,
                        value=association.value,
                        encoding=association.encoding,
                        first_field_path=(
                            "encodings",
                            "value_encodings",
                            first_index,
                        ),
                    )
                )
                continue
            first_indexes[pair] = index
            value_encodings.setdefault(association.value, []).append(
                association.encoding
            )
        return types.MappingProxyType(value_encodings), encodings_diagnostics
