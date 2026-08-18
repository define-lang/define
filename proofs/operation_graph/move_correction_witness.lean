import calculation_correctness
import list_history_support
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Move Correction Witness

This module proves that its seven-operation model is a `ValidResolvedHistory`
with an explicit finite set of queryable position names. The universal
calculation then selects the last Move as the final dependency of the box
Destroy after Move Correction removes an earlier Move candidate.
-/

namespace Define.OperationGraph

namespace MoveCorrectionHistory

def boxPosition : Position := [0]

def originPosition : Position := [0, 0]

def middlePosition : Position := [0, 1]

def targetPosition : Position := [0, 2]

def holderAPosition : Position := [1]

def holderCPosition : Position := [2]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createOrigin : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create originPosition

def moveOriginToHolderA : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move originPosition holderAPosition

def moveHolderAToMiddle : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move holderAPosition middlePosition

def moveMiddleToTarget : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .move middlePosition targetPosition

def moveTargetToHolderC : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move targetPosition holderCPosition

def destroyBox : ParticleOperation where
  operationOrder := 6
  actionParent := []
  kind := .destroy boxPosition

def operations : List ParticleOperation :=
  [createBox, createOrigin, moveOriginToHolderA, moveHolderAToMiddle,
    moveMiddleToTarget, moveTargetToHolderC, destroyBox]

abbrev IsOperation : ParticleOperation → Prop :=
  ListHistory.IsOperation operations

abbrev occupiedBefore : Nat → Position → Prop :=
  ListHistory.occupiedBefore operations

def queryableBefore (_operationOrder : Nat) (position : Position) : Prop :=
  position = [] ∨ position = boxPosition ∨ position = originPosition ∨
    position = middlePosition ∨ position = targetPosition ∨
      position = holderAPosition ∨ position = holderCPosition

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔
      position = boxPosition ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = originPosition ∨ position = boxPosition ∨
        position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔
      position = holderAPosition ∨ position = boxPosition ∨
        position = [] := by
  change
    OccupancyAfter moveOriginToHolderA (occupiedBefore 2) position ↔ _
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_two _).mp source_occupied with
        source_is_origin | source_is_box | source_is_empty
      · have relative_is_empty : relative = [] := by
          simpa [originPosition] using source_is_origin
        subst relative_is_empty
        exact Or.inl rfl
      · simp [originPosition, boxPosition] at source_is_box
      · exact nomatch source_is_empty
    · rcases (occupied_two position).mp occupied with rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_two _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by change ¬originPosition <+: boxPosition; decide,
        by change ¬holderAPosition <+: boxPosition; decide,
        (occupied_two _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by change ¬originPosition <+: []; decide,
        by change ¬holderAPosition <+: []; decide,
        (occupied_two _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔
      position = middlePosition ∨ position = boxPosition ∨
        position = [] := by
  change
    OccupancyAfter moveHolderAToMiddle (occupiedBefore 3) position ↔ _
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_three _).mp source_occupied with
        source_is_holder | source_is_box | source_is_empty
      · have relative_is_empty : relative = [] := by
          simpa [holderAPosition] using source_is_holder
        subst relative_is_empty
        exact Or.inl rfl
      · simp [holderAPosition, boxPosition] at source_is_box
      · exact nomatch source_is_empty
    · rcases (occupied_three position).mp occupied with rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_three _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by change ¬holderAPosition <+: boxPosition; decide,
        by change ¬middlePosition <+: boxPosition; decide,
        (occupied_three _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by change ¬holderAPosition <+: []; decide,
        by change ¬middlePosition <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔
      position = targetPosition ∨ position = boxPosition ∨
        position = [] := by
  change OccupancyAfter moveMiddleToTarget (occupiedBefore 4) position ↔ _
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_four _).mp source_occupied with
        source_is_middle | source_is_box | source_is_empty
      · have relative_is_empty : relative = [] := by
          simpa [middlePosition] using source_is_middle
        subst relative_is_empty
        exact Or.inl rfl
      · simp [middlePosition, boxPosition] at source_is_box
      · exact nomatch source_is_empty
    · rcases (occupied_four position).mp occupied with rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_four _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by change ¬middlePosition <+: boxPosition; decide,
        by change ¬targetPosition <+: boxPosition; decide,
        (occupied_four _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by change ¬middlePosition <+: []; decide,
        by change ¬targetPosition <+: []; decide,
        (occupied_four _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔
      position = holderCPosition ∨ position = boxPosition ∨
        position = [] := by
  change OccupancyAfter moveTargetToHolderC (occupiedBefore 5) position ↔ _
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_five _).mp source_occupied with
        source_is_target | source_is_box | source_is_empty
      · have relative_is_empty : relative = [] := by
          simpa [targetPosition] using source_is_target
        subst relative_is_empty
        exact Or.inl rfl
      · simp [targetPosition, boxPosition] at source_is_box
      · exact nomatch source_is_empty
    · rcases (occupied_five position).mp occupied with rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_five _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by change ¬targetPosition <+: boxPosition; decide,
        by change ¬holderCPosition <+: boxPosition; decide,
        (occupied_five _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by change ¬targetPosition <+: []; decide,
        by change ¬holderCPosition <+: []; decide,
        (occupied_five _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_seven (position : Position) :
    occupiedBefore 7 position ↔
      position = holderCPosition ∨ position = [] := by
  constructor
  · rintro ⟨not_under_box, occupied⟩
    rcases (occupied_six position).mp occupied with rfl | rfl | rfl
    · exact Or.inl rfl
    · exact absurd List.prefix_rfl not_under_box
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by change ¬boxPosition <+: holderCPosition; decide,
        (occupied_six _).mpr (Or.inl rfl)⟩
    · exact ⟨by change ¬boxPosition <+: []; decide,
        (occupied_six _).mpr (Or.inr (Or.inr rfl))⟩

theorem operationAt_tail (operationOrder : Nat) :
    ListHistory.operationAt operations (operationOrder + 7) = none := rfl

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 7) position ↔ occupiedBefore 7 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 7) position ↔
            occupiedBefore (extra + 7) position := by
        show occupiedBefore (extra + 7 + 1) position ↔ _
        simp [occupiedBefore, ListHistory.occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

theorem operation_shape {operation : ParticleOperation}
    (operation_member : IsOperation operation) :
    operation = createBox ∨ operation = createOrigin ∨
      operation = moveOriginToHolderA ∨
        operation = moveHolderAToMiddle ∨
          operation = moveMiddleToTarget ∨
            operation = moveTargetToHolderC ∨ operation = destroyBox := by
  simpa [IsOperation, ListHistory.IsOperation, operations] using operation_member

theorem conditions : ListHistory.Conditions operations where
  member_operation_at := by
    intro operation operation_member
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [ListHistory.operationAt, operations] at operation_at
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · simp [createBox, EmptyPosition] at empty_position
    · simp [createOrigin, EmptyPosition] at empty_position
    · have source_is_origin : source = originPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_origin
      exact (occupied_two _).mpr (Or.inl rfl)
    · have source_is_holder_a : source = holderAPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_holder_a
      exact (occupied_three _).mpr (Or.inl rfl)
    · have source_is_middle : source = middlePosition :=
        (Option.some.inj empty_position).symm
      subst source_is_middle
      exact (occupied_four _).mpr (Or.inl rfl)
    · have source_is_target : source = targetPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_target
      exact (occupied_five _).mpr (Or.inl rfl)
    · have source_is_box : source = boxPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_box
      exact (occupied_six _).mpr (Or.inr (Or.inl rfl))
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_box : target = boxPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_box
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · rfl
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_origin : target = originPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_origin
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_one _).mpr (Or.inr rfl)
      · exact (occupied_one _).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_holder_a : target = holderAPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder_a
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_two _).mpr (Or.inr (Or.inr rfl))
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_middle : target = middlePosition :=
        (Option.some.inj fill_position).symm
      subst target_is_middle
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_three _).mpr (Or.inr (Or.inr rfl))
      · exact (occupied_three _).mpr (Or.inr (Or.inl rfl))
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_target : target = targetPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_target
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_four _).mpr (Or.inr (Or.inr rfl))
      · exact (occupied_four _).mpr (Or.inr (Or.inl rfl))
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_holder_c : target = holderCPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder_c
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_five _).mpr (Or.inr (Or.inr rfl))
      · exact False.elim (parent_is_not_target rfl)
    · simp [destroyBox, FillPosition] at fill_position
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_box : target = boxPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_box
      intro box_occupied
      simpa [boxPosition] using (occupied_zero boxPosition).mp box_occupied
    · have target_is_origin : target = originPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_origin
      intro origin_occupied
      rcases (occupied_one originPosition).mp origin_occupied with
        position_eq | position_eq <;>
        simp [originPosition, boxPosition] at position_eq
    · have target_is_holder_a : target = holderAPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder_a
      intro holder_occupied
      rcases (occupied_two holderAPosition).mp holder_occupied with
        position_eq | position_eq | position_eq <;>
        simp [holderAPosition, originPosition, boxPosition] at position_eq
    · have target_is_middle : target = middlePosition :=
        (Option.some.inj fill_position).symm
      subst target_is_middle
      intro middle_occupied
      rcases (occupied_three middlePosition).mp middle_occupied with
        position_eq | position_eq | position_eq <;>
        simp [middlePosition, holderAPosition, boxPosition] at position_eq
    · have target_is_target : target = targetPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_target
      intro target_occupied
      rcases (occupied_four targetPosition).mp target_occupied with
        position_eq | position_eq | position_eq <;>
        simp [targetPosition, middlePosition, boxPosition] at position_eq
    · have target_is_holder_c : target = holderCPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder_c
      intro holder_occupied
      rcases (occupied_five holderCPosition).mp holder_occupied with
        position_eq | position_eq | position_eq <;>
        simp [holderCPosition, targetPosition, boxPosition] at position_eq
    · simp [destroyBox, FillPosition] at fill_position
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · simp [createBox] at operation_kind
    · simp [createOrigin] at operation_kind
    · simp [moveOriginToHolderA] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      exact (by change ¬originPosition <+: holderAPosition; decide)
    · simp [moveHolderAToMiddle] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      exact (by change ¬holderAPosition <+: middlePosition; decide)
    · simp [moveMiddleToTarget] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      exact (by change ¬middlePosition <+: targetPosition; decide)
    · simp [moveTargetToHolderC] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      exact (by change ¬targetPosition <+: holderCPosition; decide)
    · simp [destroyBox] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_shape operation_member with
      rfl | rfl | rfl | rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix

theorem operated_position_queryable (operation : ParticleOperation)
    (position : Position) (operation_member : IsOperation operation)
    (operates_on_position : OperatesOn operation position) :
    queryableBefore operation.operationOrder position := by
  rcases operation_shape operation_member with
    rfl | rfl | rfl | rfl | rfl | rfl | rfl
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, createBox] using operates_on_position))
  · exact Or.inr (Or.inr (Or.inl (by
      simpa [OperatesOn, createOrigin] using operates_on_position)))
  · rcases operates_on_position with position_is_source | position_is_target
    · exact Or.inr (Or.inr (Or.inl position_is_source))
    · exact Or.inr (Or.inr (Or.inr (Or.inr
        (Or.inr (Or.inl position_is_target)))))
  · rcases operates_on_position with position_is_source | position_is_target
    · exact Or.inr (Or.inr (Or.inr (Or.inr
        (Or.inr (Or.inl position_is_source)))))
    · exact Or.inr (Or.inr (Or.inr (Or.inl position_is_target)))
  · rcases operates_on_position with position_is_source | position_is_target
    · exact Or.inr (Or.inr (Or.inr (Or.inl position_is_source)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl position_is_target))))
  · rcases operates_on_position with position_is_source | position_is_target
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl position_is_source))))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr position_is_target)))))
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, destroyBox] using operates_on_position))

theorem queryable_conditions :
    ListHistory.QueryableConditions operations queryableBefore where
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    rcases child_queryable with rfl | rfl | rfl | rfl | rfl | rfl | rfl
    · exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
    · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl rfl))
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl rfl))))
    · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl rfl)))))
    · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr rfl)))))
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl ((occupied_zero position).mp position_occupied)
    · rcases (occupied_one position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_two position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_three position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl rfl)))))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_four position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_five position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl rfl))))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_six position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr rfl)))))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_seven position).mp
        ((occupied_tail operationOrder position).mp position_occupied) with
        rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr rfl)))))
      · exact Or.inl rfl
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    exact operated_position_queryable operation position operation_member
      operates_on_position
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    exact operated_position_queryable operation position operation_member
      operates_on_position

def history : ValidResolvedHistory IsOperation :=
  ListHistory.validHistoryWithQueryable operations conditions queryableBefore
    queryable_conditions

theorem final_move_entry_before_destroy :
    IsEntryBefore history destroyBox.operationOrder targetPosition
      moveTargetToHolderC := by
  refine ⟨by simp [IsOperation, ListHistory.IsOperation, operations], by decide,
    Or.inl rfl, ?_⟩
  intro newerCandidate newer_member newer_than_move newer_before_destroy
    newer_writes_target
  rcases operation_shape newer_member with
    rfl | rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, moveTargetToHolderC] at newer_than_move
  · simp [MoreRecent, createOrigin, moveTargetToHolderC] at newer_than_move
  · simp [MoreRecent, moveOriginToHolderA, moveTargetToHolderC] at newer_than_move
  · simp [MoreRecent, moveHolderAToMiddle, moveTargetToHolderC] at newer_than_move
  · simp [MoreRecent, moveMiddleToTarget, moveTargetToHolderC] at newer_than_move
  · simp [MoreRecent, moveTargetToHolderC] at newer_than_move
  · simp [destroyBox] at newer_before_destroy

theorem final_move_source_candidate :
    IsSourceCandidateAt history destroyBox moveTargetToHolderC
      targetPosition := by
  exact ⟨by simp [IsOperation, ListHistory.IsOperation, operations], boxPosition,
    rfl, Or.inr (Or.inr (Or.inr (Or.inr (Or.inl rfl)))),
    Or.inr ⟨[2], rfl⟩, final_move_entry_before_destroy⟩

theorem final_move_after_comparison :
    (calculationFor history destroyBox).AfterComparison
      moveTargetToHolderC := by
  refine ⟨Or.inl ⟨targetPosition, final_move_source_candidate⟩, ?_⟩
  intro newerCandidate newer_in_collection newer_than_move newer_related
  have newer_before_destroy :=
    calculationFor_inCollection_is_previous history newer_in_collection
  simp [MoreRecent, moveTargetToHolderC] at newer_than_move
  simp [MoreRecent, destroyBox] at newer_before_destroy
  omega

theorem calculated_dependency :
    CalculatedDependency history destroyBox moveTargetToHolderC := by
  apply
    (calculatedDependency_exact history destroyBox moveTargetToHolderC).mpr
  change
    (calculationFor history destroyBox).AfterMoveCorrection
      (CalculatedDependency history) moveTargetToHolderC
  refine ⟨final_move_after_comparison, Or.inr ?_⟩
  intro otherCandidate other_after_comparison other_ne_final_move
  intro other_reaches_final_move
  have final_before_other :=
    reaches_decreases_order
      (calculatedDependency_pointsBackward history) other_reaches_final_move
  have other_member :=
    (calculationFor_inCollection_operations history other_after_comparison.1).2
  rcases operation_shape other_member with
    rfl | rfl | rfl | rfl | rfl | rfl | rfl
  · simp [createBox, moveTargetToHolderC] at final_before_other
  · simp [createOrigin, moveTargetToHolderC] at final_before_other
  · simp [moveOriginToHolderA, moveTargetToHolderC] at final_before_other
  · simp [moveHolderAToMiddle, moveTargetToHolderC] at final_before_other
  · simp [moveMiddleToTarget, moveTargetToHolderC] at final_before_other
  · exact False.elim (other_ne_final_move rfl)
  · have other_before_destroy :=
      calculationFor_inCollection_is_previous history other_after_comparison.1
    simp [MoreRecent, destroyBox] at other_before_destroy

end MoveCorrectionHistory

end Define.OperationGraph
