import calculation_correctness
import independence_witness_support
import minimality
import witness_support

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Empty Rule's transitive child positions

History: `create parent`, `create child`, `destroy child`, `destroy parent`.

Complete Empty Rule: the Collection for the parent Destroy includes the most
recent previous operation on each transitive child position, the child
Destroy. The Comparison then excludes the parent Create in its favor, so the
parent Destroy depends exactly on the child Destroy.

Weakened rule (collect only the emptied position and its parent positions):
the parent Destroy sees only the parent Create and depends on it, so it never
reaches the child Destroy, and destroying the parent is not ordered after the
operation that emptied its child position.
-/

namespace EmptyRuleChildPositions

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

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild ∨
    operation = destroyChild ∨ operation = destroyParent

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | 2 => some destroyChild
  | 3 => some destroyParent
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
              cases previousOrder with
              | zero =>
                  exact induction_hypothesis position_occupied.2
              | succ previousOrder =>
                  cases previousOrder with
                  | zero =>
                      exact induction_hypothesis position_occupied.2
                  | succ previousOrder =>
                      exact induction_hypothesis position_occupied

def validHistory : ValidResolvedHistory isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  queryableBefore := queryableBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Option.some.inj operation_at).symm))
    · simp [operationAt] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt] at operation_at
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    rcases laterOrder with _ | _ | _ | _ | laterOrder
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
    · have first_shape :
          firstOrder = 0 ∨ firstOrder = 1 ∨ firstOrder = 2 := by
        omega
      rcases first_shape with first_is_zero | first_is_one | first_is_two
      · subst first_is_zero
        simp [operationAt] at first_none
      · subst first_is_one
        simp [operationAt] at first_none
      · subst first_is_two
        simp [operationAt] at first_none
    · have first_shape :
          firstOrder = 0 ∨ firstOrder = 1 ∨ firstOrder = 2 ∨
            firstOrder = 3 := by
        omega
      rcases first_shape with
        first_is_zero | first_is_one | first_is_two | first_is_three
      · subst first_is_zero
        simp [operationAt] at first_none
      · subst first_is_one
        simp [operationAt] at first_none
      · subst first_is_two
        simp [operationAt] at first_none
      · subst first_is_three
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
    rcases operation_member with rfl | rfl | rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [createParent, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [createChild, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [destroyChild, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inl (by
        simpa [destroyParent, OperatesOn] using operates_on_position))
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [createParent, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [createChild, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inr (by
        simpa [destroyChild, OperatesOn] using operates_on_position))
    · exact Or.inr (Or.inl (by
        simpa [destroyParent, OperatesOn] using operates_on_position))
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl
    · simp [createParent, EmptyPosition] at empty_position
    · simp [createChild, EmptyPosition] at empty_position
    · have source_is_child : source = childPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact Or.inl rfl
    · have source_is_parent : source = parentPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_parent
      exact
        ⟨by simp [ParentOrSame, childPosition, parentPosition],
          Or.inr (Or.inl rfl)⟩
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl
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
    · simp [destroyChild, FillPosition] at fill_position
    · simp [destroyParent, FillPosition] at fill_position
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl
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
    · simp [destroyChild, FillPosition] at fill_position
    · simp [destroyParent, FillPosition] at fill_position
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_member with rfl | rfl | rfl | rfl <;>
      simp [createParent, createChild, destroyChild, destroyParent] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix
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
  rcases newer_member with rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent] at newer_than_parent
  · simp [createChild] at newer_before_child
  · simp [createChild, destroyChild] at newer_before_child
  · simp [createChild, destroyParent] at newer_before_child

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

theorem child_entry_before_destroy :
    IsEntryBefore validHistory destroyChild.operationOrder childPosition
      createChild := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_child newer_before_destroy
    newer_writes_child
  rcases newer_member with rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, createChild] at newer_than_child
  · simp [MoreRecent, createChild] at newer_than_child
  · simp [destroyChild] at newer_before_destroy
  · simp [destroyChild, destroyParent] at newer_before_destroy

theorem child_is_source_candidate :
    IsSourceCandidate validHistory destroyChild createChild := by
  refine ⟨childPosition, by simp [isOperation], childPosition, rfl,
    Or.inr (Or.inr rfl), related_refl childPosition,
    child_entry_before_destroy⟩

theorem child_after_comparison :
    (calculationFor validHistory destroyChild).AfterComparison createChild := by
  refine ⟨Or.inl child_is_source_candidate, ?_⟩
  intro newerCandidate newer_in_collection newer_than_child
    newer_related_to_child
  rcases newer_in_collection with newer_source | newer_fill
  · rcases newer_source with
      ⟨candidatePosition, newer_operation_member, source, empty_position,
        candidate_queryable, candidate_related, entry⟩
    have newer_before_destroy := entry.candidate_is_previous
    simp [MoreRecent, createChild] at newer_than_child
    simp [destroyChild] at newer_before_destroy
    omega
  · have no_fill_candidate :
        (calculationFor validHistory destroyChild).fillCandidate = none := by
      have well_formed := calculationFor_wellFormed validHistory destroyChild
      change
        (calculationFor validHistory destroyChild).fillCandidate = none at well_formed
      exact well_formed
    change
      (calculationFor validHistory destroyChild).fillCandidate =
        some newerCandidate at newer_fill
    exact nomatch no_fill_candidate.symm.trans newer_fill

theorem calculated_destroy_child :
    CalculatedDependency validHistory destroyChild createChild := by
  apply (calculatedDependency_exact validHistory destroyChild createChild).mpr
  change
    (calculationFor validHistory destroyChild).AfterMoveCorrection
      (CalculatedDependency validHistory) createChild
  exact ⟨child_after_comparison, Or.inl (not_move_of_kind_create rfl)⟩

theorem destroy_entry_before_parent_destroy :
    IsEntryBefore validHistory destroyParent.operationOrder childPosition
      destroyChild := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_destroy
    newer_before_parent_destroy newer_writes_child
  rcases newer_member with rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, destroyChild] at newer_than_destroy
  · simp [MoreRecent, createChild, destroyChild] at newer_than_destroy
  · simp [MoreRecent, destroyChild] at newer_than_destroy
  · simp [destroyParent] at newer_before_parent_destroy

theorem destroy_child_is_parent_source_candidate :
    IsSourceCandidate validHistory destroyParent destroyChild := by
  refine ⟨childPosition, by simp [isOperation], parentPosition, rfl,
    Or.inr (Or.inr rfl), Or.inr ⟨[0], rfl⟩,
    destroy_entry_before_parent_destroy⟩

theorem destroy_child_after_parent_comparison :
    (calculationFor validHistory destroyParent).AfterComparison destroyChild := by
  refine ⟨Or.inl destroy_child_is_parent_source_candidate, ?_⟩
  intro newerCandidate newer_in_collection newer_than_destroy
    newer_related_to_destroy
  rcases newer_in_collection with newer_source | newer_fill
  · rcases newer_source with
      ⟨candidatePosition, newer_operation_member, source, empty_position,
        candidate_queryable, candidate_related, entry⟩
    have newer_before_parent_destroy := entry.candidate_is_previous
    simp [MoreRecent, destroyChild] at newer_than_destroy
    simp [destroyParent] at newer_before_parent_destroy
    omega
  · have no_fill_candidate :
        (calculationFor validHistory destroyParent).fillCandidate = none := by
      have well_formed := calculationFor_wellFormed validHistory destroyParent
      change
        (calculationFor validHistory destroyParent).fillCandidate = none at well_formed
      exact well_formed
    change
      (calculationFor validHistory destroyParent).fillCandidate =
        some newerCandidate at newer_fill
    exact nomatch no_fill_candidate.symm.trans newer_fill

theorem calculated_parent_destroy_child :
    CalculatedDependency validHistory destroyParent destroyChild := by
  apply
    (calculatedDependency_exact validHistory destroyParent destroyChild).mpr
  change
    (calculationFor validHistory destroyParent).AfterMoveCorrection
      (CalculatedDependency validHistory) destroyChild
  exact
    ⟨destroy_child_after_parent_comparison,
      Or.inl (not_move_of_kind_destroy rfl)⟩

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency validHistory

theorem create_child_dependency_is_parent {candidate : ParticleOperation}
    (direct_dependency : CompleteDependency createChild candidate) :
    candidate = createParent := by
  have rule_dependency :=
    (calculatedDependency_exact validHistory createChild candidate).mp
      direct_dependency
  have fill_candidate :
      (calculationFor validHistory createChild).IsFillCandidate candidate := by
    simpa [RuleCalculation.Dependency, calculationFor, createChild] using
      rule_dependency
  exact
    isFillCandidateFor_unique validHistory createChild
      ((calculationFor_fillCandidate_iff validHistory createChild candidate).mp
        fill_candidate)
      ((calculationFor_fillCandidate_iff validHistory createChild createParent).mp
        parent_is_fill_candidate)

theorem destroy_child_dependency_is_child {candidate : ParticleOperation}
    (direct_dependency : CompleteDependency destroyChild candidate) :
    candidate = createChild := by
  have candidate_member :=
    (calculatedDependency_operations validHistory direct_dependency).2
  have points_backward :=
    calculatedDependency_pointsBackward validHistory destroyChild candidate
      direct_dependency
  have rule_dependency :=
    (calculatedDependency_exact validHistory destroyChild candidate).mp
      direct_dependency
  have after_comparison :
      (calculationFor validHistory destroyChild).AfterComparison candidate := by
    exact rule_dependency.1
  rcases candidate_member with rfl | rfl | rfl | rfl
  · exact False.elim
      (after_comparison.2 createChild (Or.inl child_is_source_candidate)
        (by simp [MoreRecent, createChild, createParent])
        ⟨childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩)
  · rfl
  · simp [destroyChild] at points_backward
  · simp [destroyChild, destroyParent] at points_backward

theorem destroy_parent_dependency_is_child {candidate : ParticleOperation}
    (direct_dependency : CompleteDependency destroyParent candidate) :
    candidate = destroyChild := by
  have candidate_member :=
    (calculatedDependency_operations validHistory direct_dependency).2
  have points_backward :=
    calculatedDependency_pointsBackward validHistory destroyParent candidate
      direct_dependency
  have rule_dependency :=
    (calculatedDependency_exact validHistory destroyParent candidate).mp
      direct_dependency
  have after_comparison :
      (calculationFor validHistory destroyParent).AfterComparison candidate := by
    exact rule_dependency.1
  rcases candidate_member with rfl | rfl | rfl | rfl
  · exact False.elim
      (after_comparison.2 destroyChild
        (Or.inl destroy_child_is_parent_source_candidate)
        (by simp [MoreRecent, destroyChild, createParent])
        ⟨childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩)
  · exact False.elim
      (after_comparison.2 destroyChild
        (Or.inl destroy_child_is_parent_source_candidate)
        (by simp [MoreRecent, destroyChild, createChild])
        ⟨childPosition, childPosition, rfl, rfl,
          related_refl childPosition⟩)
  · rfl
  · simp [destroyParent] at points_backward

theorem complete_dependency_iff {operation dependencyOperation : ParticleOperation} :
    CompleteDependency operation dependencyOperation ↔
      (operation = createChild ∧ dependencyOperation = createParent) ∨
        (operation = destroyChild ∧ dependencyOperation = createChild) ∨
          (operation = destroyParent ∧ dependencyOperation = destroyChild) := by
  constructor
  · intro direct_dependency
    have operation_member :=
      (calculatedDependency_operations validHistory direct_dependency).1
    rcases operation_member with rfl | rfl | rfl | rfl
    · have points_backward :=
        calculatedDependency_pointsBackward validHistory createParent
          dependencyOperation direct_dependency
      simp [createParent] at points_backward
    · exact Or.inl ⟨rfl, create_child_dependency_is_parent direct_dependency⟩
    · exact Or.inr (Or.inl
        ⟨rfl, destroy_child_dependency_is_child direct_dependency⟩)
    · exact Or.inr (Or.inr
        ⟨rfl, destroy_parent_dependency_is_child direct_dependency⟩)
  · rintro (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · exact calculated_child_parent
    · exact calculated_destroy_child
    · exact calculated_parent_destroy_child

def weakenedDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = destroyChild then some createChild
    else if operation = destroyParent then some createParent
    else none

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  weakenedDependencyTarget operation = some dependencyOperation

def operations : List ParticleOperation :=
  [createParent, createChild, destroyChild, destroyParent]

def weakenedRules : RuleVariant :=
  { completeRules with emptyChildPositions := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules operations =
      some (graphForDependency operations fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG validHistory).2

theorem required_ordering : RelatedPrevious destroyParent destroyChild :=
  ⟨moreRecent_of_order_lt (by decide),
    parentPosition, childPosition, rfl, rfl, Or.inl ⟨[0], rfl⟩⟩

example : Reaches CompleteDependency destroyParent destroyChild :=
  .direct calculated_parent_destroy_child

theorem weakened_misses_required_ordering :
    ¬Reaches WeakenedDependency destroyParent destroyChild := by
  have from_create_parent :
      ∀ target, ¬Reaches WeakenedDependency createParent target := by
    intro target path
    have no_edge : weakenedDependencyTarget createParent = none := by decide
    cases path with
    | direct edge => exact nomatch (no_edge.symm.trans edge)
    | step edge _ => exact nomatch (no_edge.symm.trans edge)
  intro path
  have only_edge :
      weakenedDependencyTarget destroyParent = some createParent := by decide
  cases path with
  | direct edge =>
      exact absurd (Option.some.inj (edge.symm.trans only_edge)) (by decide)
  | @step _ next _ edge remaining_path =>
      have next_is_parent : next = createParent :=
        Option.some.inj (edge.symm.trans only_edge)
      subst next_is_parent
      exact from_create_parent destroyChild remaining_path

end EmptyRuleChildPositions

end IndependenceWitnesses

end Define.OperationGraph
