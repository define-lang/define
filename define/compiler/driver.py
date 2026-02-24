"""Compilation driver for the Define compiler.

The interfaces in this file deal with real OS Path objects,
compared to most of the rest of Define where the interfaces
expect and return PurePosixPath. This is essentially the interface
to the outside world's unvalidated command-line input, as well
as the interface that translates our internal error objects into
actual error strings.
"""

import enum
import sys
from pathlib import Path, PurePosixPath
from typing import TextIO

from define.compiler import (
    exceptions,
    program_validator,
    validation_result,
)


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    def validate_program(self, path: Path) -> list[validation_result.ValidationResult]:
        """Compile a source file and all the files it references."""
        resolved_path = self._resolve_path(path)
        return program_validator.ProgramValidator().validate_program(path=resolved_path)

    @staticmethod
    def _resolve_path(path: Path) -> PurePosixPath:
        """Resolve a file path to be a POSIX path relative to the project root."""
        resolved = path
        if resolved.is_absolute():
            cwd = Path.cwd()
            try:
                resolved = resolved.relative_to(cwd)
            except ValueError:
                raise exceptions.AbsolutePathError(
                    input_path=path,
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
                    input_path=path,
                    resolved_path=resolved,
                    project_root=project_root,
                ) from None
        return PurePosixPath(resolved.as_posix())

    def run(
        self,
        path: Path,
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
            results = self.validate_program(path)
        except exceptions.DefineError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        had_errors = False
        for result in results:
            if result.exception is not None:
                print(str(result.exception), file=error_stream)
                had_errors = True
            if result.diagnostics:
                if result.source is None:
                    raise ValueError(
                        "result.source must be set when there are diagnostics"
                    )
                source_lines = result.source.splitlines()
                file_name = str(result.file_path)
                for diagnostic in result.diagnostics:
                    print(diagnostic.format(source_lines, file_name), file=error_stream)
                had_errors = True

        return ExitCode.ERROR if had_errors else ExitCode.SUCCESS
