"""Name generation for literal Python actions."""

import re
import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import action_context, naming
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_model,
)

_BINDING_HOLE_METHOD_PREFIX = "accept_"
_ACTION_PARENT_BINDING_HOLE_METHOD_NAME = "accept_action_parent"
_CREATE_FRAGMENT_PREFIX = "create_"
_DESTROY_FRAGMENT_PREFIX = "destroy_"
_DESTRUCTION_CONNECTION_PREFIX = "destruction_connection_"
_DESTRUCTION_CONNECTIONS_SUFFIX = "_destruction_connections"
_DESTRUCTION_POSITION_PREFIX = "destruction_position_"
_EMPTY_RULE_BINDING_HOLE_METHOD_PREFIX = "accept_for_empty_rule_"
_EXECUTION_PREFIX = "execution_"
_GLOBAL_NAME_PREFIX = "global_"
_GUARANTEE_MOVE_SEPARATOR = "__move__"
_GUARANTEE_PREFIX = "guarantee_"
_IDENTIFIER_SEPARATOR = "_"
_INITIALIZER_PREFIX = "init_"
_CONTINUE_DESTROY_PREFIX = "continue_"
_LOCAL_POSITION_PREFIX = "local_position_"
_MOVE_FRAGMENT_PREFIX = "move_"
_MOVE_TARGET_SEPARATOR = "_to_"
_REQUIREMENT_BINDING_HOLE_METHOD_PREFIXES = {
    action_contract.PositionOccupancyState.EMPTY: "accept_when_empty_",
    action_contract.PositionOccupancyState.OCCUPIED: "accept_when_occupied_",
}

type _PlannedBindingHole = (
    operation_graph_model.MoveRuleBindingHole
    | operation_graph_model.EmptyRuleBindingHole
    | operation_graph_model.ActionParentLastOperationNode
    | operation_graph_model.RequirementNode
)
_TRIGGERED_ACTION_PREFIX = "trigger_"
_CALLEE_BINDING_JOIN_METHOD_SEPARATOR = "__"
_TYPED_CHAIN_SEPARATOR = "__"
_UNSAFE_IDENTIFIER_CHARACTERS = re.compile(r"[\W_]+")


@dataclass(frozen=True, slots=True)
class TriggeredActionNames:
    """Names for one Action Execution in an execution class."""

    canonical_name: str
    # The method that initializes the triggered action's execution.
    initializer_name: str
    # The member that stores the triggered action's execution.
    execution_name: str


# Keep a mapping only for a distinct generated member or method. When a consumer
# reaches that same generated object through another plan object, it must follow
# the plan relationship back to the canonical name instead of adding a
# dictionary that re-keys or copies the name.
@dataclass(frozen=True, slots=True)
class ActionNames:
    """All names allocated while generating one action."""

    # The execution member for each local position source name.
    local_positions: dict[str, str]
    # The execution method for each Binding Hole.
    binding_hole_method_names: dict[operation_graph_model.BindingHole, str]
    # The canonical name, initializer method, and execution member for each
    # Action Execution.
    triggered_actions: dict[operation_graph_model.ActionExecution, TriggeredActionNames]
    # The trigger method for each caller-contributed Destructor.
    destruction_contract_destructor_trigger_method_names: dict[
        action_plan.DestructionContractDestructorExecutionPlan, str
    ]
    # The execution method for each Callee Binding Join.
    callee_binding_join_method_names: dict[action_plan.CalleeBindingJoin, str]
    # The execution method for each action fragment.
    fragments: dict[action_plan.ActionFragment, str]
    continue_destroy_methods: dict[action_plan.ActionFragment, str]
    destruction_connections: dict[action_plan.DestructionConnection, str]
    triggered_destruction_connections: dict[operation_graph_model.ActionExecution, str]
    destruction_positions: dict[
        operation_graph_model.DestructionFragmentDestroyNode, str
    ]
    # The guarantees task-list member for each guarantee publication.
    guarantee_publications: dict[action_plan.GuaranteePublication, str]


@typing.final
class ActionNameGenerator:
    """Allocate every generated member name for one action."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        plan: action_plan.ActionPlan,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedAction
        ],
    ):
        """Initialize from the Action Definition, Action Plan, and generated actions."""
        self._definition = definition
        self._plan = plan
        self._current_fqun = definition.typed_name.name_content.fqun.canonical
        self._generated_actions = generated_actions
        self._execution_allocator = naming.NameAllocator()
        self._typed_name_identifiers: dict[str, str] = {}

    def generate(self) -> ActionNames:
        """Allocate all action member names."""
        # Allocating every name before building template contexts prevents
        # context-generation order from changing name-collision resolution.
        local_positions = self._local_position_names()
        binding_hole_method_names = self._binding_hole_method_names()
        triggered_actions = self._triggered_action_names()
        destruction_contract_destructor_trigger_method_names = (
            self._destruction_contract_destructor_trigger_method_names()
        )
        callee_binding_join_method_names = self._callee_binding_join_method_names(
            triggered_actions
        )
        fragments = self._fragment_method_names()
        continue_destroy_methods = self._continue_destroy_method_names(fragments)
        destruction_connections = self._destruction_connection_names(triggered_actions)
        triggered_destruction_connections = (
            self._triggered_destruction_connection_names(triggered_actions)
        )
        destruction_positions = self._destruction_position_names()
        guarantee_publications = self._guarantee_publication_names()
        return ActionNames(
            local_positions=local_positions,
            binding_hole_method_names=binding_hole_method_names,
            triggered_actions=triggered_actions,
            destruction_contract_destructor_trigger_method_names=(
                destruction_contract_destructor_trigger_method_names
            ),
            callee_binding_join_method_names=callee_binding_join_method_names,
            fragments=fragments,
            continue_destroy_methods=continue_destroy_methods,
            destruction_connections=destruction_connections,
            triggered_destruction_connections=triggered_destruction_connections,
            destruction_positions=destruction_positions,
            guarantee_publications=guarantee_publications,
        )

    def _local_position_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for statement in self._definition.action_statements.statements:
            if isinstance(statement, ast.LocalPositionDefinition):
                source_name = statement.typed_name.name_content.name
                names[source_name] = self._execution_allocator.allocate(
                    _LOCAL_POSITION_PREFIX + source_name
                )
        return names

    def _binding_hole_method_names(
        self,
    ) -> dict[operation_graph_model.BindingHole, str]:
        method_names: dict[operation_graph_model.BindingHole, str] = {}
        for binding_hole_fanout in self._plan.binding_hole_fanouts:
            # EmptyRuleBindingHoleNode values are resolved before action planning.
            binding_hole = typing.cast(
                "_PlannedBindingHole", binding_hole_fanout.binding_hole
            )
            method_names[binding_hole_fanout.binding_hole] = (
                self._execution_allocator.allocate(
                    self._binding_hole_method_name(binding_hole)
                )
            )
        return method_names

    def _binding_hole_method_name(
        self,
        binding_hole: _PlannedBindingHole,
    ) -> str:
        """Return the execution method name for one Binding Hole."""
        match binding_hole:
            case operation_graph_model.MoveRuleBindingHole():
                if binding_hole.caller_empty_rule_collection is not None:
                    return self._empty_rule_binding_hole_method_name(
                        binding_hole.caller_empty_rule_collection
                    )
                caller_fill_dependency = typing.cast(
                    "operation_graph_model.CallerFillDependency",
                    binding_hole.caller_fill_dependency,
                )
                return self._requirement_binding_hole_method_name(
                    caller_fill_dependency.requirement
                )
            case operation_graph_model.EmptyRuleBindingHole():
                return self._empty_rule_binding_hole_method_name(binding_hole)
            case operation_graph_model.ActionParentLastOperationNode():
                return _ACTION_PARENT_BINDING_HOLE_METHOD_NAME
            case operation_graph_model.RequirementNode():
                return self._requirement_binding_hole_method_name(
                    binding_hole.requirement
                )
        typing.assert_never(binding_hole)

    def _empty_rule_binding_hole_method_name(
        self,
        empty_rule_binding_hole: operation_graph_model.CallerEmptyRuleCollection,
    ) -> str:
        identifier = self._typed_chain_identifier(
            empty_rule_binding_hole.requirement_position
        )
        return _EMPTY_RULE_BINDING_HOLE_METHOD_PREFIX + identifier

    def _requirement_binding_hole_method_name(
        self,
        requirement: operation_graph_model.OperationGraphRequirement,
    ) -> str:
        identifier = self._typed_chain_identifier(requirement.requirement_position)
        return (
            _REQUIREMENT_BINDING_HOLE_METHOD_PREFIXES[requirement.required_state]
            + identifier
        )

    def _triggered_action_names(
        self,
    ) -> dict[operation_graph_model.ActionExecution, TriggeredActionNames]:
        names: dict[operation_graph_model.ActionExecution, TriggeredActionNames] = {}
        for planned_execution in self._plan.action_executions:
            action_execution = planned_execution.execution
            canonical_name = self._execution_allocator.allocate(
                _TRIGGERED_ACTION_PREFIX
                + self._typed_chain_identifier(action_execution.action_chain)
            )
            names[action_execution] = TriggeredActionNames(
                canonical_name=canonical_name,
                initializer_name=self._execution_allocator.allocate(
                    _INITIALIZER_PREFIX + _EXECUTION_PREFIX + canonical_name
                ),
                execution_name=self._execution_allocator.allocate(
                    _EXECUTION_PREFIX + canonical_name
                ),
            )
        return names

    def _destruction_contract_destructor_trigger_method_names(
        self,
    ) -> dict[action_plan.DestructionContractDestructorExecutionPlan, str]:
        names: dict[action_plan.DestructionContractDestructorExecutionPlan, str] = {}
        for action_execution in self._plan.action_executions:
            for connection in action_execution.created_destruction_connections:
                for destructor in connection.destruction_contract_destructors:
                    names[destructor] = self._execution_allocator.allocate(
                        _TRIGGERED_ACTION_PREFIX
                        + self._typed_chain_identifier(
                            destructor.execution.action_chain
                        )
                    )
        return names

    def _callee_binding_join_method_names(
        self,
        triggered_action_names: dict[
            operation_graph_model.ActionExecution, TriggeredActionNames
        ],
    ) -> dict[action_plan.CalleeBindingJoin, str]:
        method_names: dict[action_plan.CalleeBindingJoin, str] = {}
        for callee_binding_join in self._plan.callee_binding_joins:
            action_execution = callee_binding_join.execution
            callee_binding_hole_method_name = self._generated_actions[
                action_execution.callee_action_name
            ].binding_hole_method_names[callee_binding_join.callee_binding_hole]
            method_names[callee_binding_join] = self._execution_allocator.allocate(
                triggered_action_names[action_execution].canonical_name
                + _CALLEE_BINDING_JOIN_METHOD_SEPARATOR
                + callee_binding_hole_method_name.removeprefix(
                    _BINDING_HOLE_METHOD_PREFIX
                )
            )
        return method_names

    def _guarantee_publication_names(
        self,
    ) -> dict[action_plan.GuaranteePublication, str]:
        allocator = naming.NameAllocator()
        publication_names: dict[action_plan.GuaranteePublication, str] = {}
        for publication in self._plan.guarantee_publications:
            publication_names[publication] = allocator.allocate(
                self._guarantee_base_name(publication)
            )
        return publication_names

    def _guarantee_base_name(
        self,
        publication: action_plan.GuaranteePublication,
    ) -> str:
        position_names: list[str] = []
        if publication.guaranteed_source is not None:
            position_names.append(
                self._typed_chain_identifier(publication.guaranteed_source)
            )
        if publication.guaranteed_target is not None:
            position_names.append(
                self._typed_chain_identifier(publication.guaranteed_target)
            )
        return _GUARANTEE_PREFIX + _GUARANTEE_MOVE_SEPARATOR.join(position_names)

    def _typed_chain_identifier(self, chain: tuple[str, ...]) -> str:
        """Convert a canonical typed chain to a DLP 27-style Python identifier."""
        return _TYPED_CHAIN_SEPARATOR.join(
            [self._typed_name_identifier(typed_name) for typed_name in chain]
        )

    def _typed_name_identifier(self, typed_name: str) -> str:
        identifier = self._typed_name_identifiers.get(typed_name)
        if identifier is not None:
            return identifier

        # TODO: Carry AST typed-name objects to every caller of this method so
        # codegen can use their NameType and source-form APIs instead of parsing
        # canonical chained-name strings.
        typed_name_parts = ast.source_form_typed_name_parts(
            typed_name,
            self._current_fqun,
        )
        safe_name = _UNSAFE_IDENTIFIER_CHARACTERS.sub(
            _IDENTIFIER_SEPARATOR,
            typed_name_parts.source_name,
        ).strip(_IDENTIFIER_SEPARATOR)
        # Actions are always global, so only a position name needs the prefix to
        # distinguish it from a local name.
        is_global_position = (
            typed_name_parts.name_type is ast.NameType.POSITION
            and typed_name_parts.is_global
        )
        prefix = _GLOBAL_NAME_PREFIX if is_global_position else ""
        identifier = (
            prefix
            + typed_name_parts.name_type.value
            + _IDENTIFIER_SEPARATOR
            + safe_name
        )
        self._typed_name_identifiers[typed_name] = identifier
        return identifier

    def _fragment_method_names(self) -> dict[action_plan.ActionFragment, str]:
        method_names: dict[action_plan.ActionFragment, str] = {}
        for fragment in self._plan.fragments:
            first_operation = fragment.operations[0]
            target = self._typed_chain_identifier(
                first_operation.target.canonical_chained_name_tuple
            )
            match first_operation:
                case operation_graph_model.MoveNode():
                    source = self._typed_chain_identifier(
                        first_operation.source.canonical_chained_name_tuple
                    )
                    base = (
                        _MOVE_FRAGMENT_PREFIX + source + _MOVE_TARGET_SEPARATOR + target
                    )
                case operation_graph_model.CreateNode():
                    base = _CREATE_FRAGMENT_PREFIX + target
                case operation_graph_model.DestroyNode():
                    base = _DESTROY_FRAGMENT_PREFIX + target
                case _:
                    raise TypeError(
                        "unsupported Particle Operation: "
                        + type(first_operation).__name__
                    )
            method_names[fragment] = self._execution_allocator.allocate(base)
        return method_names

    def _continue_destroy_method_names(
        self,
        fragment_names: dict[action_plan.ActionFragment, str],
    ) -> dict[action_plan.ActionFragment, str]:
        names: dict[action_plan.ActionFragment, str] = {}
        for fragment in self._plan.fragments:
            if not isinstance(fragment, action_plan.DestructionActionFragment):
                continue
            names[fragment] = self._execution_allocator.allocate(
                _CONTINUE_DESTROY_PREFIX + fragment_names[fragment]
            )
        return names

    def _destruction_connection_names(
        self,
        triggered_action_names: dict[
            operation_graph_model.ActionExecution, TriggeredActionNames
        ],
    ) -> dict[action_plan.DestructionConnection, str]:
        names: dict[action_plan.DestructionConnection, str] = {}
        for execution_plan in self._plan.action_executions:
            for connection in execution_plan.created_destruction_connections:
                names[connection] = self._execution_allocator.allocate(
                    _DESTRUCTION_CONNECTION_PREFIX
                    + triggered_action_names[execution_plan.execution].canonical_name
                )
        return names

    def _triggered_destruction_connection_names(
        self,
        triggered_action_names: dict[
            operation_graph_model.ActionExecution, TriggeredActionNames
        ],
    ) -> dict[operation_graph_model.ActionExecution, str]:
        names: dict[operation_graph_model.ActionExecution, str] = {}
        for execution_plan in self._plan.action_executions:
            if not execution_plan.created_destruction_connections:
                continue
            execution = execution_plan.execution
            names[execution] = self._execution_allocator.allocate(
                triggered_action_names[execution].canonical_name
                + _DESTRUCTION_CONNECTIONS_SUFFIX
            )
        return names

    def _destruction_position_names(
        self,
    ) -> dict[operation_graph_model.DestructionFragmentDestroyNode, str]:
        names: dict[operation_graph_model.DestructionFragmentDestroyNode, str] = {}
        for callee_binding_join in self._plan.callee_binding_joins:
            for operation in callee_binding_join.contributed_destruction_operations:
                target = self._typed_chain_identifier(
                    operation.target.canonical_chained_name_tuple
                )
                names[operation] = self._execution_allocator.allocate(
                    _DESTRUCTION_POSITION_PREFIX + target
                )
        return names
