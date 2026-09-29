"""Python code generation for sequential action statements."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import msgspec

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    destruction_contracts,
    naming,
    operation_labels,
    position_expression,
    template_context,
    value_types,
)
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from define.compiler.validator.reference_graph import destruction_contract


class GeneratedActionStatements(msgspec.Struct):
    """Generated statements and the imports and contract classes they require."""

    statements: list[template_context.ActionStatementContext]
    imports: set[str]
    contract_definitions: list[template_context.DestructionContractDefinition]


@final
class ActionStatementsGenerator:
    """Build template data in the order statements execute."""

    def __init__(
        self,
        action_input: codegen_input.ActionCodegenInput,
        converter: naming.NameConverter,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated definitions and known destructions."""
        self._action_input = action_input
        self._converter = converter
        self._trace_operations = trace_operations
        self._class_names = naming.LocalNameAllocator()

    def _collect_imports(
        self,
        contracts: destruction_contracts.DestructionContractsGenerator,
    ) -> set[str]:
        """Collect modules needed by statements and their triggered actions."""
        modules: set[str] = set()
        for step in self._action_input.steps:
            match step:
                case ast.LocalPositionDefinition():
                    for constraint in self._converter.constraints_to_class_references(
                        step.constraints
                    ):
                        modules.add(constraint.module_name)
                case ast.CreateParticleStatement():
                    modules.update(
                        self._converter.referenced_modules(step.target_position)
                    )
                case ast.MoveParticleStatement():
                    modules.update(
                        self._converter.referenced_modules(step.source_position)
                    )
                    modules.update(
                        self._converter.referenced_modules(step.target_position)
                    )
                case codegen_input.LiteralValueSetting():
                    modules.update(
                        self._converter.referenced_modules(step.target_position)
                    )
                case codegen_input.PositionValueSetting():
                    modules.update(
                        self._converter.referenced_modules(step.target_position)
                    )
                    modules.update(
                        self._converter.referenced_modules(step.source_position)
                    )
                case codegen_input.ActionExecution():
                    modules.update(self._converter.referenced_modules(step.action))
                    for connection in step.destruction_connections:
                        modules.update(contracts.referenced_modules(connection))
                case codegen_input.Destruction():
                    for action in step.destructors:
                        modules.update(self._converter.referenced_modules(action))
                    for position in step.positions:
                        modules.update(self._converter.referenced_modules(position))
                case codegen_input.ActionOperationExecution():
                    modules.add(
                        self._converter.function_reference(
                            step.encoding_operation
                        ).module_name
                    )
                    for argument in step.arguments:
                        if not isinstance(argument.looking_at, str):
                            modules.update(
                                self._converter.referenced_modules(argument.looking_at)
                            )
        return modules

    def generate(self) -> GeneratedActionStatements:
        """Generate statements and automatic destruction in execution order."""
        local_position_names: dict[str, str] = {}
        positions = position_expression.PositionExpressionBuilder(
            self._converter,
            local_position_names,
            self._action_input.definition.interface_positions_by_name.keys(),
        )
        propagated_destructions = self._action_input.propagated_destructions
        contract_names = self._converter.destruction_method_names(
            propagated_destructions
        )
        action_path = (
            self._action_input.definition.typed_name.name_content.path.relative_path
        )
        # Contract classes share the action's Python module, so their names
        # must not collide with the action class or its own contract class.
        _ = self._class_names.allocate(
            self._converter.class_name(self._action_input.definition.typed_name)
        )
        if propagated_destructions:
            _ = self._class_names.allocate(
                self._converter.destruction_contract_class_name(action_path)
            )
        contracts = destruction_contracts.DestructionContractsGenerator(
            self._converter,
            positions,
            contract_names,
            self._class_names,
            trace_operations=self._trace_operations,
        )
        contract_definitions: list[template_context.DestructionContractDefinition] = []
        names = naming.LocalNameAllocator()
        # Collect imports before allocating local names: Python locals shadow
        # imported module names throughout the method, even before assignment.
        # Collecting imports as we generate statements would discover conflicts
        # after earlier local names have already been allocated.
        imports = self._collect_imports(contracts)
        names.reserve_module_first_names(imports)
        statements: list[template_context.ActionStatementContext] = []
        for statement in self._action_input.steps:
            match statement:
                case ast.LocalPositionDefinition():
                    source_name = statement.typed_name.name_content.name
                    name = names.allocate(source_name)
                    local_position_names[source_name] = name
                    statements.append(
                        template_context.LocalPositionContext(
                            name=name,
                            local_typed_name=statement.typed_name.source_typed_name,
                            constraints=self._converter.constraints_to_class_references(
                                statement.constraints
                            ),
                            value_type=value_types.constrained_python_value_type(
                                statement.constraints
                            ),
                        )
                    )
                case codegen_input.Destruction():
                    statements.extend(
                        self._destruction(statement, positions, contract_names)
                    )
                case ast.CreateParticleStatement():
                    statements.append(
                        template_context.CreateParticleContext(
                            position=positions.build(statement.target_position),
                            operation_label=self._operation_label(
                                template_context.StatementKind.CREATE_PARTICLE,
                                statement.target_position,
                            ),
                        )
                    )
                case ast.MoveParticleStatement():
                    statements.append(
                        template_context.MoveParticleContext(
                            position=positions.build(statement.source_position),
                            to_position=positions.build(statement.target_position),
                            operation_label=self._operation_label(
                                template_context.StatementKind.MOVE_PARTICLE,
                                statement.source_position,
                                statement.target_position,
                            ),
                        )
                    )
                case codegen_input.LiteralValueSetting():
                    statements.append(
                        template_context.SetValueContext(
                            position=positions.build(
                                statement.target_position,
                                value_type=value_types.python_value_type(
                                    statement.value_type
                                ),
                            ),
                            value=statement.value,
                            operation_label=self._literal_value_label(
                                statement.target_position, statement.value
                            ),
                        )
                    )
                case codegen_input.PositionValueSetting():
                    value_type = value_types.python_value_type(statement.value_type)
                    statements.append(
                        template_context.SetValueFromContext(
                            position=positions.build(
                                statement.target_position, value_type=value_type
                            ),
                            source_position=positions.build(
                                statement.source_position, value_type=value_type
                            ),
                            operation_label=self._operation_label(
                                template_context.StatementKind.SET_VALUE_FROM,
                                statement.target_position,
                                statement.source_position,
                            ),
                        )
                    )
                case codegen_input.ActionExecution():
                    execution, contract = self._run(statement, positions, contracts)
                    statements.append(execution)
                    if contract is not None:
                        contract_definitions.append(contract)
                case codegen_input.ActionOperationExecution():
                    statements.append(
                        self._execute_operation(statement, positions, names)
                    )
        return GeneratedActionStatements(
            statements=statements,
            imports=imports,
            contract_definitions=contract_definitions,
        )

    def _destruction(
        self,
        destruction: codegen_input.Destruction,
        positions: position_expression.PositionExpressionBuilder,
        contract_names: dict[destruction_contract.PropagatedDestruction, str],
    ) -> list[template_context.ActionStatementContext]:
        # TODO: Investigate running each particle's Destructors, completing each
        # child's destruction, then destroying the particle. This could avoid
        # keeping independent sibling particles alive until all Destructors finish,
        # but contracts would need to preserve contributions per particle rather
        # than flattening them into separate Destructor and destruction lists.
        statements: list[template_context.ActionStatementContext] = []
        for action in destruction.destructors:
            # Destructors preserve caller-provided contracted particles, so
            # their invocations have no incoming destruction contributions.
            statements.append(
                template_context.RunActionContext(position=positions.build(action))
            )
        for context_type, prefix in (
            (
                template_context.RunContractDestructorsContext,
                naming.RUN_DESTRUCTORS_PREFIX,
            ),
            (template_context.DestroyContractChildrenContext, naming.DESTROY_PREFIX),
        ):
            for propagated in destruction.contract_destructions:
                name = contract_names[propagated]
                position = propagated.destruction_fact.destroyed_position_in_destroyer
                statements.append(
                    context_type(
                        position=positions.build(position),
                        contract_method=prefix + name,
                    )
                )
        for position in destruction.positions:
            statements.append(
                template_context.DestroyParticleContext(
                    position=positions.build(position),
                    operation_label=self._operation_label(
                        template_context.StatementKind.DESTROY_PARTICLE, position
                    ),
                )
            )
        return statements

    def _run(
        self,
        execution: codegen_input.ActionExecution,
        positions: position_expression.PositionExpressionBuilder,
        contracts: destruction_contracts.DestructionContractsGenerator,
    ) -> tuple[
        template_context.RunActionContext,
        template_context.DestructionContractDefinition | None,
    ]:
        contract = contracts.generate(execution)
        argument = (
            template_context.DestructionContractArgument(
                class_name=contract.class_name,
                forwarded_methods=contract.forwarded_methods,
            )
            if contract is not None
            else None
        )
        return template_context.RunActionContext(
            position=positions.build(execution.action), destruction_contract=argument
        ), contract

    def _execute_operation(
        self,
        execution: codegen_input.ActionOperationExecution,
        positions: position_expression.PositionExpressionBuilder,
        names: naming.LocalNameAllocator,
    ) -> template_context.ExecuteOperationContext:
        arguments: list[template_context.PositionExpr | str] = []
        outputs: list[template_context.PositionExpr] = []
        output_view_names: list[str] = []
        for argument in execution.arguments:
            looking_at = argument.looking_at
            # Validation reports output views that look at literals, so a
            # literal is always an argument and never receives a result.
            if isinstance(looking_at, str):
                arguments.append(looking_at)
                continue
            value_type = value_types.constrained_python_value_type(
                argument.interface_view.constraints
            )
            if argument.interface_view.is_input:
                arguments.append(positions.build(looking_at, value_type=value_type))
            if argument.interface_view.is_output:
                outputs.append(positions.build(looking_at, value_type=value_type))
                output_view_names.append(
                    argument.interface_view.typed_name.name_content.name
                )
        # A single returned value goes straight to its position.
        result_names: list[str] = []
        if len(outputs) > 1:
            for view_name in output_view_names:
                result_names.append(names.allocate(view_name))
        return template_context.ExecuteOperationContext(
            function=self._converter.function_reference(execution.encoding_operation),
            arguments=arguments,
            outputs=outputs,
            result_names=result_names,
            operation_label=self._execution_label(execution),
        )

    def _operation_label(
        self,
        kind: template_context.StatementKind,
        position: ast.PositionReference,
        destination: ast.PositionReference | None = None,
    ) -> str | None:
        if self._trace_operations:
            return operation_labels.operation_label(
                self._action_input.definition.typed_name,
                kind,
                position,
                destination,
            )
        return None

    def _execution_label(
        self, execution: codegen_input.ActionOperationExecution
    ) -> str | None:
        if self._trace_operations:
            return operation_labels.operation_execution_label(
                self._action_input.definition.typed_name, execution
            )
        return None

    def _literal_value_label(
        self, position: ast.PositionReference, value: str
    ) -> str | None:
        if self._trace_operations:
            return operation_labels.literal_value_operation_label(
                self._action_input.definition.typed_name, position, value
            )
        return None
