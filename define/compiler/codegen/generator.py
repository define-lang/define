"""Code generator for the Define compiler."""

from pathlib import Path

from define.compiler import ast
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.graphs import reference_graph
from define.compiler.validator.reference_graph import operation_graph


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        graph: reference_graph.ReferenceGraph,
        operation_graphs: operation_graph.OperationGraphs,
        entry_action: ast.ActionDefinition,
        output_dir: Path,
    ):
        """Generate code for a validated Define program.

        Expects a ReferenceGraph from a ProgramValidationResult with no
        errors. Has undefined behavior (including potentially crashing)
        if the graph comes from a validation with errors.
        """
        # TODO: Diagnose entry-point requirements that cannot be satisfied
        # because no caller triggers the entry point.
        python_gen = python_generator.PythonLiteralCodeGenerator()
        python_gen.generate(graph, operation_graphs, entry_action, output_dir)
