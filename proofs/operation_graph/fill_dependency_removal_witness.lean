import calculation_correctness
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Fill Dependency Removal Witness

This module proves that its six-operation model is a `ValidResolvedHistory`
and applies the universal calculation to it. The first Move retains unrelated
Empty and Fill Dependencies. The second Move removes its Fill Dependency because
the retained Empty Dependency already reaches it.
-/

namespace Define.OperationGraph

namespace FillDependencyRemoval

def boxPosition : Position := [0]

def itemPosition : Position := [0, 0]

def holderPosition : Position := [1]

def payPosition : Position := [1, 0]

def depositPosition : Position := [1, 1]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createItem : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create itemPosition

def createHolder : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .create holderPosition

def moveItemToPay : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move itemPosition payPosition

def createSecondItem : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .create itemPosition

def moveSecondToDeposit : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move itemPosition depositPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createBox ∨ operation = createItem ∨ operation = createHolder ∨
    operation = moveItemToPay ∨ operation = createSecondItem ∨
    operation = moveSecondToDeposit

def operationAt : Nat → Option ParticleOperation
  | 0 => some createBox
  | 1 => some createItem
  | 2 => some createHolder
  | 3 => some moveItemToPay
  | 4 => some createSecondItem
  | 5 => some moveSecondToDeposit
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
    occupiedBefore 3 position ↔
      position = [1] ∨ position = [0, 0] ∨ position = [0] ∨ position = [] :=
  Iff.rfl

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔
      position = [1, 0] ∨ position = [1] ∨ position = [0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_three _).mp source_occupied with
        extended | extended | extended | extended
      · simp [itemPosition] at extended
      · have relative_shape : relative = [] := by
          simpa [itemPosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · simp [itemPosition] at extended
      · exact nomatch extended
    · rcases (occupied_three position).mp occupied with rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr rfl))
  · rintro (rfl | rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_three _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1]; decide,
        by show ¬([1, 0] : List Nat) <+: [1]; decide,
        (occupied_three _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        by show ¬([1, 0] : List Nat) <+: [0]; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        by show ¬([1, 0] : List Nat) <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inr rfl)))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔
      position = [0, 0] ∨ position = [1, 0] ∨ position = [1] ∨
        position = [0] ∨ position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · rcases (occupied_four position).mp occupied with rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
  · rintro (rfl | rfl | rfl | rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four _).mpr (Or.inl rfl))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inl rfl)))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inr (Or.inl rfl))))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inr (Or.inr rfl))))

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔
      position = [1, 1] ∨ position = [1, 0] ∨ position = [1] ∨
        position = [0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_five _).mp source_occupied with
        extended | extended | extended | extended | extended
      · have relative_shape : relative = [] := by
          simpa [itemPosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · simp [itemPosition] at extended
      · simp [itemPosition] at extended
      · simp [itemPosition] at extended
      · exact nomatch extended
    · rcases (occupied_five position).mp occupied with rfl | rfl | rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
  · rintro (rfl | rfl | rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_five _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1, 0]; decide,
        by show ¬([1, 1] : List Nat) <+: [1, 0]; decide,
        (occupied_five _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1]; decide,
        by show ¬([1, 1] : List Nat) <+: [1]; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        by show ¬([1, 1] : List Nat) <+: [0]; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inr (Or.inl rfl))))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        by show ¬([1, 1] : List Nat) <+: []; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inr (Or.inr rfl))))⟩

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
      rcases child_occupied with rfl | rfl | rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child)))
    · rw [occupied_four] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child)))
    · rw [occupied_five] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr
          (List.eq_nil_of_prefix_nil parent_of_child))))
    · rw [occupied_tail, occupied_six] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr
          (List.eq_nil_of_prefix_nil parent_of_child))))
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · have source_is_item : source = itemPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_item
      exact (occupied_three _).mpr (Or.inr (Or.inl rfl))
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · have source_is_item : source = itemPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_item
      exact (occupied_five _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_box : target = boxPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_box
      intro occupied
      simpa [boxPosition] using (occupied_zero boxPosition).mp occupied
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro occupied
      rcases (occupied_one itemPosition).mp occupied with item_eq | item_eq <;>
        simp [itemPosition] at item_eq
    · have target_is_holder : target = holderPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder
      intro occupied
      rcases (occupied_two holderPosition).mp occupied with
        holder_eq | holder_eq | holder_eq <;>
        simp [holderPosition] at holder_eq
    · have target_is_pay : target = payPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_pay
      intro occupied
      rcases (occupied_three payPosition).mp occupied with
        pay_eq | pay_eq | pay_eq | pay_eq <;>
        simp [payPosition] at pay_eq
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro occupied
      rcases (occupied_four itemPosition).mp occupied with
        item_eq | item_eq | item_eq | item_eq <;>
        simp [itemPosition] at item_eq
    · have target_is_deposit : target = depositPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_deposit
      intro occupied
      rcases (occupied_five depositPosition).mp occupied with
        deposit_eq | deposit_eq | deposit_eq | deposit_eq | deposit_eq <;>
        simp [depositPosition] at deposit_eq
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
    position = boxPosition ∨
      (1 ≤ operationOrder ∧ position = itemPosition) ∨
        (2 ≤ operationOrder ∧ position = holderPosition) ∨
          (3 ≤ operationOrder ∧ position = payPosition) ∨
            (5 ≤ operationOrder ∧ position = depositPosition)

theorem operated_position_queryable (operation : ParticleOperation)
    (position : Position) (operation_member : isOperation operation)
    (operates_on_position : OperatesOn operation position) :
    queryableBefore operation.operationOrder position := by
  rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
  · exact Or.inr (Or.inl (by
      simpa [OperatesOn, createBox] using operates_on_position))
  · exact Or.inr (Or.inr (Or.inl ⟨by decide, by
      simpa [OperatesOn, createItem] using operates_on_position⟩))
  · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, by
      simpa [OperatesOn, createHolder] using operates_on_position⟩)))
  · rcases operates_on_position with position_is_item | position_is_pay
    · exact Or.inr (Or.inr (Or.inl ⟨by decide, position_is_item⟩))
    · exact Or.inr (Or.inr (Or.inr
        (Or.inr (Or.inl ⟨by decide, position_is_pay⟩))))
  · exact Or.inr (Or.inr (Or.inl ⟨by decide, by
      simpa [OperatesOn, createSecondItem] using operates_on_position⟩))
  · rcases operates_on_position with position_is_item | position_is_deposit
    · exact Or.inr (Or.inr (Or.inl ⟨by decide, position_is_item⟩))
    · exact Or.inr (Or.inr (Or.inr
        (Or.inr (Or.inr ⟨by decide, position_is_deposit⟩))))

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
    rcases child_queryable with rfl | rfl |
      ⟨one_le, rfl⟩ | ⟨two_le, rfl⟩ | ⟨three_le, rfl⟩ | ⟨five_le, rfl⟩
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
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inl ⟨three_le, rfl⟩))))
    · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
      · exact Or.inl rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by omega, rfl⟩)))
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inr ⟨five_le, rfl⟩))))
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl ((occupied_zero position).mp position_occupied)
    · rcases (occupied_one position).mp position_occupied with rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_two position).mp position_occupied with rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_three position).mp position_occupied with
        rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)))
      · exact Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_four position).mp position_occupied with
        rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inl ⟨by decide, rfl⟩))))
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_five position).mp position_occupied with
        rfl | rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inl ⟨by decide, rfl⟩))))
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
    · rcases (occupied_six position).mp
          ((occupied_tail operationOrder position).mp position_occupied) with
        rfl | rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inr ⟨by omega, rfl⟩))))
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inl ⟨by omega, rfl⟩))))
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by omega, rfl⟩)))
      · exact Or.inr (Or.inl rfl)
      · exact Or.inl rfl
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    exact operated_position_queryable operation position operation_member
      operates_on_position
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact Or.inr (Or.inl (by
        simpa [OperatesOn, createBox] using operates_on_position))
    · simp [createItem] at operation_before
      exact Or.inr (Or.inr (Or.inl ⟨by omega, by
        simpa [OperatesOn, createItem] using operates_on_position⟩))
    · simp [createHolder] at operation_before
      exact Or.inr (Or.inr (Or.inr (Or.inl ⟨by omega, by
        simpa [OperatesOn, createHolder] using operates_on_position⟩)))
    · simp [moveItemToPay] at operation_before
      rcases operates_on_position with position_is_item | position_is_pay
      · exact Or.inr (Or.inr (Or.inl ⟨by omega, position_is_item⟩))
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inl ⟨by omega, position_is_pay⟩))))
    · simp [createSecondItem] at operation_before
      exact Or.inr (Or.inr (Or.inl ⟨by omega, by
        simpa [OperatesOn, createSecondItem] using operates_on_position⟩))
    · simp [moveSecondToDeposit] at operation_before
      rcases operates_on_position with position_is_item | position_is_deposit
      · exact Or.inr (Or.inr (Or.inl ⟨by omega, position_is_item⟩))
      · exact Or.inr (Or.inr (Or.inr
          (Or.inr (Or.inr ⟨by omega, position_is_deposit⟩))))
  empty_position_is_occupied := occupancy.empty_position_is_occupied
  fill_position_is_available := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_box : target = boxPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_box
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_zero []).mpr rfl
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_one []).mpr (Or.inr rfl)
      · exact (occupied_one boxPosition).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_holder : target = holderPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder
      intro parent parent_of_target parent_is_not_target
      rcases prefix_singleton_iff.mp parent_of_target with rfl | rfl
      · exact (occupied_two []).mpr (Or.inr (Or.inr rfl))
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_pay : target = payPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_pay
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_three []).mpr (Or.inr (Or.inr (Or.inr rfl)))
      · exact (occupied_three holderPosition).mpr (Or.inl rfl)
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_four []).mpr (Or.inr (Or.inr (Or.inr rfl)))
      · exact (occupied_four boxPosition).mpr
          (Or.inr (Or.inr (Or.inl rfl)))
      · exact False.elim (parent_is_not_target rfl)
    · have target_is_deposit : target = depositPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_deposit
      intro parent parent_of_target parent_is_not_target
      rcases prefix_pair_iff.mp parent_of_target with rfl | rfl | rfl
      · exact (occupied_five []).mpr
          (Or.inr (Or.inr (Or.inr (Or.inr rfl))))
      · exact (occupied_five holderPosition).mpr
          (Or.inr (Or.inr (Or.inl rfl)))
      · exact False.elim (parent_is_not_target rfl)
  fill_position_is_empty := occupancy.fill_position_is_empty
  move_source_not_parent_of_target := by
    intro operation source target operation_member operation_kind
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · simp [createBox] at operation_kind
    · simp [createItem] at operation_kind
    · simp [createHolder] at operation_kind
    · simp [moveItemToPay] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      intro item_parent_of_pay
      rcases prefix_pair_iff.mp item_parent_of_pay with
        item_is_empty | item_is_holder | item_is_pay
      · simp [itemPosition] at item_is_empty
      · simp [itemPosition] at item_is_holder
      · simp [itemPosition] at item_is_pay
    · simp [createSecondItem] at operation_kind
    · simp [moveSecondToDeposit] at operation_kind
      rcases operation_kind with ⟨rfl, rfl⟩
      intro item_parent_of_deposit
      rcases prefix_pair_iff.mp item_parent_of_deposit with
        item_is_empty | item_is_holder | item_is_deposit
      · simp [itemPosition] at item_is_empty
      · simp [itemPosition] at item_is_holder
      · simp [itemPosition] at item_is_deposit
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;>
      exact List.nil_prefix
  operation_transition := occupancy.operation_transition
  no_operation_transition := occupancy.no_operation_transition

theorem create_box_entry_before_item :
    IsEntryBefore history createItem.operationOrder boxPosition createBox := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_box newer_before_item
    newer_writes_box
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox] at newer_than_box
  · simp [createItem] at newer_before_item
  · simp [createItem, createHolder] at newer_before_item
  · simp [createItem, moveItemToPay] at newer_before_item
  · simp [createItem, createSecondItem] at newer_before_item
  · simp [createItem, moveSecondToDeposit] at newer_before_item

theorem create_item_fill_candidate :
    (calculationFor history createItem).IsFillCandidate createBox := by
  apply (calculationFor_fillCandidate_iff history createItem createBox).mpr
  refine ⟨⟨by simp [isOperation], itemPosition, boxPosition, rfl,
    Or.inr (Or.inl rfl), ⟨[0], rfl⟩, create_box_entry_before_item⟩, ?_⟩
  intro newerCandidate newer_fill_entry newer_than_box
  have newer_before_item :=
    isFillEntry_candidate_is_previous newer_fill_entry
  simp [MoreRecent, createBox, createItem] at newer_than_box newer_before_item
  omega

theorem create_item_entry_before_first_move :
    IsEntryBefore history moveItemToPay.operationOrder itemPosition createItem := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_item newer_before_move
    newer_writes_item
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createItem] at newer_than_item
  · simp [MoreRecent, createItem] at newer_than_item
  · change itemPosition = holderPosition at newer_writes_item
    simp [itemPosition, holderPosition] at newer_writes_item
  · simp [moveItemToPay] at newer_before_move
  · simp [moveItemToPay, createSecondItem] at newer_before_move
  · simp [moveItemToPay, moveSecondToDeposit] at newer_before_move

theorem first_move_source_candidate :
    IsSourceCandidateAt history moveItemToPay createItem itemPosition := by
  exact ⟨by simp [isOperation], itemPosition, rfl,
    Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)), related_refl itemPosition,
    create_item_entry_before_first_move⟩

theorem holder_entry_before_first_move :
    IsEntryBefore history moveItemToPay.operationOrder holderPosition
      createHolder := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_holder newer_before_move
    newer_writes_holder
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createHolder] at newer_than_holder
  · simp [MoreRecent, createItem, createHolder] at newer_than_holder
  · simp [MoreRecent, createHolder] at newer_than_holder
  · simp [moveItemToPay] at newer_before_move
  · simp [moveItemToPay, createSecondItem] at newer_before_move
  · simp [moveItemToPay, moveSecondToDeposit] at newer_before_move

theorem first_move_fill_candidate :
    (calculationFor history moveItemToPay).IsFillCandidate createHolder := by
  apply
    (calculationFor_fillCandidate_iff history moveItemToPay createHolder).mpr
  refine ⟨⟨by simp [isOperation], payPosition, holderPosition, rfl,
    Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))),
    ⟨[0], rfl⟩, holder_entry_before_first_move⟩, ?_⟩
  intro newerCandidate newer_fill_entry newer_than_holder
  have newer_before_move :=
    isFillEntry_candidate_is_previous newer_fill_entry
  simp [MoreRecent, createHolder, moveItemToPay] at newer_than_holder newer_before_move
  omega

theorem first_move_entry_before_second_item :
    IsEntryBefore history createSecondItem.operationOrder itemPosition
      moveItemToPay := by
  refine ⟨by simp [isOperation], by decide, Or.inl rfl, ?_⟩
  intro newerCandidate newer_member newer_than_move newer_before_second_item
    newer_writes_item
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, moveItemToPay] at newer_than_move
  · simp [MoreRecent, createItem, moveItemToPay] at newer_than_move
  · simp [MoreRecent, createHolder, moveItemToPay] at newer_than_move
  · simp [MoreRecent, moveItemToPay] at newer_than_move
  · simp [createSecondItem] at newer_before_second_item
  · simp [createSecondItem, moveSecondToDeposit] at newer_before_second_item

theorem second_item_fill_candidate :
    (calculationFor history createSecondItem).IsFillCandidate moveItemToPay := by
  apply
    (calculationFor_fillCandidate_iff history createSecondItem
      moveItemToPay).mpr
  refine ⟨⟨by simp [isOperation], itemPosition, itemPosition, rfl,
    Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)), List.prefix_rfl,
    first_move_entry_before_second_item⟩, ?_⟩
  intro newerCandidate newer_fill_entry newer_than_move
  have newer_before_second_item :=
    isFillEntry_candidate_is_previous newer_fill_entry
  simp [MoreRecent, moveItemToPay, createSecondItem] at newer_than_move newer_before_second_item
  omega

theorem holder_entry_before_second_move :
    IsEntryBefore history moveSecondToDeposit.operationOrder holderPosition
      createHolder := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_holder newer_before_second_move
    newer_writes_holder
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createHolder] at newer_than_holder
  · simp [MoreRecent, createItem, createHolder] at newer_than_holder
  · simp [MoreRecent, createHolder] at newer_than_holder
  · simp [WritesEntry, moveItemToPay, holderPosition, itemPosition,
      payPosition] at newer_writes_holder
  · change holderPosition = itemPosition at newer_writes_holder
    simp [holderPosition, itemPosition] at newer_writes_holder
  · simp [moveSecondToDeposit] at newer_before_second_move

theorem second_move_fill_entry_is_holder {candidate : ParticleOperation}
    (fill_entry : IsFillEntry history moveSecondToDeposit candidate) :
    candidate = createHolder := by
  rcases fill_entry with
    ⟨operation_member, fillPosition, position, fill_position, position_queryable,
      position_parent, entry⟩
  have fill_is_deposit : fillPosition = depositPosition :=
    (Option.some.inj fill_position).symm
  subst fill_is_deposit
  rcases entry.2.2.1.operated_position with
    ⟨operatedPosition, candidate_operates, operated_parent_position⟩
  have operated_parent_deposit :
      ParentOrSame operatedPosition depositPosition :=
    operated_parent_position.trans position_parent
  rcases entry.1 with rfl | rfl | rfl | rfl | rfl | rfl
  · have operated_is_box : operatedPosition = boxPosition := by
      simpa [OperatesOn, createBox] using candidate_operates
    subst operated_is_box
    exact False.elim
      ((by decide : ¬(boxPosition <+: depositPosition))
        operated_parent_deposit)
  · have operated_is_item : operatedPosition = itemPosition := by
      simpa [OperatesOn, createItem] using candidate_operates
    subst operated_is_item
    exact False.elim
      ((by decide : ¬(itemPosition <+: depositPosition))
        operated_parent_deposit)
  · rfl
  · rcases candidate_operates with operated_is_item | operated_is_pay
    · subst operated_is_item
      exact False.elim
        ((by decide : ¬(itemPosition <+: depositPosition))
          operated_parent_deposit)
    · subst operated_is_pay
      exact False.elim
        ((by decide : ¬(payPosition <+: depositPosition))
          operated_parent_deposit)
  · have operated_is_item : operatedPosition = itemPosition := by
      simpa [OperatesOn, createSecondItem] using candidate_operates
    subst operated_is_item
    exact False.elim
      ((by decide : ¬(itemPosition <+: depositPosition))
        operated_parent_deposit)
  · have candidate_before_operation := entry.2.1
    simp [moveSecondToDeposit] at candidate_before_operation

theorem second_move_fill_candidate :
    (calculationFor history moveSecondToDeposit).IsFillCandidate
      createHolder := by
  apply
    (calculationFor_fillCandidate_iff history moveSecondToDeposit
      createHolder).mpr
  refine ⟨⟨by simp [isOperation], depositPosition, holderPosition, rfl,
    Or.inr (Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩))),
    ⟨[1], rfl⟩, holder_entry_before_second_move⟩, ?_⟩
  intro newerCandidate newer_fill_entry newer_than_holder
  have newer_is_holder := second_move_fill_entry_is_holder newer_fill_entry
  subst newer_is_holder
  simp [MoreRecent] at newer_than_holder

theorem create_second_entry_before_second_move :
    IsEntryBefore history moveSecondToDeposit.operationOrder itemPosition
      createSecondItem := by
  refine ⟨by simp [isOperation], by decide, rfl, ?_⟩
  intro newerCandidate newer_member newer_than_second_item
    newer_before_second_move newer_writes_item
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createItem, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createHolder, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, moveItemToPay, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createSecondItem] at newer_than_second_item
  · simp [moveSecondToDeposit] at newer_before_second_move

theorem second_move_source_candidate :
    IsSourceCandidateAt history moveSecondToDeposit createSecondItem
      itemPosition := by
  exact ⟨by simp [isOperation], itemPosition, rfl,
    Or.inr (Or.inr (Or.inl ⟨by decide, rfl⟩)), related_refl itemPosition,
    create_second_entry_before_second_move⟩

theorem create_holder_not_related_create_item :
    ¬OperationsRelated createHolder createItem := by
  rintro ⟨holderOperationPosition, itemOperationPosition, holder_operates,
    item_operates, positions_related⟩
  have holder_position : holderOperationPosition = holderPosition := by
    simpa [OperatesOn, createHolder] using holder_operates
  have item_position : itemOperationPosition = itemPosition := by
    simpa [OperatesOn, createItem] using item_operates
  subst holder_position
  subst item_position
  exact
    (by decide :
      ¬(holderPosition <+: itemPosition ∨ itemPosition <+: holderPosition))
      positions_related

theorem create_second_not_related_create_holder :
    ¬OperationsRelated createSecondItem createHolder := by
  rintro ⟨itemOperationPosition, holderOperationPosition, item_operates,
    holder_operates, positions_related⟩
  have item_position : itemOperationPosition = itemPosition := by
    simpa [OperatesOn, createSecondItem] using item_operates
  have holder_position : holderOperationPosition = holderPosition := by
    simpa [OperatesOn, createHolder] using holder_operates
  subst item_position
  subst holder_position
  exact
    (by decide :
      ¬(itemPosition <+: holderPosition ∨ holderPosition <+: itemPosition))
      positions_related

theorem first_move_item_after_comparison :
    (calculationFor history moveItemToPay).AfterComparison createItem := by
  refine ⟨Or.inl ⟨itemPosition, first_move_source_candidate⟩, ?_⟩
  intro newerCandidate newer_in_collection newer_than_item newer_related
  have newer_before_move :=
    calculationFor_inCollection_is_previous history newer_in_collection
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createItem] at newer_than_item
  · simp [MoreRecent, createItem] at newer_than_item
  · exact create_holder_not_related_create_item newer_related
  · simp [MoreRecent, moveItemToPay] at newer_before_move
  · simp [MoreRecent, moveItemToPay, createSecondItem] at newer_before_move
  · simp [MoreRecent, moveItemToPay, moveSecondToDeposit] at newer_before_move

theorem first_move_holder_after_comparison :
    (calculationFor history moveItemToPay).AfterComparison createHolder := by
  refine ⟨Or.inr first_move_fill_candidate, ?_⟩
  intro newerCandidate newer_in_collection newer_than_holder newer_related
  have newer_before_move :=
    calculationFor_inCollection_is_previous history newer_in_collection
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createHolder] at newer_than_holder
  · simp [MoreRecent, createItem, createHolder] at newer_than_holder
  · simp [MoreRecent, createHolder] at newer_than_holder
  · simp [MoreRecent, moveItemToPay] at newer_before_move
  · simp [MoreRecent, moveItemToPay, createSecondItem] at newer_before_move
  · simp [MoreRecent, moveItemToPay, moveSecondToDeposit] at newer_before_move

theorem first_move_source_candidate_shape {candidate : ParticleOperation}
    (source_candidate :
      (calculationFor history moveItemToPay).sourceCandidate candidate) :
    candidate = createItem ∨ candidate = createBox := by
  rcases source_candidate with ⟨position, candidate_at⟩
  rcases candidate_at with
    ⟨operation_member, emptyPosition, empty_position, position_queryable,
      position_related, entry⟩
  have empty_is_item : emptyPosition = itemPosition :=
    (Option.some.inj empty_position).symm
  subst empty_is_item
  rcases entry.1 with rfl | rfl | rfl | rfl | rfl | rfl
  · exact Or.inr rfl
  · exact Or.inl rfl
  · have position_is_holder : position = holderPosition := entry.2.2.1
    subst position_is_holder
    exact False.elim
      ((by decide :
        ¬(holderPosition <+: itemPosition ∨
          itemPosition <+: holderPosition)) position_related)
  · have candidate_before_move := entry.2.1
    simp [moveItemToPay] at candidate_before_move
  · have candidate_before_move := entry.2.1
    simp [moveItemToPay, createSecondItem] at candidate_before_move
  · have candidate_before_move := entry.2.1
    simp [moveItemToPay, moveSecondToDeposit] at candidate_before_move

theorem create_item_fill_candidate_eq {candidate : ParticleOperation}
    (fill_candidate :
      (calculationFor history createItem).IsFillCandidate candidate) :
    candidate = createBox := by
  exact
    isFillCandidateFor_unique history createItem
      ((calculationFor_fillCandidate_iff history createItem candidate).mp
        fill_candidate)
      ((calculationFor_fillCandidate_iff history createItem createBox).mp
        create_item_fill_candidate)

theorem calculated_create_item_box :
    CalculatedDependency history createItem createBox := by
  apply (calculatedDependency_exact history createItem createBox).mpr
  simpa [RuleCalculation.Dependency, calculationFor, createItem] using
    create_item_fill_candidate

theorem create_box_no_dependencies (candidate : ParticleOperation) :
    ¬CalculatedDependency history createBox candidate := by
  intro direct_dependency
  have points_backward :=
    calculatedDependency_pointsBackward history createBox candidate
      direct_dependency
  simp [createBox] at points_backward

theorem create_item_dependency_is_box {candidate : ParticleOperation}
    (direct_dependency : CalculatedDependency history createItem candidate) :
    candidate = createBox := by
  have rule_dependency :=
    (calculatedDependency_exact history createItem candidate).mp
      direct_dependency
  have fill_candidate :
      (calculationFor history createItem).IsFillCandidate candidate := by
    simpa [RuleCalculation.Dependency, calculationFor, createItem] using
      rule_dependency
  exact create_item_fill_candidate_eq fill_candidate

theorem create_item_does_not_reach_holder :
    ¬Reaches (CalculatedDependency history) createItem createHolder := by
  intro path
  cases path with
  | direct direct_dependency =>
      exact
        (by decide : createHolder ≠ createBox)
          (create_item_dependency_is_box direct_dependency)
  | step direct_dependency remaining_path =>
      rw [create_item_dependency_is_box direct_dependency] at remaining_path
      exact
        no_reaches_of_no_dependency create_box_no_dependencies remaining_path

theorem calculated_first_move_item :
    CalculatedDependency history moveItemToPay createItem := by
  apply (calculatedDependency_exact history moveItemToPay createItem).mpr
  change
    (calculationFor history moveItemToPay).MoveRuleDependency
      (CalculatedDependency history) createItem
  refine ⟨⟨first_move_item_after_comparison,
    Or.inl (not_move_of_kind_create rfl)⟩, ?_⟩
  rintro ⟨fill_candidate, sourceCandidate, source_candidate,
    source_correction, candidates_distinct, source_reaches⟩
  have candidate_is_holder :=
    isFillCandidateFor_unique history moveItemToPay
      ((calculationFor_fillCandidate_iff history moveItemToPay createItem).mp
        fill_candidate)
      ((calculationFor_fillCandidate_iff history moveItemToPay createHolder).mp
        first_move_fill_candidate)
  exact (by decide : createItem ≠ createHolder) candidate_is_holder

theorem calculated_first_move_holder :
    CalculatedDependency history moveItemToPay createHolder := by
  apply (calculatedDependency_exact history moveItemToPay createHolder).mpr
  change
    (calculationFor history moveItemToPay).MoveRuleDependency
      (CalculatedDependency history) createHolder
  refine ⟨⟨first_move_holder_after_comparison,
    Or.inl (not_move_of_kind_create rfl)⟩, ?_⟩
  rintro ⟨fill_candidate, sourceCandidate, source_candidate,
    source_correction, candidates_distinct, source_reaches⟩
  rcases first_move_source_candidate_shape source_candidate with
    rfl | rfl
  · exact create_item_does_not_reach_holder source_reaches
  · exact
      no_reaches_of_no_dependency create_box_no_dependencies source_reaches

theorem calculated_second_item_first_move :
    CalculatedDependency history createSecondItem moveItemToPay := by
  apply
    (calculatedDependency_exact history createSecondItem moveItemToPay).mpr
  simpa [RuleCalculation.Dependency, calculationFor, createSecondItem] using
    second_item_fill_candidate

theorem second_move_fill_candidate_eq {candidate : ParticleOperation}
    (fill_candidate :
      (calculationFor history moveSecondToDeposit).IsFillCandidate candidate) :
    candidate = createHolder := by
  exact
    isFillCandidateFor_unique history moveSecondToDeposit
      ((calculationFor_fillCandidate_iff history moveSecondToDeposit
        candidate).mp fill_candidate)
      ((calculationFor_fillCandidate_iff history moveSecondToDeposit
        createHolder).mp second_move_fill_candidate)

theorem first_move_not_in_second_move_collection :
    ¬(calculationFor history moveSecondToDeposit).InCollection
      moveItemToPay := by
  rintro (source_candidate | fill_candidate)
  · rcases source_candidate with ⟨position, candidate_at⟩
    rcases candidate_at with
      ⟨operation_member, emptyPosition, empty_position, position_queryable,
        position_related, entry⟩
    have empty_is_item : emptyPosition = itemPosition :=
      (Option.some.inj empty_position).symm
    subst empty_is_item
    rcases entry.2.2.1 with
      position_is_item | position_is_pay |
        ⟨relativePosition, relative_nonempty, position_shape,
          source_child_queryable⟩
    · subst position_is_item
      exact
        entry.2.2.2 createSecondItem (by simp [isOperation])
          (show MoreRecent createSecondItem moveItemToPay from
            (by decide :
              moveItemToPay.operationOrder < createSecondItem.operationOrder))
          (by decide) rfl
    · subst position_is_pay
      exact
        (by decide :
          ¬(payPosition <+: itemPosition ∨ itemPosition <+: payPosition))
          position_related
    · rcases relativePosition with _ | ⟨relativeHead, relativeTail⟩
      · exact relative_nonempty rfl
      · change queryableBefore 3
          (itemPosition ++ relativeHead :: relativeTail) at source_child_queryable
        simp [queryableBefore, itemPosition, boxPosition, holderPosition,
          payPosition, depositPosition] at source_child_queryable
  · exact
      (by decide : moveItemToPay ≠ createHolder)
        (second_move_fill_candidate_eq fill_candidate)

theorem second_move_item_after_comparison :
    (calculationFor history moveSecondToDeposit).AfterComparison
      createSecondItem := by
  refine ⟨Or.inl ⟨itemPosition, second_move_source_candidate⟩, ?_⟩
  intro newerCandidate newer_in_collection newer_than_second_item newer_related
  have newer_before_move :=
    calculationFor_inCollection_is_previous history newer_in_collection
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createItem, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createHolder, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, moveItemToPay, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, createSecondItem] at newer_than_second_item
  · simp [MoreRecent, moveSecondToDeposit] at newer_before_move

theorem second_move_holder_after_comparison :
    (calculationFor history moveSecondToDeposit).AfterComparison
      createHolder := by
  refine ⟨Or.inr second_move_fill_candidate, ?_⟩
  intro newerCandidate newer_in_collection newer_than_holder newer_related
  have newer_before_move :=
    calculationFor_inCollection_is_previous history newer_in_collection
  have newer_member :=
    (calculationFor_inCollection_operations history newer_in_collection).2
  rcases newer_member with rfl | rfl | rfl | rfl | rfl | rfl
  · simp [MoreRecent, createBox, createHolder] at newer_than_holder
  · simp [MoreRecent, createItem, createHolder] at newer_than_holder
  · simp [MoreRecent, createHolder] at newer_than_holder
  · exact first_move_not_in_second_move_collection newer_in_collection
  · exact create_second_not_related_create_holder newer_related
  · simp [MoreRecent, moveSecondToDeposit] at newer_before_move

theorem second_item_reaches_holder :
    Reaches (CalculatedDependency history) createSecondItem createHolder :=
  .step calculated_second_item_first_move
    (.direct calculated_first_move_holder)

theorem calculated_second_move_item :
    CalculatedDependency history moveSecondToDeposit createSecondItem := by
  apply
    (calculatedDependency_exact history moveSecondToDeposit
      createSecondItem).mpr
  change
    (calculationFor history moveSecondToDeposit).MoveRuleDependency
      (CalculatedDependency history) createSecondItem
  refine ⟨⟨second_move_item_after_comparison,
    Or.inl (not_move_of_kind_create rfl)⟩, ?_⟩
  rintro ⟨fill_candidate, sourceCandidate, source_candidate,
    source_correction, candidates_distinct, source_reaches⟩
  exact
    (by decide : createSecondItem ≠ createHolder)
      (second_move_fill_candidate_eq fill_candidate)

theorem second_move_fill_dependency_removed :
    ¬CalculatedDependency history moveSecondToDeposit createHolder := by
  intro direct_dependency
  have rule_dependency :=
    (calculatedDependency_exact history moveSecondToDeposit createHolder).mp
      direct_dependency
  change
    (calculationFor history moveSecondToDeposit).MoveRuleDependency
      (CalculatedDependency history) createHolder at rule_dependency
  exact rule_dependency.2
    ⟨second_move_fill_candidate, createSecondItem,
      ⟨itemPosition, second_move_source_candidate⟩,
      ⟨second_move_item_after_comparison,
        Or.inl (not_move_of_kind_create rfl)⟩,
      (by decide), second_item_reaches_holder⟩

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

end FillDependencyRemoval

end Define.OperationGraph
