"""Python literal code generator for the Define compiler."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

from define.compiler.codegen.literal.python import (
    action_statements,
    position_definition,
    template_env,
)
from define.compiler.validator import validation_result

if TYPE_CHECKING:
    from define.compiler import ast

_TEMPLATES_DIR = Path(__file__).parent
_COMPILED_DIR = _TEMPLATES_DIR / "templates.compiled"
_ENV = template_env.create_environment(_TEMPLATES_DIR, _COMPILED_DIR)
_MAIN_TEMPLATE = _ENV.get_template("main.j2")


class PythonLiteralCodeGenerator:
    """Generates literal Python code for a validated Define entry point."""

    def generate_entry_point(
        self, entry_point_result: validation_result.DefinitionValidationResult
    ) -> str:
        """Generate Python code for the entry point position."""
        definition = cast("ast.PositionDefinition", entry_point_result.definition)
        context = position_definition.PositionDefinitionGenerator(definition).generate()

        return _MAIN_TEMPLATE.render(
            class_name=context.class_name,
            typed_name=context.typed_name,
            has_init=context.has_init,
            statements=context.statements,
            StatementKind=action_statements.StatementKind,
        )
