from define.compiler.codegen.literal.python import (
    action_context,
    naming,
    template_context,
)

def render_module_header(
    imports: list[str],
    typing_names: list[str],
    needs_runtime_import: bool,
) -> str: ...
def render_position(definition: template_context.PositionDefinitionContext) -> str: ...
def render_action(definition: action_context.ActionDefinitionContext) -> str: ...
def render_encoding_operation(
    definition: template_context.EncodingOperationDefinitionContext,
) -> str: ...
def render_entry_point(
    entry_reference: naming.ClassReference, trace_operations: bool
) -> str: ...
