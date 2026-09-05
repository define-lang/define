"""Name generation for literal Python actions."""

from __future__ import annotations

import re
import typing
from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    naming,
)
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.data_structures import typed_name_dict

_ACCEPT_PREFIX = "accept_"
_CREATE_FRAGMENT_PREFIX = "create_"
_DESTROY_FRAGMENT_PREFIX = "destroy_"
_DESTRUCTOR_RUN_PREFIX = "run_"
_DESTRUCTION_CONNECTION_PREFIX = "destruction_connection_"
_DESTRUCTION_POSITION_PREFIX = "destruction_position_"
_EMPTY_RULE_BINDING_HOLE_BASE_PREFIX = "for_empty_rule_"
_EXECUTION_PREFIX = "execution_"
_GLOBAL_NAME_PREFIX = "global_"
_GUARANTEE_FANOUT_PREFIX = "accept_guarantee_"
_INIT_PREFIX = "init_"
_CONTINUE_PREFIX = "continue_"
_JOIN_PREFIX = "join_"
_JOIN_FOR_PREFIX = "join_for_"
_LOCAL_POSITION_PREFIX = "local_position_"
_MOVE_FRAGMENT_PREFIX = "move_"
_ON_PREFIX = "on_"
_REQUIREMENT_BINDING_HOLE_BASE_PREFIXES = {
    action_contract.PositionOccupancyState.EMPTY: "when_empty_",
    action_contract.PositionOccupancyState.OCCUPIED: "when_occupied_",
}
_REGISTER_GUARANTEE_PREFIX = "register_guarantee_"

_ACTION_PARENT_BINDING_HOLE_BASE_NAME = "action_parent_occupied"
_DESTRUCTION_CONNECTION_COMPLETION_METHOD_NAME = "complete"
_CALLEE_BINDING_METHOD_SEPARATOR = "__"
_GUARANTEE_MOVE_SEPARATOR = "__move__"
_IDENTIFIER_SEPARATOR = "_"
_MEMBER_ACCESS_SEPARATOR = "."
_MOVE_TARGET_SEPARATOR = "_to_"
_TYPED_CHAIN_SEPARATOR = "__"
_UNSAFE_IDENTIFIER_CHARACTERS = re.compile(r"[\W_]+")


@dataclass(frozen=True, slots=True)
class ActionExecutionNames:
    """Names for one Action Execution in an execution class."""

    # For example, ``action_runner``.
    canonical_name: str
    # For example, ``execution_action_runner``.
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
    binding_holes: dict[
        operation_graph_model.BindingHole,
        action_context.GeneratedBindingHoleNames,
    ]
    # The canonical name and execution member for each Action Execution.
    action_executions: dict[operation_graph_model.ActionExecution, ActionExecutionNames]
    # The run method for each caller-contributed Destructor.
    destruction_contract_destructor_run_method_names: dict[
        action_plan.DestructionContractDestructorExecutionPlan, str
    ]
    # The generated methods for each Callee Binding Plan that needs one.
    callee_binding_plans: dict[action_plan.CalleeBindingPlan, str]
    callee_binding_invocations: dict[action_plan.CalleeBindingPlan, str]
    # The execution method for each action fragment.
    fragments: dict[action_plan.ActionFragment, str]
    join_member_names: dict[action_plan.JoinTarget, str]
    continue_destroy_methods: dict[action_plan.ActionFragment, str]
    destruction_connections: dict[action_plan.DestructionConnection, str]
    destruction_positions: dict[
        operation_graph_model.DestructionFragmentDestroyNode, str
    ]
    guarantees: dict[action_plan.ActionGuarantees, str]
    guarantee_consumption_init_method_names: dict[
        action_plan.GuaranteeConsumptionPlan, str
    ]
    deferred_guarantee_registration_method_names: dict[
        action_plan.DeferredGuaranteeRegistration, str
    ]
    _generated_actions: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_context.GeneratedActionInterface
    ] = field(repr=False, compare=False)

    def _callee_binding_method_name(
        self,
        callee_binding_plan: action_plan.CalleeBindingPlan,
    ) -> str:
        """Return the caller expression that invokes one Callee Binding."""
        if callee_binding_plan.requires_caller_method:
            return self.callee_binding_plans[callee_binding_plan]
        return self._callee_binding_hole_invocation_method_name(callee_binding_plan)

    def callee_binding_plan_method_names(
        self,
        callee_binding_plans: list[action_plan.CalleeBindingPlan],
    ) -> list[str]:
        """Return the method that performs each Callee Binding Plan."""
        return [
            self._callee_binding_method_name(callee_binding_plan)
            for callee_binding_plan in callee_binding_plans
        ]

    def _callee_binding_hole_invocation_method_name(
        self,
        callee_binding_plan: action_plan.CalleeBindingPlan,
    ) -> str:
        """Return the direct Callee Binding Hole invocation."""
        execution = callee_binding_plan.execution
        execution_name = self.action_executions[execution].execution_name
        callee_method_name = (
            self._generated_actions[execution.callee_action_name]
            .binding_holes[callee_binding_plan.callee_binding_hole]
            .method_name
        )
        return execution_name + _MEMBER_ACCESS_SEPARATOR + callee_method_name

    def callee_binding_init_method_name(
        self,
        callee_binding_plan: action_plan.CalleeBindingPlan,
    ) -> str | None:
        """Return the callee init method invoked by this plan."""
        if not callee_binding_plan.caller_invokes_init_method:
            return None
        binding_hole_names = self._generated_actions[
            callee_binding_plan.execution.callee_action_name
        ].binding_holes[callee_binding_plan.callee_binding_hole]
        if callee_binding_plan.requires_separate_init:
            return typing.cast(
                "str",
                binding_hole_names.separate_init_method_name,
            )
        return binding_hole_names.method_name

    def _callee_continuation_invocation_method_name(
        self,
        callee_binding_plan: action_plan.CalleeBindingPlan,
    ) -> str:
        """Return the direct invocation of a callee Binding Hole continuation."""
        execution = callee_binding_plan.execution
        execution_name = self.action_executions[execution].execution_name
        callee_method_name = typing.cast(
            "str",
            self._generated_actions[execution.callee_action_name]
            .binding_holes[callee_binding_plan.callee_binding_hole]
            .continuation_method_name,
        )
        return execution_name + _MEMBER_ACCESS_SEPARATOR + callee_method_name

    def _fanout_continuation_method_name(
        self,
        continuation: action_plan.FanoutContinuation,
    ) -> str:
        """Return the generated method name for one fanout continuation."""
        match continuation:
            case action_plan.ActionFragment():
                return self.fragments[continuation]
            case action_plan.CalleeBindingPlan():
                if continuation.requires_separate_init:
                    invocation_method_name = self.callee_binding_invocations.get(
                        continuation
                    )
                    if invocation_method_name is not None:
                        return invocation_method_name
                    return self._callee_continuation_invocation_method_name(
                        continuation
                    )
                return self._callee_binding_method_name(continuation)
            case action_plan.DestructionConnection():
                return (
                    self.destruction_connections[continuation]
                    + _MEMBER_ACCESS_SEPARATOR
                    + _DESTRUCTION_CONNECTION_COMPLETION_METHOD_NAME
                )

    def fanout_continuation_method_names(
        self,
        continuations: list[action_plan.FanoutContinuation],
    ) -> list[str]:
        """Return the generated method name for every fanout continuation."""
        return [
            self._fanout_continuation_method_name(continuation)
            for continuation in continuations
        ]

    def destruction_connection_continuation_method_names(
        self,
        continuations: list[action_plan.DestructionConnectionContinuation],
    ) -> list[str]:
        """Return the method name for every Destruction Connection continuation."""
        method_names: list[str] = []
        for continuation in continuations:
            match continuation:
                case action_plan.ActionFragment():
                    method_names.append(self.fragments[continuation])
                case action_plan.DestructionContractDestructorExecutionPlan():
                    method_names.append(
                        self.destruction_contract_destructor_run_method_names[
                            continuation
                        ]
                    )
                case action_plan.CalleeBindingPlan():
                    method_names.append(self.callee_binding_plans[continuation])
        return method_names

    def generated_execution_path(
        self,
        execution_path: Sequence[operation_graph_model.ActionExecution],
    ) -> tuple[list[str], action_context.GeneratedActionInterface]:
        """Return generated member names and the final action for an execution path."""
        first_execution = execution_path[0]
        nested_member_names, generated_callee = self.nested_generated_execution_path(
            execution_path
        )
        execution_member_names = [
            self.action_executions[first_execution].execution_name,
            *nested_member_names,
        ]
        return execution_member_names, generated_callee

    def nested_generated_execution_path(
        self,
        execution_path: Sequence[operation_graph_model.ActionExecution],
    ) -> tuple[list[str], action_context.GeneratedActionInterface]:
        """Return descendant member names and the final action for an execution path."""
        current_generated_action = self._generated_actions[
            execution_path[0].callee_action_name
        ]
        execution_member_names: list[str] = []
        for execution in execution_path[1:]:
            execution_member_names.append(
                current_generated_action.execution_member_names[execution]
            )
            current_generated_action = self._generated_actions[
                execution.callee_action_name
            ]
        return execution_member_names, current_generated_action


@typing.final
class ActionNameGenerator:
    """Allocate every generated member name for one action."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        plan: action_plan.ActionPlan,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedActionInterface
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
        binding_holes = self._binding_hole_names()
        action_executions = self._action_execution_names()
        destruction_contract_destructor_run_method_names = (
            self._destruction_contract_destructor_run_method_names()
        )
        callee_binding_plans = self._callee_binding_plan_names(action_executions)
        callee_binding_invocations = self._callee_binding_invocation_names()
        fragments = self._fragment_method_names()
        join_member_names = self._join_member_names(
            binding_holes,
            callee_binding_plans,
            fragments,
        )
        continue_destroy_methods = self._continue_destroy_method_names(fragments)
        destruction_connections = self._destruction_connection_names(action_executions)
        destruction_positions = self._destruction_position_names()
        guarantees = self._guarantee_names()
        guarantee_consumption_init_method_names = (
            self._guarantee_consumption_init_method_names()
        )
        deferred_guarantee_registration_method_names = (
            self._deferred_guarantee_registration_method_names()
        )
        return ActionNames(
            local_positions=local_positions,
            binding_holes=binding_holes,
            action_executions=action_executions,
            destruction_contract_destructor_run_method_names=(
                destruction_contract_destructor_run_method_names
            ),
            callee_binding_plans=callee_binding_plans,
            callee_binding_invocations=callee_binding_invocations,
            fragments=fragments,
            join_member_names=join_member_names,
            continue_destroy_methods=continue_destroy_methods,
            destruction_connections=destruction_connections,
            destruction_positions=destruction_positions,
            guarantees=guarantees,
            guarantee_consumption_init_method_names=(
                guarantee_consumption_init_method_names
            ),
            deferred_guarantee_registration_method_names=(
                deferred_guarantee_registration_method_names
            ),
            _generated_actions=self._generated_actions,
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

    def _binding_hole_names(
        self,
    ) -> dict[
        operation_graph_model.BindingHole,
        action_context.GeneratedBindingHoleNames,
    ]:
        names: dict[
            operation_graph_model.BindingHole,
            action_context.GeneratedBindingHoleNames,
        ] = {}
        for fanout in self._plan.binding_hole_fanouts.values():
            binding_hole = fanout.binding_hole
            base_name = self._binding_hole_base_name(binding_hole)
            inits = fanout.inits
            if fanout.continuations:
                method_name = self._binding_hole_method_prefix(binding_hole) + base_name
            # TODO: I'm not sure this specialization is worth modifying the callee
            # API contract for.
            elif len(inits.action_executions) == 1 and not inits.callee_binding_plans:
                execution = inits.action_executions[0]
                method_name = _INIT_PREFIX + self._typed_chain_identifier(
                    execution.action_chain
                )
            else:
                method_name = _INIT_PREFIX + base_name
            method_name = self._execution_allocator.allocate(method_name)
            names[binding_hole] = action_context.GeneratedBindingHoleNames(
                base_name,
                method_name,
            )
        for fanout in self._plan.binding_hole_fanouts.values():
            if not fanout.inits.has_inits or not fanout.continuations:
                continue
            binding_hole = fanout.binding_hole
            binding_hole_names = names[binding_hole]
            binding_hole_names.separate_init_method_name = (
                self._execution_allocator.allocate(
                    _INIT_PREFIX + binding_hole_names.base_name
                )
            )
            binding_hole_names.continuation_method_name = (
                self._execution_allocator.allocate(
                    _CONTINUE_PREFIX + binding_hole_names.base_name
                )
            )
        return names

    @staticmethod
    def _binding_hole_method_prefix(
        binding_hole: operation_graph_action_resolver.ResolvedBindingHole,
    ) -> str:
        if isinstance(
            binding_hole,
            operation_graph_model.ActionParentLastOperationNode,
        ):
            return _ON_PREFIX
        return _ACCEPT_PREFIX

    def _binding_hole_base_name(
        self,
        binding_hole: operation_graph_action_resolver.ResolvedBindingHole,
    ) -> str:
        """Return the generated-name base shared by one Binding Hole's members."""
        match binding_hole:
            case operation_graph_model.MoveRuleBindingHole():
                if binding_hole.caller_empty_rule_collection is not None:
                    return self._empty_rule_binding_hole_base_name(
                        binding_hole.caller_empty_rule_collection
                    )
                caller_fill_dependency = typing.cast(
                    "operation_graph_model.CallerFillDependency",
                    binding_hole.caller_fill_dependency,
                )
                return self._requirement_binding_hole_base_name(
                    caller_fill_dependency.requirement
                )
            case operation_graph_model.EmptyRuleBindingHole():
                return self._empty_rule_binding_hole_base_name(binding_hole)
            case operation_graph_model.ActionParentLastOperationNode():
                return _ACTION_PARENT_BINDING_HOLE_BASE_NAME
            case operation_graph_model.RequirementNode():
                return self._requirement_binding_hole_base_name(
                    binding_hole.requirement
                )
        typing.assert_never(binding_hole)

    def _empty_rule_binding_hole_base_name(
        self,
        empty_rule_binding_hole: operation_graph_model.CallerEmptyRuleCollection,
    ) -> str:
        identifier = self._typed_chain_identifier(
            empty_rule_binding_hole.requirement_position
        )
        return _EMPTY_RULE_BINDING_HOLE_BASE_PREFIX + identifier

    def _requirement_binding_hole_base_name(
        self,
        requirement: operation_graph_model.OperationGraphRequirement,
    ) -> str:
        identifier = self._typed_chain_identifier(requirement.requirement_position)
        return (
            _REQUIREMENT_BINDING_HOLE_BASE_PREFIXES[requirement.required_state]
            + identifier
        )

    def _action_execution_names(
        self,
    ) -> dict[operation_graph_model.ActionExecution, ActionExecutionNames]:
        names: dict[operation_graph_model.ActionExecution, ActionExecutionNames] = {}
        for planned_execution in self._plan.action_executions.values():
            action_execution = planned_execution.execution
            canonical_name = self._execution_allocator.allocate(
                self._typed_chain_identifier(action_execution.action_chain)
            )
            names[action_execution] = ActionExecutionNames(
                canonical_name=canonical_name,
                execution_name=self._execution_allocator.allocate(
                    _EXECUTION_PREFIX + canonical_name
                ),
            )
        return names

    def _destruction_contract_destructor_run_method_names(
        self,
    ) -> dict[action_plan.DestructionContractDestructorExecutionPlan, str]:
        names: dict[action_plan.DestructionContractDestructorExecutionPlan, str] = {}
        for action_execution in self._plan.action_executions.values():
            for connection in action_execution.created_destruction_connections:
                for destructor in connection.destruction_contract_destructors:
                    names[destructor] = self._execution_allocator.allocate(
                        _DESTRUCTOR_RUN_PREFIX
                        + self._typed_chain_identifier(
                            destructor.execution.action_chain
                        )
                    )
        return names

    def _callee_binding_plan_names(
        self,
        action_execution_names: dict[
            operation_graph_model.ActionExecution, ActionExecutionNames
        ],
    ) -> dict[action_plan.CalleeBindingPlan, str]:
        names: dict[action_plan.CalleeBindingPlan, str] = {}
        for callee_binding_plan in self._plan.callee_binding_method_plans:
            action_execution = callee_binding_plan.execution
            if (
                callee_binding_plan.requires_separate_init
                or not callee_binding_plan.has_continuations
            ):
                callee_binding_hole_base_name = (
                    self._generated_actions[action_execution.callee_action_name]
                    .binding_holes[callee_binding_plan.callee_binding_hole]
                    .base_name
                )
                method_name = self._execution_allocator.allocate(
                    _INIT_PREFIX
                    + action_execution_names[action_execution].canonical_name
                    + _CALLEE_BINDING_METHOD_SEPARATOR
                    + callee_binding_hole_base_name
                )
            elif callee_binding_plan.guarantee_dependencies:
                method_name = self._execution_allocator.allocate(
                    _GUARANTEE_FANOUT_PREFIX
                    + self._typed_chain_identifier(action_execution.action_chain)
                )
            else:
                callee_binding_hole_base_name = (
                    self._generated_actions[action_execution.callee_action_name]
                    .binding_holes[callee_binding_plan.callee_binding_hole]
                    .base_name
                )
                method_name = self._execution_allocator.allocate(
                    action_execution_names[action_execution].canonical_name
                    + _CALLEE_BINDING_METHOD_SEPARATOR
                    + callee_binding_hole_base_name
                )
            names[callee_binding_plan] = method_name
        return names

    def _callee_binding_invocation_names(
        self,
    ) -> dict[action_plan.CalleeBindingPlan, str]:
        names: dict[action_plan.CalleeBindingPlan, str] = {}
        for callee_binding_plan in self._plan.callee_binding_method_plans:
            if not callee_binding_plan.requires_separate_init:
                continue
            names[callee_binding_plan] = self._execution_allocator.allocate(
                _GUARANTEE_FANOUT_PREFIX
                + self._typed_chain_identifier(
                    callee_binding_plan.execution.action_chain
                )
            )
        return names

    def _join_member_names(
        self,
        binding_holes: dict[
            operation_graph_model.BindingHole,
            action_context.GeneratedBindingHoleNames,
        ],
        callee_binding_plan_names: dict[action_plan.CalleeBindingPlan, str],
        fragment_method_names: dict[action_plan.ActionFragment, str],
    ) -> dict[action_plan.JoinTarget, str]:
        names: dict[action_plan.JoinTarget, str] = {}
        for fanout in self._plan.binding_hole_fanouts.values():
            if not fanout.requires_join_check:
                continue
            base_name = binding_holes[fanout.binding_hole].base_name
            names[fanout] = self._execution_allocator.allocate(_JOIN_PREFIX + base_name)
        for fragment in self._plan.fragments:
            if not fragment.requires_join_check:
                continue
            names[fragment] = self._execution_allocator.allocate(
                _JOIN_FOR_PREFIX + fragment_method_names[fragment]
            )
        for callee_binding_plan in self._plan.callee_binding_method_plans:
            if not callee_binding_plan.requires_join_check:
                continue
            names[callee_binding_plan] = self._execution_allocator.allocate(
                _JOIN_FOR_PREFIX + callee_binding_plan_names[callee_binding_plan]
            )
        return names

    def _guarantee_names(
        self,
    ) -> dict[action_plan.ActionGuarantees, str]:
        allocator = naming.NameAllocator()
        guarantee_names: dict[action_plan.ActionGuarantees, str] = {}
        for fragment in self._plan.fragments:
            guarantees = fragment.guarantees
            if guarantees is None:
                continue
            guarantee_names[guarantees] = allocator.allocate(
                self._guarantee_base_name(guarantees)
            )
        return guarantee_names

    def _guarantee_consumption_init_method_names(
        self,
    ) -> dict[action_plan.GuaranteeConsumptionPlan, str]:
        method_names: dict[action_plan.GuaranteeConsumptionPlan, str] = {}
        for consumption_plan in self._plan.guarantee_consumption_plans:
            if not consumption_plan.inits.has_inits:
                continue
            path_names: list[str] = []
            for execution in consumption_plan.guarantee.executions:
                path_names.append(self._typed_chain_identifier(execution.action_chain))
            publishing_action = self._generated_actions[
                consumption_plan.guarantee.executions[-1].callee_action_name
            ]
            path_names.append(
                publishing_action.guarantee_names_by_operation[
                    consumption_plan.guarantee.operation
                ]
            )
            method_names[consumption_plan] = self._execution_allocator.allocate(
                _INIT_PREFIX + _TYPED_CHAIN_SEPARATOR.join(path_names)
            )
        return method_names

    def _guarantee_base_name(
        self,
        guarantees: action_plan.ActionGuarantees,
    ) -> str:
        position_names: list[str] = []
        if guarantees.guaranteed_source is not None:
            position_names.append(
                self._typed_chain_identifier(guarantees.guaranteed_source)
            )
        if guarantees.guaranteed_target is not None:
            position_names.append(
                self._typed_chain_identifier(guarantees.guaranteed_target)
            )
        return _GUARANTEE_MOVE_SEPARATOR.join(position_names)

    def _deferred_guarantee_registration_method_names(
        self,
    ) -> dict[action_plan.DeferredGuaranteeRegistration, str]:
        method_names: dict[action_plan.DeferredGuaranteeRegistration, str] = {}
        for planned_execution in self._plan.action_executions.values():
            for registration in planned_execution.deferred_guarantee_registrations:
                operation = registration.consumption_plan.guarantee.operation
                method_names[registration] = self._execution_allocator.allocate(
                    _REGISTER_GUARANTEE_PREFIX
                    + self._typed_chain_identifier(
                        operation.target.canonical_chained_name_tuple
                    )
                )
        return method_names

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
                _CONTINUE_PREFIX + fragment_names[fragment]
            )
        return names

    def _destruction_connection_names(
        self,
        action_execution_names: dict[
            operation_graph_model.ActionExecution, ActionExecutionNames
        ],
    ) -> dict[action_plan.DestructionConnection, str]:
        names: dict[action_plan.DestructionConnection, str] = {}
        for execution_plan in self._plan.action_executions.values():
            for connection in execution_plan.created_destruction_connections:
                names[connection] = self._execution_allocator.allocate(
                    _DESTRUCTION_CONNECTION_PREFIX
                    + action_execution_names[execution_plan.execution].canonical_name
                )
        return names

    def _destruction_position_names(
        self,
    ) -> dict[operation_graph_model.DestructionFragmentDestroyNode, str]:
        names: dict[operation_graph_model.DestructionFragmentDestroyNode, str] = {}
        for operation in self._plan.destruction_connection_by_operation:
            target = self._typed_chain_identifier(
                operation.target.canonical_chained_name_tuple
            )
            names[operation] = self._execution_allocator.allocate(
                _DESTRUCTION_POSITION_PREFIX + target
            )
        return names
