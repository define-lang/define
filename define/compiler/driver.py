"""Compilation driver for the Define compiler."""

import enum
import os
import sys
from functools import cached_property
from pathlib import Path
from typing import TextIO

import lark

from defcl.python import parser as defcl_parser
from define.compiler import (
    diagnostics,
    parser,
    parser_exceptions,
    transformer,
    validator,
)
from define.config.project import config_pb2

_DOCS_ROOT = "https://github.com/mkanat/define/define/docs"
_CONFIG_PATH = Path(".define/project/config.defcl")


class DriverError(Exception):
    """Base class for errors raised by the driver."""


class NotProjectRootError(DriverError):
    """The current directory is not a Define project root."""


class PathError(DriverError):
    """A file path that does not fall under the project root."""

    label: str = "Path is outside the project root"
    input_path: Path
    resolved_path: Path
    project_root: Path

    def __init__(self, input_path: Path, resolved_path: Path, project_root: Path):
        """Initialize with the input path, resolved path, and project root."""
        self.input_path = input_path
        self.resolved_path = resolved_path
        self.project_root = project_root
        super().__init__(
            f"{self.label}: {input_path}\n"
            + f"  Resolved to: {resolved_path}\n"
            + f"  Project root: {project_root}\n"
            + f"For more information, see {_DOCS_ROOT}/project-root.md"
        )


class AbsolutePathError(PathError):
    """An absolute path does not fall under the project root."""

    label: str = "Absolute path is outside the project root"


class RelativePathError(PathError):
    """A relative path resolves to a location outside the project root."""

    label: str = "Relative path resolves to outside the project root"


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


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
    ) -> tuple[list[diagnostics.Diagnostic], str]:
        """Compile a single Define source file and return diagnostics and source text."""
        if not _CONFIG_PATH.exists():
            raise NotProjectRootError(
                f"Not a Define project root: {_CONFIG_PATH} not found.\n"
                + "The Define compiler must be run from a project root directory.\n"
                + f"A project root is any directory containing {_CONFIG_PATH}.\n"
                + f"For more information, see {_DOCS_ROOT}/project-root.md"
            )
        resolved_path = self._resolve_path(path)

        tree, source = self._parser.parse_file(resolved_path)
        program = transformer.DefineTransformer().transform(tree)
        file_path = str(resolved_path.with_suffix(""))
        diagnostics = validator.Validator(program, source).validate(
            file_path=file_path,
            expected_universe_name=self.project_config.project.universe_name or "",
        )
        return diagnostics, source

    @staticmethod
    def _resolve_path(path: os.PathLike[str]) -> Path:
        """Resolve a file path to be relative to the project root."""
        input_path = Path(path)
        resolved = input_path
        if resolved.is_absolute():
            cwd = Path.cwd()
            try:
                resolved = resolved.relative_to(cwd)
            except ValueError:
                raise AbsolutePathError(
                    input_path=input_path,
                    resolved_path=resolved,
                    project_root=cwd,
                ) from None
        if ".." in resolved.parts:
            project_root = Path.cwd().resolve()
            resolved = (project_root / resolved).resolve()
            try:
                resolved = resolved.relative_to(project_root)
            except ValueError:
                raise RelativePathError(
                    input_path=input_path,
                    resolved_path=resolved,
                    project_root=project_root,
                ) from None
        return resolved

    def run(
        self,
        path: os.PathLike[str],
        error_stream: TextIO | None = None,
    ) -> ExitCode:
        """Validate a Define source file and write any errors to the given stream.

        Args:
            path: Path to the .def file to validate.
            error_stream: Where to write error messages (syntax errors, diagnostics).
                Defaults to sys.stderr.

        Returns:
            ExitCode.SUCCESS if validation passed with no errors.
            ExitCode.ERROR if a syntax error occurred or validation diagnostics were reported.
        """
        if error_stream is None:
            error_stream = sys.stderr
        try:
            diagnostics_result, source = self.validate_file(path)
        except parser_exceptions.DefineSyntaxError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR
        except lark.exceptions.UnexpectedInput as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR
        except DriverError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        if diagnostics_result:
            source_lines = source.splitlines()
            for diagnostic in diagnostics_result:
                print(diagnostic.format(source_lines), file=error_stream)
            return ExitCode.ERROR

        return ExitCode.SUCCESS
