import minimality
import moved_child_entry_witness
import non_vacuity_witness
import vanished_child_name_witness
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
This aggregate currently contains the one concrete model that still uses the
legacy `ResolvedDefineGraph` interface. It demonstrates selected semantic
obligations but supplies no premise to the minimality theorem. It will move to
its own module as it is migrated to the actual resolved-history calculation.

`NonVacuity`, imported from `non_vacuity_witness.lean`, applies the actual
calculation to the Create-and-Destroy history matching the
create_and_destroy_of_an_implied_position integration test.

`VanishedChildName`, imported from `vanished_child_name_witness.lean`,
demonstrates `latest_source_candidate` at a position name that no longer refers
to a position: an operation on the child position of a destroyed and replaced
parent particle is a keyed candidate that the Comparison always excludes.

`MovedChildEntry`, imported from `moved_child_entry_witness.lean`, demonstrates
a Move selected as the most-recent entry for a moved particle's transitive child
position, and a Move surviving the Move Correction as a final dependency.

`FillDependencyRemoval` demonstrates the Move Rule: one Move keeps both an
Empty Dependency and an unrelated Fill Dependency as a two-dependency
reachability antichain, and a later Move's Fill Dependency is removed because a
remaining Empty Dependency reaches it. This is the redundancy family covered by
the move_excludes_create_fill_dependency_reached_through_source_dependency
integration test.

The namespace below still constructs the older `ResolvedDefineGraph` interface
directly; it remains to be migrated to the same end-to-end path as the imported
witnesses.
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

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  (operation = moveItemToPay ∧
    ((candidate = createItem ∧ candidatePosition = itemPosition) ∨
      (candidate = createBox ∧ candidatePosition = boxPosition))) ∨
  (operation = moveSecondToDeposit ∧
    ((candidate = createSecondItem ∧ candidatePosition = itemPosition) ∨
      (candidate = createBox ∧ candidatePosition = boxPosition)))

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := fun candidate =>
    ∃ candidatePosition, sourceCandidateAt operation candidate candidatePosition
  fillCandidate :=
    if operation = createItem then some createBox
    else if operation = moveItemToPay then some createHolder
    else if operation = createSecondItem then some moveItemToPay
    else if operation = moveSecondToDeposit then some createHolder
    else none

def dependency (operation candidate : ParticleOperation) : Prop :=
  (operation = createItem ∧ candidate = createBox) ∨
    (operation = moveItemToPay ∧ candidate = createItem) ∨
    (operation = moveItemToPay ∧ candidate = createHolder) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧ candidate = createSecondItem)

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rintro candidate ⟨candidatePosition, source_at⟩
      rcases source_at with ⟨rfl, _⟩ | ⟨rfl, _⟩ <;>
        simp [moveItemToPay, moveSecondToDeposit] at operation_kind
  | destroy target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rw [if_neg, if_neg, if_neg, if_neg]
      all_goals
        intro operation_is_filler
        subst operation_is_filler
        simp [createItem, moveItemToPay, createSecondItem,
          moveSecondToDeposit] at operation_kind
  | move source target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]

theorem fill_item : (calculation createItem).fillCandidate = some createBox := by
  show (if (createItem : ParticleOperation) = createItem then some createBox
    else if (createItem : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (createItem : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (createItem : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createBox
  rw [if_pos rfl]

theorem fill_first_move :
    (calculation moveItemToPay).fillCandidate = some createHolder := by
  show (if (moveItemToPay : ParticleOperation) = createItem then some createBox
    else if (moveItemToPay : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (moveItemToPay : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (moveItemToPay : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createHolder
  rw [if_neg (by decide), if_pos rfl]

theorem fill_second_item :
    (calculation createSecondItem).fillCandidate = some moveItemToPay := by
  show (if (createSecondItem : ParticleOperation) = createItem then
      some createBox
    else if (createSecondItem : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (createSecondItem : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (createSecondItem : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some moveItemToPay
  rw [if_neg (by decide), if_neg (by decide), if_pos rfl]

theorem fill_second_move :
    (calculation moveSecondToDeposit).fillCandidate = some createHolder := by
  show (if (moveSecondToDeposit : ParticleOperation) = createItem then
      some createBox
    else if (moveSecondToDeposit : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (moveSecondToDeposit : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (moveSecondToDeposit : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createHolder
  rw [if_neg (by decide), if_neg (by decide), if_neg (by decide), if_pos rfl]

theorem fill_shapes {operation candidate : ParticleOperation}
    (fill : (calculation operation).IsFillCandidate candidate) :
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = moveItemToPay ∧ candidate = createHolder) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧ candidate = createHolder) := by
  have fill_eq : (if operation = createItem then some createBox
      else if operation = moveItemToPay then some createHolder
      else if operation = createSecondItem then some moveItemToPay
      else if operation = moveSecondToDeposit then some createHolder
      else none) = some candidate := fill
  by_cases first : operation = createItem
  · rw [if_pos first] at fill_eq
    exact Or.inl ⟨first, (Option.some.inj fill_eq).symm⟩
  · rw [if_neg first] at fill_eq
    by_cases second : operation = moveItemToPay
    · rw [if_pos second] at fill_eq
      exact Or.inr (Or.inl ⟨second, (Option.some.inj fill_eq).symm⟩)
    · rw [if_neg second] at fill_eq
      by_cases third : operation = createSecondItem
      · rw [if_pos third] at fill_eq
        exact Or.inr (Or.inr (Or.inl ⟨third, (Option.some.inj fill_eq).symm⟩))
      · rw [if_neg third] at fill_eq
        by_cases fourth : operation = moveSecondToDeposit
        · rw [if_pos fourth] at fill_eq
          exact Or.inr (Or.inr (Or.inr
            ⟨fourth, (Option.some.inj fill_eq).symm⟩))
        · rw [if_neg fourth] at fill_eq
          exact nomatch fill_eq

theorem in_collection_shapes {operation candidate : ParticleOperation}
    (in_collection : (calculation operation).InCollection candidate) :
    (operation = moveItemToPay ∧
      (candidate = createItem ∨ candidate = createBox ∨
        candidate = createHolder)) ∨
    (operation = moveSecondToDeposit ∧
      (candidate = createSecondItem ∨ candidate = createBox ∨
        candidate = createHolder)) ∨
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) := by
  rcases in_collection with ⟨candidatePosition, source_at⟩ | fill
  · rcases source_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inl ⟨rfl, Or.inl rfl⟩
      · exact Or.inl ⟨rfl, Or.inr (Or.inl rfl)⟩
    · rcases shapes with ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, Or.inl rfl⟩)
      · exact Or.inr (Or.inl ⟨rfl, Or.inr (Or.inl rfl)⟩)
  · rcases fill_shapes fill with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
    · exact Or.inl ⟨rfl, Or.inr (Or.inr rfl)⟩
    · exact Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩))
    · exact Or.inr (Or.inl ⟨rfl, Or.inr (Or.inr rfl)⟩)

theorem related_item_box : OperationsRelated createItem createBox :=
  ⟨itemPosition, boxPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem related_second_box : OperationsRelated createSecondItem createBox :=
  ⟨itemPosition, boxPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem after_comparison_item :
    (calculation moveItemToPay).AfterComparison createItem := by
  refine ⟨Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent newer_related
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · rcases newer_related with
      ⟨newerPosition, olderPosition, operates_newer, operates_older, related⟩
    have newer_is_holder : newerPosition = holderPosition := operates_newer
    have older_is_item : olderPosition = itemPosition := operates_older
    subst newer_is_holder
    subst older_is_item
    exact absurd related
      (by decide : ¬(holderPosition <+: itemPosition ∨
        itemPosition <+: holderPosition))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_holder_first :
    (calculation moveItemToPay).AfterComparison createHolder := by
  refine ⟨Or.inr fill_first_move, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_second_item :
    (calculation moveSecondToDeposit).AfterComparison createSecondItem := by
  refine ⟨Or.inl ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_holder_second :
    (calculation moveSecondToDeposit).AfterComparison createHolder := by
  refine ⟨Or.inr fill_second_move, ?_⟩
  intro newer newer_in newer_recent newer_related
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · rcases newer_related with
      ⟨newerPosition, olderPosition, operates_newer, operates_older, related⟩
    have newer_is_item : newerPosition = itemPosition := operates_newer
    have older_is_holder : olderPosition = holderPosition := operates_older
    subst newer_is_item
    subst older_is_holder
    exact absurd related
      (by decide : ¬(itemPosition <+: holderPosition ∨
        holderPosition <+: itemPosition))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_shapes {operation candidate : ParticleOperation}
    (after_comparison : (calculation operation).AfterComparison candidate) :
    (operation = moveItemToPay ∧
      (candidate = createItem ∨ candidate = createHolder)) ∨
    (operation = moveSecondToDeposit ∧
      (candidate = createSecondItem ∨ candidate = createHolder)) ∨
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) := by
  rcases in_collection_shapes after_comparison.1 with
    ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | shape | shape
  · rcases shapes with rfl | rfl | rfl
    · exact Or.inl ⟨rfl, Or.inl rfl⟩
    · exact (after_comparison.2 createItem
        (Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide : createBox.operationOrder < createItem.operationOrder)
        related_item_box).elim
    · exact Or.inl ⟨rfl, Or.inr rfl⟩
  · rcases shapes with rfl | rfl | rfl
    · exact Or.inr (Or.inl ⟨rfl, Or.inl rfl⟩)
    · exact (after_comparison.2 createSecondItem
        (Or.inl ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide :
          createBox.operationOrder < createSecondItem.operationOrder)
        related_second_box).elim
    · exact Or.inr (Or.inl ⟨rfl, Or.inr rfl⟩)
  · exact Or.inr (Or.inr (Or.inl shape))
  · exact Or.inr (Or.inr (Or.inr shape))

theorem box_no_dependencies (candidate : ParticleOperation) :
    ¬dependency createBox candidate := by
  rintro (⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩) <;>
    exact absurd box_eq (by decide)

theorem item_dependency_is_box {candidate : ParticleOperation}
    (edge : dependency createItem candidate) : candidate = createBox := by
  rcases edge with
    ⟨_, rfl⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩
  · rfl
  all_goals exact absurd item_eq (by decide)

theorem item_no_reach_holder : ¬Reaches dependency createItem createHolder := by
  intro path
  cases path with
  | direct edge =>
      exact absurd (item_dependency_is_box edge) (by decide)
  | step edge rest =>
      rw [item_dependency_is_box edge] at rest
      exact no_reaches_of_no_dependency box_no_dependencies rest

theorem second_item_reaches_holder :
    Reaches dependency createSecondItem createHolder :=
  .step (Or.inr (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))))
    (.direct (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))))

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  constructor
  · rintro (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · exact fill_item
    · exact ⟨⟨after_comparison_item,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal =>
          absurd (Option.some.inj (fill_first_move.symm.trans removal.1))
            (by decide)⟩
    · exact ⟨⟨after_comparison_holder_first,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal => by
          rcases removal with
            ⟨_, src, src_candidate, src_correction, src_ne, src_reaches⟩
          rcases src_candidate with ⟨srcPosition, src_at⟩
          rcases src_at with ⟨_, ⟨rfl, _⟩ | ⟨rfl, _⟩⟩ | ⟨move_eq, _⟩
          · exact item_no_reach_holder src_reaches
          · exact src_correction.1.2 createItem
              (Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
              (by decide :
                createBox.operationOrder < createItem.operationOrder)
              related_item_box
          · exact absurd move_eq (by decide)⟩
    · exact fill_second_item
    · exact ⟨⟨after_comparison_second_item,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal =>
          absurd (Option.some.inj (fill_second_move.symm.trans removal.1))
            (by decide)⟩
  · intro rule_dependency
    rcases operation_kind : operation.kind with target | target | source_target
    · have fill : (calculation operation).IsFillCandidate candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases fill_shapes fill with
        ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact Or.inl ⟨rfl, rfl⟩
      · simp [moveItemToPay] at operation_kind
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩)))
      · simp [moveSecondToDeposit] at operation_kind
    · have after_correction :
            (calculation operation).AfterMoveCorrection dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes after_correction.1 with
        ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · simp [moveItemToPay] at operation_kind
      · simp [moveSecondToDeposit] at operation_kind
      · simp [createItem] at operation_kind
      · simp [createSecondItem] at operation_kind
    · have move_rule :
            (calculation operation).MoveRuleDependency dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes move_rule.1.1 with
        ⟨rfl, rfl | rfl⟩ | ⟨rfl, rfl | rfl⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
      · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩)))
      · exact (move_rule.2 ⟨fill_second_move, createSecondItem,
          ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩,
          ⟨after_comparison_second_item,
            Or.inl (not_move_of_kind_create rfl)⟩,
          (by decide), second_item_reaches_holder⟩).elim
      · simp [createItem] at operation_kind
      · simp [createSecondItem] at operation_kind

def graph : ResolvedDefineGraph where
  isOperation := isOperation
  dependency := dependency
  calculation := calculation
  calculation_operation := fun _ => rfl
  calculation_well_formed := calculation_well_formed
  exact_dependency := exact_dependency
  occupancy := occupancy
  sourceCandidateAt := sourceCandidateAt
  source_candidate_iff := fun _ _ => Iff.rfl
  source_candidate_empty_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl List.prefix_rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl ⟨[0], rfl⟩⟩
    · exact ⟨itemPosition, rfl, Or.inl List.prefix_rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl ⟨[0], rfl⟩⟩
  source_candidate_operated_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨_, rfl, List.prefix_rfl⟩
  non_move_source_candidate_operates_on_position := by
    intro operation candidate candidatePosition candidate_at _
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;> rfl
  source_candidate_is_previous := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createItem.operationOrder < moveItemToPay.operationOrder)
      · exact (by decide :
          createBox.operationOrder < moveItemToPay.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createSecondItem.operationOrder < moveSecondToDeposit.operationOrder)
      · exact (by decide :
          createBox.operationOrder < moveSecondToDeposit.operationOrder)
  source_candidate_operations := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩
  latest_source_candidate := by
    intro operation emptyPosition position previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_item : emptyPosition = itemPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_item
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_box : position = boxPosition := previous_operates
        subst position_is_box
        exact ⟨createBox, Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createItem, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_holder : position = holderPosition := previous_operates
        subst position_is_holder
        exact absurd position_related
          (by decide : ¬(holderPosition <+: itemPosition ∨
            itemPosition <+: holderPosition))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_item : emptyPosition = itemPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_item
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_box : position = boxPosition := previous_operates
        subst position_is_box
        exact ⟨createBox, Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩,
          Or.inr (by decide :
            createItem.operationOrder < createSecondItem.operationOrder)⟩
      · have position_is_holder : position = holderPosition := previous_operates
        subst position_is_holder
        exact absurd position_related
          (by decide : ¬(holderPosition <+: itemPosition ∨
            itemPosition <+: holderPosition))
      · rcases previous_operates with rfl | rfl
        · exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩,
            Or.inr (by decide :
              moveItemToPay.operationOrder < createSecondItem.operationOrder)⟩
        · exact absurd position_related
            (by decide : ¬(payPosition <+: itemPosition ∨
              itemPosition <+: payPosition))
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact ⟨itemPosition, boxPosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact ⟨payPosition, holderPosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact ⟨itemPosition, itemPosition, rfl, Or.inl rfl, List.prefix_rfl⟩
    · exact ⟨depositPosition, holderPosition, rfl, rfl, ⟨[1], rfl⟩⟩
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact (by decide : createBox.operationOrder < createItem.operationOrder)
    · exact (by decide :
        createHolder.operationOrder < moveItemToPay.operationOrder)
    · exact (by decide :
        moveItemToPay.operationOrder < createSecondItem.operationOrder)
    · exact (by decide :
        createHolder.operationOrder < moveSecondToDeposit.operationOrder)
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩

example : dependency moveItemToPay createItem := Or.inr (Or.inl ⟨rfl, rfl⟩)

example : dependency moveItemToPay createHolder :=
  Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))

example : ¬dependency moveSecondToDeposit createHolder := by
  rintro (⟨move_eq, _⟩ | ⟨move_eq, _⟩ | ⟨move_eq, _⟩ | ⟨move_eq, _⟩ |
    ⟨_, candidate_eq⟩)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd candidate_eq (by decide)

example : Acyclic graph.dependency := graph.acyclic

example : TransitivelyMinimal graph.dependency := graph.transitivelyMinimal

end FillDependencyRemoval

end Define.OperationGraph
