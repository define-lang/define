"""Name generation for literal Python actions."""

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import action_context, naming
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph,
    operation_graph_action_resolver,
)

_ACCEPT_CALLER_INPUT_PREFIX = "accept_"
_ACTION_PARENT_CALLER_INPUT_NAME = "accept_action_parent"
_CREATE_FRAGMENT_PREFIX = "create_"
_DESTROY_FRAGMENT_PREFIX = "destroy_"
_EMPTY_RULE_CALLER_INPUT_PREFIX = "accept_for_empty_rule_"
_EXECUTION_SUFFIX = "__execution"
_GLOBAL_NAME_PREFIX = "global_"
_GUARANTEE_MOVE_SEPARATOR = "__move__"
_GUARANTEE_PREFIX = "guarantee_"
_IDENTIFIER_SEPARATOR = "_"
_INITIALIZER_PREFIX = "init_"
_LOCAL_POSITION_PREFIX = "local_position_"
_MOVE_FRAGMENT_PREFIX = "move_"
_MOVE_TARGET_SEPARATOR = "_to_"
_REQUIREMENT_CALLER_INPUT_PREFIXES = {
    action_contract.PositionOccupancyState.EMPTY: "accept_when_empty_",
    action_contract.PositionOccupancyState.OCCUPIED: "accept_when_occupied_",
}
_TRIGGERED_ACTION_PREFIX = "trigger_"
_TRIGGERED_INPUT_SEPARATOR = "__"
_TYPED_CHAIN_SEPARATOR = "__"

_EXECUTION_RESERVED_NAMES = ("action", "scheduler")


@dataclass(frozen=True, slots=True)
class TriggeredActionNames:
    """Names for one Action Triggering in an execution class."""

    # The method that initializes the triggered action's execution.
    initializer_name: str
    # The member that stores the triggered action's execution.
    execution_name: str


@dataclass(frozen=True, slots=True)
class ActionNames:
    """All names allocated while generating one action."""

    # The execution member for each local position source name.
    local_positions: dict[str, str]
    # The execution method for each caller input.
    caller_inputs: dict[operation_graph_action_resolver.ResolvedCallerInput, str]
    # The initializer method and execution member for each Action Triggering.
    triggered_actions: dict[operation_graph.ActionTrigger, TriggeredActionNames]
    # The execution method for each triggered action input.
    triggered_inputs: dict[action_plan.TriggeredActionInput, str]
    # The execution method for each action fragment.
    fragments: dict[action_plan.ActionFragment, str]
    # The guarantees task-list member for each guarantee publication.
    guarantee_publications: dict[action_plan.GuaranteePublication, str]
    # The guarantees member for each Action Triggering whose callee has guarantees.
    child_guarantees: dict[operation_graph.ActionTrigger, str]


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
        """Initialize with the execution namespace and its naming inputs."""
        self._definition = definition
        self._plan = plan
        self._current_fqun = definition.typed_name.name_content.fqun.canonical
        self._generated_actions = generated_actions
        self._execution_allocator = naming.NameAllocator(_EXECUTION_RESERVED_NAMES)

    def generate(self) -> ActionNames:
        """Allocate all action member names."""
        # Allocating every name before building template contexts prevents
        # context-generation order from changing name-collision resolution.
        local_positions = self._local_position_names()
        caller_inputs = self._caller_input_method_names()
        triggered_action_base_names = self._triggered_action_base_names()
        triggered_actions = self._triggered_action_names(triggered_action_base_names)
        triggered_inputs = self._triggered_input_method_names(
            triggered_action_base_names
        )
        fragments = self._fragment_method_names()
        guarantee_allocator = naming.NameAllocator()
        guarantee_publications = self._guarantee_publication_names(guarantee_allocator)
        child_guarantees = self._child_guarantees_names(
            triggered_action_base_names,
            guarantee_allocator,
        )
        return ActionNames(
            local_positions=local_positions,
            caller_inputs=caller_inputs,
            triggered_actions=triggered_actions,
            triggered_inputs=triggered_inputs,
            fragments=fragments,
            guarantee_publications=guarantee_publications,
            child_guarantees=child_guarantees,
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

    def _caller_input_method_names(
        self,
    ) -> dict[operation_graph_action_resolver.ResolvedCallerInput, str]:
        method_names: dict[
            operation_graph_action_resolver.ResolvedCallerInput, str
        ] = {}
        for caller_input in self._plan.caller_inputs:
            method_names[caller_input.resolved_input] = (
                self._execution_allocator.allocate(
                    self._caller_input_name(caller_input.resolved_input)
                )
            )
        return method_names

    def _caller_input_name(
        self,
        resolved_input: operation_graph_action_resolver.ResolvedCallerInput,
    ) -> str:
        """Return the method name for a caller input."""
        match resolved_input:
            case operation_graph_action_resolver.ResolvedEmptyRuleInput():
                identifier = self._typed_chain_identifier(
                    resolved_input.dependencies.requirement_position
                )
                return _EMPTY_RULE_CALLER_INPUT_PREFIX + identifier
            case operation_graph_action_resolver.ResolvedActionParentInput():
                return _ACTION_PARENT_CALLER_INPUT_NAME
            case operation_graph_action_resolver.ResolvedRequirementInput():
                identifier = self._typed_chain_identifier(
                    resolved_input.node.requirement_position
                )
                return (
                    _REQUIREMENT_CALLER_INPUT_PREFIXES[
                        resolved_input.node.required_state
                    ]
                    + identifier
                )
            case _:
                raise TypeError(
                    f"unknown caller input type: {type(resolved_input).__name__}"
                )

    def _triggered_action_base_names(
        self,
    ) -> dict[operation_graph.ActionTrigger, str]:
        allocator = naming.NameAllocator()
        names: dict[operation_graph.ActionTrigger, str] = {}
        for action_trigger in self._plan.action_triggers:
            names[action_trigger] = allocator.allocate(
                _TRIGGERED_ACTION_PREFIX
                + self._typed_chain_identifier(action_trigger.action_chain)
            )
        return names

    def _triggered_action_names(
        self,
        base_names: dict[operation_graph.ActionTrigger, str],
    ) -> dict[operation_graph.ActionTrigger, TriggeredActionNames]:
        names: dict[operation_graph.ActionTrigger, TriggeredActionNames] = {}
        for action_trigger in self._plan.action_triggers:
            base_name = base_names[action_trigger]
            names[action_trigger] = TriggeredActionNames(
                initializer_name=self._execution_allocator.allocate(
                    _INITIALIZER_PREFIX + base_name + _EXECUTION_SUFFIX
                ),
                execution_name=self._execution_allocator.allocate(
                    base_name + _EXECUTION_SUFFIX
                ),
            )
        return names

    def _triggered_input_method_names(
        self,
        triggered_action_base_names: dict[operation_graph.ActionTrigger, str],
    ) -> dict[action_plan.TriggeredActionInput, str]:
        method_names: dict[action_plan.TriggeredActionInput, str] = {}
        for triggered_input in self._plan.triggered_action_inputs:
            action_trigger = triggered_input.action_trigger
            callee_input_method_name = self._generated_actions[
                action_trigger.callee_action_name
            ].input_method_names[triggered_input.callee_input]
            method_names[triggered_input] = self._execution_allocator.allocate(
                triggered_action_base_names[action_trigger]
                + _TRIGGERED_INPUT_SEPARATOR
                + callee_input_method_name.removeprefix(_ACCEPT_CALLER_INPUT_PREFIX)
            )
        return method_names

    def _guarantee_publication_names(
        self,
        allocator: naming.NameAllocator,
    ) -> dict[action_plan.GuaranteePublication, str]:
        publication_names: dict[action_plan.GuaranteePublication, str] = {}
        for publication in self._plan.guarantee_publications:
            publication_names[publication] = allocator.allocate(
                self._guarantee_base_name(publication)
            )
        return publication_names

    def _child_guarantees_names(
        self,
        triggered_action_base_names: dict[operation_graph.ActionTrigger, str],
        allocator: naming.NameAllocator,
    ) -> dict[operation_graph.ActionTrigger, str]:
        child_guarantees_names: dict[operation_graph.ActionTrigger, str] = {}
        for action_trigger in self._plan.action_triggers:
            generated_callee = self._generated_actions[
                action_trigger.callee_action_name
            ]
            if generated_callee.guarantee_interface is not None:
                child_guarantees_names[action_trigger] = allocator.allocate(
                    triggered_action_base_names[action_trigger]
                )
        return child_guarantees_names

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
        # TODO: Carry AST typed-name objects to every caller of this method so
        # codegen can use their NameType and source-form APIs instead of parsing
        # canonical chained-name strings.
        parts: list[str] = []
        for typed_name in chain:
            typed_name_parts = ast.source_form_typed_name_parts(
                typed_name,
                self._current_fqun,
            )
            replaced_name = "".join(
                character if character.isalnum() else _IDENTIFIER_SEPARATOR
                for character in typed_name_parts.source_name
            )
            safe_name = _IDENTIFIER_SEPARATOR.join(
                part for part in replaced_name.split(_IDENTIFIER_SEPARATOR) if part
            )
            prefix = _GLOBAL_NAME_PREFIX if typed_name_parts.is_global else ""
            parts.append(
                prefix
                + typed_name_parts.name_type.value
                + _IDENTIFIER_SEPARATOR
                + safe_name
            )
        return _TYPED_CHAIN_SEPARATOR.join(parts)

    def _fragment_method_names(self) -> dict[action_plan.ActionFragment, str]:
        method_names: dict[action_plan.ActionFragment, str] = {}
        for fragment in self._plan.fragments:
            first_operation = fragment.operations[0]
            target = self._typed_chain_identifier(
                first_operation.target.canonical_chained_name_tuple
            )
            match first_operation:
                case operation_graph.MoveNode():
                    source = self._typed_chain_identifier(
                        first_operation.source.canonical_chained_name_tuple
                    )
                    base = (
                        _MOVE_FRAGMENT_PREFIX + source + _MOVE_TARGET_SEPARATOR + target
                    )
                case operation_graph.CreateNode():
                    base = _CREATE_FRAGMENT_PREFIX + target
                case operation_graph.DestroyNode():
                    base = _DESTROY_FRAGMENT_PREFIX + target
                case _:
                    raise TypeError(
                        "unsupported Particle Operation: "
                        + type(first_operation).__name__
                    )
            method_names[fragment] = self._execution_allocator.allocate(base)
        return method_names
