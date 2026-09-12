"""Generate caller contributions to destruction contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    naming,
    operation_labels,
    position_expression,
    template_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import destruction_contract


@final
class DestructionContractsGenerator:
    """Build contract methods and classes for one action's invocations."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        codegen_input: validation_result.CodegenInput,
        positions: position_expression.PositionExpressionBuilder,
        contract_names: dict[destruction_contract.PropagatedDestruction, str],
        class_names: naming.LocalNameAllocator,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated contracts and generation inputs."""
        self._definition = definition
        self._converter = converter
        self._codegen_input = codegen_input
        self._positions = positions
        self._contract_names = contract_names
        self._class_names = class_names
        self._trace_operations = trace_operations

    def direct_contracts(
        self,
    ) -> dict[ast.SourceLocation, list[tuple[str, ast.PositionReference]]]:
        """Associate direct destructions with their contract methods and positions."""
        direct_contracts: dict[
            ast.SourceLocation, list[tuple[str, ast.PositionReference]]
        ] = {}
        for propagated, method_name in self._contract_names.items():
            fact = propagated.destruction_fact
            destruction = fact.destruction
            if destruction.destroying_action != self._definition.typed_name:
                continue
            direct_contracts.setdefault(destruction.location, []).append(
                (method_name, fact.destroyed_position_in_destroyer)
            )

        return direct_contracts

    def referenced_modules(
        self,
        connection: destruction_contract.DestructionConnection,
    ) -> Iterator[str]:
        """Yield modules used by one connection's contributions."""
        for _, position in self._forwarded_contributions(connection):
            if position is not None:
                yield from self._converter.referenced_modules(position)
        contribution = connection.contribution
        if contribution is None:
            return
        for action in contribution.destructors:
            yield from self._converter.referenced_modules(
                self._relative_to_contracted_particle(contribution, action)
            )
        for position in contribution.positions:
            yield from self._converter.referenced_modules(
                self._relative_to_contracted_particle(contribution, position)
            )

    def generate(
        self,
        location: ast.SourceLocation,
        action: ast.ActionReference,
    ) -> template_context.DestructionContractDefinition | None:
        """Generate the contribution class needed by an action invocation."""
        connections = self._codegen_input.destruction_connections.get(location, {}).get(
            action, ()
        )
        callee_names = self._converter.destruction_method_names(
            connection.callee_destruction for connection in connections
        )
        methods: list[template_context.DestructionContractMethod] = []
        forwarded_methods: list[str] = []
        for connection in connections:
            name = callee_names[connection.callee_destruction]
            forwarding = self._forwarded_contributions(connection)
            for kind in (
                template_context.StatementKind.RUN_CONTRACT_DESTRUCTORS,
                template_context.StatementKind.DESTROY_CONTRACT_CHILDREN,
            ):
                prefix = (
                    naming.RUN_DESTRUCTORS_PREFIX
                    if kind == template_context.StatementKind.RUN_CONTRACT_DESTRUCTORS
                    else naming.DESTROY_PREFIX
                )
                forwarded: list[template_context.ForwardedContribution] = []
                for caller_name, relative in forwarding:
                    method_name = prefix + caller_name
                    forwarded_methods.append(method_name)
                    forwarded.append(
                        template_context.ForwardedContribution(
                            method_name=method_name,
                            position=(
                                self._positions.build(
                                    relative,
                                    from_contract_particle=True,
                                )
                                if relative is not None
                                else None
                            ),
                        )
                    )
                statements = []
                if connection.contribution is not None:
                    if kind == template_context.StatementKind.RUN_CONTRACT_DESTRUCTORS:
                        statements = self._destructor_statements(
                            connection.contribution
                        )
                    else:
                        statements = self._destruction_statements(
                            connection.contribution
                        )
                if forwarded or statements:
                    methods.append(
                        template_context.DestructionContractMethod(
                            name=prefix + name,
                            forwarded=forwarded,
                            statements=statements,
                        )
                    )
        if not methods:
            return None
        callee = action.get_last_action()
        callee_class = self._converter.class_reference(callee)
        base = naming.ClassReference(
            class_name=self._converter.destruction_contract_class_name(
                callee.name_content.path.relative_path
            ),
            module_name=callee_class.module_name,
        )
        class_name = self._class_names.allocate(base.class_name)
        return template_context.DestructionContractDefinition(
            class_name=class_name,
            base=base,
            forwarded_methods=forwarded_methods,
            methods=methods,
        )

    def _forwarded_contributions(
        self,
        connection: destruction_contract.DestructionConnection,
    ) -> list[tuple[str, ast.PositionReference | None]]:
        forwarded: list[tuple[str, ast.PositionReference | None]] = []
        callee_position = connection.callee_destruction.destruction_fact.destroyed_position_in_destroyer
        for destruction in connection.forwarded_destructions:
            position = destruction.destruction_fact.destroyed_position_in_destroyer
            # A caller can discover a contracted child of a particle already
            # covered by the callee's contract. Forward through that callee
            # contribution, passing the child's actual particle.
            suffix = position.typed_names[len(callee_position.typed_names) :]
            relative = (
                ast.PositionReference(location=position.location, typed_names=suffix)
                if suffix
                else None
            )
            forwarded.append((self._contract_names[destruction], relative))
        return forwarded

    def _destructor_statements(
        self,
        contribution: destruction_contract.DestructionContribution,
    ) -> list[template_context.ActionStatementContext]:
        statements: list[template_context.ActionStatementContext] = []
        for destructor in contribution.destructors:
            relative = self._relative_to_contracted_particle(contribution, destructor)
            statements.append(
                template_context.RunActionContext(
                    position=self._positions.build(
                        relative,
                        from_contract_particle=True,
                    ),
                )
            )
        return statements

    def _destruction_statements(
        self,
        contribution: destruction_contract.DestructionContribution,
    ) -> list[template_context.ActionStatementContext]:
        statements: list[template_context.ActionStatementContext] = []
        for position in contribution.positions:
            relative = self._relative_to_contracted_particle(contribution, position)
            label = None
            if self._trace_operations:
                fact = contribution.destruction_fact
                full_position = (
                    fact.destroyed_position_in_destroyer.with_position_suffix(
                        *position.typed_names[
                            len(contribution.position_in_caller.typed_names) :
                        ]
                    )
                )
                label = operation_labels.operation_label(
                    fact.destruction.destroying_action,
                    template_context.StatementKind.DESTROY_PARTICLE,
                    full_position,
                )
            statements.append(
                template_context.DestroyParticleContext(
                    position=self._positions.build(
                        relative,
                        from_contract_particle=True,
                    ),
                    operation_label=label,
                )
            )
        return statements

    @staticmethod
    def _relative_to_contracted_particle(
        contribution: destruction_contract.DestructionContribution,
        reference: ast.ChainedName,
    ) -> ast.ChainedName:
        return type(reference)(
            location=reference.location,
            typed_names=reference.typed_names[
                len(contribution.position_in_caller.typed_names) :
            ],
        )
