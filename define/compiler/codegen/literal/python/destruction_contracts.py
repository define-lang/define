"""Generate caller contributions to destruction contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    known_destruction_work,
    naming,
    template_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler.codegen.literal.python import (
        position_expression,
    )
    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )


@final
class DestructionContractsGenerator:
    """Build contract methods and classes for one action's executions."""

    def __init__(
        self,
        converter: naming.NameConverter,
        positions: position_expression.PositionExpressionBuilder,
        contract_names: dict[destruction_contract.DestructionContract, str],
        class_names: naming.LocalNameAllocator,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated contracts and generation inputs."""
        self._converter = converter
        self._positions = positions
        self._contract_names = contract_names
        self._class_names = class_names
        self._work = known_destruction_work.KnownDestructionWorkGenerator(
            converter, positions, trace_operations=trace_operations
        )

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
        yield from self._work.referenced_modules(contribution.work)

    def generate(
        self,
        execution: codegen_input.ActionExecution,
    ) -> template_context.DestructionContractDefinition | None:
        """Generate the contribution class needed by an action execution."""
        connections = execution.destruction_connections
        callee_names = self._converter.destruction_method_names(
            connection.callee_destruction_contract for connection in connections
        )
        methods: list[template_context.DestructionContractMethod] = []
        forwarded_methods: list[str] = []
        for connection in connections:
            name = callee_names[connection.callee_destruction_contract]
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
                contribution = connection.contribution
                if contribution is not None:
                    if kind == template_context.StatementKind.RUN_CONTRACT_DESTRUCTORS:
                        statements = self._work.destructor_statements(
                            contribution.work, from_contract_particle=True
                        )
                    else:
                        statements = self._work.destroy_statements(
                            contribution.work,
                            connection.callee_destruction_contract.destruction_fact.destroying_definition.typed_name,
                            from_contract_particle=True,
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
        callee = execution.action.get_last_action()
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
        contribution = connection.contribution
        if contribution is None:
            return forwarded
        callee_position = connection.callee_destruction_contract.destruction_fact.destroyed_position_in_destroyer
        for caller_contract in contribution.destruction_contracts:
            position = caller_contract.destruction_fact.destroyed_position_in_destroyer
            # A caller can discover a contracted child of a particle already
            # covered by the callee's contract. Forward through that callee
            # contribution, passing the child's actual particle.
            suffix = position.typed_names[len(callee_position.typed_names) :]
            relative = (
                ast.PositionReference(location=position.location, typed_names=suffix)
                if suffix
                else None
            )
            forwarded.append((self._contract_names[caller_contract], relative))
        return forwarded
