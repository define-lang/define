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
    constants,
    diagnostics,
    exceptions,
    overall_stats,
    parser,
)
from define.compiler.codegen import generator
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import (
    operation_graph,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator


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
    operation_graphs: operation_graph.OperationGraphs


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    def __init__(self, parser_instance: parser.Parser | None = None):
        """Initialize the driver.

        If parser_instance is provided, it will be used instead of
        constructing a new one. This is only a performance optimization
        that avoids reconstructing the Lark grammar on each compilation.
        """
        self._parser_instance: parser.Parser | None = parser_instance

    def validate_program(self, path: Path) -> DriverResult:
        """Validate a source file and all the files it references."""
        resolved_path = self._resolve_path(path)
        pv = program_validator.ProgramStructuralValidator(self._parser_instance)
        return self._assemble_result(pv.validate_program(path=resolved_path))

    def validate_source(self, source: str) -> DriverResult:
        """Validate source text in non-filesystem mode."""
        pv = program_validator.ProgramStructuralValidator(self._parser_instance)
        return self._assemble_result(pv.validate_program_non_filesystem(source))

    def _assemble_result(
        self, program_result: validation_result.ProgramValidationResult
    ) -> DriverResult:
        """Run reference-graph validation and wrap the program result."""
        # TODO: Make ReferenceGraphValidator return diagnostics instead of
        # adding them to definitions itself?
        reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
            program_result.reference_graph,
            program_result.definition_results,
        ).validate()
        # TODO: Retain only the validation data needed after this point so the
        # remaining compiler state can be released before code generation.
        return DriverResult(
            result=program_result,
            overall_stats=overall_stats.calculate_overall_stats(
                program_result.file_results,
                program_result.config_loading_time_ns,
            ),
            operation_graphs=reference_graph_result.operation_graphs,
        )

    def compile_program(
        self,
        path: Path,
        output_dir: Path,
        *,
        trace_operations: bool = False,
    ) -> DriverResult:
        """Validate and then run code generation on a source file."""
        return self._generate_code(
            self.validate_program(path),
            output_dir,
            trace_operations=trace_operations,
        )

    def compile_source(
        self,
        source: str,
        output_dir: Path,
        *,
        trace_operations: bool = False,
    ) -> DriverResult:
        """Validate source text in non-filesystem mode and run code generation."""
        return self._generate_code(
            self.validate_source(source),
            output_dir,
            trace_operations=trace_operations,
        )

    @staticmethod
    def _generate_code(
        driver_result: DriverResult,
        output_dir: Path,
        *,
        trace_operations: bool = False,
    ) -> DriverResult:
        """Run code generation on an already-validated result."""
        if driver_result.result.has_errors():
            return driver_result
        program_result = driver_result.result
        first_file = program_result.file_results[0]
        entry_action = program_result.entry_action
        if entry_action is None:
            first_file.add_file_diagnostic(
                diagnostics.EntryPointNotConstructorDiagnostic(
                    location=first_file.definition_results[0].definition.location
                )
            )
            return driver_result
        codegen = generator.CodeGenerator()
        codegen.generate(
            program_result.reference_graph,
            driver_result.operation_graphs,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
        )
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
        path: Path | None = None,
        mode: DriverMode = DriverMode.VALIDATE,
        error_stream: TextIO | None = None,
        stats_stream: TextIO | None = None,
        stats_mode: overall_stats.StatsMode = overall_stats.StatsMode.OVERALL,
        output_dir: Path | None = None,
        source: str | None = None,
    ) -> ExitCode:
        """Validate (and optionally compile) a Define source file or source text.

        Args:
            path: Path to the .dfn file to validate. Required unless source is given.
            mode: Whether to only validate or also compile.
            error_stream: Where to write error messages (syntax errors, diagnostics).
                Defaults to sys.stderr.
            stats_stream: Where to write timing statistics.
                If None, no stats are printed.
            stats_mode: Level of detail for stats output.
            output_dir: Directory to write generated files into in compile mode.
                Required when mode is COMPILE.
            source: Source text to validate in non-filesystem mode instead of
                reading from path.
        """
        if error_stream is None:
            error_stream = sys.stderr
        try:
            if mode == DriverMode.COMPILE:
                if output_dir is None:
                    raise ValueError("output_dir is required when mode is COMPILE")
                if source is not None:
                    driver_result = self.compile_source(source, output_dir)
                else:
                    if path is None:
                        raise ValueError("path is required when source is not given")
                    driver_result = self.compile_program(path, output_dir)
            elif source is not None:
                driver_result = self.validate_source(source)
            else:
                if path is None:
                    raise ValueError("path is required when source is not given")
                driver_result = self.validate_program(path)
        except exceptions.DefineError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        all_error_strings: list[str] = []
        for result in driver_result.result.file_results:
            if result.exception is not None:
                all_error_strings.append(str(result.exception))
            if result.diagnostics:
                if result.source is None:
                    raise ValueError(
                        "result.source must be set when there are diagnostics"
                    )
                source_lines = result.source.splitlines()
                for diagnostic in result.diagnostics:
                    all_error_strings.append(diagnostic.format(source_lines))

        if all_error_strings:
            print(constants.ERROR_DIVIDER.join(all_error_strings), file=error_stream)

        if stats_stream is not None:
            stats_output = overall_stats.format_stats(
                driver_result.overall_stats,
                driver_result.result.file_results,
                stats_mode,
            )
            print(stats_output, file=stats_stream, end="")

        return ExitCode.ERROR if all_error_strings else ExitCode.SUCCESS
