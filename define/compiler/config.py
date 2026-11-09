"""Project configuration loading and validation."""

from __future__ import annotations

import types
import typing
from pathlib import Path, PurePosixPath

import msgspec
import protovalidate
from google.protobuf import message

from defcl.python import loader as dcl_loader
from define.compiler import constants
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.config.deps import local_pb2
from define.config.project import config_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from source_rendering.python import rendering


CONFIG_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/project/config.defcl")
)
LOCAL_DEPS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/deps/local.defcl")
)

_EMPTY_DEPS: types.MappingProxyType[str, define_path.DefinePathFromPosix] = (
    types.MappingProxyType({})
)


def universe_needs_configuration(fqun: str) -> bool:
    """Whether a project must configure a universe as a sub-root before referencing it."""
    # TODO: Remove this once the Define Standard Library exists.
    return fqun != constants.STANDARD_UNIVERSE


class ProjectRootConfig(msgspec.Struct):
    """Resolved project configuration for a project root."""

    fqun: str
    sub_roots: Mapping[str, define_path.DefinePath]


class RootConfigResult(msgspec.Struct, frozen=True):
    """A project root's resolved configuration, or the diagnostics that keep it from loading."""

    # None when there are diagnostics.
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
        self, expected_fqun: str | None = None
    ) -> RootConfigResult:
        """Load and resolve this root's own configuration.

        If expected_fqun is given, the universe name that this root's own
        config declares must match it.
        """
        loaded = self._load_project_root_config(expected_fqun)
        if isinstance(loaded, list):
            return RootConfigResult(root_config=None, diagnostics=loaded)
        return RootConfigResult(root_config=loaded, diagnostics=[])

    def _load_project_root_config(
        self, expected_fqun: str | None
    ) -> ProjectRootConfig | list[diagnostics.FormattableDiagnostic]:
        config_path = self.config_path()
        if not self.is_project_root():
            if self._root == constants.PROJECT_ROOT:
                return [
                    diagnostics.NotRunFromProjectRootDiagnostic(
                        config_path=str(config_path)
                    )
                ]
            return [
                diagnostics.SubRootNotProjectRootDiagnostic(
                    config_path=str(config_path),
                    sub_root_path=str(self._root),
                )
            ]
        project_config = self._load_config(CONFIG_PATH, config_pb2.ProjectConfigFile)
        if isinstance(project_config, list):
            return project_config
        fqun = project_config.project.universe_name or ""
        if expected_fqun and fqun != expected_fqun:
            return [
                diagnostics.SubRootFqunMismatchDiagnostic(
                    config_path=str(config_path),
                    field_path=("project", "universe_name"),
                    expected_fqun=expected_fqun,
                    actual_fqun=fqun,
                    sub_root_path=str(self._root),
                )
            ]
        sub_roots = self._local_deps_config()
        if isinstance(sub_roots, list):
            return sub_roots
        return ProjectRootConfig(fqun=fqun, sub_roots=sub_roots)

    def _load_config[M: message.Message](
        self,
        subpath: define_path.DefinePath,
        message_type: type[M],
    ) -> M | list[diagnostics.FormattableDiagnostic]:
        """Load and validate a defcl config file, or return the diagnostics for why it is not valid."""
        path = (self._root / subpath).as_posix_path()
        loaded = dcl_loader.load_file(str(path), message_type, self._source_map)
        if loaded.message is None:
            return list(loaded.diagnostics)
        result = loaded.message
        try:
            protovalidate.validate(result)
        except protovalidate.ValidationError as e:
            violation_diagnostics: list[diagnostics.FormattableDiagnostic] = []
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
                violation_diagnostics.append(
                    diagnostics.ConfigViolationDiagnostic(
                        config_path=str(path),
                        field_path=tuple(field_path),
                        violation_message=violation.proto.message,
                    )
                )
            return violation_diagnostics
        return result

    def _local_deps_config(
        self,
    ) -> (
        types.MappingProxyType[str, define_path.DefinePathFromPosix]
        | list[diagnostics.FormattableDiagnostic]
    ):
        """Load and validate the local dependency overrides, or return the diagnostics for why they are not valid.

        Returns an immutable mapping from universe name to relative path.
        """
        deps_path = (self._root / LOCAL_DEPS_PATH).as_posix_path()
        if not Path(deps_path).exists():
            return _EMPTY_DEPS
        result = self._load_config(LOCAL_DEPS_PATH, local_pb2.LocalDepsFile)
        if isinstance(result, list):
            return result
        deps: dict[str, define_path.DefinePathFromPosix] = {}
        # The index of the local dependency that first declares each universe.
        first_indices: dict[str, int] = {}
        for index, dep in enumerate(result.deps.local):
            first_index = first_indices.get(dep.universe_name)
            if first_index is not None:
                return [
                    diagnostics.DuplicateLocalDependencyDiagnostic(
                        config_path=str(deps_path),
                        field_path=("deps", "local", index, "universe_name"),
                        universe_name=dep.universe_name,
                        first_field_path=(
                            "deps",
                            "local",
                            first_index,
                            "universe_name",
                        ),
                    )
                ]
            first_indices[dep.universe_name] = index
            deps[dep.universe_name] = define_path.DefinePathFromPosix(
                PurePosixPath(dep.path)
            )
        return types.MappingProxyType(deps)
