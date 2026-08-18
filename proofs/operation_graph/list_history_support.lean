import valid_history

set_option warningAsError true
set_option autoImplicit false

/-!
# Concrete List History Support

This module removes the bookkeeping needed to present a concrete finite list of
Particle Operations as a `ValidResolvedHistory`. Occupancy still follows the
exact operation semantics. Concrete witnesses must prove every operation
precondition; this module supplies only the list indexing, the transition after
the list ends, and a queryable-name relation that accepts every position.

Universal queryability is suitable when a witness has no Moves: only positions
with earlier entries can enter an Empty Collection, so admitting unused names
does not add candidates. Witnesses with Moves should provide a narrower
queryable-name model because a Move writes entries for its queryable transitive
child positions.
-/

namespace Define.OperationGraph

namespace ListHistory

def operationAt : List ParticleOperation → Nat → Option ParticleOperation
  | [], _ => none
  | operation :: _, 0 => some operation
  | _ :: remaining, operationOrder + 1 =>
      operationAt remaining operationOrder

def occupiedBefore (operations : List ParticleOperation) :
    Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operations operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operations operationOrder)
            position
      | none => occupiedBefore operations operationOrder position

def IsOperation (operations : List ParticleOperation)
    (operation : ParticleOperation) : Prop :=
  operation ∈ operations

theorem operationAt_is_member (operations : List ParticleOperation)
    {operationOrder : Nat} {operation : ParticleOperation}
    (operation_at : operationAt operations operationOrder = some operation) :
    IsOperation operations operation := by
  induction operations generalizing operationOrder with
  | nil => simp [operationAt] at operation_at
  | cons first remaining induction_hypothesis =>
      cases operationOrder with
      | zero =>
          have operation_is_first : operation = first :=
            (Option.some.inj operation_at).symm
          subst operation_is_first
          exact List.mem_cons_self
      | succ operationOrder =>
          exact List.mem_cons_of_mem first
            (induction_hypothesis operation_at)

theorem operationAt_none_of_le (operations : List ParticleOperation)
    {firstOrder laterOrder : Nat} (first_le_later : firstOrder ≤ laterOrder)
    (first_none : operationAt operations firstOrder = none) :
    operationAt operations laterOrder = none := by
  induction operations generalizing firstOrder laterOrder with
  | nil => rfl
  | cons first remaining induction_hypothesis =>
      cases firstOrder with
      | zero => simp [operationAt] at first_none
      | succ firstOrder =>
          cases laterOrder with
          | zero => omega
          | succ laterOrder =>
              exact induction_hypothesis
                (Nat.le_of_succ_le_succ first_le_later) first_none

structure Conditions (operations : List ParticleOperation) where
  member_operation_at :
    ∀ operation,
      IsOperation operations operation →
        operationAt operations operation.operationOrder = some operation
  operation_at_has_order :
    ∀ operationOrder operation,
      operationAt operations operationOrder = some operation →
        operation.operationOrder = operationOrder
  empty_position_is_occupied :
    ∀ operation source,
      IsOperation operations operation →
        EmptyPosition operation = some source →
          occupiedBefore operations operation.operationOrder source
  fill_position_is_available :
    ∀ operation target,
      IsOperation operations operation →
        FillPosition operation = some target →
          Available (occupiedBefore operations operation.operationOrder) target
  fill_position_is_empty :
    ∀ operation target,
      IsOperation operations operation →
        FillPosition operation = some target →
          ¬occupiedBefore operations operation.operationOrder target
  move_source_not_parent_of_target :
    ∀ operation source target,
      IsOperation operations operation →
        operation.kind = .move source target →
          ¬ParentOrSame source target
  operated_position_has_action_parent :
    ∀ operation position,
      IsOperation operations operation →
        OperatesOn operation position →
          ParentOrSame operation.actionParent position

structure QueryableConditions (operations : List ParticleOperation)
    (queryableBefore : Nat → Position → Prop) where
  queryable_prefix_closed :
    ∀ operationOrder, PrefixClosed (queryableBefore operationOrder)
  occupied_position_is_queryable :
    ∀ operationOrder position,
      occupiedBefore operations operationOrder position →
        queryableBefore operationOrder position
  operated_position_is_queryable :
    ∀ operation position,
      IsOperation operations operation →
        OperatesOn operation position →
          queryableBefore operation.operationOrder position
  operated_position_remains_queryable :
    ∀ operationOrder operation position,
      IsOperation operations operation →
        operation.operationOrder < operationOrder →
          OperatesOn operation position →
            queryableBefore operationOrder position

def validHistoryWithQueryable (operations : List ParticleOperation)
    (conditions : Conditions operations)
    (queryableBefore : Nat → Position → Prop)
    (queryableConditions : QueryableConditions operations queryableBefore) :
    ValidResolvedHistory (IsOperation operations) where
  operationAt := operationAt operations
  occupiedBefore := occupiedBefore operations
  queryableBefore := queryableBefore
  member_operation_at := conditions.member_operation_at
  operation_at_is_member := by
    intro operationOrder operation operation_at
    exact operationAt_is_member operations operation_at
  operation_at_has_order := conditions.operation_at_has_order
  no_operation_after_none := by
    intro firstOrder laterOrder first_le_later first_none
    exact operationAt_none_of_le operations first_le_later first_none
  initial_prefix_closed := by
    intro parent child parent_of_child child_occupied
    exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
  queryable_prefix_closed := queryableConditions.queryable_prefix_closed
  occupied_position_is_queryable :=
    queryableConditions.occupied_position_is_queryable
  operated_position_is_queryable :=
    queryableConditions.operated_position_is_queryable
  operated_position_remains_queryable :=
    queryableConditions.operated_position_remains_queryable
  empty_position_is_occupied := conditions.empty_position_is_occupied
  fill_position_is_available := conditions.fill_position_is_available
  fill_position_is_empty := conditions.fill_position_is_empty
  move_source_not_parent_of_target :=
    conditions.move_source_not_parent_of_target
  operated_position_has_action_parent :=
    conditions.operated_position_has_action_parent
  operation_transition := by
    intro operationOrder operation operation_at position
    show (match operationAt operations operationOrder with
      | some operation =>
          OccupancyAfter operation
            (occupiedBefore operations operationOrder) position
      | none => occupiedBefore operations operationOrder position) ↔ _
    rw [operation_at]
  no_operation_transition := by
    intro operationOrder no_operation position
    show (match operationAt operations operationOrder with
      | some operation =>
          OccupancyAfter operation
            (occupiedBefore operations operationOrder) position
      | none => occupiedBefore operations operationOrder position) ↔ _
    rw [no_operation]

theorem universally_queryable_conditions (operations : List ParticleOperation) :
    QueryableConditions operations (fun _ _ => True) where
  queryable_prefix_closed := by
    intro operationOrder parent child parent_of_child child_queryable
    trivial
  occupied_position_is_queryable := by
    intro operationOrder position position_occupied
    trivial
  operated_position_is_queryable := by
    intro operation position operation_member operates_on_position
    trivial
  operated_position_remains_queryable := by
    intro operationOrder operation position operation_member operation_before
      operates_on_position
    trivial

def validHistory (operations : List ParticleOperation)
    (conditions : Conditions operations) :
    ValidResolvedHistory (IsOperation operations) :=
  validHistoryWithQueryable operations conditions (fun _ _ => True)
    (universally_queryable_conditions operations)

end ListHistory

end Define.OperationGraph
