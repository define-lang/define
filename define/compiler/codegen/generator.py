"""Code generator for the Define compiler."""

from collections.abc import Sequence
from pathlib import Path

from define.compiler import ast
from define.compiler.codegen.literal.python import generator as python_generator
from define.compiler.validator.reference_graph import operation_graph


class CodeGenerator:
    """Generates code for Define programs."""

    def generate(
        self,
        definitions: Sequence[ast.QualityDefinition],
        operation_graphs: operation_graph.OperationGraphs,
        entry_action: ast.ActionDefinition,
        output_dir: Path,
        *,
        trace_operations: bool = False,
    ):
        """Generate code for a validated Define program.

        Expects definitions in direct-callee-first order from a validation with
        no errors.
        """
        # TODO: Diagnose entry-point requirements that cannot be satisfied
        # because no caller triggers the entry point.
        # TODO: Parallelize code generation across definitions in the same way
        # that reference graph validation parallelizes definition traversal.
        python_gen = python_generator.PythonLiteralCodeGenerator()
        python_gen.generate(
            definitions,
            operation_graphs,
            entry_action,
            output_dir,
            trace_operations=trace_operations,
        )
