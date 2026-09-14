from define.compiler.codegen.literal.python import (
    action_context,
    naming,
    template_context,
)

def render_position(definition: template_context.PositionDefinitionContext) -> str: ...
def render_action(definition: action_context.ActionDefinitionContext) -> str: ...
def render_entry_point(
    entry_reference: naming.ClassReference, trace_operations: bool
) -> str: ...
