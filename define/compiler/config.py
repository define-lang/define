"""Project configuration loading and validation."""

import types
from pathlib import Path, PurePosixPath

import protovalidate
from google.protobuf import message

from defcl.python import exceptions as dcl_exceptions
from defcl.python import parser as defcl_parser
from define.compiler import exceptions
from define.config.deps import local_pb2
from define.config.project import config_pb2

CONFIG_PATH = PurePosixPath(".define/project/config.defcl")
LOCAL_DEPS_PATH = PurePosixPath(".define/deps/local.defcl")

_EMPTY_DEPS: types.MappingProxyType[str, PurePosixPath] = types.MappingProxyType({})


class ConfigLoader:
    """Loads and validates Define project configuration files."""

    _root: PurePosixPath

    def __init__(self, root: PurePosixPath):
        """Initialize with the project root path."""
        self._root = root

    def _load_config[M: message.Message](
        self, subpath: PurePosixPath, message_type: type[M]
    ) -> M:
        """Load and validate a defcl config file."""
        path = Path(self._root / subpath)
        try:
            result = defcl_parser.parse_file(path, message_type)
        except dcl_exceptions.DclSyntaxError as e:
            raise exceptions.ConfigSyntaxError(e) from e
        try:
            protovalidate.validate(result)
        except protovalidate.ValidationError as e:
            messages: list[str] = []
            for violation in e.violations:
                field_path = ".".join(
                    elem.field_name for elem in violation.proto.field.elements
                )
                if field_path:
                    messages.append(f"{field_path}: {violation.proto.message}")
                else:
                    messages.append(violation.proto.message)
            raise exceptions.ConfigValidationError(path, messages) from e
        return result

    def assert_is_project_root(self) -> None:
        """Raise NotProjectRootError if the root is not a project root."""
        config_path = Path(self._root / CONFIG_PATH)
        if not config_path.exists():
            raise exceptions.NotProjectRootError(config_path)

    def project_config(self) -> config_pb2.ProjectConfigFile:
        """Load and validate the project configuration."""
        return self._load_config(CONFIG_PATH, config_pb2.ProjectConfigFile)

    def local_deps_config(self) -> types.MappingProxyType[str, PurePosixPath]:
        """Load and validate the local dependency overrides.

        Returns an immutable mapping from universe name to relative path.
        """
        deps_path = Path(self._root / LOCAL_DEPS_PATH)
        if not deps_path.exists():
            return _EMPTY_DEPS
        result = self._load_config(LOCAL_DEPS_PATH, local_pb2.LocalDepsFile)
        deps: dict[str, PurePosixPath] = {}
        for dep in result.deps.local:
            if dep.universe_name in deps:
                raise exceptions.ConfigValidationError(
                    deps_path,
                    [f'deps.local: duplicate universe_name "{dep.universe_name}"'],
                )
            deps[dep.universe_name] = PurePosixPath(dep.path)
        return types.MappingProxyType(deps)
