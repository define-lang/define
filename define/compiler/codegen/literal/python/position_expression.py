"""Build Python position expressions from validated references."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler import ast, name_types
from define.compiler.codegen.literal.python import renderer

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from define.compiler.codegen.literal.python import naming


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
        value_type: str | None = None,
    ) -> renderer.PositionExpression:
        """Build an expression that accesses a Position or Action Reference.

        ``value_type`` is the Python type of the referenced position's value,
        when the expression uses that value.
        """
        typed_names = position_reference.typed_names
        last_index = len(typed_names) - 1
        first = typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            if first.source_typed_name in self._interface_position_names:
                local_position_name = None
                chain_elements: list[renderer.ChainElement] = [
                    renderer.ChainElement.PositionFromAction(
                        typed_name=first.source_typed_name,
                        value_type=value_type if last_index == 0 else None,
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
                _global_quality_element(
                    None, first.name_type, self._converter.class_reference(first)
                )
            ]
        for i, elem in enumerate(typed_names[1:]):
            prev = typed_names[i]
            if isinstance(elem, ast.GlobalTypedNameReference):
                chain_element = _global_quality_element(
                    prev.name_type,
                    elem.name_type,
                    self._converter.class_reference(elem),
                )
            else:
                chain_element = renderer.ChainElement.PositionFromAction(
                    typed_name=elem.full_typed_name,
                    value_type=value_type if i + 1 == last_index else None,
                )
            chain_elements.append(chain_element)
        return renderer.PositionExpression(
            local_position_name=local_position_name,
            chain_elements=chain_elements,
            from_contract_particle=from_contract_particle,
        )


def _global_quality_element(
    previous_name_type: name_types.NameType | None,
    name_type: name_types.NameType,
    class_reference: renderer.ClassReference,
) -> renderer.ChainElement:
    """Return the chain element for a global quality, given the name type of what comes before it, if anything does."""
    if previous_name_type is None:
        if name_type == name_types.NameType.ACTION:
            return renderer.ChainElement.ImpliedAction(class_reference=class_reference)
        return renderer.ChainElement.ImpliedPosition(class_reference=class_reference)
    if name_type == name_types.NameType.ACTION:
        return renderer.ChainElement.ActionFromPosition(class_reference=class_reference)
    return renderer.ChainElement.PositionFromPosition(class_reference=class_reference)
