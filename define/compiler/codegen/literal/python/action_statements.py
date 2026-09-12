"""Python code generation for sequential action statements."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler import ast
from define.compiler.codegen.literal.python import naming, template_context

if TYPE_CHECKING:
    from define.compiler.validator.reference_graph import (
        action_contract,
    )

_OPERATION_NAMES = {
    template_context.StatementKind.CREATE_PARTICLE: "create",
    template_context.StatementKind.MOVE_PARTICLE: "move",
    template_context.StatementKind.DESTROY_PARTICLE: "destroy",
}


@final
class ActionStatementsGenerator:
    """Build template data in the order statements execute."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        destructions: dict[ast.SourceLocation, list[ast.PositionReference]],
        triggered_actions: action_contract.TriggeredActions,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated definitions and known destructions."""
        self._definition = definition
        self._converter = converter
        self._destructions = destructions
        self._triggered_actions = triggered_actions
        self._trace_operations = trace_operations
        self._local_position_names: dict[str, str] = {}
        self._interface_position_names = {
            position.typed_name.source_typed_name
            for position in definition.interface_positions
        }

    def _collect_imports(self) -> set[str]:
        """Collect modules needed by statements and their triggered actions."""
        modules: set[str] = set()
        locations = [self._definition.action_statements.location]
        for statement in self._definition.action_statements.statements:
            locations.append(statement.location)
            if isinstance(statement, ast.LocalPositionDefinition):
                for quality in statement.constraint_typed_names:
                    modules.add(self._converter.class_reference(quality).module_name)
            elif isinstance(statement, ast.CreateParticleStatement):
                self._add_position_imports(statement.target_position, modules)
            elif isinstance(statement, ast.MoveParticleStatement):
                self._add_position_imports(statement.source_position, modules)
                self._add_position_imports(statement.target_position, modules)
        for location in locations:
            for action in self._triggered_actions.get(location, ()):
                self._add_position_imports(action, modules)
            for position in self._destructions.get(location, ()):
                self._add_position_imports(position, modules)
        return modules

    def _add_position_imports(
        self,
        position: ast.PositionReference | ast.ActionReference,
        modules: set[str],
    ):
        for name in position.typed_names:
            if isinstance(name, ast.GlobalTypedNameReference):
                modules.add(self._converter.class_reference(name).module_name)

    def generate(
        self,
    ) -> tuple[list[template_context.ActionStatementContext], set[str]]:
        """Generate statements and automatic destruction in execution order."""
        names = naming.LocalNameAllocator()
        imports = self._collect_imports()
        names.reserve_module_first_names(imports)
        statements: list[template_context.ActionStatementContext] = []
        for statement in self._definition.action_statements.statements:
            match statement:
                case ast.LocalPositionDefinition():
                    source_name = statement.typed_name.name_content.name
                    name = names.allocate(source_name)
                    self._local_position_names[source_name] = name
                    statements.append(
                        template_context.ActionStatementContext(
                            kind=template_context.StatementKind.LOCAL_POSITION,
                            local_position_name=name,
                            local_typed_name=statement.typed_name.source_typed_name,
                            constraints=self._converter.constraints_to_class_references(
                                statement.constraints
                            ),
                        )
                    )
                case ast.DestroyParticleStatement():
                    statements.extend(self._destruction(statement.location))
                case ast.CreateParticleStatement():
                    statements.append(
                        self._operation(
                            template_context.StatementKind.CREATE_PARTICLE,
                            statement.target_position,
                        )
                    )
                    for action in self._triggered_actions.get(statement.location, ()):
                        statements.append(self._run(action))
                case ast.MoveParticleStatement():
                    statements.append(
                        self._operation(
                            template_context.StatementKind.MOVE_PARTICLE,
                            statement.source_position,
                            statement.target_position,
                        )
                    )
                    for action in self._triggered_actions.get(statement.location, ()):
                        statements.append(self._run(action))
        statements.extend(
            self._destruction(self._definition.action_statements.location)
        )
        return statements, imports

    def _destruction(
        self, location: ast.SourceLocation
    ) -> list[template_context.ActionStatementContext]:
        destruction = self._destructions[location]
        statements = [
            self._run(action) for action in self._triggered_actions.get(location, ())
        ]
        for position in destruction:
            statements.append(
                self._operation(
                    template_context.StatementKind.DESTROY_PARTICLE, position
                )
            )
        return statements

    def _run(
        self, action: ast.ActionReference
    ) -> template_context.ActionStatementContext:
        return template_context.ActionStatementContext(
            kind=template_context.StatementKind.RUN_ACTION,
            position=self.build_position(action),
        )

    def _operation(
        self,
        kind: template_context.StatementKind,
        position: ast.PositionReference,
        destination: ast.PositionReference | None = None,
    ) -> template_context.ActionStatementContext:
        label = None
        if self._trace_operations:
            position_name = self._position_name(position)
            if destination is not None:
                position_name += ", " + self._position_name(destination)
            operation = _OPERATION_NAMES[kind]
            action_name = (
                self._definition.typed_name.name_content.path.name.removeprefix("/")
            )
            label = f"{action_name}.{operation}({position_name})"
        return template_context.ActionStatementContext(
            kind=kind,
            position=self.build_position(position),
            to_position=self.build_position(destination)
            if destination is not None
            else None,
            operation_label=label,
        )

    @staticmethod
    def _position_name(position: ast.PositionReference) -> str:
        return "::".join(name.name_content.source_name for name in position.typed_names)

    def build_position(
        self,
        position_reference: ast.PositionReference | ast.ActionReference,
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
        )
