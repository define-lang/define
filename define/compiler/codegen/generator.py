"""Code generator for the Define compiler."""

from dataclasses import dataclass, field

from define.compiler import ast, diagnostics
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.validator import reference_graph


@dataclass
class GenerationResult:
    """Result of code generation."""

    code: str | None = None
    diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        graph: reference_graph.ReferenceGraph,
        entry_file_definitions: list[ast.QualityDefinition],
    ) -> GenerationResult:
        """Generate code for a validated Define program.

        Finds the entry point (a PositionDefinition) among the given
        definitions. Returns a GenerationResult with generated code on
        success, or diagnostics if entry point validation fails.

        Expects a ReferenceGraph from a ProgramValidationResult with no
        errors. Has undefined behavior (including potentially crashing)
        if the graph comes from a validation with errors.
        """
        entry_point = None
        for definition in entry_file_definitions:
            if isinstance(definition, ast.PositionDefinition):
                entry_point = definition

        if entry_point is None:
            if entry_file_definitions:
                position = entry_file_definitions[0].position
            else:
                position = ast.START_OF_FILE_POSITION
            return GenerationResult(
                diagnostics=[
                    diagnostics.EntryPointNotPositionDiagnostic(position=position)
                ]
            )

        python_gen = python_generator.PythonLiteralCodeGenerator()
        code = python_gen.generate(graph, entry_point)
        return GenerationResult(code=code)
