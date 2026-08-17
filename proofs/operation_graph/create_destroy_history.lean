import valid_history

set_option warningAsError true
set_option autoImplicit false

/-!
# Concrete Create and Destroy History

This module gives a concrete valid resolved history containing a Create followed
by a Destroy of the same position. It establishes that the shared history
conditions are jointly satisfiable without assuming any operation graph
property.
-/

namespace Define.OperationGraph

namespace CreateDestroyHistory

def actionParent : Position := []

def target : Position := [0]

def createOperation : ParticleOperation where
  operationOrder := 0
  actionParent := actionParent
  kind := .create target

def destroyOperation : ParticleOperation where
  operationOrder := 1
  actionParent := actionParent
  kind := .destroy target

def IsOperation (operation : ParticleOperation) : Prop :=
  operation = createOperation ∨ operation = destroyOperation

def operationAt : Nat → Option ParticleOperation
  | 0 => some createOperation
  | 1 => some destroyOperation
  | _ => none

def occupiedBefore (operationOrder : Nat) (position : Position) : Prop :=
  position = actionParent ∨ (operationOrder = 1 ∧ position = target)

def queryableBefore (_operationOrder : Nat) (position : Position) : Prop :=
  position = actionParent ∨ position = target

def history : ValidResolvedHistory IsOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  queryableBefore := queryableBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      rfl
    · subst operation_is_destroy
      rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        exact Or.inl operation_at.symm
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            exact Or.inr operation_at.symm
        | succ operationOrder =>
            simp [operationAt] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        subst operation
        rfl
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            subst operation
            rfl
        | succ operationOrder =>
            simp [operationAt] at operation_at
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    cases laterOrder with
    | zero =>
        have first_is_zero : firstOrder = 0 := by omega
        subst first_is_zero
        simp [operationAt] at first_none
    | succ laterOrder =>
        cases laterOrder with
        | zero =>
            have first_is_zero_or_one : firstOrder = 0 ∨ firstOrder = 1 := by
              omega
            rcases first_is_zero_or_one with first_is_zero | first_is_one
            · subst first_is_zero
              simp [operationAt] at first_none
            · subst first_is_one
              simp [operationAt] at first_none
        | succ laterOrder =>
            rfl
  initial_prefix_closed := by
    intro parent child parent_of_child child_occupied
    have child_is_action_parent : child = actionParent := by
      simpa [occupiedBefore] using child_occupied
    subst child
    have parent_is_action_parent : parent = actionParent := by
      simpa [actionParent, ParentOrSame] using
        List.eq_nil_of_prefix_nil parent_of_child
    exact Or.inl parent_is_action_parent
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    rcases child_queryable with child_is_action_parent | child_is_target
    · subst child
      exact Or.inl (List.eq_nil_of_prefix_nil parent_of_child)
    · subst child
      have parent_shape : parent = [] ∨ parent = target := by
        simpa [ParentOrSame, target, List.prefix_cons_iff] using parent_of_child
      exact parent_shape.imp (fun parent_is_empty => by
        simpa [actionParent] using parent_is_empty) id
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    rcases position_occupied with position_is_action_parent | ⟨_, position_is_target⟩
    · exact Or.inl position_is_action_parent
    · exact Or.inr position_is_target
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      have position_is_target : position = target := by
        simpa [createOperation, OperatesOn] using operates_on_position
      exact Or.inr position_is_target
    · subst operation_is_destroy
      have position_is_target : position = target := by
        simpa [destroyOperation, OperatesOn] using operates_on_position
      exact Or.inr position_is_target
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      have position_is_target : position = target := by
        simpa [createOperation, OperatesOn] using operates_on_position
      exact Or.inr position_is_target
    · subst operation_is_destroy
      have position_is_target : position = target := by
        simpa [destroyOperation, OperatesOn] using operates_on_position
      exact Or.inr position_is_target
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      simp [createOperation, EmptyPosition] at empty_position
    · subst operation_is_destroy
      simp [destroyOperation, EmptyPosition] at empty_position
      exact Or.inr ⟨rfl, empty_position.symm⟩
  fill_position_is_available := by
    intro operation filledPosition operation_member fill_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      have filled_position_is_target : filledPosition = target := by
        simpa [createOperation, FillPosition] using fill_position.symm
      subst filledPosition
      intro parent parent_of_target parent_is_not_target
      have parent_shape : parent = [] ∨ parent = target := by
        simpa [ParentOrSame, target, List.prefix_cons_iff] using parent_of_target
      rcases parent_shape with parent_is_action_parent | parent_is_target
      · exact Or.inl (by simpa [actionParent] using parent_is_action_parent)
      · exact False.elim (parent_is_not_target parent_is_target)
    · subst operation_is_destroy
      simp [destroyOperation, FillPosition] at fill_position
  fill_position_is_empty := by
    intro operation filledPosition operation_member fill_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      have filled_position_is_target : filledPosition = target := by
        simpa [createOperation, FillPosition] using fill_position.symm
      subst filledPosition
      simp [occupiedBefore, createOperation, actionParent, target]
    · subst operation_is_destroy
      simp [destroyOperation, FillPosition] at fill_position
  move_source_not_parent_of_target := by
    intro operation source moveTarget operation_member operation_kind
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      simp [createOperation] at operation_kind
    · subst operation_is_destroy
      simp [destroyOperation] at operation_kind
  operated_position_has_action_parent := by
    intro operation position operation_member operates_on_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      exact List.nil_prefix
    · subst operation_is_destroy
      exact List.nil_prefix
  operation_transition := by
    intro operationOrder operation operation_at position
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        subst operation
        simp [occupiedBefore, OccupancyAfter, createOperation, actionParent,
          target, or_comm]
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            subst operation
            simp [occupiedBefore, OccupancyAfter, destroyOperation, actionParent,
              target, ParentOrSame]
            constructor
            · intro position_is_action_parent
              subst position_is_action_parent
              simp
            · rintro ⟨_, position_is_action_parent | position_is_target⟩
              · exact position_is_action_parent
              · subst position_is_target
                simp_all
        | succ operationOrder =>
            simp [operationAt] at operation_at
  no_operation_transition := by
    intro operationOrder no_operation position
    cases operationOrder with
    | zero =>
        simp [operationAt] at no_operation
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at no_operation
        | succ operationOrder =>
            simp [occupiedBefore]

theorem operation_member : IsOperation createOperation :=
  Or.inl rfl

theorem destroy_operation_member : IsOperation destroyOperation :=
  Or.inr rfl

end CreateDestroyHistory

end Define.OperationGraph
