"""Build Python position expressions from validated references."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler import ast
from define.compiler.codegen.literal.python import naming, template_context

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet


@final
class PositionExpressionBuilder:
    """Resolve position names and reference chains for one action."""

    def __init__(
        self,
        converter: naming.NameConverter,
        local_position_names: dict[str, str],
        interface_position_names: AbstractSet[str],
    ):
        """Initialize from the action's position names."""
        self._converter = converter
        self._local_position_names = local_position_names
        self._interface_position_names = interface_position_names

    def build(
        self,
        position_reference: ast.ChainedName,
        *,
        from_contract_particle: bool = False,
    ) -> template_context.PositionExpr:
        """Build an expression that accesses a Position or Action Reference."""
        first = position_reference.typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            if first.source_typed_name in self._interface_position_names:
                local_position_name = None
                chain_elements: list[template_context.ChainElement] = [
                    template_context.InterfacePositionChainElement(
                        previous_name_type=ast.NameType.ACTION,
                        name_type=first.name_type,
                        typed_name=first.source_typed_name,
                    )
                ]
            else:
                local_position_name = self._local_position_names[
                    first.name_content.name
                ]
                chain_elements = []
        else:
            local_position_name = None
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
            local_position_name=local_position_name,
            chain_elements=chain_elements,
            from_contract_particle=from_contract_particle,
        )
