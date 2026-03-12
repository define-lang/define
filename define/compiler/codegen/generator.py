"""Code generator for the Define compiler."""

from define.compiler import ast, diagnostics
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.validator import validation_result


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self, program_result: validation_result.ProgramValidationResult
    ) -> str | None:
        """Generate code for a validated Define program.

        Returns generated code on success, or None if entry point
        validation fails (diagnostics are added to the result).

        Expects a ProgramValidationResult with no errors. Has undefined
        behavior (including potentially crashing) if passed in a
        ProgramValidationResult with errors.
        """
        first_result = program_result.file_results[0]
        entry_point_result = None
        for def_result in first_result.definition_results:
            if isinstance(def_result.definition, ast.PositionDefinition):
                entry_point_result = def_result

        if not entry_point_result:
            if first_result.definition_results:
                position = first_result.definition_results[0].definition.position
            else:
                position = ast.SourcePosition(
                    line=1, column=1, end_line=1, end_column=1
                )
            first_result.add_file_diagnostic(
                diagnostics.EntryPointNotPositionDiagnostic(position=position)
            )
            return None

        python_gen = python_generator.PythonLiteralCodeGenerator()
        return python_gen.generate_entry_point(entry_point_result)
