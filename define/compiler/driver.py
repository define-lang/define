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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TextIO

from define.compiler import (
    exceptions,
    overall_stats,
)
from define.compiler.codegen import generator
from define.compiler.validator import program_validator, validation_result


class DriverMode(enum.StrEnum):
    """Mode of operation for the driver."""

    VALIDATE = "validate"
    COMPILE = "compile"


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


@dataclass
class DriverResult:
    """Full result of a compilation run."""

    result: validation_result.ProgramValidationResult
    overall_stats: overall_stats.OverallStats


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    def validate_program(self, path: Path) -> DriverResult:
        """Validate a source file and all the files it references."""
        resolved_path = self._resolve_path(path)
        pv = program_validator.ProgramValidator()
        program_result = pv.validate_program(path=resolved_path)
        return DriverResult(
            result=program_result,
            overall_stats=overall_stats.calculate_overall_stats(
                program_result.file_results, program_result.config_loading_time_ns
            ),
        )

    def compile_program(self, path: Path, output_dir: Path) -> DriverResult:
        """Validate and then run code generation on a source file."""
        driver_result = self.validate_program(path)
        if driver_result.result.has_errors():
            return driver_result
        program_result = driver_result.result
        first_file = program_result.file_results[0]
        entry_file_definitions = [r.definition for r in first_file.definition_results]
        codegen = generator.CodeGenerator()
        gen_diagnostics = codegen.generate(
            program_result.reference_graph,
            entry_file_definitions,
            output_dir,
            entry_point_file_path=first_file.file_path,
        )
        for diagnostic in gen_diagnostics:
            first_file.add_file_diagnostic(diagnostic)
        return driver_result

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
        mode: DriverMode = DriverMode.VALIDATE,
        error_stream: TextIO | None = None,
        stats_stream: TextIO | None = None,
        stats_mode: overall_stats.StatsMode = overall_stats.StatsMode.OVERALL,
        output_dir: Path | None = None,
    ) -> ExitCode:
        """Validate (and optionally compile) a Define source file.

        Args:
            path: Path to the .def file to validate.
            mode: Whether to only validate or also compile.
            error_stream: Where to write error messages (syntax errors, diagnostics).
                Defaults to sys.stderr.
            stats_stream: Where to write timing statistics.
                If None, no stats are printed.
            stats_mode: Level of detail for stats output.
            output_dir: Directory to write generated files into in compile mode.
                Required when mode is COMPILE.
        """
        if error_stream is None:
            error_stream = sys.stderr
        try:
            if mode == DriverMode.COMPILE:
                if output_dir is None:
                    raise ValueError("output_dir is required when mode is COMPILE")
                driver_result = self.compile_program(path, output_dir)
            else:
                driver_result = self.validate_program(path)
        except exceptions.DefineError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        had_errors = False
        for result in driver_result.result.file_results:
            if result.exception is not None:
                print(str(result.exception), file=error_stream)
                had_errors = True
            if result.diagnostics:
                if result.source is None:
                    raise ValueError(
                        "result.source must be set when there are diagnostics"
                    )
                source_lines = result.source.splitlines()
                for diagnostic in result.diagnostics:
                    print(diagnostic.format(source_lines), file=error_stream)
                had_errors = True

        if stats_stream is not None:
            stats_output = overall_stats.format_stats(
                driver_result.overall_stats,
                driver_result.result.file_results,
                stats_mode,
            )
            print(stats_output, file=stats_stream, end="")

        return ExitCode.ERROR if had_errors else ExitCode.SUCCESS
