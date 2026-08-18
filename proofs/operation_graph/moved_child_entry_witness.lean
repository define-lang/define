import calculation_correctness
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Moved Child Entry Witness

This module proves that its five-operation model is a `ValidResolvedHistory`
and applies the universal calculation to it. The Move writes an entry for the
moved particle's queryable transitive child position. That Move is consequently
the source candidate selected by a later Destroy and survives Move Correction as
a final dependency.
-/

namespace Define.OperationGraph

namespace MovedChildEntry

def sourcePosition : Position := [0]

def sourceChild : Position := [0, 0]

def targetPosition : Position := [1]

def targetChild : Position := [1, 0]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create sourcePosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create sourceChild

def moveParent : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move sourcePosition targetPosition

def destroyMovedChild : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy targetChild

def destroyMovedParent : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .destroy targetPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild ∨ operation = moveParent ∨
    operation = destroyMovedChild ∨ operation = destroyMovedParent

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | 2 => some moveParent
  | 3 => some destroyMovedChild
  | 4 => some destroyMovedParent
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

theorem operationAt_tail (operationOrder : Nat) :
    operationAt (operationOrder + 5) = none := rfl

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = [0, 0] ∨ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔
      position = [1] ∨ position = [1, 0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_two _).mp source_occupied with
        extended | extended | extended
      · have relative_shape : relative = [0] := by
          simpa [sourcePosition] using extended
        subst relative_shape
        exact Or.inr (Or.inl rfl)
      · have relative_shape : relative = [] := by
          simpa [sourcePosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · exact nomatch extended
    · rcases (occupied_two position).mp occupied with rfl | rfl | rfl
      · exact absurd ⟨[0], rfl⟩ not_source
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_two _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inl ⟨[0], rfl, (occupied_two _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0] : List Nat) <+: []; decide,
        by show ¬([1] : List Nat) <+: []; decide,
        (occupied_two _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔ position = [1] ∨ position = [] := by
  constructor
  · rintro ⟨not_under_child, occupied⟩
    rcases (occupied_three position).mp occupied with rfl | rfl | rfl
    · exact Or.inl rfl
    · exact absurd List.prefix_rfl not_under_child
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by show ¬([1, 0] : List Nat) <+: [1]; decide,
        (occupied_three _).mpr (Or.inl rfl)⟩
    · exact ⟨by show ¬([1, 0] : List Nat) <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_four position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([1] : List Nat) <+: []; decide,
      (occupied_four _).mpr (Or.inr rfl)⟩

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 5) position ↔ occupiedBefore 5 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 5) position ↔
            occupiedBefore (extra + 5) position := by
        show occupiedBefore (extra + 5 + 1) position ↔ _
        simp [occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Option.some.inj operation_at).symm)))
    · simp [operationAt_tail] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt_tail] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    · rw [occupied_zero] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_one] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_two] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_three] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inl rfl
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_four] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_tail, occupied_five] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some source)
    · exact nomatch
        (empty_position : (none : Option Position) = some source)
    · have source_is_source : source = sourcePosition :=
        (Option.some.inj empty_position).symm
      subst source_is_source
      exact (occupied_two _).mpr (Or.inr (Or.inl rfl))
    · have source_is_child : source = targetChild :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_three _).mpr (Or.inr (Or.inl rfl))
    · have source_is_target : source = targetPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_target
      exact (occupied_four _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · have target_is_source : target = sourcePosition :=
        (Option.some.inj fill_position).symm
      subst target_is_source
      intro occupied
      simpa [sourcePosition] using (occupied_zero sourcePosition).mp occupied
    · have target_is_child : target = sourceChild :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro occupied
      rcases (occupied_one sourceChild).mp occupied with child_eq | child_eq <;>
        simp [sourceChild] at child_eq
    · have target_is_target : target = targetPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_target
      intro occupied
      rcases (occupied_two targetPosition).mp occupied with
        target_eq | target_eq | target_eq <;>
        simp [targetPosition] at target_eq
    · exact nomatch
        (fill_position : (none : Option Position) = some target)
    · exact nomatch
        (fill_position : (none : Option Position) = some target)
  operation_transition := by
    intro operationOrder operation operation_at position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [operation_at]
  no_operation_transition := by
    intro operationOrder no_operation position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [no_operation]

def queryableBefore (operationOrder : Nat) (position : Position) : Prop :=
  position = [] ∨
    position = sourcePosition ∨
      (1 ≤ operationOrder ∧ position = sourceChild) ∨
        (2 ≤ operationOrder ∧ position = targetPosition) ∨
          (3 ≤ operationOrder ∧ position = targetChild)

theorem operated_position_queryable (operation : ParticleOperation)
    (position : Position) (operation_member : isOperation operation)
    (operates_on_position : OperatesOn operation position) :
    queryableBefore operation.operationOrder position := by
  rcases operation_member with rfl | rfl | rfl | rfl | rfl
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, createParent] using operates_on_position))
  · exact Or.inr (Or.inr (Or.inl ⟨by decide, by
      simpa [OperatesOn, createChild] using operates_on_position⟩))
  · rcases operates_on_position with position_is_source | position_is_target
    · exact Or.inr (Or.inl position_is_source)
    · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, position_is_target⟩)))
  · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨by decide, by
      simpa [OperatesOn, destroyMovedChild] using operates_on_position⟩)))
  · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, by
      simpa [OperatesOn, destroyMovedParent] using operates_on_position⟩)))

def history : ValidResolvedHistory isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  queryableBefore := queryableBefore
  member_operation_at := occupancy.member_operation_at
  operation_at_is_member := occupancy.operation_at_is_member
  operation_at_has_order := occupancy.operation_at_has_order
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    by_cases later_before_end : laterOrder < 5
    · have first_before_end : firstOrder < 5 := by omega
      have first_shape :
          firstOrder = 0 ∨ firstOrder = 1 ∨ firstOrder = 2 ∨
            firstOrder = 3 ∨ firstOrder = 4 := by
        omega
      rcases first_shape with rfl | rfl | rfl | rfl | rfl <;>
        simp [operationAt] at first_none
    · have end_le_later : 5 ≤ laterOrder := by omega
      rcases Nat.exists_eq_add_of_le end_le_later with ⟨extra, rfl⟩
      simpa [Nat.add_comm] using operationAt_tail extra
  initial_prefix_closed := by
    intro parent child parent_of_child child_occupied
    exact occupancy.parent_position_is_occupied 0 parent child parent_of_child
      child_occupied
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    rcases child_queryable with rfl | rfl |
      ⟨one_le, rfl⟩ | ⟨two_le, rfl⟩ | ⟨three_le, rfl⟩
    · exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
    · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl ⟨one_le, rfl⟩))
    · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨two_le, rfl⟩)))
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by omega, rfl⟩)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨three_le, rfl⟩)))
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl ((occupied_zero position).mp position_occupied)
    · rcases (occupied_one position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_two position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_three position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨by decide, rfl⟩)))
      · exact Or.inl rfl
    · rcases (occupied_four position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)))
      · exact Or.inl rfl
    · exact Or.inl ((occupied_five position).mp
        ((occupied_tail operationOrder position).mp position_occupied))
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    exact operated_position_queryable operation position operation_member
      operates_on_position
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [OperatesOn, createParent] using operates_on_position))
    · simp [createChild] at operation_before
      exact Or.inr (Or.inr (Or.inl ⟨by omega, by
        simpa [OperatesOn, createChild] using operates_on_position⟩))
    · simp [moveParent] at operation_before
      rcases operates_on_position with position_is_source | position_is_target
      · exact Or.inr (Or.inl position_is_source)
      · exact Or.inr (Or.inr (Or.inr
          (Or.inl ⟨by omega, position_is_target⟩)))
    · simp [destroyMovedChild] at operation_before
      exact Or.inr (Or.inr (Or.inr (Or.inr ⟨by omega, by
        simpa [OperatesOn, destroyMovedChild] using operates_on_position⟩)))
    · simp [destroyMovedParent] at operation_before
      exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by omega, by
        simpa [OperatesOn, destroyMovedParent] using operates_on_position⟩)))
  empty_position_is_occupied := occupancy.empty_position_is_occupied
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · have target_is_source : target = sourcePosition :=
        (Option.some.inj fill_position).symm
      subst target_is_source
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_zero []).mpr rfl
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_child : target = sourceChild :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_one []).mpr (Or.inr rfl)
      · exact (occupied_one sourcePosition).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_target : target = targetPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_target
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_two []).mpr (Or.inr (Or.inr rfl))
      · exact False.elim (parent_is_not_target rfl)
    · simp [FillPosition, destroyMovedChild] at fill_position
    · simp [FillPosition, destroyMovedParent] at fill_position
  fill_position_is_empty := occupancy.fill_position_is_empty
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · simp [createParent] at operation_kind
    · simp [createChild] at operation_kind
    · simp [moveParent] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      intro source_parent_of_target
      rcases prefix_singleton_iff.mp source_parent_of_target with
        source_is_empty | source_is_target
      · simp [sourcePosition] at source_is_empty
      · simp [sourcePosition] at source_is_target
    · simp [destroyMovedChild] at operation_kind
    · simp [destroyMovedParent] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix
  operation_transition := occupancy.operation_transition
  no_operation_transition := occupancy.no_operation_transition

theorem move_writes_target_child :
    WritesEntry history moveParent targetChild := by
  exact Or.inr (Or.inr ⟨[0], by decide, rfl,
    Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))⟩)

theorem moved_child_source_candidate :
    IsSourceCandidateAt history destroyMovedChild moveParent targetChild := by
  refine ⟨by simp [isOperation], targetChild, rfl,
    Or.inr (Or.inr (Or.inr (Or.inr ⟨by decide, rfl⟩))),
    related_refl targetChild, ?_⟩
  refine ⟨by simp [isOperation], by decide, move_writes_target_child, ?_⟩
  intro newerCandidate newer_member newer_than_move
    newer_before_destroy newer_writes_child
  rcases newer_member with rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, moveParent] at newer_than_move
  · simp [MoreRecent, createChild, moveParent] at newer_than_move
  · simp [MoreRecent, moveParent] at newer_than_move
  · simp [destroyMovedChild] at newer_before_destroy
  · simp [destroyMovedChild, destroyMovedParent] at newer_before_destroy

theorem move_parent_after_comparison :
    (calculationFor history destroyMovedChild).AfterComparison moveParent := by
  refine ⟨Or.inl ⟨targetChild, moved_child_source_candidate⟩, ?_⟩
  intro newerCandidate newer_in_collection newer_than_move operations_related
  have newer_before_destroy :=
    calculationFor_inCollection_is_previous history newer_in_collection
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  rcases newer_member with rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, moveParent] at newer_than_move
  · simp [MoreRecent, createChild, moveParent] at newer_than_move
  · simp [MoreRecent, moveParent] at newer_than_move
  · simp [MoreRecent, destroyMovedChild] at newer_before_destroy
  · simp [MoreRecent, destroyMovedChild, destroyMovedParent] at newer_before_destroy

theorem move_parent_related_create_parent :
    OperationsRelated moveParent createParent :=
  ⟨sourcePosition, sourcePosition, Or.inl rfl, rfl,
    related_refl sourcePosition⟩

theorem move_parent_related_create_child :
    OperationsRelated moveParent createChild :=
  ⟨sourcePosition, sourceChild, Or.inl rfl, rfl, Or.inl ⟨[0], rfl⟩⟩

theorem calculated_dependency :
    CalculatedDependency history destroyMovedChild moveParent := by
  apply
    (calculatedDependency_exact history destroyMovedChild moveParent).mpr
  change
    (calculationFor history destroyMovedChild).AfterMoveCorrection
      (CalculatedDependency history) moveParent
  refine ⟨move_parent_after_comparison, Or.inr ?_⟩
  intro otherCandidate other_after_comparison other_ne_move
  have other_in_collection := other_after_comparison.1
  have other_before_destroy :=
    calculationFor_inCollection_is_previous history other_in_collection
  have other_member :=
    (calculationFor_inCollection_operations history other_in_collection).2
  rcases other_member with rfl | rfl | rfl | rfl | rfl
  · exact False.elim
      (other_after_comparison.2 moveParent
        (Or.inl ⟨targetChild, moved_child_source_candidate⟩)
        (show MoreRecent moveParent createParent from
          (by decide : createParent.operationOrder < moveParent.operationOrder))
        move_parent_related_create_parent)
  · exact False.elim
      (other_after_comparison.2 moveParent
        (Or.inl ⟨targetChild, moved_child_source_candidate⟩)
        (show MoreRecent moveParent createChild from
          (by decide : createChild.operationOrder < moveParent.operationOrder))
        move_parent_related_create_child)
  · exact False.elim (other_ne_move rfl)
  · simp [MoreRecent, destroyMovedChild] at other_before_destroy
  · simp [MoreRecent, destroyMovedChild, destroyMovedParent] at other_before_destroy

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  IsSourceCandidateAt history operation candidate candidatePosition

noncomputable def calculation (operation : ParticleOperation) : RuleCalculation :=
  calculationFor history operation

def dependency (operation candidate : ParticleOperation) : Prop :=
  CalculatedDependency history operation candidate

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed :=
  calculationFor_wellFormed history operation

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  change
    CalculatedDependency history operation candidate ↔
      (calculationFor history operation).Dependency
        (CalculatedDependency history) candidate
  exact calculatedDependency_exact history operation candidate

noncomputable def graph : ResolvedDefineGraph :=
  calculatedResolvedDefineGraph history

end MovedChildEntry

end Define.OperationGraph
