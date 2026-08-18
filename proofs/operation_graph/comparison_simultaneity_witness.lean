import calculation_correctness
import list_history_support
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Comparison Simultaneity Witness

This module proves that its nine-operation model is a `ValidResolvedHistory`
and applies the universal calculation to its final Destroy. All position names
are treated as queryable throughout resolution. Because the history has no
Moves, unused queryable names never acquire entries and therefore never become
candidates.
-/

namespace Define.OperationGraph

namespace ComparisonSimultaneityHistory

def parentPosition : Position := [0]

def childPosition : Position := [0, 0]

def grandChildXPosition : Position := [0, 0, 0]

def grandChildYPosition : Position := [0, 0, 1]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create parentPosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create childPosition

def createGrandChildX : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .create grandChildXPosition

def destroyGrandChildX : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy grandChildXPosition

def destroyChild : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .destroy childPosition

def recreateChild : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .create childPosition

def createGrandChildY : ParticleOperation where
  operationOrder := 6
  actionParent := []
  kind := .create grandChildYPosition

def destroyGrandChildY : ParticleOperation where
  operationOrder := 7
  actionParent := []
  kind := .destroy grandChildYPosition

def destroyRecreatedChild : ParticleOperation where
  operationOrder := 8
  actionParent := []
  kind := .destroy childPosition

def operations : List ParticleOperation :=
  [createParent, createChild, createGrandChildX, destroyGrandChildX,
    destroyChild, recreateChild, createGrandChildY, destroyGrandChildY,
    destroyRecreatedChild]

abbrev IsOperation : ParticleOperation → Prop :=
  ListHistory.IsOperation operations

abbrev occupiedBefore : Nat → Position → Prop :=
  ListHistory.occupiedBefore operations

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔
      position = parentPosition ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = childPosition ∨ position = parentPosition ∨
        position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔
      position = grandChildXPosition ∨ position = childPosition ∨
        position = parentPosition ∨ position = [] := Iff.rfl

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔
      position = childPosition ∨ position = parentPosition ∨
        position = [] := by
  constructor
  · rintro ⟨not_under_x, occupied⟩
    rcases (occupied_three position).mp occupied with rfl | rfl | rfl | rfl
    · exact absurd List.prefix_rfl not_under_x
    · exact Or.inl rfl
    · exact Or.inr (Or.inl rfl)
    · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact ⟨by change ¬grandChildXPosition <+: childPosition; decide,
        (occupied_three _).mpr (Or.inr (Or.inl rfl))⟩
    · exact ⟨by change ¬grandChildXPosition <+: parentPosition; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact ⟨by change ¬grandChildXPosition <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inr rfl)))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔
      position = parentPosition ∨ position = [] := by
  constructor
  · rintro ⟨not_under_child, occupied⟩
    rcases (occupied_four position).mp occupied with rfl | rfl | rfl
    · exact absurd List.prefix_rfl not_under_child
    · exact Or.inl rfl
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by change ¬childPosition <+: parentPosition; decide,
        (occupied_four _).mpr (Or.inr (Or.inl rfl))⟩
    · exact ⟨by change ¬childPosition <+: []; decide,
        (occupied_four _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔
      position = childPosition ∨ position = parentPosition ∨
        position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_five position).mp occupied)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_five _).mpr (Or.inl rfl))
    · exact Or.inr ((occupied_five _).mpr (Or.inr rfl))

theorem occupied_seven (position : Position) :
    occupiedBefore 7 position ↔
      position = grandChildYPosition ∨ position = childPosition ∨
        position = parentPosition ∨ position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_six position).mp occupied)
  · rintro (rfl | rfl | rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_six _).mpr (Or.inl rfl))
    · exact Or.inr ((occupied_six _).mpr (Or.inr (Or.inl rfl)))
    · exact Or.inr ((occupied_six _).mpr (Or.inr (Or.inr rfl)))

theorem occupied_eight (position : Position) :
    occupiedBefore 8 position ↔
      position = childPosition ∨ position = parentPosition ∨
        position = [] := by
  constructor
  · rintro ⟨not_under_y, occupied⟩
    rcases (occupied_seven position).mp occupied with rfl | rfl | rfl | rfl
    · exact absurd List.prefix_rfl not_under_y
    · exact Or.inl rfl
    · exact Or.inr (Or.inl rfl)
    · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact ⟨by change ¬grandChildYPosition <+: childPosition; decide,
        (occupied_seven _).mpr (Or.inr (Or.inl rfl))⟩
    · exact ⟨by change ¬grandChildYPosition <+: parentPosition; decide,
        (occupied_seven _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact ⟨by change ¬grandChildYPosition <+: []; decide,
        (occupied_seven _).mpr (Or.inr (Or.inr (Or.inr rfl)))⟩

theorem operation_shape {operation : ParticleOperation}
    (operation_member : IsOperation operation) :
    operation = createParent ∨ operation = createChild ∨
      operation = createGrandChildX ∨ operation = destroyGrandChildX ∨
        operation = destroyChild ∨ operation = recreateChild ∨
          operation = createGrandChildY ∨
            operation = destroyGrandChildY ∨
              operation = destroyRecreatedChild := by
  simpa [IsOperation, ListHistory.IsOperation, operations] using operation_member

theorem conditions : ListHistory.Conditions operations where
  member_operation_at := by
    intro operation operation_member
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [ListHistory.operationAt, operations] at operation_at
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · simp [createParent, EmptyPosition] at empty_position
    · simp [createChild, EmptyPosition] at empty_position
    · simp [createGrandChildX, EmptyPosition] at empty_position
    · have source_is_x : source = grandChildXPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_x
      exact (occupied_three _).mpr (Or.inl rfl)
    · have source_is_child : source = childPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_four _).mpr (Or.inl rfl)
    · simp [recreateChild, EmptyPosition] at empty_position
    · simp [createGrandChildY, EmptyPosition] at empty_position
    · have source_is_y : source = grandChildYPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_y
      exact (occupied_seven _).mpr (Or.inl rfl)
    · have source_is_child : source = childPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_eight _).mpr (Or.inl rfl)
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
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
      · exact (occupied_one _).mpr (Or.inr rfl)
      · exact (occupied_one _).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_x : target = grandChildXPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_x
      intro parent parent_of_target parent_is_not_target
      rcases prefix_triple_iff.mp parent_of_target with rfl | rfl | rfl | rfl
      · exact (occupied_two _).mpr (Or.inr (Or.inr rfl))
      · exact (occupied_two _).mpr (Or.inr (Or.inl rfl))
      · exact (occupied_two _).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · simp [destroyGrandChildX, FillPosition] at fill_position
    · simp [destroyChild, FillPosition] at fill_position
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_five _).mpr (Or.inr rfl)
      · exact (occupied_five _).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_y : target = grandChildYPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_y
      intro parent parent_of_target parent_is_not_target
      rcases prefix_triple_iff.mp parent_of_target with rfl | rfl | rfl | rfl
      · exact (occupied_six _).mpr (Or.inr (Or.inr rfl))
      · exact (occupied_six _).mpr (Or.inr (Or.inl rfl))
      · exact (occupied_six _).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · simp [destroyGrandChildY, FillPosition] at fill_position
    · simp [destroyRecreatedChild, FillPosition] at fill_position
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro parent_occupied
      simpa [parentPosition] using
        (occupied_zero parentPosition).mp parent_occupied
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro child_occupied
      rcases (occupied_one childPosition).mp child_occupied with
        position_eq | position_eq <;>
        simp [childPosition, parentPosition] at position_eq
    · have target_is_x : target = grandChildXPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_x
      intro x_occupied
      rcases (occupied_two grandChildXPosition).mp x_occupied with
        position_eq | position_eq | position_eq <;>
        simp [grandChildXPosition, childPosition, parentPosition] at position_eq
    · simp [destroyGrandChildX, FillPosition] at fill_position
    · simp [destroyChild, FillPosition] at fill_position
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro child_occupied
      rcases (occupied_five childPosition).mp child_occupied with
        position_eq | position_eq <;>
        simp [childPosition, parentPosition] at position_eq
    · have target_is_y : target = grandChildYPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_y
      intro y_occupied
      rcases (occupied_six grandChildYPosition).mp y_occupied with
        position_eq | position_eq | position_eq <;>
        simp [grandChildYPosition, childPosition, parentPosition] at position_eq
    · simp [destroyGrandChildY, FillPosition] at fill_position
    · simp [destroyRecreatedChild, FillPosition] at fill_position
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;>
      simp [createParent, createChild, createGrandChildX, destroyGrandChildX,
        destroyChild, recreateChild, createGrandChildY, destroyGrandChildY,
        destroyRecreatedChild] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix

def history : ValidResolvedHistory IsOperation :=
  ListHistory.validHistory operations conditions

theorem grand_child_y_entry_before_final_destroy :
    IsEntryBefore history destroyRecreatedChild.operationOrder
      grandChildYPosition destroyGrandChildY := by
  refine ⟨by simp [IsOperation, ListHistory.IsOperation, operations], by decide,
    rfl, ?_⟩
  intro newerCandidate newer_member newer_than_y newer_before_final
    newer_writes_y
  rcases operation_shape newer_member with
    rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createParent, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, createChild, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, createGrandChildX, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, destroyGrandChildX, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, destroyChild, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, recreateChild, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, createGrandChildY, destroyGrandChildY] at newer_than_y
  · simp [MoreRecent, destroyGrandChildY] at newer_than_y
  · simp [destroyRecreatedChild] at newer_before_final

theorem grand_child_y_source_candidate :
    IsSourceCandidateAt history destroyRecreatedChild destroyGrandChildY
      grandChildYPosition := by
  exact ⟨by simp [IsOperation, ListHistory.IsOperation, operations],
    childPosition, rfl, trivial, Or.inr ⟨[1], rfl⟩,
    grand_child_y_entry_before_final_destroy⟩

theorem grand_child_y_after_comparison :
    (calculationFor history destroyRecreatedChild).AfterComparison
      destroyGrandChildY := by
  refine ⟨Or.inl ⟨grandChildYPosition, grand_child_y_source_candidate⟩, ?_⟩
  intro newerCandidate newer_in_collection newer_than_y newer_related
  have newer_before_final :=
    calculationFor_inCollection_is_previous history newer_in_collection
  simp [MoreRecent, destroyGrandChildY] at newer_than_y
  simp [MoreRecent, destroyRecreatedChild] at newer_before_final
  omega

theorem calculated_dependency :
    CalculatedDependency history destroyRecreatedChild destroyGrandChildY := by
  apply
    (calculatedDependency_exact history destroyRecreatedChild
      destroyGrandChildY).mpr
  change
    (calculationFor history destroyRecreatedChild).AfterMoveCorrection
      (CalculatedDependency history) destroyGrandChildY
  exact
    ⟨grand_child_y_after_comparison,
      Or.inl (not_move_of_kind_destroy rfl)⟩

end ComparisonSimultaneityHistory

end Define.OperationGraph
