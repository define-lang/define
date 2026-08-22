"""Python code generator for action statements blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.codegen.literal.python import naming, template_context
from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_model,
)

if TYPE_CHECKING:
    from define.compiler.codegen import action_plan


class ActionStatementsGenerator:
    """Build template data for an action's statements and Action References."""

    _block: ast.ActionStatementsBlock
    _converter: naming.NameConverter
    _defining_typed_name: ast.GlobalTypedNameInDefinition
    _interface_position_names: set[str]
    _local_position_names: dict[str, str]
    _destruction_position_names: dict[
        operation_graph_model.DestructionFragmentDestroyNode, str
    ]
    _destruction_connection_by_operation: dict[
        operation_graph_model.DestructionFragmentDestroyNode,
        action_plan.DestructionConnection,
    ]
    _destruction_connection_names: dict[action_plan.DestructionConnection, str]
    _operation_labels: operation_graph_labeler.OperationGraphLabeler | None

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        local_position_names: dict[str, str],
        destruction_position_names: dict[
            operation_graph_model.DestructionFragmentDestroyNode, str
        ],
        destruction_connection_by_operation: dict[
            operation_graph_model.DestructionFragmentDestroyNode,
            action_plan.DestructionConnection,
        ],
        destruction_connection_names: dict[action_plan.DestructionConnection, str],
        operation_labels: operation_graph_labeler.OperationGraphLabeler | None,
    ):
        """Initialize with the action definition to generate data for.

        ``operation_labels`` is present for traced generation and absent for
        ordinary generation.
        """
        self._block = definition.action_statements
        self._converter = converter
        self._defining_typed_name = definition.typed_name
        self._interface_position_names = {
            interface_position.typed_name.source_typed_name
            for interface_position in definition.interface_positions
        }
        self._local_position_names = local_position_names
        self._destruction_position_names = destruction_position_names
        self._destruction_connection_by_operation = destruction_connection_by_operation
        self._destruction_connection_names = destruction_connection_names
        self._operation_labels = operation_labels

    def build_local_positions(self) -> list[template_context.ActionStatementContext]:
        """Build template data for the action's local position definitions."""
        positions: list[template_context.ActionStatementContext] = []
        for statement in self._block.statements:
            if not isinstance(statement, ast.LocalPositionDefinition):
                continue
            positions.append(
                template_context.ActionStatementContext(
                    kind=template_context.StatementKind.LOCAL_POSITION,
                    local_position_member_name=self._local_position_names[
                        statement.typed_name.name_content.name
                    ],
                    local_typed_name=statement.typed_name.source_typed_name,
                    constraints=self._converter.constraints_to_class_references(
                        statement.constraints,
                    ),
                )
            )
        return positions

    def build_operation(
        self,
        node: operation_graph_model.PositionOperationNode,
    ) -> template_context.ActionStatementContext:
        """Build template data for one operation-graph node."""
        local_label = (
            self._operation_labels.operation_label(
                self._defining_typed_name,
                node,
            )
            if self._operation_labels is not None
            else None
        )
        match node:
            case operation_graph_model.CreateNode():
                return template_context.ActionStatementContext(
                    kind=template_context.StatementKind.CREATE_PARTICLE,
                    position=self.build_position(node.target),
                    operation_label=local_label,
                )
            case operation_graph_model.DestroyNode():
                destruction_connection_name = None
                if isinstance(
                    node, operation_graph_model.DestructionFragmentDestroyNode
                ):
                    destruction_connection_name = self._destruction_connection_names[
                        self._destruction_connection_by_operation[node]
                    ]
                    position = template_context.PositionExpr(
                        local_position_member_name=self._destruction_position_names[
                            node
                        ],
                        chain_elements=[],
                    )
                else:
                    position = self.build_position(node.target)
                return template_context.ActionStatementContext(
                    kind=template_context.StatementKind.DESTROY_PARTICLE,
                    position=position,
                    operation_label=local_label,
                    destruction_connection_name=destruction_connection_name,
                )
            case operation_graph_model.MoveNode():
                return template_context.ActionStatementContext(
                    kind=template_context.StatementKind.MOVE_PARTICLE,
                    position=self.build_position(node.source),
                    to_position=self.build_position(node.target),
                    operation_label=local_label,
                )
            case _:
                raise TypeError(
                    f"unsupported Particle Operation: {type(node).__name__}"
                )

    def build_action(
        self,
        action_reference: ast.ActionReference,
    ) -> template_context.PositionExpr:
        """Build an expression that accesses a triggered action."""
        return self.build_position(action_reference)

    def build_position(
        self,
        position_reference: ast.PositionReference | ast.ActionReference,
    ) -> template_context.PositionExpr:
        """Build an expression that accesses a Position or Action Reference."""
        first = position_reference.typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            if first.source_typed_name in self._interface_position_names:
                local_position_member_name = None
                chain_elements: list[template_context.ChainElement] = [
                    template_context.InterfacePositionChainElement(
                        previous_name_type=ast.NameType.ACTION,
                        name_type=first.name_type,
                        typed_name=first.source_typed_name,
                    )
                ]
            else:
                local_position_member_name = self._local_position_names[
                    first.name_content.name
                ]
                chain_elements = []
        else:
            local_position_member_name = None
            chain_elements = [
                template_context.GlobalQualityChainElement(
                    previous_name_type=None,
                    name_type=first.name_type,
                    class_reference=self._converter.class_reference(first),
                )
            ]
        for i, elem in enumerate(position_reference.typed_names[1:]):
            prev = position_reference.typed_names[i]
            if isinstance(elem, ast.GlobalTypedNameReference):
                chain_element: template_context.ChainElement = (
                    template_context.GlobalQualityChainElement(
                        previous_name_type=prev.name_type,
                        name_type=elem.name_type,
                        class_reference=self._converter.class_reference(elem),
                    )
                )
            else:
                chain_element = template_context.InterfacePositionChainElement(
                    previous_name_type=prev.name_type,
                    name_type=elem.name_type,
                    typed_name=elem.full_typed_name,
                )
            chain_elements.append(chain_element)
        return template_context.PositionExpr(
            local_position_member_name=local_position_member_name,
            chain_elements=chain_elements,
        )
