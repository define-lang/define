"""Python literal code generator for the Define compiler."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

from define.compiler.codegen.literal.python import (
    action_definition,
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
        self,
        entry_point_result: validation_result.DefinitionValidationResult,
        action_results: list[validation_result.DefinitionValidationResult],
    ) -> str:
        """Generate Python code for the entry point position and its actions."""
        definition = cast("ast.PositionDefinition", entry_point_result.definition)
        pos_context = position_definition.PositionDefinitionGenerator(
            definition
        ).generate()

        action_contexts: list[action_definition.ActionDefinitionContext] = []
        for result in action_results:
            action_def = cast("ast.ActionDefinition", result.definition)
            action_contexts.append(
                action_definition.ActionDefinitionGenerator(action_def).generate()
            )

        has_action_body = any(ctx.has_body for ctx in action_contexts)

        return _MAIN_TEMPLATE.render(
            class_name=pos_context.class_name,
            typed_name=pos_context.typed_name,
            has_init=pos_context.has_init,
            has_action_body=has_action_body,
            statements=pos_context.statements,
            actions=action_contexts,
            StatementKind=action_statements.StatementKind,
            ChainAccessor=action_statements.ChainAccessor,
        )
