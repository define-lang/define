"""Generate the statements for the part of a destruction that one action knows about."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler.codegen.literal.python import (
    naming,
    operation_labels,
    template_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast
    from define.compiler.codegen.literal.python import (
        position_expression,
    )
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )


@final
class KnownDestructionWorkGenerator:
    """Generate the statements for a KnownDestructionWork."""

    def __init__(
        self,
        converter: naming.NameConverter,
        positions: position_expression.PositionExpressionBuilder,
        *,
        trace_operations: bool,
    ):
        """Initialize from the generation inputs of the action whose statements these are."""
        self._converter = converter
        self._positions = positions
        self._trace_operations = trace_operations

    def referenced_modules(
        self, work: destruction_contract.KnownDestructionWork
    ) -> Iterator[str]:
        """Yield the modules the statements for ``work`` use."""
        for destructor in work.destructors:
            yield from self._converter.referenced_modules(destructor)
        for reference in work.guaranteed_particle_destructors:
            yield from self._converter.referenced_modules(reference.position)
            yield self._converter.class_reference(reference.action).module_name
        for destroyed in work.positions:
            yield from self._converter.referenced_modules(destroyed.position)

    def destructor_statements(
        self,
        work: destruction_contract.KnownDestructionWork,
        *,
        from_contract_particle: bool,
    ) -> list[template_context.ActionStatementContext]:
        """Return the statements that run the Destructors ``work`` runs, in an action's body or, with ``from_contract_particle``, in a Destruction Contract method."""
        statements: list[template_context.ActionStatementContext] = []
        for destructor in work.destructors:
            # Destructors preserve caller-provided contracted particles, so
            # their invocations have no incoming destruction contributions.
            statements.append(
                template_context.RunActionContext(
                    position=self._positions.build(
                        destructor, from_contract_particle=from_contract_particle
                    )
                )
            )
        for reference in work.guaranteed_particle_destructors:
            statements.append(
                self.run_guaranteed_particle_destructors_statement(
                    reference, from_contract_particle=from_contract_particle
                )
            )
        return statements

    def run_guaranteed_particle_destructors_statement(
        self,
        reference: destruction_contract.RunGuaranteedParticleDestructors,
        *,
        from_contract_particle: bool,
    ) -> template_context.RunGuaranteedParticleDestructorsContext:
        """Return the statement that calls the method ``reference`` names, in an action's body or, with ``from_contract_particle``, in a method that takes a particle."""
        return template_context.RunGuaranteedParticleDestructorsContext(
            action=self._converter.class_reference(reference.action),
            method_name=naming.NameConverter.guaranteed_particle_destructors_method_name(
                reference.position_in_action
            ),
            position=self._positions.build(
                reference.position, from_contract_particle=from_contract_particle
            ),
        )

    def destroy_statements(
        self,
        work: destruction_contract.KnownDestructionWork,
        destroying_action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        *,
        from_contract_particle: bool,
    ) -> list[template_context.ActionStatementContext]:
        """Return the statements that destroy the particles ``work`` destroys, in an action's body or, with ``from_contract_particle``, in a Destruction Contract method."""
        statements: list[template_context.ActionStatementContext] = []
        for destroyed in work.positions:
            label = None
            if self._trace_operations:
                label = operation_labels.operation_label(
                    destroying_action,
                    template_context.StatementKind.DESTROY_PARTICLE,
                    destroyed.position_in_destroyer,
                )
            statements.append(
                template_context.DestroyParticleContext(
                    position=self._positions.build(
                        destroyed.position,
                        from_contract_particle=from_contract_particle,
                    ),
                    operation_label=label,
                )
            )
        return statements
