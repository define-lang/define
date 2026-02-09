"""Compilation driver for the Define compiler."""

import os
from functools import cached_property
from pathlib import Path

from defcl.python import parser as defcl_parser
from define.compiler import parser, transformer, validator
from define.config.project import config_pb2

_DOCS_ROOT = "https://github.com/mkanat/define/define/docs"
_CONFIG_PATH = Path(".define/project/config.defcl")


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    _parser: parser.Parser

    def __init__(self):
        """Initialize the driver."""
        self._parser = parser.Parser()

    @cached_property
    def project_config(self) -> config_pb2.ProjectConfigFile:
        """Load and return the project configuration."""
        return defcl_parser.parse_file(_CONFIG_PATH, config_pb2.ProjectConfigFile)

    def validate_file(
        self, path: os.PathLike[str]
    ) -> tuple[list[validator.Diagnostic], str]:
        """Compile a single Define source file and return diagnostics and source text."""
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Not a Define project root: {_CONFIG_PATH} not found.\n"
                + "The Define compiler must be run from a project root directory.\n"
                + f"A project root is any directory containing {_CONFIG_PATH}.\n"
                + f"For more information, see {_DOCS_ROOT}/project-root.md"
            )
        tree, source = self._parser.parse_file(path)
        program = transformer.DefineTransformer().transform(tree)
        file_path = str(Path(path).with_suffix(""))
        diagnostics = validator.Validator(program, source).validate(
            file_path=file_path,
            expected_universe_name=self.project_config.project.universe_name or "",
        )
        return diagnostics, source
