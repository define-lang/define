import calculation_correctness
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Vanished Child Name Witness

This module proves that its six-operation model is a `ValidResolvedHistory` and
applies the universal calculation to it. The destroyed child's position name
remains queryable after its parent is destroyed and recreated. The earlier
Destroy is therefore a source candidate at that name, while the newer parent
Create excludes it during the simultaneous Comparison.
-/

namespace Define.OperationGraph

namespace VanishedChildName

def parentPosition : Position := [0]

def childPosition : Position := [0, 0]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create parentPosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create childPosition

def destroyChild : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .destroy childPosition

def destroyParent : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy parentPosition

def recreateParent : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .create parentPosition

def destroyAgain : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .destroy parentPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild ∨ operation = destroyChild ∨
    operation = destroyParent ∨ operation = recreateParent ∨
    operation = destroyAgain

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | 2 => some destroyChild
  | 3 => some destroyParent
  | 4 => some recreateParent
  | 5 => some destroyAgain
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

theorem operationAt_tail (operationOrder : Nat) :
    operationAt (operationOrder + 6) = none := rfl

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = [0, 0] ∨ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔ position = [0] ∨ position = [] := by
  constructor
  · rintro ⟨not_under_child, occupied⟩
    rcases (occupied_two position).mp occupied with rfl | rfl | rfl
    · exact absurd List.prefix_rfl not_under_child
    · exact Or.inl rfl
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        (occupied_two _).mpr (Or.inr (Or.inl rfl))⟩
    · exact ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        (occupied_two _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_three position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([0] : List Nat) <+: []; decide,
      (occupied_three _).mpr (Or.inr rfl)⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔ position = [0] ∨ position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four position).mp occupied)
  · rintro (rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four _).mpr rfl)

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_five position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([0] : List Nat) <+: []; decide,
      (occupied_five _).mpr (Or.inr rfl)⟩

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 6) position ↔ occupiedBefore 6 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 6) position ↔
            occupiedBefore (extra + 6) position := by
        show occupiedBefore (extra + 6 + 1) position ↔ _
        simp [occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
        (Option.some.inj operation_at).symm))))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
        (Option.some.inj operation_at).symm))))
    · simp [operationAt_tail] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt_tail] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
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
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_four] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_five] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_tail, occupied_six] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · simp [EmptyPosition, createParent] at empty_position
    · simp [EmptyPosition, createChild] at empty_position
    · have source_is_child : source = childPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_two _).mpr (Or.inl rfl)
    · have source_is_parent : source = parentPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_parent
      exact (occupied_three _).mpr (Or.inl rfl)
    · simp [EmptyPosition, recreateParent] at empty_position
    · have source_is_parent : source = parentPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_parent
      exact (occupied_five _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro occupied
      simpa [parentPosition] using (occupied_zero parentPosition).mp occupied
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro occupied
      rcases (occupied_one childPosition).mp occupied with child_eq | child_eq <;>
        simp [childPosition] at child_eq
    · simp [FillPosition, destroyChild] at fill_position
    · simp [FillPosition, destroyParent] at fill_position
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro occupied
      simpa [parentPosition] using (occupied_four parentPosition).mp occupied
    · simp [FillPosition, destroyAgain] at fill_position
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

def queryableBefore : Nat → Position → Prop
  | 0, position => position = [] ∨ position = parentPosition
  | _operationOrder + 1, position =>
      position = [] ∨ position = parentPosition ∨ position = childPosition

theorem operated_position_queryable (operation : ParticleOperation)
    (position : Position) (operation_member : isOperation operation)
    (operates_on_position : OperatesOn operation position) :
    queryableBefore operation.operationOrder position := by
  rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
  · exact Or.inr (by
      simpa [OperatesOn, createParent] using operates_on_position)
  · exact Or.inr (Or.inr (by
      simpa [OperatesOn, createChild] using operates_on_position))
  · exact Or.inr (Or.inr (by
      simpa [OperatesOn, destroyChild] using operates_on_position))
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, destroyParent] using operates_on_position))
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, recreateParent] using operates_on_position))
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, destroyAgain] using operates_on_position))

def history : ValidResolvedHistory isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  queryableBefore := queryableBefore
  member_operation_at := occupancy.member_operation_at
  operation_at_is_member := occupancy.operation_at_is_member
  operation_at_has_order := occupancy.operation_at_has_order
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    by_cases later_before_end : laterOrder < 6
    · have first_before_end : firstOrder < 6 := by omega
      have first_shape :
          firstOrder = 0 ∨ firstOrder = 1 ∨ firstOrder = 2 ∨
            firstOrder = 3 ∨ firstOrder = 4 ∨ firstOrder = 5 := by
        omega
      rcases first_shape with rfl | rfl | rfl | rfl | rfl | rfl <;>
        simp [operationAt] at first_none
    · have end_le_later : 6 ≤ laterOrder := by omega
      rcases Nat.exists_eq_add_of_le end_le_later with ⟨extra, rfl⟩
      simpa [Nat.add_comm] using operationAt_tail extra
  initial_prefix_closed := by
    intro parent child parent_of_child child_occupied
    exact occupancy.parent_position_is_occupied 0 parent child parent_of_child
      child_occupied
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    rcases operationOrder with _ | operationOrder
    · rcases child_queryable with rfl | rfl
      · exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inl rfl
        · exact Or.inr rfl
    · rcases child_queryable with rfl | rfl | rfl
      · exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inl rfl
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inl rfl
        · exact Or.inr (Or.inl rfl)
        · exact Or.inr (Or.inr rfl)
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl ((occupied_zero position).mp position_occupied)
    · rcases (occupied_one position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_two position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr rfl)
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_three position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · exact Or.inl ((occupied_four position).mp position_occupied)
    · rcases (occupied_five position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · exact Or.inl ((occupied_six position).mp
        ((occupied_tail operationOrder position).mp position_occupied))
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    exact operated_position_queryable operation position operation_member
      operates_on_position
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operationOrder with _ | operationOrder
    · omega
    · rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inl (by
          simpa [OperatesOn, createParent] using operates_on_position))
      · exact Or.inr (Or.inr (by
          simpa [OperatesOn, createChild] using operates_on_position))
      · exact Or.inr (Or.inr (by
          simpa [OperatesOn, destroyChild] using operates_on_position))
      · exact Or.inr (Or.inl (by
          simpa [OperatesOn, destroyParent] using operates_on_position))
      · exact Or.inr (Or.inl (by
          simpa [OperatesOn, recreateParent] using operates_on_position))
      · exact Or.inr (Or.inl (by
          simpa [OperatesOn, destroyAgain] using operates_on_position))
  empty_position_is_occupied := occupancy.empty_position_is_occupied
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_zero []).mpr rfl
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_one []).mpr (Or.inr rfl)
      · exact (occupied_one parentPosition).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · simp [FillPosition, destroyChild] at fill_position
    · simp [FillPosition, destroyParent] at fill_position
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_four []).mpr rfl
      · exact False.elim (parent_is_not_target rfl)
    · simp [FillPosition, destroyAgain] at fill_position
  fill_position_is_empty := occupancy.fill_position_is_empty
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;>
      simp [createParent, createChild, destroyChild, destroyParent,
        recreateParent, destroyAgain] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix
  operation_transition := occupancy.operation_transition
  no_operation_transition := occupancy.no_operation_transition

theorem vanished_child_source_candidate :
    IsSourceCandidateAt history destroyAgain destroyChild childPosition := by
  refine ⟨by simp [isOperation], parentPosition, rfl,
    Or.inr (Or.inr rfl), Or.inr ⟨[0], rfl⟩, ?_⟩
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_destroy_child
    newer_before_destroy_again newer_writes_child
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, destroyChild] at newer_than_destroy_child
  · simp [MoreRecent, createChild, destroyChild] at newer_than_destroy_child
  · simp [MoreRecent, destroyChild] at newer_than_destroy_child
  · change childPosition = parentPosition at newer_writes_child
    simp [childPosition, parentPosition] at newer_writes_child
  · change childPosition = parentPosition at newer_writes_child
    simp [childPosition, parentPosition] at newer_writes_child
  · simp [destroyAgain] at newer_before_destroy_again

theorem recreated_parent_source_candidate :
    IsSourceCandidateAt history destroyAgain recreateParent parentPosition := by
  refine ⟨by simp [isOperation], parentPosition, rfl,
    Or.inr (Or.inl rfl), related_refl parentPosition, ?_⟩
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_recreate
    newer_before_destroy_again newer_writes_parent
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, recreateParent] at newer_than_recreate
  · simp [MoreRecent, createChild, recreateParent] at newer_than_recreate
  · simp [MoreRecent, destroyChild, recreateParent] at newer_than_recreate
  · simp [MoreRecent, destroyParent, recreateParent] at newer_than_recreate
  · simp [MoreRecent, recreateParent] at newer_than_recreate
  · simp [destroyAgain] at newer_before_destroy_again

theorem vanished_child_excluded :
    ¬(calculationFor history destroyAgain).AfterComparison destroyChild := by
  intro destroy_child_after_comparison
  exact
    destroy_child_after_comparison.2 recreateParent
      (Or.inl ⟨parentPosition, recreated_parent_source_candidate⟩)
      (show MoreRecent recreateParent destroyChild from
        (by decide : destroyChild.operationOrder < recreateParent.operationOrder))
      ⟨parentPosition, childPosition, rfl, rfl, Or.inl ⟨[0], rfl⟩⟩

theorem calculated_dependency :
    CalculatedDependency history destroyAgain recreateParent := by
  apply
    (calculatedDependency_exact history destroyAgain recreateParent).mpr
  change
    (calculationFor history destroyAgain).AfterMoveCorrection
      (CalculatedDependency history) recreateParent
  refine ⟨⟨Or.inl ⟨parentPosition, recreated_parent_source_candidate⟩,
    ?_⟩, Or.inl (not_move_of_kind_create rfl)⟩
  intro newerCandidate newer_in_collection newer_than_recreate
    operations_related
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  have newer_before_destroy_again :=
    calculationFor_inCollection_is_previous history newer_in_collection
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, recreateParent] at newer_than_recreate
  · simp [MoreRecent, createChild, recreateParent] at newer_than_recreate
  · simp [MoreRecent, destroyChild, recreateParent] at newer_than_recreate
  · simp [MoreRecent, destroyParent, recreateParent] at newer_than_recreate
  · simp [MoreRecent, recreateParent] at newer_than_recreate
  · simp [MoreRecent, destroyAgain] at newer_before_destroy_again

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

end VanishedChildName

end Define.OperationGraph
