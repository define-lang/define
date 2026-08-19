import calculation_correctness
import independence_witness_support
import minimality
import witness_support

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Fill Rule's transitive parent positions

History: `create parent` then `create parent::child`.

Complete Fill Rule: filling the child position depends on the most recent
previous operation among the ones on that position *and its transitive parent
positions*; the Create of the parent position is on the chain, so the child
Create depends on it.

Weakened rule (the Fill Rule consults only the filled position itself): the
child position has no previous operation, so the child Create has no
dependency, and nothing orders it after the Create that its parent particle
comes from. The pair is related and previous but unreachable.
-/

namespace FillRuleParentPositions

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

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

def queryableBefore (_operationOrder : Nat) (position : Position) : Prop :=
  position = [] ∨ position = parentPosition ∨ position = childPosition

theorem occupied_position_is_queryable (operationOrder : Nat)
    (position : Position) (position_occupied : occupiedBefore operationOrder position) :
    queryableBefore operationOrder position := by
  induction operationOrder with
  | zero =>
      exact Or.inl position_occupied
  | succ previousOrder induction_hypothesis =>
      cases previousOrder with
      | zero =>
          rcases position_occupied with position_is_parent | position_is_empty
          · exact Or.inr (Or.inl position_is_parent)
          · exact Or.inl position_is_empty
      | succ previousOrder =>
          cases previousOrder with
          | zero =>
              rcases position_occupied with position_is_child | occupied_before
              · exact Or.inr (Or.inr position_is_child)
              · exact induction_hypothesis occupied_before
          | succ previousOrder =>
              exact induction_hypothesis position_occupied

def validHistory : ValidResolvedHistory isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  queryableBefore := queryableBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        exact Or.inl (Option.some.inj operation_at).symm
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            exact Or.inr (Option.some.inj operation_at).symm
        | succ operationOrder =>
            simp [operationAt] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        rw [← Option.some.inj operation_at]
        rfl
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            rw [← Option.some.inj operation_at]
            rfl
        | succ operationOrder =>
            simp [operationAt] at operation_at
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    rcases laterOrder with _ | _ | laterOrder
    · have first_is_zero : firstOrder = 0 := by omega
      subst first_is_zero
      simp [operationAt] at first_none
    · have first_is_zero_or_one : firstOrder = 0 ∨ firstOrder = 1 := by
        omega
      rcases first_is_zero_or_one with first_is_zero | first_is_one
      · subst first_is_zero
        simp [operationAt] at first_none
      · subst first_is_one
        simp [operationAt] at first_none
    · rfl
  initial_prefix_closed := by
    intro parent child parent_of_child child_occupied
    subst child
    exact List.eq_nil_of_prefix_nil parent_of_child
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    rcases child_queryable with child_is_empty | child_is_parent | child_is_child
    · subst child
      exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
    · subst child
      rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
    · subst child
      rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr rfl)
  occupied_position_is_queryable := occupied_position_is_queryable
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [createParent, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [createChild, OperatesOn] using operates_on_position))
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operation_member with rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [createParent, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [createChild, OperatesOn] using operates_on_position))
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl <;>
      simp [createParent, createChild, EmptyPosition] at empty_position
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · rfl
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact Or.inr rfl
      · exact Or.inl rfl
      · exact False.elim (parent_is_not_target rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro parent_occupied
      simp [createParent, occupiedBefore, parentPosition] at parent_occupied
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro child_occupied
      rcases child_occupied with child_is_parent | child_is_empty
      · simp [childPosition, parentPosition] at child_is_parent
      · simp [occupiedBefore, childPosition] at child_is_empty
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_member with rfl | rfl <;>
      simp [createParent, createChild] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl <;> exact List.nil_prefix
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

theorem parent_entry_before_child :
    IsEntryBefore validHistory createChild.operationOrder parentPosition
      createParent := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_parent newer_before_child
    newer_writes_parent
  rcases newer_member with rfl | rfl
  · simp [MoreRecent, createParent] at newer_than_parent
  · simp [createChild] at newer_before_child

theorem parent_is_fill_candidate :
    (calculationFor validHistory createChild).IsFillCandidate createParent := by
  apply
    (calculationFor_fillCandidate_iff validHistory createChild createParent).mpr
  refine ⟨⟨by simp [isOperation], childPosition, parentPosition, rfl,
    Or.inr (Or.inl rfl), ⟨[0], rfl⟩, parent_entry_before_child⟩, ?_⟩
  intro newerCandidate newer_fill_entry newer_than_parent
  have newer_before_child :=
    isFillEntry_candidate_is_previous newer_fill_entry
  simp [MoreRecent, createParent] at newer_than_parent
  simp [createChild] at newer_before_child
  omega

theorem calculated_child_parent :
    CalculatedDependency validHistory createChild createParent := by
  apply (calculatedDependency_exact validHistory createChild createParent).mpr
  simpa [RuleCalculation.Dependency, calculationFor, createChild] using
    parent_is_fill_candidate

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency validHistory

theorem complete_dependency_iff {operation dependencyOperation : ParticleOperation} :
    CompleteDependency operation dependencyOperation ↔
      operation = createChild ∧ dependencyOperation = createParent := by
  constructor
  · intro direct_dependency
    have operations :=
      calculatedDependency_operations validHistory direct_dependency
    have points_backward :=
      calculatedDependency_pointsBackward validHistory operation
        dependencyOperation direct_dependency
    rcases operations.1 with rfl | rfl
    · simp [createParent] at points_backward
    · rcases operations.2 with rfl | rfl
      · exact ⟨rfl, rfl⟩
      · simp [createChild] at points_backward
  · rintro ⟨rfl, rfl⟩
    exact calculated_child_parent

abbrev WeakenedDependency (_ _ : ParticleOperation) : Prop := False

def operations : List ParticleOperation := [createParent, createChild]

def weakenedRules : RuleVariant :=
  { completeRules with fillParentPositions := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules operations =
      some (graphForDependency operations fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG validHistory).2

theorem required_ordering : RelatedPrevious createChild createParent :=
  ⟨moreRecent_of_order_lt (by decide),
    childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

example : Reaches CompleteDependency createChild createParent :=
  .direct calculated_child_parent

theorem weakened_misses_required_ordering :
    ¬Reaches WeakenedDependency createChild createParent := by
  intro path
  cases path with
  | direct edge => exact edge
  | step edge _ => exact edge

end FillRuleParentPositions

end IndependenceWitnesses

end Define.OperationGraph
