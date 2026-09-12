"""Code generator for the Define compiler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen.literal.python import generator as python_generator

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler import ast
    from define.compiler.validator import validation_result


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        codegen_input: validation_result.CodegenInput,
        entry_action: ast.ActionDefinition,
        output_dir: Path,
        *,
        trace_operations: bool = False,
        max_workers: int | None = None,
    ):
        """Generate code for a validated Define program.

        Expects the direct-reference-first order from a validation with no errors.
        """
        # TODO: Diagnose entry-point requirements that cannot be satisfied
        # because no caller triggers the entry point.
        python_gen = python_generator.PythonLiteralCodeGenerator()
        python_gen.generate(
            codegen_input,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
            max_workers=max_workers,
        )
