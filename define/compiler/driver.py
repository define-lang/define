"""Compilation driver for the Define compiler."""

import enum
import os
import sys
from functools import cached_property
from pathlib import Path
from typing import TextIO

import lark

from define.compiler import (
    config,
    exceptions,
    parser_exceptions,
    validator,
)
from define.config.project import config_pb2


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    @cached_property
    def project_config(self) -> config_pb2.ProjectConfigFile:
        """Load and return the project configuration."""
        return config.project_config()

    def validate_file(self, path: os.PathLike[str]) -> validator.ValidationResult:
        """Compile a single Define source file and return diagnostics and source text."""
        config.assert_is_project_root()
        resolved_path = self._resolve_path(path)
        return validator.Validator().parse_and_validate_file(
            path=resolved_path,
            expected_universe_name=self.project_config.project.universe_name or "",
        )

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
                raise exceptions.AbsolutePathError(
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
                raise exceptions.RelativePathError(
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
            result = self.validate_file(path)
        except parser_exceptions.DefineSyntaxError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR
        except lark.exceptions.UnexpectedInput as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR
        except exceptions.DriverError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        if result.diagnostics:
            source_lines = result.source.splitlines()
            for diagnostic in result.diagnostics:
                print(diagnostic.format(source_lines), file=error_stream)
            return ExitCode.ERROR

        return ExitCode.SUCCESS
