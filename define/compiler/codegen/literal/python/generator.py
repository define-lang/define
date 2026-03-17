"""Python literal code generator for the Define compiler."""

from pathlib import Path

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_definition,
    action_statements,
    naming,
    position_definition,
    template_env,
)
from define.compiler.validator import reference_graph

_TEMPLATES_DIR = Path(__file__).parent
_COMPILED_DIR = _TEMPLATES_DIR / "templates.compiled"
_ENV = template_env.create_environment(_TEMPLATES_DIR, _COMPILED_DIR)
_MAIN_TEMPLATE = _ENV.get_template("main.j2")


class PythonLiteralCodeGenerator:
    """Generates literal Python code for a validated Define entry point."""

    def generate(
        self,
        graph: reference_graph.ReferenceGraph,
        entry_point: ast.PositionDefinition,
    ) -> str:
        """Generate Python code for the entry point position and its actions."""
        converter = naming.NameConverter()
        action_contexts: list[action_definition.ActionDefinitionContext] = []
        position_contexts: list[position_definition.PositionDefinitionContext] = []

        for definition in graph.dfs_postorder_from(entry_point):
            if isinstance(definition, ast.ActionDefinition):
                action_contexts.append(
                    action_definition.ActionDefinitionGenerator(
                        definition, converter
                    ).generate()
                )
            elif isinstance(definition, ast.PositionDefinition):
                position_contexts.append(
                    position_definition.PositionDefinitionGenerator(
                        definition, converter
                    ).generate()
                )

        has_action_body = any(ctx.has_body for ctx in action_contexts)
        has_init = any(ctx.has_init for ctx in position_contexts)
        entry_point_context = position_contexts[-1]

        return _MAIN_TEMPLATE.render(
            entry_point_class_name=entry_point_context.class_name,
            has_init=has_init,
            has_action_body=has_action_body,
            positions=position_contexts,
            actions=action_contexts,
            StatementKind=action_statements.StatementKind,
            ChainAccessor=action_statements.ChainAccessor,
        )
