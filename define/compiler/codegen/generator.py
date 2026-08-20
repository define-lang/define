"""Code generator for the Define compiler."""

from pathlib import Path

from define.compiler import ast
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.graphs import reference_graph_executor
from define.compiler.validator.reference_graph import operation_graph


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        definition_order: reference_graph_executor.ReferenceGraphOrder,
        operation_graphs: operation_graph.OperationGraphs,
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
            definition_order,
            operation_graphs,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
            max_workers=max_workers,
        )
