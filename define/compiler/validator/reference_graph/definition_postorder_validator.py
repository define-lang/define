"""Post-order validation for a single definition during the reference graph DFS walk."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import cached_property

from define.compiler import ast, diagnostics
from define.compiler.graphs import action_call_graph
from define.compiler.validator import scope_tracker
from define.compiler.validator.reference_graph import (
    action_contract,
    dead_constraint_tracker,
    particle_operation,
    particle_tracker,
    requirement_violation,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import operation_graph


@dataclass
class PostorderValidationResult:
    """Result of validating a single definition during the DFS post-order walk."""

    diagnostics: list[diagnostics.Diagnostic]
    edges: list[action_call_graph.ActionGraphEdge]
    contract: action_contract.ActionContract
    operation_graph: operation_graph.OperationGraph


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


class ActionPostorderValidator:
    """Validates an action definition during a DFS post-order walk of the reference graph."""

    _definition_result: validation_result.DefinitionValidationResult
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _action_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.ActionContract
    ]
    _definition_quality_cache: dict[
        tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
    ]
    _diagnostics: list[diagnostics.Diagnostic]
    _action_edges: list[action_call_graph.ActionGraphEdge]
    _inferred_requirements: dict[tuple[str, ...], action_contract.PositionRequirement]
    _destruction_contracts: list[action_contract.DestructionContract]
    _nested_guarantees: list[action_contract.NestedGuarantees]
    _dead_tracker: dead_constraint_tracker.DeadConstraintTracker

    def __init__(
        self,
        definition_result: validation_result.DefinitionValidationResult,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
        action_contracts: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_contract.ActionContract
        ],
        definition_quality_cache: dict[
            tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
        ],
    ):
        """Initialize with the definition to validate and the full results map."""
        self._definition_result = definition_result
        self._definition_results = definition_results
        self._action_contracts = action_contracts
        self._definition_quality_cache = definition_quality_cache
        self._diagnostics = []
        self._action_edges = []
        self._inferred_requirements = {}
        self._destruction_contracts = []
        self._nested_guarantees = []
        self._dead_tracker = dead_constraint_tracker.DeadConstraintTracker()

    @property
    def _definition(self) -> ast.QualityDefinition:
        return self._definition_result.definition

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    @cached_property
    def _tracker(self) -> particle_tracker.ParticleTracker:
        return particle_tracker.ParticleTracker(
            self._inferred_requirements,
            self._action_definition.trigger_position_reference,
        )

    @cached_property
    def _executor(self) -> particle_operation.ParticleOperationExecutor:
        return particle_operation.ParticleOperationExecutor(self._tracker)

    @cached_property
    def _implied_quality_list(self) -> tuple[ast.GlobalTypedNameReference, ...]:
        return tuple(
            impl.typed_global_name for impl in self._definition.quality_implications
        )

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
            contracted_position=inferred_from_chain,
            local_position=position,
            inferred_at=inferred_from_chain.location,
            propagated_from=None,
            scope=scope,
        )

    def _record_requirement(
        self,
        *,
        required_state: action_contract.PositionOccupancyState,
        contracted_position: ast.PositionReference,
        local_position: ast.PositionReference,
        inferred_at: ast.SourceLocation,
        propagated_from: action_contract.PositionRequirement | None,
        scope: scope_tracker.ScopeTracker,
        destructor_attachment: action_contract.DestructorAttachment | None = None,
    ):
        """Record a requirement in this definition's contract and reflect it in the tracker.

        Args:
            required_state: The state that the requirement says the position must be in.
            contracted_position: The requirement's position as we expose it in
                this action's contract.
            local_position: The position in this definition's local namespace
                that we are actually operating on.
            inferred_at: The statement this action inferred the requirement at.
            propagated_from: The inner requirement this was propagated
                from, or None for a directly inferred requirement.
            scope: The scope tracker (for resolving qualities of local positions).
        """
        requirement_key = contracted_position.canonical_chained_name_tuple
        # This both prevents us from double-inferring requirements, and also
        # implements the "caller requirements override callee requirements" part
        # of the spec (when recording propagated requirements).
        if requirement_key in self._inferred_requirements:
            return
        # If a position has been touched by a guarantee or any particle
        # statement already, no requirement should be emitted. This handles the
        # situation where one triggered action creates an EmptyGuarantee and
        # another action or caller tries to then destroy / move from that same
        # position.
        if self._tracker.has_been_touched(contracted_position):
            return
        self._inferred_requirements[requirement_key] = (
            action_contract.PositionRequirement(
                required_state=required_state,
                position=contracted_position,
                inferred_at=inferred_at,
                enclosing_action=self._action_definition,
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

    def _propagate_action_requirements(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate the triggered action's requirements into this definition's contract."""
        action_parent = action_chain.parent_position()
        parent_origin = self._parent_particle_comes_from_caller(action_parent)
        if parent_origin is not None:
            caller_path_to_action = action_chain.replace_parent_position_with_prefix(
                parent_origin
            )
        elif (
            isinstance(action_chain.typed_names[0], ast.GlobalTypedNameReference)
            and action_chain.typed_names[0].name_type == ast.NameType.ACTION
        ):
            caller_path_to_action = action_chain
        else:
            # We created the action's parent particle in this action.
            caller_path_to_action = None
        for inner_req in contract.requirements.values():
            self._maybe_propagate_one_requirement(
                inner_req, action_chain, caller_path_to_action, action_parent, scope
            )

    def _maybe_propagate_one_requirement(
        self,
        inner_req: action_contract.PositionRequirement,
        action_chain: ast.ActionReference,
        caller_path_to_action: ast.ChainedName | None,
        action_parent: ast.PositionReference | None,
        scope: scope_tracker.ScopeTracker,
    ):
        """Propagate ``inner_req`` when the caller must satisfy it.

        There are two different propagation situations:
        1. The callee's parent position was created by our caller, in which case
           we propagate all requirements that the current action did not satisfy.
        2. The callee's parent position was created by us (the current action) in
           which case we only propagate requirements when one of the particles
           in the callee's contracted positions came from our caller.

        To understand Case 2: it happens when the _parent_ particle of one of our
        contracted positions was moved by us (the current action) from one of our
        _own_ contracted positions. For example, let's say the requirement is on
        interface::b::c. We had our_interface with ::b::c as child positions, but
        all we did in this action is "move our_interface to interface." We don't
        actually _know_ the state of "b" and its child "c". Only our caller knows.
        """
        local_position = inner_req.position.in_caller(action_chain)
        moved_particle = None
        if not self._tracker.has_known_state(local_position):
            moved_particle = self._ancestor_from_contracted_position(
                local_position, action_parent
            )
        if moved_particle is not None:
            owner_key, owner = moved_particle
            # Make it the child of the contracted position, not the child of this
            # action.
            contracted_position = ast.PositionReference(
                location=local_position.location,
                typed_names=(
                    *owner.origin_position.typed_names,
                    *local_position.typed_names[len(owner_key) :],
                ),
            )
        elif caller_path_to_action is not None:
            # inner_req.position:
            #   position<iface>::position</box_target>::position</q>
            # contracted_position:
            #   position<outer_iface>::action</inner>::position<iface>::position</box_target>::position</q>
            contracted_position = inner_req.position.in_caller(caller_path_to_action)
        else:
            return
        self._record_requirement(
            required_state=inner_req.required_state,
            contracted_position=contracted_position,
            local_position=local_position,
            inferred_at=action_chain.location,
            propagated_from=inner_req,
            scope=scope,
        )

    def _ancestor_from_contracted_position(
        self,
        position: ast.PositionReference,
        action_parent: ast.PositionReference | None,
    ) -> tuple[tuple[str, ...], particle_tracker.ParticleInfo] | None:
        """If any of our parents were moved from a contracted position, return that ancestor's position and the particle in it."""
        nearest_ancestor = self._tracker.nearest_particle_above(position)
        if nearest_ancestor is None:
            # The ancestor is an implied action with no parent name.
            return None
        ancestor_position, ancestor_particle = nearest_ancestor
        if not ancestor_particle.from_caller:
            # This action created the ancestor, so it was not moved from a
            # contracted position.
            return None
        if (
            action_parent is not None
            and ancestor_position == action_parent.canonical_chained_name_tuple
        ):
            # The ancestor is the direct parent of the action. It's from the caller,
            # but that's what our normal propagation path handles, so
            # _maybe_propagate_one_requirement will just handle it.
            return None
        if (
            ancestor_position
            == ancestor_particle.origin_position.canonical_chained_name_tuple
        ):
            # The particle is still in its origin position, so it hasn't been moved.
            return None
        return nearest_ancestor

    def _parent_particle_comes_from_caller(
        self,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the parent particle's contracted-position origin chain if it came from the caller."""
        if parent is None:
            return None
        # This check is necessary because we have to run _maybe_infer_requirement
        # before the executor runs its parent-occupancy check, so we can run into
        # situations where the developer has written a statement that operates on
        # the child of a non-existent particle. The executor's parent check
        # will later detect this situation, emit a diagnostic, and mark the
        # relevant position error.
        if not self._tracker.is_occupied(parent):
            return None
        particle_info = self._tracker.get_occupant(parent)
        if not particle_info.from_caller:
            return None
        return particle_info.origin_position

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

    def _run_constructors(
        self,
        position: ast.PositionReference,
        qualities: tuple[ast.GlobalTypedNameReference, ...],
        scope: scope_tracker.ScopeTracker,
    ):
        """Trigger every constructor on the particle just created in position (DLP 32)."""
        for quality in qualities:
            if quality.name_type != ast.NameType.ACTION:
                continue
            definition_result = self._definition_results.get(quality)
            # The constructor's file may have failed to load or parse, which is
            # reported elsewhere; skipping it here keeps the cascade crash-free.
            if definition_result is None or not isinstance(
                definition_result.definition, ast.ActionDefinition
            ):
                continue
            if not definition_result.definition.is_constructor:
                continue
            contract = self._action_contracts[quality]
            # The constructor is a quality of the particle in `position`, so its
            # interface positions hang off position::action</construct> while its
            # implied qualities hang off the position itself.
            action_chain = position.with_action_suffix(quality)
            self._fire_triggered_action(contract, action_chain, position, scope)

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
        # An error-state position is opaque: we cannot claim its destructors
        # would fire and we cannot reason about its subtree, so the cascade
        # skips it entirely.
        occupancy = self._tracker.get_occupancy_info(position)
        if occupancy.has_error:
            return
        if occupancy.occupant is None:
            # Validation checks will throw an error later for this case,
            # if this is the root particle we are explicitly destroying.
            return
        # A particle keeps its own qualities across moves, so it is the source
        # of the qualities to check for destructors (not the position).
        particle = occupancy.occupant
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
            action_chain = destructor.position.with_action_suffix(destructor.quality)
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

    def _propagate_destructor_requirements(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
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
                contracted_position=inner_req.position.in_caller(
                    caller_path_to_destructor
                ),
                local_position=inner_req.position.in_caller(action_chain),
                inferred_at=caller_path_to_destructor.location,
                propagated_from=inner_req,
                scope=scope,
                destructor_attachment=attachment,
            )

    def _check_interface_fill_trigger(
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
        # The action's file may have failed to load or parse.
        contract = self._action_contracts.get(action_ref)
        if contract is None:
            return
        trigger_element = typing.cast(
            "ast.LocalTypedNameReference", interface_position.typed_names[0]
        )
        if trigger_element.full_typed_name != contract.trigger_position_name:
            return

        action_chain = position.get_chain_to_last_action()
        if action_chain is None:
            raise ValueError(f"no action in chain: {position.source_chained_name}")

        self._fire_triggered_action(
            contract,
            action_chain,
            self._tracker.get_occupant(position).last_position,
            scope,
        )

    def _fire_triggered_action(
        self,
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        self._propagate_action_requirements(contract, action_chain, scope)
        self._check_requirements(contract, action_chain, acting_on_position)
        self._check_destructor_requirements_from_contracts(
            contract, action_chain, scope
        )
        self._nested_guarantees.append(
            self._tracker.apply_guarantees(
                action_chain,
                contract.guarantees,
                acting_on_position,
                [
                    requirement.position
                    for requirement in contract.requirements.values()
                ],
            )
        )
        self._dead_tracker.mark_alive(action_chain)
        self._action_edges.append(
            action_call_graph.ActionGraphEdge(
                source=self._definition.typed_name.source_typed_name,
                target=action_chain.typed_names[-1].full_typed_name,
            )
        )

    def _check_requirements(
        self,
        contract: action_contract.ActionContract,
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
        #   req.position:
        #     position<iface>::action</inner>::position<item>
        #   full_caller_chain:
        #     position<box>::action</outer>::position<iface>::action</inner>::position<item>
        for req in contract.requirements.values():
            # TODO: This allocates a single-use ChainedName per requirement per
            # caller just so _check_one_requirement can read its
            # canonical_chained_name_tuple. Across a dense call graph this is one
            # of the top compiler-own hotspots (the ChainedName.__getattr__ +
            # in_caller cluster).
            full_caller_chain = req.position.in_caller(prefix_chain)
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
        occupancy = self._tracker.get_occupancy_info(full_caller_chain)
        if occupancy.has_error:
            return
        occupant = occupancy.occupant
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
        contract: action_contract.ActionContract,
        action_chain: ast.ActionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Verify caller-attached destructors that a triggered action's Destruction Contracts surfaced.

        Args:
            contract: The triggered action's contract, whose
                ``destruction_contracts`` are processed.
            action_chain: The names up to and including the triggered action.
                Each contract's contracted positions are remapped into this caller
                via ``in_caller(action_chain)``.
            scope: This definition's scope, used to resolve the position
                constraints that attach each destructor.
        """
        # The hop recording that this definition triggered the action, used
        # if its destruction contract has to be re-recorded and passed on to
        # the caller action. Constructed once here for memory efficiency so it
        # can be shared across mutliple destruction contracts as needed.
        trigger_step = action_contract.PropagationStep(
            location=action_chain.location,
            kind=action_contract.PropagationKind.ACTION_TRIGGER,
            enclosing_quality_name=self._definition.typed_name.source_typed_name,
            triggered_quality_name=action_chain.typed_names[-1].full_typed_name,
        )
        for destruction_contract in contract.destruction_contracts:
            self._check_one_destruction_contract(
                destruction_contract, action_chain, trigger_step, scope
            )

    def _check_one_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        action_chain: ast.ActionReference,
        trigger_step: action_contract.PropagationStep,
        scope: scope_tracker.ScopeTracker,
    ):
        caller_particle_position = (
            destruction_contract.destroyed_position_contracted.in_caller(action_chain)
        )
        # The action's requirement check already handles missing or
        # error-state particles, so there is nothing more to verify here.
        occupancy = self._tracker.get_occupancy_info(caller_particle_position)
        if occupancy.has_error or occupancy.occupant is None:
            return
        caller_particle = occupancy.occupant
        destroying_definition_result = self._definition_results.get(
            destruction_contract.destroying_action
        )
        destroying_definition = None
        if destroying_definition_result is not None and isinstance(
            destroying_definition_result.definition, ast.ActionDefinition
        ):
            destroying_definition = destroying_definition_result.definition
        # Only the action that created the particle may treat an untouched child as
        # empty; otherwise an untouched child's state is error, because a higher caller
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
            trigger_step=trigger_step,
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
                trigger_step,
            )

    def _re_record_destruction_contract(
        self,
        destruction_contract: action_contract.DestructionContract,
        caller_particle: particle_tracker.ParticleInfo,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        newly_verified: list[ast.GlobalTypedNameReference],
        trigger_step: action_contract.PropagationStep,
    ):
        # Carry the merged destruction-time picture and the destructors checked
        # so far upward; everything else describes the original destroyer and is
        # fixed. This definition's trigger of the callee leads the trigger chain,
        # since it runs before every hop already recorded below it.
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
                trigger_chain=(trigger_step, *destruction_contract.trigger_chain),
            )
        )

    def _verify_destruction_cascade(
        self,
        position: ast.PositionReference,
        *,
        destruction_contract: action_contract.DestructionContract,
        destroying_definition: ast.ActionDefinition | None,
        caller_prefix_length: int,
        trigger_step: action_contract.PropagationStep,
        scope: scope_tracker.ScopeTracker,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
        newly_verified: list[ast.GlobalTypedNameReference],
    ):
        occupancy_info = self._tracker.get_occupancy_info(position)
        if occupancy_info.has_error or occupancy_info.occupant is None:
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
        particle = occupancy_info.occupant
        for quality in reversed(particle.qualities):
            if quality.name_type == ast.NameType.POSITION:
                child = position.with_position_suffix(quality)
                self._verify_destruction_cascade(
                    child,
                    destruction_contract=destruction_contract,
                    destroying_definition=destroying_definition,
                    caller_prefix_length=caller_prefix_length,
                    trigger_step=trigger_step,
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
                        trigger_step=trigger_step,
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
                        trigger_step=trigger_step,
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
        trigger_step: action_contract.PropagationStep,
        scope: scope_tracker.ScopeTracker,
        merged_child_state: dict[tuple[str, ...], action_contract.ChildOccupancy],
        created_in_this_action: bool,
    ) -> bool:
        """Verify one destructor found in the cascade; return whether it was fully resolved here."""
        destructor_contract = self._action_contracts.get(destructor_quality)
        if destructor_contract is None or destroying_definition is None:
            return False
        action_chain = particle_position.with_action_suffix(destructor_quality)
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
                    trigger_step=trigger_step,
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
        action_chain: ast.ActionReference,
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
        required_position = inner_req.position.in_caller(action_chain)
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
            if self._tracker.has_error_state(required_position):
                occupancy = action_contract.ERROR_OCCUPANCY
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
                    self._dead_tracker.register_position_constraints(
                        stmt, self._definition_results
                    )
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
            occupancy = self._tracker.get_occupancy_info(position)
            if occupancy.has_error or occupancy.occupant is None:
                continue
            auto_destruction_target = occupancy.occupant.last_position
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
        if self._tracker.has_error_state(position):
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
        self._run_constructors(position, qualities, scope)
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
        if self._tracker.has_error_state(stmt.target_position):
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
            self._tracker.mark_error(stmt.source_position)
            self._tracker.mark_error(stmt.target_position)
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
        if self._tracker.has_error_state(from_pos) or self._tracker.has_error_state(
            to_pos
        ):
            self._tracker.mark_error(from_pos)
            self._tracker.mark_error(to_pos)
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
        # DLP 42: a constraint the destination requires is required for the
        # move, so it is marked alive against the moved particle's origin position.
        self._mark_move_required_constraints_alive(
            from_pos, target_required_qualities or ()
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

        Marks the chain's occupancy state as ERROR in the tracker if validation fails.
        """
        self._dead_tracker.mark_alive(chain)
        if len(chain.typed_names) < 2:
            return
        elements = chain.typed_names
        first = elements[0]
        # An interface position at index 0 is in scope and provides its own
        # constraints; every other parent name in the chain must be a global
        # definition that we have to look up.
        index = 0
        if scope.is_defined(first):
            self._check_chain_element_in_constraints(
                chain,
                elements[1],
                scope.get_definition(first).constraints,
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
                        position_def.constraints,
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
        """Get the QualityDefinition for a chain element, or None on failure (and mark chain error)."""
        parent_result = self._definition_results.get(parent)
        # This means the definition's file did not load or did not parse.
        if parent_result is None:
            self._tracker.mark_error(chain)
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
        if child.full_typed_name not in action_def.interface_positions_by_name:
            self._emit_not_in_action_diagnostic(chain, child, parent_name)
            return 0
        # The caller guarantees child exists, but not that the child's child exists.
        if child_index + 1 >= len(elements):
            return 1
        next_child = elements[child_index + 1]
        self._check_chain_element_in_constraints(
            chain,
            next_child,
            action_def.interface_positions_by_name[child.full_typed_name].constraints,
            child.source_typed_name,
        )
        return 2

    def _check_chain_element_in_constraints(
        self,
        chain: ast.PositionReference,
        element: ast.TypedNameReference,
        constraints: ast.PositionConstraintBlock | None,
        parent_name: str,
    ):
        """Check that a chain element is an explicit constraint of its parent name."""
        element_name = element.full_typed_name
        declared = constraints.as_set if constraints is not None else frozenset[str]()
        if element_name not in declared:
            self._diagnostics.append(
                diagnostics.ChainElementNotInConstraintsDiagnostic(
                    location=element.location,
                    element_name=element_name,
                    parent_name=parent_name,
                )
            )
            self._tracker.mark_error(chain)

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
        self._tracker.mark_error(chain)

    def _mark_move_required_constraints_alive(
        self,
        from_pos: ast.PositionReference,
        target_required: tuple[ast.GlobalTypedNameReference, ...],
    ):
        """Tell the ledger which of the moved particle's origin constraints the destination requires (DLP 42)."""
        if not self._dead_tracker.has_pending():
            return
        if self._tracker.has_error_state(from_pos) or not self._tracker.is_occupied(
            from_pos
        ):
            return
        origin = self._tracker.get_occupant(from_pos).origin_position
        self._dead_tracker.mark_move_required(origin, target_required)

    def _check_dead_constraints(self):
        """Emit a diagnostic for each constraint left dead per DLP 42's child-position and untriggered-action rules."""
        for candidate in self._dead_tracker.dead_constraints():
            diagnostic_class = (
                diagnostics.UntriggeredActionDiagnostic
                if candidate.constraint.name_type == ast.NameType.ACTION
                else diagnostics.DeadChildPositionDiagnostic
            )
            self._diagnostics.append(
                diagnostic_class(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )

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

    @property
    def _action_definition(self) -> ast.ActionDefinition:
        return typing.cast("ast.ActionDefinition", self._definition)

    @property
    def _interface_positions(self) -> dict[str, ast.LocalPositionDefinition]:
        return self._action_definition.interface_positions_by_name

    def _mark_output_interface_constraints_alive(
        self, own_guarantees: list[action_contract.GuaranteePair]
    ):
        """Mark alive the constraints of every interface position the action exposes as output (DLP 42).

        An interface position is output iff the action's own contract guarantees
        it holds a particle at the end (OccupiedByNew or OccupiedByExisting); its
        constraints then define a particle a caller consumes. Reading the actual
        first-level guarantees is correct however the position was filled, with no
        separate occupancy bookkeeping.
        """
        if not self._dead_tracker.has_pending():
            return
        for key, guarantee in own_guarantees:
            if len(key) != 1 or not isinstance(
                guarantee,
                action_contract.OccupiedByNewGuarantee
                | action_contract.OccupiedByExistingGuarantee,
            ):
                continue
            interface_def = self._interface_positions.get(key[0])
            if interface_def is not None:
                self._dead_tracker.mark_constraints_alive(
                    interface_def.typed_name, interface_def.constraint_typed_names
                )

    @property
    def _trigger_position_name(self) -> str | None:
        if self._action_definition.trigger_position is not None:
            return self._action_definition.trigger_position.typed_name.full_typed_name
        return None

    def analyze(self) -> PostorderValidationResult:
        """Run post-order validation and return diagnostics, edges, and contract."""
        action_def = self._action_definition
        contract = self._analyze_action_definition(action_def)
        return PostorderValidationResult(
            diagnostics=self._diagnostics,
            edges=self._action_edges,
            contract=contract,
            operation_graph=self._tracker.operation_graph,
        )

    def _check_trigger(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.ScopeTracker,
    ):
        """Check trigger, detecting self-triggering as an error."""
        if position.get_last_action_children() is not None:
            self._check_interface_fill_trigger(position, scope)
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
                self._dead_tracker.register_position_constraints(
                    pos, self._definition_results
                )

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

        # The contract's own guarantees tell us which interface positions the
        # action exposes as output, which keeps their constraints alive (DLP 42).
        contract = self._generate_contract()
        self._mark_output_interface_constraints_alive(contract.guarantees.own)
        self._check_dead_constraints()
        return contract

    def _generate_contract(self) -> action_contract.ActionContract:
        """Generate the action contract from inferred requirements and final tracker state."""
        if self._action_definition.is_destructor:
            guarantees = self._check_destructor_guarantees()
        else:
            guarantees = action_contract.Guarantees(
                own=self._tracker.generate_own_guarantees(
                    self._action_definition.interface_position_names,
                    self._implied_quality_list,
                    self._inferred_requirements,
                ),
                nested=tuple(self._nested_guarantees),
            )
        return action_contract.ActionContract(
            requirements=self._inferred_requirements,
            guarantees=guarantees,
            destruction_contracts=self._destruction_contracts,
            trigger_position_name=self._trigger_position_name or "",
        )

    def _check_destructor_guarantees(self) -> action_contract.Guarantees:
        """Emit a diagnostic for each guarantee a destructor produces and return a contract that masks them.

        A destructor may not change any contracted position's state (DLP 41), so
        each guarantee it produces is a violation. The returned contract may not
        advertise such a guarantee, so each is replaced with an ErrorGuarantee
        that leaves the position's post-destructor state undetermined for any
        consumer of the contract. The destructor's guarantees are fully expanded
        (no nested references), so the returned contract has no nested guarantees.
        """
        produced = self._tracker.generate_flattened_guarantees(
            self._action_definition.interface_position_names,
            self._implied_quality_list,
            self._inferred_requirements,
        )
        rewritten: list[action_contract.GuaranteePair] = []
        for key, guarantee in produced:
            # TODO: caused_by names the position as it was written in the action
            # where the guarantee originated, so a guarantee surfaced from a
            # deeply-nested triggered action gets that callee's short chained name
            # (e.g. "position<out>") instead of its full chained name relative to
            # the destructor (e.g.
            # "action</a>::position<box>::action</b>::position<out>"). ``key`` holds
            # that full chained name, but only as canonical names, not a source form.
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
                case action_contract.ErrorGuarantee():
                    rewritten.append((key, guarantee))
                    continue
                case action_contract.UnchangedGuarantee():
                    rewritten.append((key, guarantee))
                    continue
                case _:
                    raise TypeError(
                        f"unexpected guarantee type {type(guarantee).__name__}"
                    )
            rewritten.append(
                (key, action_contract.ErrorGuarantee(caused_by=guarantee.caused_by))
            )
        return action_contract.Guarantees(own=rewritten, nested=())

    def _chain_for_inferred_requirement(
        self,
        position: ast.PositionReference,
        parent: ast.PositionReference | None,
    ) -> ast.PositionReference | None:
        """Return the chain to record as `inferred_from`, or None if this isn't a contracted position."""
        # The population of the trigger position itself is handled elsewhere and
        # doesn't create a requirement. (However, actions on children of the
        # position still do create requirements.)
        if self._trigger_position_name == position.canonical_chained_name:
            return None
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
        """Whether the chain's first name is a contracted name of this action."""
        # The structural validator guarantees the name is defined, so we don't
        # re-check. An action's own interface positions are contracted; an
        # implied quality is global.
        return (
            position.starts_with_global
            or position.typed_names[0].full_typed_name in self._interface_positions
        )

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
