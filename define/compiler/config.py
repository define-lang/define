"""Project configuration loading and validation."""

from __future__ import annotations

import types
import typing
from pathlib import Path, PurePosixPath

import msgspec
import protovalidate
from google.protobuf import message

from defcl.python import loader as dcl_loader
from define.compiler import ast, constants
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.config.deps import local_pb2
from define.config.project import config_pb2
from source_rendering.python import rendering

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from defcl.python import errors as dcl_errors


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
    diagnostics: list[diagnostics.ConfigDiagnostic]


class ConfigLoader:
    """Loads and validates Define project configuration files."""

    _root: define_path.DefinePath

    def __init__(self, root: define_path.DefinePath):
        """Initialize with the project root path."""
        self._root = root

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
    ) -> ProjectRootConfig | list[diagnostics.ConfigDiagnostic]:
        config_path = self.config_path()
        if not self.is_project_root():
            location = ast.start_of_file_location(str(config_path))
            if self._root == constants.PROJECT_ROOT:
                return [
                    diagnostics.NotRunFromProjectRootDiagnostic(
                        location=location, config_path=str(config_path)
                    )
                ]
            return [
                diagnostics.SubRootNotProjectRootDiagnostic(
                    location=location,
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
                    location=ast.start_of_file_location(str(config_path)),
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
    ) -> M | list[diagnostics.ConfigDiagnostic]:
        """Load and validate a defcl config file, or return the diagnostics for why it is not valid."""
        path = (self._root / subpath).as_posix_path()
        loaded = dcl_loader.load_file(path, message_type)
        if loaded.message is None:
            found_diagnostics: list[diagnostics.ConfigDiagnostic] = []
            for dcl_diagnostic in loaded.diagnostics:
                found_diagnostics.append(_dcl_diagnostic(str(path), dcl_diagnostic))
            return found_diagnostics
        result = loaded.message
        try:
            protovalidate.validate(result)
        except protovalidate.ValidationError as e:
            messages: list[str] = []
            for violation in e.violations:
                field = violation.proto.field
                if field:
                    field_path = ".".join(elem.field_name for elem in field.elements)
                    messages.append(f"{field_path}: {violation.proto.message}")
                else:
                    # TODO: Add a real test for this once the config schema
                    # can produce a root-level/message-level protovalidate violation.
                    messages.append(violation.proto.message)
            return [
                diagnostics.InvalidConfigDiagnostic(
                    location=ast.start_of_file_location(str(path)),
                    violation_messages=messages,
                )
            ]
        return result

    def _local_deps_config(
        self,
    ) -> (
        types.MappingProxyType[str, define_path.DefinePathFromPosix]
        | list[diagnostics.ConfigDiagnostic]
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
        for dep in result.deps.local:
            if dep.universe_name in deps:
                return [
                    diagnostics.InvalidConfigDiagnostic(
                        location=ast.start_of_file_location(str(deps_path)),
                        violation_messages=[
                            f'deps.local: duplicate universe_name "{dep.universe_name}"'
                        ],
                    )
                ]
            deps[dep.universe_name] = define_path.DefinePathFromPosix(
                PurePosixPath(dep.path)
            )
        return types.MappingProxyType(deps)


def _dcl_diagnostic(
    path: str, dcl_diagnostic: dcl_errors.DclDiagnostic
) -> diagnostics.ConfigDclDiagnostic:
    location = dcl_diagnostic.location
    return diagnostics.ConfigDclDiagnostic(
        location=rendering.SourceLocation(
            line=location.line,
            column=location.column,
            end_line=location.end_line,
            end_column=location.end_column,
            file_path=path,
        ),
        dcl_diagnostic=dcl_diagnostic,
    )
