"""Compilation driver for the Define compiler.

The interfaces in this file deal with real OS Path objects,
compared to most of the rest of Define where the interfaces
expect and return PurePosixPath. This is essentially the interface
to the outside world's unvalidated command-line input, as well
as the interface that translates our internal error objects into
actual error strings.
"""

import abc
import collections.abc
import enum
import sys
import typing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TextIO

from define.compiler import (
    ast,
    constants,
    diagnostics,
    exceptions,
    overall_stats,
    parser,
)
from define.compiler.codegen import generator
from define.compiler.graphs import reference_graph_executor
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


def _error_strings(
    file_results: list[validation_result.FileValidationResult],
) -> list[str]:
    """Format every exception and diagnostic for the command-line caller."""
    error_strings: list[str] = []
    for result in file_results:
        if result.exception is not None:
            error_strings.append(str(result.exception))
        if result.diagnostics:
            if result.source_lines is None:
                raise ValueError(
                    "result.source_lines must be set when there are diagnostics"
                )
            for diagnostic in result.diagnostics:
                error_strings.append(diagnostic.format(result.source_lines))
    return error_strings


class CompilerResult(abc.ABC):
    """A compiler result that can report errors and validation timings."""

    overall_stats: overall_stats.OverallStats
    operation_graphs: operation_graph.OperationGraphs

    @abc.abstractmethod
    def error_strings(self) -> list[str]:
        """Format errors for the command-line caller."""

    @abc.abstractmethod
    def file_timing_results(
        self,
    ) -> collections.abc.Sequence[overall_stats.FileTiming]:
        """Provide the retained per-file validation timings."""


@dataclass
class CompilerValidationResult(CompilerResult):
    """Result of completing every compiler validation stage."""

    program_validation: validation_result.ProgramValidationResult
    definition_order: reference_graph_executor.ReferenceGraphOrder
    overall_stats: overall_stats.OverallStats
    operation_graphs: operation_graph.OperationGraphs

    @typing.override
    def error_strings(self) -> list[str]:
        """Format errors from the detailed program validation data."""
        return _error_strings(self.program_validation.file_results)

    @typing.override
    def file_timing_results(
        self,
    ) -> collections.abc.Sequence[overall_stats.FileTiming]:
        """Provide the per-file validation timings."""
        return [
            overall_stats.FileTiming(result.file_path, result.stats)
            for result in self.program_validation.file_results
        ]


@dataclass(frozen=True, slots=True)
class CompilationResult(CompilerResult):
    """Caller-facing result retained after compilation."""

    all_diagnostics: list[diagnostics.Diagnostic]
    all_exceptions: list[validation_result.AnyValidationException]
    entry_action: ast.ActionDefinition | None
    _error_strings: list[str]
    file_timings: list[overall_stats.FileTiming]
    overall_stats: overall_stats.OverallStats
    operation_graphs: operation_graph.OperationGraphs

    @classmethod
    def from_validation_result(
        cls, validation: CompilerValidationResult
    ) -> typing.Self:
        """Create the compact result retained after compilation."""
        program_validation = validation.program_validation
        return cls(
            all_diagnostics=program_validation.all_diagnostics,
            all_exceptions=program_validation.all_exceptions,
            entry_action=program_validation.entry_action,
            _error_strings=_error_strings(program_validation.file_results),
            file_timings=[
                overall_stats.FileTiming(file_result.file_path, file_result.stats)
                for file_result in program_validation.file_results
            ],
            overall_stats=validation.overall_stats,
            operation_graphs=validation.operation_graphs,
        )

    def has_errors(self) -> bool:
        """Whether validation produced exceptions or diagnostics."""
        return bool(self.all_exceptions or self.all_diagnostics)

    @typing.override
    def error_strings(self) -> list[str]:
        """Return errors formatted before detailed validation data was released."""
        return self._error_strings

    @typing.override
    def file_timing_results(
        self,
    ) -> collections.abc.Sequence[overall_stats.FileTiming]:
        """Provide the retained per-file validation timings."""
        return self.file_timings


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    def __init__(self, parser_instance: parser.Parser | None = None):
        """Initialize the driver.

        If parser_instance is provided, it will be used instead of
        constructing a new one. This is only a performance optimization
        that avoids reconstructing the Lark grammar on each compilation.
        """
        self._parser_instance: parser.Parser | None = parser_instance

    def validate_program(
        self, path: Path, *, max_threads: int | None = None
    ) -> CompilerValidationResult:
        """Validate a source file and all the files it references."""
        resolved_path = self._resolve_path(path)
        structural_validator = program_validator.ProgramStructuralValidator(
            self._parser_instance
        )
        program_validation = structural_validator.validate_program(
            path=resolved_path, max_workers=max_threads
        )
        # The result owns the completed data but not the PathTracker or other
        # coordinator state, so release the coordinator before the next stage.
        del structural_validator
        return self._complete_validation(
            program_validation,
            max_threads=max_threads,
        )

    def validate_source(
        self, source: str, *, max_threads: int | None = None
    ) -> CompilerValidationResult:
        """Validate source text in non-filesystem mode."""
        structural_validator = program_validator.ProgramStructuralValidator(
            self._parser_instance
        )
        program_validation = structural_validator.validate_program_non_filesystem(
            source, max_workers=max_threads
        )
        # The result owns the completed data but not the PathTracker or other
        # coordinator state, so release the coordinator before the next stage.
        del structural_validator
        return self._complete_validation(
            program_validation,
            max_threads=max_threads,
        )

    def _complete_validation(
        self,
        program_result: validation_result.ProgramValidationResult,
        *,
        max_threads: int | None = None,
    ) -> CompilerValidationResult:
        """Run reference graph validation and produce the compiler result."""
        # TODO: Make ReferenceGraphValidator return diagnostics instead of
        # adding them to definitions itself?
        reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
            program_result.reference_graph,
            program_result.definition_results,
        ).validate(max_workers=max_threads)
        return CompilerValidationResult(
            program_validation=program_result,
            definition_order=reference_graph_result.definition_order,
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
        max_threads: int | None = None,
    ) -> CompilationResult:
        """Validate and then run code generation on a source file."""
        return self._generate_code(
            self.validate_program(path, max_threads=max_threads),
            output_dir,
            trace_operations=trace_operations,
            max_threads=max_threads,
        )

    def compile_source(
        self,
        source: str,
        output_dir: Path,
        *,
        trace_operations: bool = False,
        max_threads: int | None = None,
    ) -> CompilationResult:
        """Validate source text in non-filesystem mode and run code generation."""
        return self._generate_code(
            self.validate_source(source, max_threads=max_threads),
            output_dir,
            trace_operations=trace_operations,
            max_threads=max_threads,
        )

    @staticmethod
    def _generate_code(
        compiler_validation: CompilerValidationResult,
        output_dir: Path,
        *,
        trace_operations: bool = False,
        max_threads: int | None = None,
    ) -> CompilationResult:
        """Run code generation on an already-validated result."""
        program_validation = compiler_validation.program_validation
        if program_validation.has_errors():
            return CompilationResult.from_validation_result(compiler_validation)
        first_file = program_validation.file_results[0]
        entry_action = program_validation.entry_action
        if entry_action is None:
            first_file.add_file_diagnostic(
                diagnostics.EntryPointNotConstructorDiagnostic(
                    location=first_file.definition_results[0].definition.location
                )
            )
            return CompilationResult.from_validation_result(compiler_validation)
        definition_order = compiler_validation.definition_order
        operation_graphs = compiler_validation.operation_graphs
        compilation_result = CompilationResult.from_validation_result(
            compiler_validation
        )
        # These locals would otherwise retain validation-only data throughout
        # codegen, when its memory can instead be reclaimed during generation.
        del first_file
        del program_validation
        del compiler_validation
        codegen = generator.CodeGenerator()
        codegen.generate(
            definition_order,
            operation_graphs,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
            max_workers=max_threads,
        )
        return compilation_result

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
        max_threads: int | None = None,
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
            max_threads: Maximum threads used by validation and code generation.
        """
        if error_stream is None:
            error_stream = sys.stderr
        try:
            if mode == DriverMode.COMPILE:
                if output_dir is None:
                    raise ValueError("output_dir is required when mode is COMPILE")
                if source is not None:
                    driver_result = self.compile_source(
                        source, output_dir, max_threads=max_threads
                    )
                else:
                    if path is None:
                        raise ValueError("path is required when source is not given")
                    driver_result = self.compile_program(
                        path, output_dir, max_threads=max_threads
                    )
            elif source is not None:
                driver_result = self.validate_source(source, max_threads=max_threads)
            else:
                if path is None:
                    raise ValueError("path is required when source is not given")
                driver_result = self.validate_program(path, max_threads=max_threads)
        except exceptions.DefineError as e:
            print(str(e), file=error_stream)
            return ExitCode.ERROR

        all_error_strings = driver_result.error_strings()

        if all_error_strings:
            print(constants.ERROR_DIVIDER.join(all_error_strings), file=error_stream)

        if stats_stream is not None:
            stats_output = overall_stats.format_stats(
                driver_result.overall_stats,
                driver_result.file_timing_results(),
                stats_mode,
            )
            print(stats_output, file=stats_stream, end="")

        return ExitCode.ERROR if all_error_strings else ExitCode.SUCCESS
