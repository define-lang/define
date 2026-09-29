"""Action context for literal Python code generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from define.compiler.codegen.literal.python import template_context, value_types

if TYPE_CHECKING:
    from collections.abc import Collection

    from define.compiler.codegen.literal.python import naming


class ActionDefinitionContext(msgspec.Struct):
    """Template context for an action and its sequential statements."""

    class_name: str
    module_name: str
    statements: list[template_context.ActionStatementContext]
    interface_positions: list[template_context.InterfacePositionContext]
    implied_qualities: list[naming.ClassReference]
    trace_operations: bool
    imports: list[str]
    contract_class_name: str | None
    contract_methods: Collection[str]
    contract_definitions: list[template_context.DestructionContractDefinition]

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.implied_qualities)

    @property
    def needs_never(self) -> bool:
        """Whether the generated class has positions whose particles have no value."""
        for interface_position in self.interface_positions:
            if interface_position.value_type == value_types.NO_VALUE:
                return True
        for statement in self.statements:
            if (
                isinstance(statement, template_context.LocalPositionContext)
                and statement.value_type == value_types.NO_VALUE
            ):
                return True
        return False
