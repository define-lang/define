"""Project configuration loading and validation."""

import types
from pathlib import Path, PurePosixPath

import protovalidate
from google.protobuf import message

from defcl.python import parser as defcl_parser
from define.compiler import exceptions
from define.config.deps import local_pb2
from define.config.project import config_pb2

CONFIG_PATH = Path(".define/project/config.defcl")
LOCAL_DEPS_PATH = Path(".define/deps/local.defcl")

_DOCS_ROOT = "https://github.com/mkanat/define/define/docs"


def _load_config[M: message.Message](path: Path, message_type: type[M]) -> M:
    """Load and validate a defcl config file."""
    result = defcl_parser.parse_file(path, message_type)
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


def assert_is_project_root() -> None:
    """Raise NotProjectRootError if the current directory is not a project root."""
    if not CONFIG_PATH.exists():
        raise exceptions.NotProjectRootError(
            f"Not a Define project root: {CONFIG_PATH} not found.\n"
            + "The Define compiler must be run from a project root directory.\n"
            + f"A project root is any directory containing {CONFIG_PATH}.\n"
            + f"For more information, see {_DOCS_ROOT}/project-root.md"
        )


def project_config() -> config_pb2.ProjectConfigFile:
    """Load and validate the project configuration from the current directory."""
    return _load_config(CONFIG_PATH, config_pb2.ProjectConfigFile)


_EMPTY_DEPS: types.MappingProxyType[str, PurePosixPath] = types.MappingProxyType({})


def local_deps_config() -> types.MappingProxyType[str, PurePosixPath]:
    """Load and validate the local dependency overrides from the current directory.

    Returns an immutable mapping from universe name to relative path.
    """
    if not LOCAL_DEPS_PATH.exists():
        return _EMPTY_DEPS
    result = _load_config(LOCAL_DEPS_PATH, local_pb2.LocalDepsFile)
    deps: dict[str, PurePosixPath] = {}
    for dep in result.deps.local:
        if dep.universe_name in deps:
            raise exceptions.ConfigValidationError(
                LOCAL_DEPS_PATH,
                [f'deps.local: duplicate universe_name "{dep.universe_name}"'],
            )
        deps[dep.universe_name] = PurePosixPath(dep.path)
    return types.MappingProxyType(deps)
