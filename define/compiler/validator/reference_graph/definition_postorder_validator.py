"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass, field
from functools import cached_property

from define.compiler import ast, diagnostics
from define.compiler.graphs import action_call_graph
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    particle_operation,
    particle_tracker,
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


@dataclass
class PostorderValidationResult:
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic] = field(default_factory=list)
    edges: list[action_call_graph.ActionGraphEdge] = field(default_factory=list)
    contract: action_contract.ActionStatementsBlockContract | None = None


@dataclass(frozen=True, slots=True)
class _CascadeDestructor:
    """One destructor in a destruction cascade, paired with the particle it fires on."""

    quality: ast.GlobalTypedNameReference
    position: ast.PositionReference
    origin_position: ast.PositionReference


@dataclass(frozen=True, slots=True)
class _ResolvedRequirement:
    """A destructor requirement whose required position's destruction-time occupancy is known here."""

    requirement: action_contract.PositionRequirement
    position: ast.PositionReference
    occupancy: action_contract.ChildOccupancy


class DefinitionPostorderValidator(abc.ABC):
    """Validates a single definition during a DFS post-order walk of the reference graph."""

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _action_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.ActionContract
    ]
    _position_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.PositionInitBlockContract
    ]
    _definition_quality_cache: dict[
        tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
    ]
    _diagnostics: list[diagnostics.Diagnostic]
    _action_edges: list[action_call_graph.ActionGraphEdge]
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]
    _destruction_contracts: list[action_contract.DestructionContract]

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
        action_contracts: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_contract.ActionContract
        ],
        position_contracts: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_contract.PositionInitBlockContract
        ],
        definition_quality_cache: dict[
            tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
        ],
    ):
        """Initialize with the definition to validate and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._action_contracts = action_contracts
        self._position_contracts = position_contracts
        self._definition_quality_cache = definition_quality_cache
        self._diagnostics = []
        self._action_edges = []
        self._inferred_requirements = {}
        self._destruction_contracts = []

    @property
    def _definition(self) -> ast.QualityDefinition:
        return self._definition_result.definition

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> particle_tracker.ParticleTracker:
        return particle_tracker.ParticleTracker()

    @cached_property
    def _executor(self) -> particle_operation.ParticleOperationExecutor:
        return particle_operation.ParticleOperationExecutor(self._tracker)

    @cached_property
    def _implied_quality_list(self) -> tuple[ast.GlobalTypedNameReference, ...]:
        return tuple(
            impl.typed_global_name for impl in self._definition.quality_implications
        )

    @abc.abstractmethod
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""

    def _maybe_infer_requirement(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        parent: ast.PositionReference | None,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer a requirement for a contracted position the first time it is referenced."""
        inferred_from_chain = self._chain_for_inferred_requirement(position, parent)
        if inferred_from_chain is None:
            return
        self._record_requirement(
            required_state=required_state,
            contracted_chain=inferred_from_chain,
            local_chain=position,
            propagated_from=None,
            scope=scope,
        )

    def _record_requirement(
        self,
        *,
        required_state: action_contract.PositionOccupancyState,
        contracted_chain: ast.ChainedName,
        local_chain: ast.ChainedName,
        propagated_from: action_contract.PositionRequirement | None,
        scope: scope_tracker.ScopeTracker,
        destructor_attachment: action_contract.DestructorAttachment | None = None,
    ):
        """Record a requirement in this definition's contract and reflect it in the tracker.

        Args:
            required_state: The state that the requirement says the position must be in.
            contracted_chain: The contracted chain as we would expose it
                in requirements for this action.
            local_chain: The chain in this definition's local
                namespace that we are actually operating on.
            propagated_from: The inner requirement this was propagated
                from, or None for a directly inferred requirement.
            scope: The scope tracker (for resolving qualities of local positions).
        """
        inferred_from = contracted_chain
        if propagated_from is not None:
            # We are recording a requirement that is propagating from an action
            # we are triggering.
            #
            # chain_in_requirement:
            #   position<iface>::position</box_target>::position</q>
            # contracted_position:
            #   position<outer_iface>::action</inner>::position<iface>::position</box_target>::position</q>
            # local_position:
            #   position<outer_box>::action</inner>::position<iface>::position</box_target>::position</q>
            chain_in_requirement = propagated_from.full_propagation_position_chain()
            contracted_position = chain_in_requirement.in_caller(contracted_chain)
            local_position = chain_in_requirement.in_caller(local_chain)
        else:
            # We are recording a requirement that this action generates itself.
            #
            # contracted_position:
            #   position<iface>::position</child>
            # local_position:
            #   position<some_local>::position</child>
            if not (
                isinstance(contracted_chain, ast.PositionReference)
                and isinstance(local_chain, ast.PositionReference)
            ):
                raise TypeError(
                    "directly-inferred requirements must be recorded with PositionReference chains"
                )
            contracted_position = contracted_chain
            local_position = local_chain
        requirement_key = contracted_position.canonical_chained_name_tuple
        # This both prevents us from double-inferring requirements, and also
        # implements the "caller requirements override callee requirements" part
        # of the spec (when recording propagated requirements).
        if requirement_key in self._inferred_requirements:
            return
        # If a position has been touched by a guarantee or any particle
        # statement already, no requirement should be emitted. This handles the
        # situation where a position init block creates an EmptyGuarantee and
        # another init block or caller tries to then destroy / move from that
        # same position.
        if self._tracker.has_been_touched(requirement_key):
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                inferred_from=inferred_from,
                enclosing_quality=self._definition,
                propagated_from=propagated_from,
                destructor_attachment=destructor_attachment,
            )
        )
        if required_state == action_contract.PositionOccupancyState.OCCUPIED:
            # We can't know exactly what qualities the particle has, but we
            # can know the minimal set that it _must_ have according to the constraints
            # the contracted position has.
            qualities = self._get_transitive_required_qualities(
                contracted_position, scope
            )
            self._executor.execute_assume_occupied(
                particle_operation.AssumeOccupied(
                    target=local_position,
                    qualities=qualities,
                    contracted_position_chain=contracted_position,
                )
            )
        elif required_state == action_contract.PositionOccupancyState.EMPTY:
            self._executor.execute_assume_empty(
                particle_operation.AssumeEmpty(target=local_position)
            )

    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the chain to record as ``inferred_from``, or None if this isn't a contracted position."""
        parent_origin = self._parent_particle_comes_from_caller(parent)
        if parent_origin is not None:
            # The particle was moved in from a contracted position, so we
            # put the requirement on that origin, not whatever position we are
            # inferring a requirement for.
            return position.replace_parent_position_with_prefix(parent_origin)
        if self._starts_with_contracted_name(position):
            return position
        return None

    def _starts_with_contracted_name(self, position: ast.PositionReference) -> bool:
        """Whether the chain's first name is a contracted name of this definition."""
        # Implied quality.
        return position.starts_with_global

    def _local_definition_cache_key(
        self,
        _local_name: ast.LocalTypedNameReference,
    ) -> tuple[str, ...] | None:
        """Return the cache key for a local-scope position, or None if uncacheable."""
        return None

    def _propagate_inner_requirements(
        self,
        contract: action_contract.ActionContract,
        trigger_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the triggered action's requirements into this definition's contract."""
        (action_chain, parent_origin) = (
            self._action_parent_comes_from_contracted_position(trigger_position)
        )
        if parent_origin is not None:
            caller_path_to_inner_action = (
                action_chain.replace_parent_position_with_prefix(parent_origin)
            )
        elif (
            isinstance(action_chain.typed_names[0], ast.GlobalTypedNameReference)
            and action_chain.typed_names[0].name_type == ast.NameType.ACTION
        ):
            caller_path_to_inner_action = action_chain
        else:
            return
        for inner_req in contract.requirements.values():
            self._record_requirement(
                required_state=inner_req.required_state,
                contracted_chain=caller_path_to_inner_action,
                local_chain=action_chain,
                propagated_from=inner_req,
                scope=scope,
            )

    def _parent_particle_comes_from_caller(
        self,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the parent particle's contracted-position origin chain if it came from the caller."""
        if parent is None:
            return None
        parent_key = parent.canonical_chained_name_tuple
        # This check is necessary because we have to run _maybe_infer_requirement
        # before the executor runs its parent-occupancy check, so we can run into
        # situations where the developer has written a statement that operates on
        # the child of a non-existent particle. The executor's parent check
        # will later detect this situation, emit a diagnostic, and mark the
        # relevant position unknown.
        if not self._tracker.is_occupied_by_key(parent_key):
            return None
        particle_info = self._tracker.get_occupant_by_key(parent_key)
        if not particle_info.from_caller:
            return None
        return particle_info.origin_position

    def _action_parent_comes_from_contracted_position(
        self,
        trigger_position: ast.PositionReference,
    ) -> tuple[ast.ChainedName, ast.PositionReference | None]:
        """Return the action's parent particle's contracted-position origin chain if it is from the caller."""
        action_chain = trigger_position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError("not an action")
        return (
            action_chain,
            self._parent_particle_comes_from_caller(action_chain.parent_position()),
        )

    def _maybe_infer_requirements_on_chain(
        self,
        required_state: action_contract.PositionOccupancyState,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Infer requirements for a position and all its parent positions.

        The leaf position uses the given required_state; all parent positions
        use OCCUPIED, since a parent must be occupied for its child to be
        accessible. Walks root-to-leaf so the tracker trie has parent nodes
        in place when children are inserted.
        """
        previous_parent: ast.PositionReference | None = None
        for parent in position.walk_parent_positions():
            # Note: We pass previous_parent down here because it avoids
            # a lot of parent_position calls (a lot of allocations, avoids
            # a lot of constructing new canonical_chained_name_tuple fields).
            self._maybe_infer_requirement(
                action_contract.PositionOccupancyState.OCCUPIED,
                parent,
                previous_parent,
                scope,
            )
            previous_parent = parent
        self._maybe_infer_requirement(required_state, position, previous_parent, scope)

    def _run_position_init_blocks(
        self,
        position: ast.PositionReference,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
        scope: scope_tracker.ScopeTracker,
    ):
        """Run the caller-side effects of every implied position's init block."""
        for quality in qualities:
            if quality.name_type != ast.NameType.POSITION:
                continue
            init_block_contract = self._position_contracts.get(quality)
            if init_block_contract is None:
                continue
            # TODO: Record an action-call-graph edge here from this definition to
            # the position whose Position Initialization Block runs (source =
            # self._definition.typed_name.source_typed_name, target =
            # quality.full_typed_name), the way _check_trigger records one for an
            # action trigger. Without it the call graph is disconnected at the
            # init-block boundary: the position's own init-block edges have no
            # incoming edge from the definition that ran them.
            self._propagate_init_block_requirements(
                position, init_block_contract, scope
            )
            self._check_init_block_requirements(position, init_block_contract, scope)
            self._tracker.apply_guarantees(
                position,
                init_block_contract.guarantees,
            )

    def _walk_destruction_cascade(
        self,
        destroyed_position: ast.PositionReference,
        *,
        is_auto_destruction: bool,
    ) -> list[_CascadeDestructor]:
        """Walk a destruction cascade once: record a Destruction Contract per caller-passed particle, and return the destructors to fire."""
        destructors: list[_CascadeDestructor] = []
        self._walk_cascade_into(
            destroyed_position,
            destroyed_position,
            destructors,
            is_auto_destruction=is_auto_destruction,
        )
        return destructors

    def _walk_cascade_into(
        self,
        position: ast.PositionReference,
        explicitly_destroyed_position: ast.PositionReference,
        destructors: list[_CascadeDestructor],
        *,
        is_auto_destruction: bool,
    ):
        # An unknown-state position is opaque: we cannot claim its destructors
        # would fire and we cannot reason about its subtree, so the cascade
        # skips it entirely.
        if self._tracker.has_unknown_state(position):
            return
        if not self._tracker.is_occupied(position):
            # Validation checks will throw an error later for this case,
            # if this is the root particle we are explicitly destroying.
            return
        # A particle keeps its own qualities across moves, so it is the source
        # of the qualities to check for destructors (not the position).
        particle = self._tracker.get_occupant(position)
        # Here, we walk the tree of particles in a depth-frst post-order traversal
        # as required by the destruction cascade.
        for quality in reversed(particle.qualities):
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                self._walk_cascade_into(
                    child,
                    explicitly_destroyed_position,
                    destructors,
                    is_auto_destruction=is_auto_destruction,
                )
            elif quality.name_type == ast.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                if definition_result is None or not isinstance(
                    definition_result.definition, ast.ActionDefinition
                ):
                    continue
                definition = definition_result.definition
                if definition.is_destructor:
                    destructors.append(
                        _CascadeDestructor(
                            quality=quality,
                            position=position,
                            origin_position=particle.origin_position,
                        )
                    )
                for interface_position in reversed(definition.interface_positions):
                    child = position.with_position_suffix(
                        quality, interface_position.typed_name
                    )
                    self._walk_cascade_into(
                        child,
                        explicitly_destroyed_position,
                        destructors,
                        is_auto_destruction=is_auto_destruction,
                    )
        if particle.from_caller:
            self._destruction_contracts.append(
                self._destruction_contract_for(
                    position,
                    particle,
                    explicitly_destroyed_position,
                    is_auto_destruction=is_auto_destruction,
                )
            )

    def _destruction_contract_for(
        self,
        position: ast.PositionReference,
        info: particle_tracker.ParticleInfo,
        destroyed_position_local: ast.PositionReference,
        *,
        is_auto_destruction: bool,
    ) -> action_contract.DestructionContract:
        """Build the Destruction Contract for one caller-passed particle the cascade destroyed."""
        return action_contract.DestructionContract(
            destroyed_position_contracted=info.origin_position,
            destroyed_position_local=destroyed_position_local,
            child_state=self._tracker.snapshot_child_state(position),
            destroying_action=self._definition.typed_name,
            # We know these destructors exist at destruction time, so they are
            # handled through the normal requirements mechanism (fired and
            # propagated as this action's own requirements), not through the
            # Destruction Contract's requirement-verification mechanism.
            verified_destructors=self._destructor_qualities(info.qualities),
            is_auto_destruction=is_auto_destruction,
        )

    def _run_destructors(
        self,
        destructors: list[_CascadeDestructor],
        scope: scope_tracker.ScopeTracker,
        auto_destruction_target: ast.PositionReference | None = None,
    ):
        """Trigger each destructor that fires during a destruction cascade."""
        # A destructor's requirements are checked as though it triggered
        # synchronously at the moment of destruction (DLP 41). The destructor is a
        # quality of the particle in `position`, so its interface positions
        # hang off position::action</destructor> while its implied qualities hang off
        # position itself; in_caller maps both correctly from this chain.
        for destructor in destructors:
            # _collect_cascade_destructors already verified the destructor's
            # definition loaded.
            contract = self._action_contracts[destructor.quality]
            action_chain = destructor.position.with_suffix(destructor.quality)
            attachment = self._destructor_attachment(
                destructor.quality, destructor.origin_position, scope
            )
            self._propagate_destructor_requirements(
                contract, action_chain, scope, attachment
            )
            self._check_requirements(
                contract,
                action_chain,
                destructor.position,
                is_destructor=True,
                destroy_target_origin_at=destructor.origin_position.location,
                auto_destruction_target=auto_destruction_target,
                destructor_attachment=attachment,
            )
            self._action_edges.append(
                action_call_graph.ActionGraphEdge(
                    source=self._definition.typed_name.source_typed_name,
                    target=destructor.quality.full_typed_name,
                )
            )

    def _propagate_init_block_requirements(
        self,
        create_target: ast.PositionReference,
        init_block_contract: action_contract.PositionInitBlockContract,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the init block's requirements into the enclosing definition's contract."""
        caller_path = self._chain_for_inferred_requirement(
            create_target, create_target.parent_position()
        )
        if caller_path is None:
            return
        for inner_req in init_block_contract.requirements.values():
            self._record_requirement(
                required_state=inner_req.required_state,
                contracted_chain=caller_path,
                local_chain=create_target,
                propagated_from=inner_req,
                scope=scope,
            )

    def _propagate_destructor_requirements(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ChainedName,
        scope: scope_tracker.ScopeTracker,
        attachment: action_contract.DestructorAttachment | None,
    ):
        """Propagate requirements into this action's contract when the destroyed particle itself was from a contracted position."""
        # For `move position<incoming> to position<local_box>.` followed by
        # `destroy position<local_box>.`:
        # action_chain:
        #   position<local_box>::action</destructor>
        # parent_origin:
        #   position<incoming>
        # caller_path_to_destructor:
        #   position<incoming>::action</destructor>
        parent_origin = self._parent_particle_comes_from_caller(
            action_chain.parent_position()
        )
        if parent_origin is None:
            return
        caller_path_to_destructor = action_chain.replace_parent_position_with_prefix(
            parent_origin
        )
        for inner_req in contract.requirements.values():
            self._record_requirement(
                required_state=inner_req.required_state,
                contracted_chain=caller_path_to_destructor,
                local_chain=action_chain,
                propagated_from=inner_req,
                scope=scope,
                destructor_attachment=attachment,
            )

    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check if filling this interface position triggers the named action.

        Only triggers when the chain ends with action<...>::position<trigger>,
        i.e., we're directly filling an action's interface position.
        """
        interface_position = position.get_last_action_children()
        if interface_position is None:
            return
        # Only trigger when filling a single interface position directly,
        # not children of interface positions.
        if len(interface_position.typed_names) != 1:
            return
        # Never None, because interface_position is not None.
        action_ref = typing.cast(
            "ast.GlobalTypedNameReference", position.get_last_action()
        )
        action_name = action_ref.full_typed_name
        # The action's file may have failed to load or parse.
        contract = self._action_contracts.get(action_ref)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.typed_names[0]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
            return

        # We only propagate inner requirements if actions actually get called.
        # (That's why this happens here in _check_trigger.)
        self._propagate_inner_requirements(contract, position, scope)
        self._check_action_requirements(position, contract, scope)
        self._tracker.apply_guarantees(position, contract.guarantees)
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action_name,
            )
        )

    def _check_action_requirements(
        self,
        trigger_position: ast.PositionReference,
        contract: action_contract.ActionContract,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check the triggered action's requirements and destruction contracts."""
        particle = self._tracker.get_occupant(trigger_position)
        action_chain = trigger_position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError(
                f"no action in chain: {trigger_position.source_chained_name}"
            )
        self._check_requirements(contract, action_chain, particle.last_position)
        self._check_destructor_requirements_from_contracts(
            contract, trigger_position, action_chain, scope
        )

    def _check_init_block_requirements(
        self,
        create_target: ast.PositionReference,
        contract: action_contract.PositionInitBlockContract,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check the init block's requirements and destruction contracts at the Create that assigns the position."""
        self._check_requirements(contract, create_target, create_target)
        self._check_destructor_requirements_from_contracts(
            contract, create_target, create_target, scope
        )

    def _check_requirements(
        self,
        contract: action_contract.ActionStatementsBlockContract,
        prefix_chain: ast.ChainedName,
        acting_on_position: ast.PositionReference,
        *,
        is_destructor: bool = False,
        destroy_target_origin_at: ast.SourceLocation | None = None,
        auto_destruction_target: ast.PositionReference | None = None,
        destructor_attachment: action_contract.DestructorAttachment | None = None,
    ):
        """Emit diagnostics for every requirement in contract that doesn't hold at acting_on_position."""
        # Action trigger:
        #   prefix_chain:
        #     position<box>::action</outer>
        #   acting_on_position:
        #     position<box>::action</outer>::position<trigger>
        #   req.full_propagation_position_chain():
        #     position<iface>::action</inner>::position<item>
        #   full_caller_chain:
        #     position<box>::action</outer>::position<iface>::action</inner>::position<item>
        # Init block:
        #   prefix_chain:
        #     position<box>
        #   acting_on_position:
        #     position<box>
        #   req.full_propagation_position_chain():
        #     position</q>::position</q_child>
        #   full_caller_chain:
        #     position<box>::position</q>::position</q_child>
        for req in contract.requirements.values():
            full_caller_chain = req.full_propagation_position_chain().in_caller(
                prefix_chain
            )
            self._check_one_requirement(
                full_caller_chain,
                acting_on_position,
                req,
                is_destructor=is_destructor,
                destroy_target_origin_at=destroy_target_origin_at,
                auto_destruction_target=auto_destruction_target,
                destructor_attachment=destructor_attachment,
            )

    def _check_one_requirement(
        self,
        full_caller_chain: ast.PositionReference,
        acting_on_position: ast.PositionReference,
        req: action_contract.PositionRequirement,
        *,
        is_destructor: bool,
        destroy_target_origin_at: ast.SourceLocation | None = None,
        auto_destruction_target: ast.PositionReference | None = None,
        destructor_attachment: action_contract.DestructorAttachment | None = None,
    ):
        """Emit a diagnostic if a single requirement is not satisfied."""
        key = full_caller_chain.canonical_chained_name_tuple
        if self._tracker.has_unknown_state_by_key(key):
            return
        occupant = (
            self._tracker.get_occupant_by_key(key)
            if self._tracker.is_occupied_by_key(key)
            else None
        )
        empty_violation = (
            req.required_state == action_contract.PositionOccupancyState.EMPTY
            and occupant is not None
        )
        occupied_violation = (
            req.required_state == action_contract.PositionOccupancyState.OCCUPIED
            and occupant is None
        )
        if not (empty_violation or occupied_violation):
            return
        if is_destructor:
            self._diagnostics.append(
                requirement_violation.direct_destructor(
                    req=req,
                    definition=self._definition,
                    full_caller_chain=full_caller_chain,
                    acting_on_position=acting_on_position,
                    occupant=occupant,
                    destroy_target_origin_at=destroy_target_origin_at,
                    auto_destruction_target=auto_destruction_target,
                    attachment=destructor_attachment,
                )
            )
            return
        self._diagnostics.append(
            requirement_violation.trigger_violation(
                req=req,
                definition=self._definition,
                full_caller_chain=full_caller_chain,
                acting_on_position=acting_on_position,
                occupant=occupant,
            )
        )

    def _destructor_qualities(
        self, qualities: tuple[ast.GlobalTypedNameReference, ...]
    ) -> tuple[ast.GlobalTypedNameReference, ...]:
        """Return the destructor-action qualities in firing order (reverse of assignment)."""
        # TODO: This feels inefficient to do every time, but let's wait for actual
        # profiling data to tell us if that's important.
        result: list[ast.GlobalTypedNameReference] = []
        for quality in reversed(qualities):
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            if definition_result is None or not isinstance(
                definition_result.definition, ast.ActionDefinition
            ):
                continue
            if definition_result.definition.is_destructor:
                result.append(quality)
        return tuple(result)

    def _check_destructor_requirements_from_contracts(
        self,
        contract: action_contract.ActionStatementsBlockContract,
        acting_position: ast.PositionReference,
        prefix_chain: ast.ChainedName,
        scope: scope_tracker.ScopeTracker,
    ):
        """Verify caller-attached destructors that a triggered action's or init block's Destruction Contracts surfaced.

        Args:
            contract: The triggered action's or init block's contract, whose
                ``destruction_contracts`` are processed.
            acting_position: The position whose filling drove this check (the
                trigger position for an action, the Create target for an init
                block); used as the location of any diagnostic emitted here.
            prefix_chain: The names in ``acting_position`` up to the triggered
                action (or the Create target for an init block). Each contract's
                contracted positions are remapped into this caller via
                ``in_caller(prefix_chain)``.
            scope: This definition's scope, used to resolve the position
                constraints that attach each destructor.
        """
        for destruction_contract in contract.destruction_contracts:
            self._check_one_destruction_contract(
                destruction_contract, acting_position, prefix_chain, scope
            )

    def _check_one_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        acting_position: ast.PositionReference,
        prefix_chain: ast.ChainedName,
        scope: scope_tracker.ScopeTracker,
    ):
        caller_particle_position = (
            destruction_contract.destroyed_position_contracted.in_caller(prefix_chain)
        )
        # The action's requirement check already handles missing or
        # unknown-state particles, so there is nothing more to verify here.
        if self._tracker.has_unknown_state(
            caller_particle_position
        ) or not self._tracker.is_occupied(caller_particle_position):
            return
        caller_particle = self._tracker.get_occupant(caller_particle_position)
        destroying_definition_result = self._definition_results.get(
            destruction_contract.destroying_action
        )
        destroying_definition = None
        if destroying_definition_result is not None and isinstance(
            destroying_definition_result.definition, ast.ActionDefinition
        ):
            destroying_definition = destroying_definition_result.definition
        # Only the action that created the particle may treat an untouched child as
        # empty; otherwise an untouched child's state is unknown, because a higher caller
        # could have filled it before passing it.
        created_in_this_action = not caller_particle.from_caller
        if created_in_this_action:
            # This action created the particle, so the child_state recorded in the
            # contract contains everything the action itself doesn't already know
            # (this is an optimization so we don't have to snapshot the child state
            # again during the action that created the particle).
            merged_child_state = destruction_contract.child_state
        else:
            # If this action is receiving a contract from an action it called,
            # then the callee's child state overrides the caller's child state.
            merged_child_state = self._tracker.snapshot_child_state(
                caller_particle_position
            )
            merged_child_state.update(destruction_contract.child_state)
        newly_verified: list[ast.GlobalTypedNameReference] = []
        self._verify_destruction_cascade(
            caller_particle_position,
            destruction_contract=destruction_contract,
            destroying_definition=destroying_definition,
            caller_prefix_length=len(
                caller_particle_position.canonical_chained_name_tuple
            ),
            acting_position=acting_position,
            scope=scope,
            merged_child_state=merged_child_state,
            created_in_this_action=created_in_this_action,
            newly_verified=newly_verified,
        )
        if not created_in_this_action:
            self._re_record_destruction_contract(
                destruction_contract,
                caller_particle,
                merged_child_state,
                newly_verified,
            )

    def _re_record_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        caller_particle: particle_tracker.ParticleInfo,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        newly_verified: list[ast.GlobalTypedNameReference],
    ):
        # Carry the merged destruction-time picture and the destructors checked
        # so far upward; everything else describes the original destroyer and is
        # fixed.
        self._destruction_contracts.append(
            action_contract.DestructionContract(
                destroyed_position_contracted=caller_particle.origin_position,
                destroyed_position_local=destruction_contract.destroyed_position_local,
                child_state=merged_child_state,
                destroying_action=destruction_contract.destroying_action,
                verified_destructors=(
                    *destruction_contract.verified_destructors,
                    *newly_verified,
                ),
                is_auto_destruction=destruction_contract.is_auto_destruction,
            )
        )

    def _verify_destruction_cascade(
        self,
        position: ast.PositionReference,
        *,
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition | None,
        caller_prefix_length: int,
        acting_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
        newly_verified: list[ast.GlobalTypedNameReference],
    ):
        if self._tracker.has_unknown_state(position) or not self._tracker.is_occupied(
            position
        ):
            return
        relative_key = position.canonical_chained_name_tuple[caller_prefix_length:]
        occupancy = merged_child_state.get(relative_key)
        # A position the destruction-time picture records as empty was emptied
        # before the destruction, so nothing there was destroyed and thus there
        # is no more work to do.
        if (
            occupancy is not None
            and occupancy.state == action_contract.PositionOccupancyState.EMPTY
        ):
            return
        particle = self._tracker.get_occupant(position)
        for quality in reversed(particle.qualities):
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                self._verify_destruction_cascade(
                    child,
                    destruction_contract=destruction_contract,
                    destroying_definition=destroying_definition,
                    caller_prefix_length=caller_prefix_length,
                    acting_position=acting_position,
                    scope=scope,
                    merged_child_state=merged_child_state,
                    created_in_this_action=created_in_this_action,
                    newly_verified=newly_verified,
                )
            elif quality.name_type == ast.NameType.ACTION:
                definition_result = self._definition_results.get(quality)
                if definition_result is None or not isinstance(
                    definition_result.definition, ast.ActionDefinition
                ):
                    continue
                definition = definition_result.definition
                if (
                    definition.is_destructor
                    and quality.full_typed_name
                    not in destruction_contract.verified_destructor_names
                    and self._verify_one_cascade_destructor(
                        destructor_quality=quality,
                        particle_position=position,
                        particle=particle,
                        destruction_contract=destruction_contract,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        acting_position=acting_position,
                        scope=scope,
                        merged_child_state=merged_child_state,
                        created_in_this_action=created_in_this_action,
                    )
                ):
                    newly_verified.append(quality)
                for interface_position in reversed(definition.interface_positions):
                    child = position.with_position_suffix(
                        quality, interface_position.typed_name
                    )
                    self._verify_destruction_cascade(
                        child,
                        destruction_contract=destruction_contract,
                        destroying_definition=destroying_definition,
                        caller_prefix_length=caller_prefix_length,
                        acting_position=acting_position,
                        scope=scope,
                        merged_child_state=merged_child_state,
                        created_in_this_action=created_in_this_action,
                        newly_verified=newly_verified,
                    )

    def _verify_one_cascade_destructor(
        self,
        *,
        destructor_quality: ast.GlobalTypedNameReference,
        particle_position: ast.PositionReference,
        particle: particle_tracker.ParticleInfo,
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition | None,
        caller_prefix_length: int,
        acting_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
    ) -> bool:
        """Verify one destructor found in the cascade; return whether it was fully resolved here."""
        destructor_contract = self._action_contracts.get(destructor_quality)
        if destructor_contract is None or destroying_definition is None:
            return False
        action_chain = particle_position.with_suffix(destructor_quality)
        attachment = self._destructor_attachment(
            destructor_quality, particle.origin_position, scope
        )
        # A destructor is checked exactly once: only at the action that knows the
        # state of every position it requires. Resolve the state of all required positions
        # first, before we attempt to check its requirements.
        resolved_requirements: list[_ResolvedRequirement] = []
        for inner_req in destructor_contract.requirements.values():
            resolution = self._resolve_destructor_requirement(
                inner_req=inner_req,
                action_chain=action_chain,
                caller_prefix_length=caller_prefix_length,
                merged_child_state=merged_child_state,
                created_in_this_action=created_in_this_action,
            )
            # If the state of any required position is not yet known, we
            # defer verification to our caller.
            if resolution is None:
                return False
            resolved_requirements.append(resolution)
        # Every required state is known here, so this is where the destructor is
        # actually verified; record the firing edge once, from the true destroyer.
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=destruction_contract.destroying_action.full_typed_name,
                target=destructor_quality.full_typed_name,
            )
        )
        for resolved_requirement in resolved_requirements:
            occupancy = resolved_requirement.occupancy
            required_state = resolved_requirement.requirement.required_state
            empty_violation = (
                required_state == action_contract.PositionOccupancyState.EMPTY
                and occupancy.state == action_contract.PositionOccupancyState.OCCUPIED
            )
            occupied_violation = (
                required_state == action_contract.PositionOccupancyState.OCCUPIED
                and occupancy.state == action_contract.PositionOccupancyState.EMPTY
            )
            if not (empty_violation or occupied_violation):
                continue
            self._diagnostics.append(
                requirement_violation.contract_destructor(
                    propagated_requirement=resolved_requirement.requirement,
                    resolved_position=resolved_requirement.position,
                    occupancy=occupancy,
                    definition=self._definition,
                    destroying_definition=destroying_definition,
                    destruction_contract=destruction_contract,
                    particle_position=particle_position,
                    particle=particle,
                    acting_position=acting_position,
                    attachment=attachment,
                )
            )
        return True

    def _destructor_attachment_location(
        self,
        destructor_quality: ast.GlobalTypedNameReference,
        origin_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> ast.SourceLocation | None:
        """Locate the constraint that puts the destructor on the particle created in origin_position.

        Prefers a constraint that is the destructor itself, then one that
        transitively implies it. Returns None when this scope cannot see a
        constraint that attaches the destructor: the particle arrived through a
        position whose constraints do not assign it, or it was created in a
        callee's local position this scope cannot resolve. In those cases no
        attachment step is shown.
        """
        last_origin_element = origin_position.typed_names[-1]
        if (
            isinstance(last_origin_element, ast.LocalTypedNameReference)
            and len(origin_position.typed_names) == 1
            and not scope.is_defined_local(origin_position)
        ):
            # The particle was created in a callee's local position, which this
            # scope cannot resolve. Per the TODO on
            # _get_transitive_required_qualities, the particle's carried
            # qualities don't yet record where each one was attached, so we
            # cannot point at the attaching constraint and show no attachment.
            return None
        direct, _ = self._get_direct_required_qualities(origin_position, scope)
        if direct is not None:
            # A constraint that directly declares the destructor is the clearest
            # attachment point, so it wins over one that only implies it.
            for root in direct:
                if root.full_typed_name == destructor_quality.full_typed_name:
                    return root.location
            for root in direct:
                if self._quality_implies(root, destructor_quality.full_typed_name):
                    return root.location
        return None

    def _destructor_attachment(
        self,
        destructor_quality: ast.GlobalTypedNameReference,
        origin_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> action_contract.DestructorAttachment | None:
        """Build the destructor's attachment, or None when this scope cannot see it."""
        attached_at = self._destructor_attachment_location(
            destructor_quality, origin_position, scope
        )
        if attached_at is None:
            return None
        return action_contract.DestructorAttachment(
            attached_at=attached_at,
            position=origin_position.typed_names[-1],
        )

    def _quality_implies(
        self, root: ast.GlobalTypedNameReference, target_full_typed_name: str
    ) -> bool:
        """Whether root transitively implies the named quality (not counting root itself)."""
        # TODO: This feels inefficient; we already did this walk to determine
        # the transitive qualities; we could preserve that informatiom somehow.
        definition_result = self._definition_results.get(root)
        if definition_result is None:
            return False
        seen = {root.full_typed_name}
        stack = [
            implication.typed_global_name
            for implication in definition_result.definition.quality_implications
        ]
        while stack:
            node = stack.pop()
            name = node.full_typed_name
            if name in seen:
                continue
            seen.add(name)
            if name == target_full_typed_name:
                return True
            definition_result = self._definition_results.get(node)
            if definition_result is not None:
                for implication in definition_result.definition.quality_implications:
                    stack.append(implication.typed_global_name)
        return False

    def _resolve_destructor_requirement(
        self,
        *,
        inner_req: action_contract.PositionRequirement,
        action_chain: ast.ChainedName,
        caller_prefix_length: int,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
    ) -> _ResolvedRequirement | None:
        """Resolve one requirement's position to its destruction-time state, or None if this action cannot know it."""
        # action_chain:
        #   position<box>::action</close_file>::position<target>::action</delete_file_destructor>
        # required_position:
        #   position<box>::action</close_file>::position<target>::position</file>
        # relative_key:
        #   ("position</file>",)
        required_position = inner_req.full_propagation_position_chain().in_caller(
            action_chain
        )
        relative_key = required_position.canonical_chained_name_tuple[
            caller_prefix_length:
        ]
        occupancy = merged_child_state.get(relative_key)
        if occupancy is None:
            # A passed-in particle's untouched position is decided higher up: this
            # action cannot resolve it, so the destructor travels up unchecked.
            if not created_in_this_action:
                return None
            # The owner created the particle, and we have optimized this case to
            # not copy the whole subtree to update a new child_state and instead
            # to just read the state out of the current tracker.
            if self._tracker.has_unknown_state(required_position):
                occupancy = action_contract.UNKNOWN_OCCUPANCY
            elif self._tracker.is_occupied(required_position):
                occupancy = action_contract.ChildOccupancy(
                    action_contract.PositionOccupancyState.OCCUPIED,
                    filled_at=self._tracker.get_occupant(
                        required_position
                    ).last_position.location,
                )
            else:
                occupancy = action_contract.EMPTY_OCCUPANCY
        return _ResolvedRequirement(
            requirement=inner_req,
            position=required_position,
            occupancy=occupancy,
        )

    def _analyze_statements(
        self,
        action_statements: ast.ActionStatementsBlock,
        scope: scope_tracker.ScopeTracker,
    ):
        validity_iter = iter(self._definition_result.particle_statement_validity)
        for stmt in action_statements.statements:
            match stmt:
                case ast.LocalPositionDefinition():
                    scope.add_definition(stmt)
                case ast.CreateParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_create(stmt, validity, scope)
                case ast.MoveParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_move(stmt, validity, scope)
                case ast.DestroyParticleStatement():
                    validity = next(validity_iter)
                    self._analyze_destroy(stmt, validity, scope)
        self._auto_destruct_locals(scope)

    def _auto_destruct_locals(self, scope: scope_tracker.ScopeTracker):
        """Destroy any particles still in positions defined locally in this block.

        Per the spec's "Automatic Destruction" section: at block end, particles
        still occupying positions defined only within this block are destroyed in
        reverse definition order, firing destructors along the way.
        """
        for definition in reversed(scope.current_scope_definitions()):
            if not isinstance(definition, ast.LocalPositionDefinition):
                continue
            position = ast.PositionReference(
                typed_names=(definition.typed_name,),
                location=definition.location,
            )
            # Spec: "If the compiler is uncertain about whether a position still
            # contains a particle, it only destroys the particle if
            # one is present."
            if self._tracker.has_unknown_state(position):
                continue
            if not self._tracker.is_occupied(position):
                continue
            auto_destruction_target = self._tracker.get_occupant(position).last_position
            destructors = self._walk_destruction_cascade(
                position, is_auto_destruction=True
            )
            self._run_destructors(
                destructors, scope, auto_destruction_target=auto_destruction_target
            )
            self._tracker.destroy(position)

    def _analyze_create(
        self,
        stmt: ast.CreateParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        position = stmt.target_position
        if self._tracker.has_unknown_state(position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, position, scope
        )
        qualities = self._get_transitive_required_qualities(position, scope)
        diags = self._executor.execute_create(
            particle_operation.Create(target=position, qualities=qualities)
        )
        self._diagnostics.extend(diags)
        if diags:
            return
        self._run_position_init_blocks(position, qualities, scope)
        self._check_trigger(position, scope)

    def _analyze_destroy(
        self,
        stmt: ast.DestroyParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not validity.target_ok:
            return
        self._validate_chained_name(stmt.target_position, scope)
        if self._tracker.has_unknown_state(stmt.target_position):
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, stmt.target_position, scope
        )

        def before_destroy():
            destructors = self._walk_destruction_cascade(
                stmt.target_position, is_auto_destruction=False
            )
            self._run_destructors(destructors, scope)

        diags = self._executor.execute_destroy(
            particle_operation.Destroy(target=stmt.target_position),
            before_destroy=before_destroy,
        )
        self._diagnostics.extend(diags)

    def _analyze_move(
        self,
        stmt: ast.MoveParticleStatement,
        validity: validation_result.ParticleStatementValidity,
        scope: scope_tracker.ScopeTracker,
    ):
        if not (validity.source_ok and validity.target_ok):
            return
        if validity.from_is_prefix_of_to:
            self._tracker.mark_unknown(stmt.source_position)
            self._tracker.mark_unknown(stmt.target_position)
            return
        self._validate_chained_name(stmt.source_position, scope)
        self._validate_chained_name(stmt.target_position, scope)
        if (
            stmt.source_position.canonical_chained_name_tuple
            == stmt.target_position.canonical_chained_name_tuple
        ):
            # We can't execute self-to-self moves because it would re-trigger
            # actions if the move is for a trigger position.
            return
        self._execute_move(stmt.source_position, stmt.target_position, scope)

    def _execute_move(
        self,
        from_pos: ast.PositionReference,
        to_pos: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Execute a move and update tracker state."""
        if self._tracker.has_unknown_state(from_pos) or self._tracker.has_unknown_state(
            to_pos
        ):
            self._tracker.mark_unknown(from_pos)
            self._tracker.mark_unknown(to_pos)
            return

        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.OCCUPIED, from_pos, scope
        )
        self._maybe_infer_requirements_on_chain(
            action_contract.PositionOccupancyState.EMPTY, to_pos, scope
        )

        target_required_qualities, _ = self._get_direct_required_qualities(
            to_pos, scope
        )
        move_diagnostics = self._executor.execute_move(
            particle_operation.Move(
                source=from_pos,
                target=to_pos,
                target_required_qualities=target_required_qualities or (),
            )
        )
        if move_diagnostics:
            self._diagnostics.extend(move_diagnostics)
            return
        self._check_trigger(to_pos, scope)

    def _validate_chained_name(
        self,
        chain: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Validate chained name elements against their parent name's constraints.

        Marks the chain's occupancy state as UNKNOWN in the tracker if validation fails.
        """
        if len(chain.typed_names) < 2:
            return
        elements = chain.typed_names
        first = elements[0]
        # An interface position (or position-self reference in an init
        # block) at index 0 is in scope and provides its own constraints;
        # every other parent name in the chain must be a global definition
        # that we have to look up.
        index = 0
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                chain,
                elements[1],
                scope.get_definition(first).constraint_typed_names,
                first.full_typed_name,
            )
            index = 1

        while index < len(elements) - 1:
            # The file_validator rejects any non-first local in a chain unless
            # it follows a global action, and _validate_action_chain_step
            # consumes that local along with the global, so parent is always
            # global here.
            parent = elements[index]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise TypeError(
                    f"chain parent at index {index} is not global: {parent}"
                )
            child = elements[index + 1]
            parent_def = self._get_chain_element_definition(parent, chain)
            if parent_def is None:
                return
            match parent_def:
                case ast.PositionDefinition() as position_def:
                    self._check_chain_element_in_constraints(
                        chain,
                        child,
                        position_def.constraint_typed_names,
                        parent.full_typed_name,
                    )
                    index += 1
                case ast.ActionDefinition() as action_def:
                    consumed = self._validate_action_chain_step(
                        chain,
                        child,
                        elements,
                        index + 1,
                        action_def,
                        parent.full_typed_name,
                    )
                    if consumed == 0:
                        return
                    index += consumed
                case _:
                    raise TypeError(f"Unexpected definition type: {type(parent_def)}")

    def _get_chain_element_definition(
        self,
        parent: ast.GlobalTypedNameReference,
        chain: ast.PositionReference,
    ) -> ast.QualityDefinition | None:
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain unknown)."""
        parent_result = self._definition_results.get(parent)
        # This means the definition's file did not load or did not parse.
        if parent_result is None:
            self._tracker.mark_unknown(chain)
            return None
        return parent_result.definition

    def _validate_action_chain_step(
        self,
        chain: ast.PositionReference,
        child: ast.TypedNameReference,
        elements: tuple[ast.TypedNameReference, ...],
        child_index: int,
        action_def: ast.ActionDefinition,
        parent_name: str,
    ) -> int:
        """Validate chain elements against an action definition's local positions.

        Returns the number of elements consumed (0 means stop walking).
        """
        # TODO: We should emit more specific diagnostics for these cases.
        if not isinstance(child, ast.LocalTypedNameReference):
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        if child.full_typed_name not in action_def.interface_position_constraints:
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            chain,
            next_child,
            action_def.interface_positions_by_name[
                child.full_typed_name
            ].constraint_typed_names,
            child.source_typed_name,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraints: tuple[ast.GlobalTypedNameReference, ...],
        parent_name: str,
    ):
        """Check if a chain element is declared in the parent's constraints (or transitively implied by one)."""
        element_name = element.full_typed_name
        # TODO: This could be slightly more efficient by making _expand_with_implications_in_order
        # a generator and just checking as we go through if we see the name or not, I think.
        expanded = {
            name.full_typed_name
            for name in self._expand_with_implications_in_order(constraints)
        }
        if element_name not in expanded:
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_unknown(chain)

    def _emit_not_in_action_diagnostic(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        parent_name: str,
    ):
        """Emit a diagnostic for a chain element not found in an action definition."""
        self._diagnostics.append(
            diagnostics.ChainElementNotInActionDiagnostic(
                location=element.location,
                element_name=element.full_typed_name,
                parent_name=parent_name,
            )
        )
        self._tracker.mark_unknown(chain)

    def _get_direct_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> tuple[
        tuple[ast.GlobalTypedNameReference, ...] | None,
        tuple[str, ...] | None,
    ]:
        """Resolve the constraint qualities required at a position, in source order.

        Also returns the cache key identifying the cacheable entity (a
        global position or an action interface position), or ``None``
        for local positions defined inside of an Action Statements Block.
        """
        if scope.is_defined_local(position):
            # is_defined_local already verified the chain is a single LocalTypedNameReference.
            local_name = typing.cast(
                "ast.LocalTypedNameReference", position.typed_names[0]
            )
            definition = scope.get_definition(local_name)
            return (
                definition.constraint_typed_names,
                self._local_definition_cache_key(local_name),
            )

        last_element = position.typed_names[-1]

        if isinstance(last_element, ast.LocalTypedNameReference):
            # Local position inside an action — look up the parent action's
            # interface position definition. Chain validation guarantees the
            # parent is a global action reference whose definition exists and
            # contains this interface position. A bare local from another scope
            # has no parent action here; the only caller that can hold one,
            # _destructor_attachment_location, filters it out before this point.
            parent = typing.cast(
                "ast.GlobalTypedNameReference", position.typed_names[-2]
            )
            action_def = self._definition_results[parent].definition
            action_def = typing.cast("ast.ActionDefinition", action_def)
            return (
                action_def.interface_positions_by_name[
                    last_element.full_typed_name
                ].constraint_typed_names,
                (parent.full_typed_name, last_element.full_typed_name),
            )

        # This can be None if the last element in the chain is a definition we never loaded
        # (file not found or failed to parse).
        definition_result = self._definition_results.get(last_element)
        if definition_result is None:
            return (None, None)
        position_def = typing.cast(
            "ast.PositionDefinition", definition_result.definition
        )
        return (position_def.constraint_typed_names, (last_element.full_typed_name,))

    def _get_transitive_required_qualities(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ) -> tuple[ast.GlobalTypedNameReference, ...]:
        # TODO: This flattens the qualities into a list, discarding the tree of
        # which constraint attached each one — directly, or transitively through
        # which implying quality. Recording that structure here and carrying it
        # on ParticleInfo.qualities would let _destructor_attachment_location
        # resolve the attachment for a particle a callee created in a local
        # position, which the destroying scope can no longer look up.
        direct, cache_key = self._get_direct_required_qualities(position, scope)
        if direct is None:
            return ()
        if cache_key is None:
            return self._expand_with_implications_in_order(direct)
        cached = self._definition_quality_cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._expand_with_implications_in_order(direct)
        self._definition_quality_cache[cache_key] = result
        return result

    def _expand_with_implications_in_order(
        self, direct: tuple[ast.GlobalTypedNameReference, ...]
    ) -> tuple[ast.GlobalTypedNameReference, ...]:
        """Expand quality implications depth-first, implications before the implying quality.

        Order follows the spec: when a quality A implies B, B is assigned
        beforehand. Implications are walked in source order.
        """
        seen: set[str] = set()
        result: list[ast.GlobalTypedNameReference] = []

        def visit(typed_name: ast.GlobalTypedNameReference):
            name = typed_name.full_typed_name
            if name in seen:
                return
            seen.add(name)
            defn_result = self._definition_results.get(typed_name)
            if defn_result is not None:
                for impl in defn_result.definition.quality_implications:
                    visit(impl.typed_global_name)
            result.append(typed_name)

        for typed_name in direct:
            visit(typed_name)
        return tuple(result)


class ActionPostorderValidator(DefinitionPostorderValidator):
    """Validates an action definition during a DFS post-order walk."""

    @property
    def _action_definition(self) -> ast.ActionDefinition:
        return typing.cast("ast.ActionDefinition", self._definition)

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._action_definition.interface_positions_by_name

    @property
    def _trigger_position_name(self) -> str | None:
        if self._action_definition.trigger_position is not None:
            return self._action_definition.trigger_position.typed_name.full_typed_name
        return None

    @typing.override
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""
        action_def = self._action_definition
        contract = self._analyze_action_definition(action_def)
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
        )

    @typing.override
    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        if position.get_last_action_children() is not None:
            super()._check_trigger(position, scope)
            return
        if self._trigger_position_name is None:
            return
        if len(position.typed_names) != 1:
            return
        if position.typed_names[0].full_typed_name != self._trigger_position_name:
            return
        self._diagnostics.append(
            diagnostics.ActionSelfTriggerDiagnostic(
                location=position.location,
                action_name=self._definition.typed_name.source_typed_name,
                position_name=position.source_chained_name,
            )
        )

    def _analyze_action_definition(
        self,
        definition: ast.ActionDefinition,
    ) -> action_contract.ActionContract:
        scope = scope_tracker.ScopeTracker()
        for pos in definition.interface_positions:
            # Skip duplicates so the first definition's constraints are preserved,
            # matching file_validator's behavior of not adding conflicting names.
            if not scope.is_defined(pos.typed_name):
                scope.add_definition(pos)

        # Set all positions from the Trigger Conditions Block as having
        # the state that the Trigger Conditions Block says they have.
        trigger_ref = self._action_definition.trigger_position_reference
        if trigger_ref is not None:
            typed_name = trigger_ref.typed_names[0]
            if scope.is_defined(typed_name):
                qualities = self._get_transitive_required_qualities(trigger_ref, scope)
                # DLP 37: We assume trigger points are occupied upon the start
                # of the action, but we can only assume they have the qualities
                # they are declared with.
                self._executor.execute_assume_occupied(
                    particle_operation.AssumeOccupied(
                        target=trigger_ref,
                        qualities=qualities,
                        contracted_position_chain=trigger_ref,
                    )
                )

        scope.enter_child_scope()
        self._analyze_statements(definition.action_statements, scope)

        return self._generate_contract()

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        guarantees = self._tracker.generate_guarantees(
            self._action_definition.interface_position_names,
            self._implied_quality_list,
            self._inferred_requirements,
        )
        if self._action_definition.is_destructor:
            guarantees = self._check_destructor_guarantees(guarantees)
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
            destruction_contracts=self._destruction_contracts,
            trigger_position_name=self._trigger_position_name or "",
        )

    def _check_destructor_guarantees(
        self, guarantees: list[action_contract.GuaranteePair]
    ) -> list[action_contract.GuaranteePair]:
        """Emit a diagnostic for each guarantee a destructor produces and replace it with an UnknownGuarantee.

        A destructor may not change any contracted position's state (DLP 41), so
        each produced guarantee is a violation. The contract it returns may not
        advertise such a guarantee, so each is replaced with an UnknownGuarantee
        that leaves the position's post-destructor state undetermined for any
        consumer of the contract.
        """
        rewritten: list[action_contract.GuaranteePair] = []
        for key, guarantee in guarantees:
            position_name = guarantee.caused_by.source_form_in_universe(
                self._enclosing_fqun
            )
            match guarantee:
                case action_contract.EmptyGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesEmptyGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                        )
                    )
                case action_contract.OccupiedByNewGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                        )
                    )
                case action_contract.OccupiedByExistingGuarantee():
                    self._diagnostics.append(
                        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic(
                            location=guarantee.caused_by.location,
                            position_name=position_name,
                            origin_name=guarantee.origin_position.source_form_in_universe(
                                self._enclosing_fqun
                            ),
                        )
                    )
                case action_contract.UnknownGuarantee():
                    rewritten.append((key, guarantee))
                    continue
                case _:
                    raise TypeError(
                        f"unexpected guarantee type {type(guarantee).__name__}"
                    )
            rewritten.append(
                (key, action_contract.UnknownGuarantee(caused_by=guarantee.caused_by))
            )
        return rewritten

    @typing.override
    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # The population of the base trigger position itself is handled elsewhere
        # and doesn't create a requirement. (However, actions on children
        # of the position still do create requirements.)
        if self._trigger_position_name == position.canonical_chained_name:
            return None
        return super()._chain_for_inferred_requirement(position, parent)

    @typing.override
    def _starts_with_contracted_name(self, position: ast.PositionReference) -> bool:
        """Whether the chain's first name is a contracted name of this action."""
        # The structural validator guarantees the name is defined, so we don't
        # re-check. An action's own interface positions are contracted.
        return (
            super()._starts_with_contracted_name(position)
            or position.typed_names[0].full_typed_name in self._interface_positions
        )

    @typing.override
    def _local_definition_cache_key(
        self,
        local_name: ast.LocalTypedNameReference,
    ) -> tuple[str, ...] | None:
        """Cache interface positions so the action's own processing fills the same key external references use."""
        if local_name.full_typed_name in self._interface_positions:
            return (
                self._action_definition.typed_name.full_typed_name,
                local_name.full_typed_name,
            )
        return None


class PositionPostorderValidator(DefinitionPostorderValidator):
    """Validates a position definition during a DFS post-order walk."""

    @typing.override
    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics and edges."""
        definition = typing.cast("ast.PositionDefinition", self._definition)
        contract = self._analyze_position_definition(definition)
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
        )

    @typing.override
    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # Doing things with the self-reference or any of its children
        # doesn't create a requirement because _nothing_ could have run
        # before the position's own init block. Thus, we know for sure
        # that it's empty when it runs.
        if (
            position.typed_names[0].full_typed_name
            == self._definition.typed_name.full_typed_name
        ):
            return None
        return super()._chain_for_inferred_requirement(position, parent)

    def _analyze_position_definition(
        self, definition: ast.PositionDefinition
    ) -> action_contract.PositionInitBlockContract | None:
        if definition.initialization is None:
            return None
        scope = scope_tracker.ScopeTracker()
        # The self-position lives in the outer scope (so we don't try to auto-destroy
        # it at the end of the init block).
        scope.add_definition(definition)
        scope.enter_child_scope()
        self._analyze_statements(definition.initialization, scope)
        return action_contract.PositionInitBlockContract(
            requirements=self._inferred_requirements,
            guarantees=self._tracker.generate_guarantees(
                (definition.typed_name,),
                self._implied_quality_list,
                self._inferred_requirements,
            ),
            destruction_contracts=self._destruction_contracts,
        )


def create_postorder_validator(
    definition_result: validation_result.DefinitionValidationResult,
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ],
    action_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.ActionContract
    ],
    position_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.PositionInitBlockContract
    ],
    definition_quality_cache: dict[
        tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
    ],
) -> DefinitionPostorderValidator:
    """Create the appropriate postorder validator for the given definition."""
    if isinstance(definition_result.definition, ast.ActionDefinition):
        return ActionPostorderValidator(
            definition_result,
            definition_results,
            action_contracts,
            position_contracts,
            definition_quality_cache,
        )
    if isinstance(definition_result.definition, ast.PositionDefinition):
        return PositionPostorderValidator(
            definition_result,
            definition_results,
            action_contracts,
            position_contracts,
            definition_quality_cache,
        )
    raise TypeError(f"Unexpected definition type: {type(definition_result.definition)}")
