"""Action context for literal Python code generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler.codegen.literal.python import naming, template_context


@dataclass
class ActionDefinitionContext:
    """Template context for an action and its sequential statements."""

    class_name: str
    module_name: str
    statements: list[template_context.ActionStatementContext]
    interface_positions: list[template_context.InterfacePositionContext]
    implied_qualities: list[naming.ClassReference]
    trace_operations: bool
    imports: list[str]

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.implied_qualities)
