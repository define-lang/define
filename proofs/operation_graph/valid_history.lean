import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Valid Resolved Particle Operation Histories

`ValidResolvedHistory` formalizes the history in `valid-history.md`. It records
the Particle Operation preconditions and exact occupancy transitions, while the
theorems below derive prefix closure, the responsible operation for newly
occupied positions, the state after a non-Move, and Move occupancy preservation.
It also records the resolved position names whose most-recent Particle
Operation may be queried at each index. It remains independent of every
operation graph rule; deriving that name trace from resolved Define source is a
separate formalization boundary.

`ExactOccupancyExecution` is the stronger interface consumed by the existing
minimality and completeness modules. It remains temporarily while those modules
are migrated to the universal calculation-correctness construction; unlike
`ValidResolvedHistory`, it assumes prefix closure at every index. No new theorem
should use that field as a substitute for the derived prefix-closure theorem.
-/

namespace Define.OperationGraph

theorem exists_occupancy_transition (occupied : Nat → Prop)
    {start finish : Nat} (start_le_finish : start ≤ finish)
    (unoccupied_at_start : ¬occupied start)
    (occupied_at_finish : occupied finish) :
    ∃ transition,
      start ≤ transition ∧
        transition < finish ∧
        ¬occupied transition ∧
        occupied (transition + 1) := by
  rcases Nat.exists_eq_add_of_le start_le_finish with ⟨distance, finish_eq⟩
  subst finish
  induction distance with
  | zero =>
      exact False.elim (unoccupied_at_start occupied_at_finish)
  | succ distance induction_hypothesis =>
      by_cases occupied_before_finish : occupied (start + distance)
      · rcases
          induction_hypothesis (Nat.le_add_right start distance)
            occupied_before_finish with
          ⟨transition, start_le_transition, transition_before_previous,
            unoccupied_before_transition, occupied_after_transition⟩
        exact
          ⟨transition, start_le_transition,
            Nat.lt_trans transition_before_previous (by omega),
            unoccupied_before_transition, occupied_after_transition⟩
      · refine ⟨start + distance, ?_, ?_, occupied_before_finish, ?_⟩
        · exact Nat.le_add_right start distance
        · omega
        · simpa [Nat.add_assoc] using occupied_at_finish

structure ValidResolvedHistory (isOperation : ParticleOperation → Prop) where
  operationAt : Nat → Option ParticleOperation
  occupiedBefore : Nat → Position → Prop
  queryableBefore : Nat → Position → Prop
  member_operation_at :
    ∀ operation,
      isOperation operation →
        operationAt operation.operationOrder = some operation
  operation_at_is_member :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        isOperation operation
  operation_at_has_order :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        operation.operationOrder = operationOrder
  no_operation_after_none :
    ∀ firstOrder laterOrder,
      firstOrder ≤ laterOrder →
        operationAt firstOrder = none →
        operationAt laterOrder = none
  initial_prefix_closed : PrefixClosed (occupiedBefore 0)
  queryable_prefix_closed :
    ∀ operationOrder, PrefixClosed (queryableBefore operationOrder)
  occupied_position_is_queryable :
    ∀ operationOrder position,
      occupiedBefore operationOrder position →
        queryableBefore operationOrder position
  operated_position_is_queryable :
    ∀ operation position,
      isOperation operation →
        OperatesOn operation position →
        queryableBefore operation.operationOrder position
  operated_position_remains_queryable :
    ∀ operationOrder operation position,
      isOperation operation →
        operation.operationOrder < operationOrder →
        OperatesOn operation position →
        queryableBefore operationOrder position
  empty_position_is_occupied :
    ∀ operation source,
      isOperation operation →
        EmptyPosition operation = some source →
        occupiedBefore operation.operationOrder source
  fill_position_is_available :
    ∀ operation target,
      isOperation operation →
        FillPosition operation = some target →
        Available (occupiedBefore operation.operationOrder) target
  fill_position_is_empty :
    ∀ operation target,
      isOperation operation →
        FillPosition operation = some target →
        ¬occupiedBefore operation.operationOrder target
  move_source_not_parent_of_target :
    ∀ operation source target,
      isOperation operation →
        operation.kind = .move source target →
        ¬ParentOrSame source target
  operated_position_has_action_parent :
    ∀ operation position,
      isOperation operation →
        OperatesOn operation position →
        ParentOrSame operation.actionParent position
  operation_transition :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        ∀ position,
          occupiedBefore (operationOrder + 1) position ↔
            OccupancyAfter operation (occupiedBefore operationOrder) position
  no_operation_transition :
    ∀ operationOrder,
      operationAt operationOrder = none →
        ∀ position,
          occupiedBefore (operationOrder + 1) position ↔
            occupiedBefore operationOrder position

theorem ValidResolvedHistory.operation_enabled
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation : ParticleOperation}
    (operation_member : isOperation operation) :
    OperationEnabled operation
      (history.occupiedBefore operation.operationOrder) := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [OperationEnabled, operation_kind]
      exact
        ⟨history.fill_position_is_available operation target operation_member
            (by simp [FillPosition, operation_kind]),
          history.fill_position_is_empty operation target operation_member
            (by simp [FillPosition, operation_kind])⟩
  | destroy target =>
      simp only [OperationEnabled, operation_kind]
      exact
        history.empty_position_is_occupied operation target operation_member
          (by simp [EmptyPosition, operation_kind])
  | move source target =>
      simp only [OperationEnabled, operation_kind]
      exact
        ⟨history.empty_position_is_occupied operation source operation_member
            (by simp [EmptyPosition, operation_kind]),
          history.fill_position_is_available operation target operation_member
            (by simp [FillPosition, operation_kind]),
          history.fill_position_is_empty operation target operation_member
            (by simp [FillPosition, operation_kind]),
          history.move_source_not_parent_of_target operation source target
            operation_member operation_kind⟩

theorem occupancyAfter_preserves_prefixClosure
    {operation : ParticleOperation} {occupiedBefore : Position → Prop}
    (prefix_closed : PrefixClosed occupiedBefore)
    (fill_available :
      ∀ target,
        FillPosition operation = some target → Available occupiedBefore target)
    (move_source_not_parent_of_target :
      ∀ source target,
        operation.kind = .move source target →
          ¬ParentOrSame source target) :
    PrefixClosed (OccupancyAfter operation occupiedBefore) := by
  intro parent child parent_of_child child_occupied
  cases operation_kind : operation.kind with
  | create target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      rcases child_occupied with child_is_target | child_occupied
      · subst child
        by_cases parent_is_target : parent = target
        · exact Or.inl parent_is_target
        · exact
            Or.inr
              (fill_available target (by simp [FillPosition, operation_kind])
                parent parent_of_child parent_is_target)
      · exact Or.inr (prefix_closed parent child parent_of_child child_occupied)
  | destroy target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      exact
        ⟨fun target_parent =>
          child_occupied.1 (target_parent.trans parent_of_child),
          prefix_closed parent child parent_of_child child_occupied.2⟩
  | move source target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      rcases child_occupied with
        ⟨relativePosition, child_is_target_child, source_child_occupied⟩ |
        ⟨source_not_parent, target_not_parent, child_occupied⟩
      · have target_of_child : ParentOrSame target child :=
          ⟨relativePosition, child_is_target_child.symm⟩
        rcases
            List.prefix_or_prefix_of_prefix parent_of_child target_of_child with
          parent_of_target | target_of_parent
        · by_cases parent_is_target : parent = target
          · subst parent_is_target
            exact
              Or.inl
                ⟨[], by simp,
                  by
                    simpa using
                      prefix_closed source (source ++ relativePosition)
                        ⟨relativePosition, rfl⟩ source_child_occupied⟩
          · refine Or.inr ⟨?_, ?_, ?_⟩
            · intro source_of_parent
              exact
                move_source_not_parent_of_target source target operation_kind
                  (source_of_parent.trans parent_of_target)
            · intro target_of_parent_again
              exact
                parent_is_target
                  (parentOrSame_antisymm parent_of_target
                    target_of_parent_again)
            · exact
                fill_available target (by simp [FillPosition, operation_kind])
                  parent parent_of_target parent_is_target
        · rcases target_of_parent with ⟨parentRelative, parent_is_target_child⟩
          subst parent_is_target_child
          subst child_is_target_child
          have relative_parent :
              ParentOrSame parentRelative relativePosition :=
            parentOrSame_resolve_iff.mp parent_of_child
          exact
            Or.inl
              ⟨parentRelative, rfl,
                prefix_closed (source ++ parentRelative)
                  (source ++ relativePosition)
                  (parentOrSame_resolve_iff.mpr relative_parent)
                  source_child_occupied⟩
      · exact
          Or.inr
            ⟨fun source_of_parent =>
              source_not_parent (source_of_parent.trans parent_of_child),
              fun target_of_parent =>
                target_not_parent (target_of_parent.trans parent_of_child),
              prefix_closed parent child parent_of_child child_occupied⟩

theorem ValidResolvedHistory.prefix_closed
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat) :
    PrefixClosed (history.occupiedBefore operationOrder) := by
  induction operationOrder with
  | zero =>
      exact history.initial_prefix_closed
  | succ previousOrder induction_hypothesis =>
      change PrefixClosed (history.occupiedBefore (previousOrder + 1))
      cases operation_at : history.operationAt previousOrder with
      | none =>
          intro parent child parent_of_child child_occupied
          have child_occupied_before :
              history.occupiedBefore previousOrder child :=
            (history.no_operation_transition previousOrder operation_at child).mp
              child_occupied
          have parent_occupied_before :
              history.occupiedBefore previousOrder parent :=
            induction_hypothesis parent child parent_of_child
              child_occupied_before
          exact
            (history.no_operation_transition previousOrder operation_at parent).mpr
              parent_occupied_before
      | some operation =>
          have operation_member : isOperation operation :=
            history.operation_at_is_member previousOrder operation operation_at
          have operation_order : operation.operationOrder = previousOrder :=
            history.operation_at_has_order previousOrder operation operation_at
          have fill_available :
              ∀ target,
                FillPosition operation = some target →
                  Available (history.occupiedBefore previousOrder) target := by
            intro target fill_position
            rw [← operation_order]
            exact
              history.fill_position_is_available operation target
                operation_member fill_position
          have valid_move :
              ∀ source target,
                operation.kind = .move source target →
                  ¬ParentOrSame source target :=
            fun source target operation_kind =>
              history.move_source_not_parent_of_target operation source target
                operation_member operation_kind
          have after_prefix_closed :=
            occupancyAfter_preserves_prefixClosure induction_hypothesis
              fill_available valid_move
          intro parent child parent_of_child child_occupied
          have child_after :
              OccupancyAfter operation
                (history.occupiedBefore previousOrder) child :=
            (history.operation_transition previousOrder operation operation_at
                child).mp child_occupied
          have parent_after :
              OccupancyAfter operation
                (history.occupiedBefore previousOrder) parent :=
            after_prefix_closed parent child parent_of_child child_after
          exact
            (history.operation_transition previousOrder operation operation_at
                parent).mpr parent_after

theorem ValidResolvedHistory.parent_position_is_occupied
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (parent child : Position) (parent_of_child : ParentOrSame parent child)
    (child_occupied : history.occupiedBefore operationOrder child) :
    history.occupiedBefore operationOrder parent :=
  history.prefix_closed operationOrder parent child parent_of_child
    child_occupied

theorem occupancyAfter_move_iff (occupiedBefore : Position → Prop)
    (source target relativePosition : Position) (operation : ParticleOperation)
    (operation_kind : operation.kind = .move source target) :
    OccupancyAfter operation occupiedBefore (target ++ relativePosition) ↔
      occupiedBefore (source ++ relativePosition) := by
  simp [OccupancyAfter, operation_kind, ParentOrSame]

structure ExactOccupancyExecution (isOperation : ParticleOperation → Prop) where
  operationAt : Nat → Option ParticleOperation
  occupiedBefore : Nat → Position → Prop
  member_operation_at :
    ∀ operation,
      isOperation operation →
        operationAt operation.operationOrder = some operation
  operation_at_is_member :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        isOperation operation
  operation_at_has_order :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        operation.operationOrder = operationOrder
  parent_position_is_occupied :
    ∀ operationOrder parent child,
      ParentOrSame parent child →
        occupiedBefore operationOrder child →
        occupiedBefore operationOrder parent
  empty_position_is_occupied :
    ∀ operation source,
      isOperation operation →
        EmptyPosition operation = some source →
        occupiedBefore operation.operationOrder source
  fill_position_is_empty :
    ∀ operation target,
      isOperation operation →
        FillPosition operation = some target →
        ¬occupiedBefore operation.operationOrder target
  operation_transition :
    ∀ operationOrder operation,
      operationAt operationOrder = some operation →
        ∀ position,
          occupiedBefore (operationOrder + 1) position ↔
            OccupancyAfter operation (occupiedBefore operationOrder) position
  no_operation_transition :
    ∀ operationOrder,
      operationAt operationOrder = none →
        ∀ position,
          occupiedBefore (operationOrder + 1) position ↔
            occupiedBefore operationOrder position

def ValidResolvedHistory.toExactOccupancyExecution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    ExactOccupancyExecution isOperation where
  operationAt := history.operationAt
  occupiedBefore := history.occupiedBefore
  member_operation_at := history.member_operation_at
  operation_at_is_member := history.operation_at_is_member
  operation_at_has_order := history.operation_at_has_order
  parent_position_is_occupied := history.parent_position_is_occupied
  empty_position_is_occupied := history.empty_position_is_occupied
  fill_position_is_empty := history.fill_position_is_empty
  operation_transition := history.operation_transition
  no_operation_transition := history.no_operation_transition

structure ValidOccupancyTrace (isOperation : ParticleOperation → Prop) where
  occupiedBefore : Nat → Position → Prop
  empty_position_is_occupied_before :
    ∀ operation source,
      isOperation operation →
        EmptyPosition operation = some source →
        occupiedBefore operation.operationOrder source
  non_move_strict_child_unoccupied_after :
    ∀ operation parent child,
      isOperation operation →
        ¬IsMove operation →
        OperatesOn operation parent →
        ParentOrSame parent child →
        parent ≠ child →
        ¬occupiedBefore (operation.operationOrder + 1) child
  newly_occupied_has_operation :
    ∀ operationOrder position,
      ¬occupiedBefore operationOrder position →
        occupiedBefore (operationOrder + 1) position →
        ∃ operation operatedPosition,
          isOperation operation ∧
            operation.operationOrder = operationOrder ∧
            OperatesOn operation operatedPosition ∧
            Related operatedPosition position

def ExactOccupancyExecution.toValidOccupancyTrace
    {isOperation : ParticleOperation → Prop}
    (execution : ExactOccupancyExecution isOperation) :
    ValidOccupancyTrace isOperation where
  occupiedBefore := execution.occupiedBefore
  empty_position_is_occupied_before := execution.empty_position_is_occupied
  non_move_strict_child_unoccupied_after := by
    intro operation parent child operation_member operation_not_move
      operation_operates_on_parent parent_of_child parent_is_not_child
    have operation_at := execution.member_operation_at operation operation_member
    have transition :=
      execution.operation_transition operation.operationOrder operation operation_at
        child
    intro child_occupied_after
    have child_after_semantics := transition.mp child_occupied_after
    cases operation_kind : operation.kind with
    | create target =>
        simp [OccupancyAfter, operation_kind] at child_after_semantics
        have parent_is_target : parent = target := by
          simpa [OperatesOn, operation_kind] using operation_operates_on_parent
        have target_empty_before :
            ¬execution.occupiedBefore operation.operationOrder target :=
          execution.fill_position_is_empty operation target operation_member (by
            simp [FillPosition, operation_kind])
        rcases child_after_semantics with child_is_target | child_occupied_before
        · exact parent_is_not_child (parent_is_target.trans child_is_target.symm)
        · exact
            target_empty_before
              (execution.parent_position_is_occupied operation.operationOrder
                target child (parent_is_target ▸ parent_of_child)
                child_occupied_before)
    | destroy target =>
        simp [OccupancyAfter, operation_kind] at child_after_semantics
        have parent_is_target : parent = target := by
          simpa [OperatesOn, operation_kind] using operation_operates_on_parent
        exact child_after_semantics.1 (parent_is_target ▸ parent_of_child)
    | move source target =>
        exact operation_not_move ⟨source, target, operation_kind⟩
  newly_occupied_has_operation := by
    intro operationOrder position unoccupied_before occupied_after
    cases operation_at : execution.operationAt operationOrder with
    | none =>
        exact
          False.elim
            (unoccupied_before
              ((execution.no_operation_transition operationOrder operation_at
                  position).mp occupied_after))
    | some operation =>
        have operation_member :=
          execution.operation_at_is_member operationOrder operation operation_at
        have operation_order :=
          execution.operation_at_has_order operationOrder operation operation_at
        have after_semantics :=
          (execution.operation_transition operationOrder operation operation_at
              position).mp occupied_after
        cases operation_kind : operation.kind with
        | create target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            rcases after_semantics with position_is_target | occupied_before_again
            · exact
                ⟨operation, target, operation_member, operation_order,
                  by simp [OperatesOn, operation_kind],
                  position_is_target ▸ related_refl target⟩
            · exact False.elim (unoccupied_before occupied_before_again)
        | destroy target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            exact False.elim (unoccupied_before after_semantics.2)
        | move source target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            rcases after_semantics with moved_position | unchanged_position
            · rcases moved_position with
                ⟨relativePosition, position_is_target_child, _⟩
              exact
                ⟨operation, target, operation_member, operation_order,
                  by simp [OperatesOn, operation_kind],
                  Or.inl ⟨relativePosition, position_is_target_child.symm⟩⟩
            · exact False.elim (unoccupied_before unchanged_position.2.2)

def ValidResolvedHistory.toValidOccupancyTrace
    {isOperation : ParticleOperation → Prop}
    (execution : ValidResolvedHistory isOperation) :
    ValidOccupancyTrace isOperation where
  occupiedBefore := execution.occupiedBefore
  empty_position_is_occupied_before := execution.empty_position_is_occupied
  non_move_strict_child_unoccupied_after := by
    intro operation parent child operation_member operation_not_move
      operation_operates_on_parent parent_of_child parent_is_not_child
    have operation_at := execution.member_operation_at operation operation_member
    have transition :=
      execution.operation_transition operation.operationOrder operation operation_at
        child
    intro child_occupied_after
    have child_after_semantics := transition.mp child_occupied_after
    cases operation_kind : operation.kind with
    | create target =>
        simp [OccupancyAfter, operation_kind] at child_after_semantics
        have parent_is_target : parent = target := by
          simpa [OperatesOn, operation_kind] using operation_operates_on_parent
        have target_empty_before :
            ¬execution.occupiedBefore operation.operationOrder target :=
          execution.fill_position_is_empty operation target operation_member (by
            simp [FillPosition, operation_kind])
        rcases child_after_semantics with child_is_target | child_occupied_before
        · exact parent_is_not_child (parent_is_target.trans child_is_target.symm)
        · exact
            target_empty_before
              (execution.parent_position_is_occupied operation.operationOrder
                target child (parent_is_target ▸ parent_of_child)
                child_occupied_before)
    | destroy target =>
        simp [OccupancyAfter, operation_kind] at child_after_semantics
        have parent_is_target : parent = target := by
          simpa [OperatesOn, operation_kind] using operation_operates_on_parent
        exact child_after_semantics.1 (parent_is_target ▸ parent_of_child)
    | move source target =>
        exact operation_not_move ⟨source, target, operation_kind⟩
  newly_occupied_has_operation := by
    intro operationOrder position unoccupied_before occupied_after
    cases operation_at : execution.operationAt operationOrder with
    | none =>
        exact
          False.elim
            (unoccupied_before
              ((execution.no_operation_transition operationOrder operation_at
                  position).mp occupied_after))
    | some operation =>
        have operation_member :=
          execution.operation_at_is_member operationOrder operation operation_at
        have operation_order :=
          execution.operation_at_has_order operationOrder operation operation_at
        have after_semantics :=
          (execution.operation_transition operationOrder operation operation_at
              position).mp occupied_after
        cases operation_kind : operation.kind with
        | create target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            rcases after_semantics with position_is_target | occupied_before_again
            · exact
                ⟨operation, target, operation_member, operation_order,
                  by simp [OperatesOn, operation_kind],
                  position_is_target ▸ related_refl target⟩
            · exact False.elim (unoccupied_before occupied_before_again)
        | destroy target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            exact False.elim (unoccupied_before after_semantics.2)
        | move source target =>
            simp [OccupancyAfter, operation_kind] at after_semantics
            rcases after_semantics with moved_position | unchanged_position
            · rcases moved_position with
                ⟨relativePosition, position_is_target_child, _⟩
              exact
                ⟨operation, target, operation_member, operation_order,
                  by simp [OperatesOn, operation_kind],
                  Or.inl ⟨relativePosition, position_is_target_child.symm⟩⟩
            · exact False.elim (unoccupied_before unchanged_position.2.2)

theorem ValidResolvedHistory.non_move_strict_child_unoccupied_after
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operation : ParticleOperation)
    (parent child : Position) (operation_member : isOperation operation)
    (operation_not_move : ¬IsMove operation)
    (operation_operates_on_parent : OperatesOn operation parent)
    (parent_of_child : ParentOrSame parent child)
    (parent_is_not_child : parent ≠ child) :
    ¬history.occupiedBefore (operation.operationOrder + 1) child :=
  history.toValidOccupancyTrace.non_move_strict_child_unoccupied_after
    operation parent child operation_member operation_not_move
    operation_operates_on_parent parent_of_child parent_is_not_child

theorem ValidResolvedHistory.newly_occupied_has_operation
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (position : Position)
    (unoccupied_before : ¬history.occupiedBefore operationOrder position)
    (occupied_after : history.occupiedBefore (operationOrder + 1) position) :
    ∃ operation,
      isOperation operation ∧
        operation.operationOrder = operationOrder ∧
        (operation.kind = .create position ∨
          ∃ source target relativePosition,
            operation.kind = .move source target ∧
              position = target ++ relativePosition ∧
              history.occupiedBefore operationOrder
                (source ++ relativePosition)) := by
  cases operation_at : history.operationAt operationOrder with
  | none =>
      exact
        False.elim
          (unoccupied_before
            ((history.no_operation_transition operationOrder operation_at
                position).mp occupied_after))
  | some operation =>
      have operation_member :=
        history.operation_at_is_member operationOrder operation operation_at
      have operation_order :=
        history.operation_at_has_order operationOrder operation operation_at
      have after_semantics :=
        (history.operation_transition operationOrder operation operation_at
            position).mp occupied_after
      cases operation_kind : operation.kind with
      | create target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          rcases after_semantics with position_is_target | occupied_before_again
          · subst position
            exact
              ⟨operation, operation_member, operation_order,
                Or.inl operation_kind⟩
          · exact False.elim (unoccupied_before occupied_before_again)
      | destroy target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          exact False.elim (unoccupied_before after_semantics.2)
      | move source target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          rcases after_semantics with moved_position | unchanged_position
          · rcases moved_position with
              ⟨relativePosition, position_is_target_child,
                source_child_occupied⟩
            exact
              ⟨operation, operation_member, operation_order,
                Or.inr
                  ⟨source, target, relativePosition, operation_kind,
                    position_is_target_child, source_child_occupied⟩⟩
          · exact False.elim (unoccupied_before unchanged_position.2.2)

theorem ValidResolvedHistory.newly_occupied_has_responsible_operation
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (position : Position)
    (unoccupied_before : ¬history.occupiedBefore operationOrder position)
    (occupied_after : history.occupiedBefore (operationOrder + 1) position) :
    ∃ operation operatedPosition,
      isOperation operation ∧
        operation.operationOrder = operationOrder ∧
        OperatesOn operation operatedPosition ∧
        ParentOrSame operatedPosition position := by
  rcases
      history.newly_occupied_has_operation operationOrder position
        unoccupied_before occupied_after with
    ⟨operation, operation_member, operation_order,
      created_position | moved_position⟩
  · exact
      ⟨operation, position, operation_member, operation_order,
        by simp [OperatesOn, created_position], List.prefix_rfl⟩
  · rcases moved_position with
      ⟨source, target, relativePosition, operation_kind,
        position_is_target_child, -⟩
    exact
      ⟨operation, target, operation_member, operation_order,
        by simp [OperatesOn, operation_kind],
        ⟨relativePosition, position_is_target_child.symm⟩⟩

theorem ValidResolvedHistory.move_preserves_occupancy
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operation : ParticleOperation)
    (source target relativePosition : Position)
    (operation_member : isOperation operation)
    (operation_kind : operation.kind = .move source target) :
    history.occupiedBefore (operation.operationOrder + 1)
          (target ++ relativePosition) ↔
      history.occupiedBefore operation.operationOrder
        (source ++ relativePosition) := by
  exact
    (history.operation_transition operation.operationOrder operation
        (history.member_operation_at operation operation_member)
        (target ++ relativePosition)).trans
      (occupancyAfter_move_iff
        (history.occupiedBefore operation.operationOrder) source target
        relativePosition operation operation_kind)

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) (operationOrder : Nat),
      PrefixClosed (history.occupiedBefore operationOrder) :=
  ValidResolvedHistory.prefix_closed

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (operation : ParticleOperation) (parent child : Position),
      isOperation operation →
        ¬IsMove operation →
        OperatesOn operation parent →
        ParentOrSame parent child →
        parent ≠ child →
        ¬history.occupiedBefore (operation.operationOrder + 1) child :=
  ValidResolvedHistory.non_move_strict_child_unoccupied_after

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
      (position : Position),
      ¬history.occupiedBefore operationOrder position →
        history.occupiedBefore (operationOrder + 1) position →
        ∃ operation,
          isOperation operation ∧
            operation.operationOrder = operationOrder ∧
            (operation.kind = .create position ∨
              ∃ source target relativePosition,
                operation.kind = .move source target ∧
                  position = target ++ relativePosition ∧
                  history.occupiedBefore operationOrder
                    (source ++ relativePosition)) :=
  ValidResolvedHistory.newly_occupied_has_operation

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (operation : ParticleOperation) (source target relativePosition : Position),
      isOperation operation →
        operation.kind = .move source target →
        (history.occupiedBefore (operation.operationOrder + 1)
              (target ++ relativePosition) ↔
          history.occupiedBefore operation.operationOrder
            (source ++ relativePosition)) :=
  ValidResolvedHistory.move_preserves_occupancy

end TypeContracts

end Define.OperationGraph
