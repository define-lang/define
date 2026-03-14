"""Python literal code generator for the Define compiler."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

from define.compiler.codegen.literal.python import (
    position_definition,
)
from define.compiler.validator import validation_result

if TYPE_CHECKING:
    from define.compiler import ast

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "python"
_MAIN_TEMPLATE = (_TEMPLATES_DIR / "main.txt").read_text()


class PythonLiteralCodeGenerator:
    """Generates literal Python code for a validated Define entry point."""

    def generate_entry_point(
        self, entry_point_result: validation_result.DefinitionValidationResult
    ) -> str:
        """Generate Python code for the entry point position."""
        definition = cast("ast.PositionDefinition", entry_point_result.definition)
        result = position_definition.PositionDefinitionGenerator(definition).generate()

        typing_import = f"\nfrom typing import {', '.join(result.typing_imports)}\n"

        return _MAIN_TEMPLATE.format(
            typing_import=typing_import,
            class_name=result.class_name,
            class_body=result.class_body,
        )
