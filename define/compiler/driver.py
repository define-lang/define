"""Compilation driver for the Define compiler.

The interfaces in this file deal with real OS Path objects,
compared to most of the rest of Define where the interfaces
expect and return PurePosixPath. This is essentially the interface
to the outside world's unvalidated command-line input, as well
as the interface that translates our internal error objects into
actual error strings.
"""

from __future__ import annotations

import abc
import enum
import sys
import typing
from dataclasses import dataclass
from typing import TextIO

from define.compiler import constants
from define.compiler.association_resolution import association_resolver
from define.compiler.codegen import generator
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator

if typing.TYPE_CHECKING:
    from pathlib import Path

    from define.compiler import ast
    from define.compiler.association_resolution import concrete_program
    from define.compiler.validator import validation_result


class DriverMode(enum.StrEnum):
    """Mode of operation for the driver."""

    VALIDATE = "validate"
    COMPILE = "compile"


class ExitCode(enum.IntEnum):
    """Exit codes returned by Driver.run()."""

    SUCCESS = 0
    ERROR = 1


class CompilerResult(abc.ABC):
    """A compiler result that can report errors."""

    @abc.abstractmethod
    def error_strings(self) -> list[str]:
        """Format errors for the command-line caller."""


@dataclass
class CompilerValidationResult(CompilerResult):
    """Result of completing every compiler validation stage."""

    program_validation: validation_result.ProgramValidationResult
    concrete_program: concrete_program.ConcreteProgram

    @typing.override
    def error_strings(self) -> list[str]:
        """Format errors from the detailed program validation data."""
        return self.program_validation.error_strings()


def validate_and_resolve_program(
    program: program_validator.StructurallyValidatedProgram,
    *,
    max_workers: int | None = None,
    allow_entry_action_occupied_implied_position_requirements: bool = False,
) -> CompilerValidationResult:
    """Run reference graph validation and association resolution on a structurally validated program, loading what resolution chooses, and produce the compiler result.

    allow_entry_action_occupied_implied_position_requirements exists only for
    validation tests of behavior that requires such a program.
    """
    program_result = program.result
    resolver = association_resolver.AssociationResolver(
        program_result.definition_results
    )
    # TODO: Make ReferenceGraphValidator return diagnostics instead of
    # adding them to definitions itself?
    reference_graph_validator.ReferenceGraphValidator(
        program_result.definition_order,
        program_result.definition_results,
        resolver,
        entry_action=program_result.entry_action,
        allow_entry_action_occupied_implied_position_requirements=(
            allow_entry_action_occupied_implied_position_requirements
        ),
    ).validate(max_workers=max_workers)
    program.load_associated(resolver.chosen_edges(), max_workers=max_workers)
    # The structural run's state, such as its resolver and loaded paths, would
    # otherwise be retained until code generation, but nothing loads more of
    # the program after this.
    del program
    resolver.resolve_encoding_operations()
    return CompilerValidationResult(
        program_validation=program_result,
        concrete_program=resolver.concrete_program(program_result.definition_order),
    )


@dataclass(frozen=True, slots=True)
class CompilationResult(CompilerResult):
    """Caller-facing result retained after compilation."""

    all_diagnostics: list[diagnostics.FormattableDiagnostic]
    entry_action: ast.ActionDefinition | None
    _error_strings: list[str]

    @classmethod
    def from_validation_result(
        cls, validation: CompilerValidationResult
    ) -> typing.Self:
        """Create the compact result retained after compilation."""
        program_validation = validation.program_validation
        return cls(
            all_diagnostics=program_validation.all_diagnostics,
            entry_action=program_validation.entry_action,
            _error_strings=program_validation.error_strings(),
        )

    def has_errors(self) -> bool:
        """Whether validation produced any diagnostics."""
        return bool(self.all_diagnostics)

    @typing.override
    def error_strings(self) -> list[str]:
        """Return errors formatted before detailed validation data was released."""
        return self._error_strings


class Driver:
    """Orchestrates the full Define compilation pipeline."""

    @staticmethod
    def validate_program(
        path: Path, *, max_threads: int | None = None
    ) -> CompilerValidationResult:
        """Validate a source file and all the files it references."""
        return validate_and_resolve_program(
            program_validator.validate_program(path, max_workers=max_threads),
            max_workers=max_threads,
        )

    @staticmethod
    def validate_source(
        source: str, *, max_threads: int | None = None
    ) -> CompilerValidationResult:
        """Validate source text in non-filesystem mode."""
        return validate_and_resolve_program(
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
            first_file.file_diagnostics.append(
                diagnostics.EntryPointNotConstructorDiagnostic(
                    location=first_file.definition_results[0].definition.location
                )
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
