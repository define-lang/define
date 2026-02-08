"""Loader for .define/project/config.defcl project configuration files."""

import pathlib

from defcl.python import parser
from define.config.project import config_pb2


def load_project_config(
    project_root: pathlib.Path,
) -> config_pb2.ProjectConfigFile:
    """Load .define/project/config.defcl from a project root."""
    config_path = project_root / ".define" / "project" / "config.defcl"
    return parser.parse_file(config_path, config_pb2.ProjectConfigFile)
