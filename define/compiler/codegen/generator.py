"""Code generator for the Define compiler."""

from pathlib import Path, PurePosixPath

from define.compiler import ast, diagnostics
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.validator import reference_graph


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        graph: reference_graph.ReferenceGraph,
        entry_file_definitions: list[ast.QualityDefinition],
        output_dir: Path,
        entry_point_file_path: PurePosixPath | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Generate code for a validated Define program.

        Finds the entry point (a PositionDefinition) among the given
        definitions. Returns diagnostics if entry point validation fails,
        or an empty list on success.

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
                position = ast.start_of_file_position(file_path=entry_point_file_path)
            return [diagnostics.EntryPointNotPositionDiagnostic(position=position)]

        python_gen = python_generator.PythonLiteralCodeGenerator()
        python_gen.generate(graph, entry_point, output_dir)
        return []
