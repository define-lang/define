"""Compilation driver for the Define compiler.

The interfaces in this file deal with real OS Path objects,
compared to most of the rest of Define where the interfaces
expect and return PurePosixPath. This is essentially the interface
to the outside world's unvalidated command-line input, as well
as the interface that translates our internal error objects into
actual error strings.
"""

from __future__ import annotations

import enum
import sys
import typing
from typing import TextIO

import msgspec

from define.compiler import constants, validation_pipeline
from define.compiler.codegen import generator
from define.compiler.errors import diagnostics
from define.compiler.validator.structural import program_validator

if typing.TYPE_CHECKING:
    from pathlib import Path


class DriverMode(enum.StrEnum):
    """Mode of operation for the driver."""

    VALIDATE = "validate"
    COMPILE = "compile"


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


class CompilationResult(msgspec.Struct, frozen=True):
    """Caller-facing result retained after compilation."""

    _sorted_diagnostics: list[diagnostics.FormattableDiagnostic]
    _error_strings: list[str]

    @classmethod
    def from_validation_result(
        cls, validation: validation_pipeline.CompilerValidationResult
    ) -> typing.Self:
        """Create the compact result retained after compilation."""
        program_validation = validation.program_validation
        return cls(
            _sorted_diagnostics=program_validation.sorted_diagnostics(),
            _error_strings=program_validation.error_strings(),
        )

    def has_errors(self) -> bool:
        """Whether validation produced any diagnostics."""
        return bool(self._sorted_diagnostics)

    def sorted_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Return every diagnostic, sorted by file and location, after those that have no location."""
        return self._sorted_diagnostics

    def error_strings(self) -> list[str]:
        """Return errors formatted before detailed validation data was released."""
        return self._error_strings


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    @staticmethod
    def validate_program(
        path: Path, *, max_threads: int | None = None
    ) -> validation_pipeline.CompilerValidationResult:
        """Validate a source file and all the files it references."""
        return validation_pipeline.validate_and_resolve_program(
            program_validator.validate_program(path, max_workers=max_threads),
            max_workers=max_threads,
        )

    @staticmethod
    def validate_source(
        source: str, *, max_threads: int | None = None
    ) -> validation_pipeline.CompilerValidationResult:
        """Validate source text in non-filesystem mode."""
        return validation_pipeline.validate_and_resolve_program(
            program_validator.validate_program_non_filesystem(
                source, max_workers=max_threads
            ),
            max_workers=max_threads,
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
        compiler_validation: validation_pipeline.CompilerValidationResult,
        output_dir: Path,
        *,
        trace_operations: bool,
        max_threads: int | None = None,
    ) -> CompilationResult:
        """Run code generation on an already-validated result."""
        program_validation = compiler_validation.program_validation
        if program_validation.has_errors():
            return CompilationResult.from_validation_result(compiler_validation)
        first_file = program_validation.file_results[0]
        entry_action = program_validation.entry_action
        if entry_action is None:
            program_validation.diagnostic_lists.append(
                [
                    diagnostics.EntryPointNotConstructorDiagnostic(
                        location=first_file.definition_results[0].definition.location
                    )
                ]
            )
            return CompilationResult.from_validation_result(compiler_validation)
        codegen_input = compiler_validation.concrete_program
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
            codegen_input,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
            max_workers=max_threads,
        )
        return compilation_result

    def run(
        self,
        path: Path | None = None,
        mode: DriverMode = DriverMode.VALIDATE,
        error_stream: TextIO | None = None,
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
            output_dir: Directory to write generated files into in compile mode.
                Required when mode is COMPILE.
            source: Source text to validate in non-filesystem mode instead of
                reading from path.
            max_threads: Maximum threads used by validation and code generation.
        """
        if error_stream is None:
            error_stream = sys.stderr
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

        all_error_strings = driver_result.error_strings()

        if all_error_strings:
            print(constants.ERROR_DIVIDER.join(all_error_strings), file=error_stream)

        return ExitCode.ERROR if all_error_strings else ExitCode.SUCCESS
