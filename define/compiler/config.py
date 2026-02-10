"""Project configuration loading and validation."""

from pathlib import Path

import protovalidate

from defcl.python import parser as defcl_parser
from define.compiler import exceptions
from define.config.project import config_pb2

CONFIG_PATH = Path(".define/project/config.defcl")

_DOCS_ROOT = "https://github.com/mkanat/define/define/docs"


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
    result = defcl_parser.parse_file(CONFIG_PATH, config_pb2.ProjectConfigFile)
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
        raise exceptions.ConfigValidationError(CONFIG_PATH, messages) from e
    return result
