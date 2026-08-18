import finite_history_schedule
import unbounded_schedule_order

set_option warningAsError true
set_option autoImplicit false

/-!
# Unbounded Schedules from Valid Resolved Histories

This module constructs a natural-number-indexed schedule from an unbounded
valid resolved history. A finite history prefix may first be permuted, after
which every later Particle Operation retains its history index. The resulting
schedule contains every Particle Operation exactly once.

If the finite permutation respects a subrelation of calculated reachability,
the complete unbounded schedule respects that subrelation. Dependencies within
the suffix retain history order, and a dependency from the permuted prefix to
the suffix would contradict the fact that calculated reachability points to a
smaller history index.
-/

namespace Define.OperationGraph

namespace ValidResolvedHistory

private theorem exists_operationAt_of_unbounded
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (operationOrder : Nat) :
    ∃ operation, history.operationAt operationOrder = some operation := by
  cases operation_at : history.operationAt operationOrder with
  | none => exact False.elim (history_is_unbounded _ operation_at)
  | some operation => exact ⟨operation, rfl⟩

private noncomputable def operationAtOfUnbounded
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (operationOrder : Nat) : ParticleOperation :=
  Classical.choose
    (history.exists_operationAt_of_unbounded history_is_unbounded
      operationOrder)

private theorem operationAt_operationAtOfUnbounded
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (operationOrder : Nat) :
    history.operationAt operationOrder =
      some (history.operationAtOfUnbounded history_is_unbounded operationOrder) :=
  Classical.choose_spec
    (history.exists_operationAt_of_unbounded history_is_unbounded
      operationOrder)

private theorem operationAtOfUnbounded_is_member
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (operationOrder : Nat) :
    isOperation
      (history.operationAtOfUnbounded history_is_unbounded operationOrder) :=
  history.operation_at_is_member operationOrder _
    (history.operationAt_operationAtOfUnbounded history_is_unbounded
      operationOrder)

private theorem operationAtOfUnbounded_has_order
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (operationOrder : Nat) :
    (history.operationAtOfUnbounded history_is_unbounded operationOrder).operationOrder =
      operationOrder :=
  history.operation_at_has_order operationOrder _
    (history.operationAt_operationAtOfUnbounded history_is_unbounded
      operationOrder)

private theorem operationAtOfUnbounded_eq_of_member
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {operation : ParticleOperation}
    (operation_member : isOperation operation) :
    history.operationAtOfUnbounded history_is_unbounded
        operation.operationOrder =
      operation := by
  apply Option.some.inj
  exact
    (history.operationAt_operationAtOfUnbounded history_is_unbounded
        operation.operationOrder).symm.trans
      (history.member_operation_at operation operation_member)

private theorem operationsBefore_length_of_unbounded
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none) :
    ∀ operationCount,
      (history.operationsBefore operationCount).length = operationCount := by
  intro operationCount
  induction operationCount with
  | zero => simp [operationsBefore]
  | succ operationCount induction_hypothesis =>
      cases operation_at : history.operationAt operationCount with
      | none => exact False.elim (history_is_unbounded _ operation_at)
      | some operation =>
          simp [operationsBefore, operation_at, induction_hypothesis]

private theorem candidatePrefix_length
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix) :
    candidatePrefix.length = prefixBound :=
  candidate_permuted.length_eq.symm.trans
    (history.operationsBefore_length_of_unbounded history_is_unbounded
      prefixBound)

private noncomputable def operationAtWithPrefix
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    (candidatePrefix : List ParticleOperation)
    (scheduleOrder : Nat) : ParticleOperation :=
  match candidatePrefix[scheduleOrder]? with
  | some operation => operation
  | none => history.operationAtOfUnbounded history_is_unbounded scheduleOrder

private noncomputable def unboundedScheduleWithPrefix
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} (candidatePrefix : List ParticleOperation)
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix) :
    UnboundedSchedule isOperation where
  occurrenceAt :=
    history.operationAtWithPrefix history_is_unbounded candidatePrefix
  occurrence_is_member := by
    intro scheduleOrder
    cases candidate_at : candidatePrefix[scheduleOrder]? with
    | none =>
        simp [operationAtWithPrefix, candidate_at]
        exact
          history.operationAtOfUnbounded_is_member history_is_unbounded
            scheduleOrder
    | some operation =>
        simp [operationAtWithPrefix, candidate_at]
        have candidate_member : operation ∈ candidatePrefix :=
          List.mem_of_getElem? candidate_at
        exact
          history.operationsBefore_operation_is_member
            (candidate_permuted.mem_iff.mpr candidate_member)
  occurrenceAt_injective := by
    intro firstOrder secondOrder operations_equal
    have candidate_length :=
      history.candidatePrefix_length history_is_unbounded candidate_permuted
    have candidate_nodup : candidatePrefix.Nodup :=
      candidate_permuted.nodup
        (history.operationsBefore_nodup prefixBound)
    cases first_at : candidatePrefix[firstOrder]? with
    | none =>
        have first_after_prefix : prefixBound ≤ firstOrder := by
          have := List.getElem?_eq_none_iff.mp first_at
          omega
        cases second_at : candidatePrefix[secondOrder]? with
        | none =>
            simp only [operationAtWithPrefix, first_at,
              second_at] at operations_equal
            have first_operation_order :=
              history.operationAtOfUnbounded_has_order history_is_unbounded
                firstOrder
            have second_operation_order :=
              history.operationAtOfUnbounded_has_order history_is_unbounded
                secondOrder
            rw [operations_equal] at first_operation_order
            omega
        | some secondOperation =>
            simp only [operationAtWithPrefix, first_at,
              second_at] at operations_equal
            have second_candidate_member :
                secondOperation ∈ candidatePrefix :=
              List.mem_of_getElem? second_at
            have second_reference_member :
                secondOperation ∈ history.operationsBefore prefixBound :=
              candidate_permuted.mem_iff.mpr second_candidate_member
            have second_before_prefix :=
              history.operationsBefore_operationOrder_lt
                second_reference_member
            have first_operation_order :=
              history.operationAtOfUnbounded_has_order history_is_unbounded
                firstOrder
            rw [operations_equal] at first_operation_order
            omega
    | some firstOperation =>
        have first_before_length : firstOrder < candidatePrefix.length :=
          (getElem?_eq_some_iff.mp first_at).choose
        have first_candidate_member : firstOperation ∈ candidatePrefix :=
          List.mem_of_getElem? first_at
        have first_reference_member :
            firstOperation ∈ history.operationsBefore prefixBound :=
          candidate_permuted.mem_iff.mpr first_candidate_member
        have first_before_prefix :=
          history.operationsBefore_operationOrder_lt first_reference_member
        cases second_at : candidatePrefix[secondOrder]? with
        | none =>
            have second_after_prefix : prefixBound ≤ secondOrder := by
              have := List.getElem?_eq_none_iff.mp second_at
              omega
            simp only [operationAtWithPrefix, first_at,
              second_at] at operations_equal
            have second_operation_order :=
              history.operationAtOfUnbounded_has_order history_is_unbounded
                secondOrder
            rw [← operations_equal] at second_operation_order
            omega
        | some secondOperation =>
            simp only [operationAtWithPrefix, first_at,
              second_at] at operations_equal
            apply
              (List.getElem?_inj first_before_length candidate_nodup).mp
            rw [first_at, second_at, operations_equal]
  contains_every_occurrence := by
    intro operation operation_member
    by_cases operation_before_prefix :
        operation.operationOrder < prefixBound
    · have reference_member :
          operation ∈ history.operationsBefore prefixBound :=
        history.operationAt_mem_operationsBefore
          (history.member_operation_at operation operation_member)
          operation_before_prefix
      have candidate_member : operation ∈ candidatePrefix :=
        candidate_permuted.mem_iff.mp reference_member
      rcases List.mem_iff_getElem?.mp candidate_member with
        ⟨scheduleOrder, candidate_at⟩
      exact
        ⟨scheduleOrder,
          by simp [operationAtWithPrefix, candidate_at]⟩
    · have candidate_length :=
        history.candidatePrefix_length history_is_unbounded
          candidate_permuted
      have candidate_at :
          candidatePrefix[operation.operationOrder]? = none :=
        List.getElem?_eq_none (by omega)
      exact
        ⟨operation.operationOrder,
          by
            simp [operationAtWithPrefix, candidate_at,
              history.operationAtOfUnbounded_eq_of_member
                history_is_unbounded operation_member]⟩

private theorem unboundedScheduleWithPrefix_occurrencesBefore_take
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix) :
    ∀ operationCount,
      operationCount ≤ candidatePrefix.length →
        (history.unboundedScheduleWithPrefix history_is_unbounded
              candidatePrefix candidate_permuted).occurrencesBefore
            operationCount =
          candidatePrefix.take operationCount := by
  intro operationCount operation_count_before_length
  induction operationCount with
  | zero => simp [UnboundedSchedule.occurrencesBefore]
  | succ operationCount induction_hypothesis =>
      have operation_before_length :
          operationCount < candidatePrefix.length := by
        omega
      cases candidate_at : candidatePrefix[operationCount]? with
      | none =>
          have operation_after_length :=
            List.getElem?_eq_none_iff.mp candidate_at
          omega
      | some operation =>
          rw [UnboundedSchedule.occurrencesBefore]
          rw [induction_hypothesis (Nat.le_of_lt operation_before_length)]
          rw [List.take_add_one]
          simp [unboundedScheduleWithPrefix, operationAtWithPrefix,
            candidate_at]

private theorem unboundedScheduleWithPrefix_occurrencesBefore
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix) :
    (history.unboundedScheduleWithPrefix history_is_unbounded candidatePrefix
          candidate_permuted).occurrencesBefore prefixBound =
      candidatePrefix := by
  have candidate_length :=
    history.candidatePrefix_length history_is_unbounded candidate_permuted
  calc
    (history.unboundedScheduleWithPrefix history_is_unbounded candidatePrefix
          candidate_permuted).occurrencesBefore prefixBound =
        candidatePrefix.take prefixBound :=
      history.unboundedScheduleWithPrefix_occurrencesBefore_take
        history_is_unbounded candidate_permuted prefixBound
        (by omega)
    _ = candidatePrefix := by rw [← candidate_length]; simp

private theorem unboundedScheduleWithPrefix_respects
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix)
    {weaker : ParticleOperation → ParticleOperation → Prop}
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous →
          Reaches (CalculatedDependency history) following previous)
    (candidate_respects : RespectsPrecedence weaker candidatePrefix) :
    (history.unboundedScheduleWithPrefix history_is_unbounded candidatePrefix
        candidate_permuted).RespectsPrecedence weaker := by
  have candidate_length :=
    history.candidatePrefix_length history_is_unbounded candidate_permuted
  have weaker_irreflexive : ∀ operation, ¬weaker operation operation := by
    intro operation operation_follows_itself
    have order_decreases :=
      reaches_decreases_order
        (calculatedDependency_pointsBackward history)
        (weaker_is_subrelation _ _ operation_follows_itself)
    omega
  intro followingOrder previousOrder following_follows_previous
  change
    weaker
        (history.operationAtWithPrefix history_is_unbounded candidatePrefix
          followingOrder)
        (history.operationAtWithPrefix history_is_unbounded candidatePrefix
          previousOrder) at following_follows_previous
  cases following_at : candidatePrefix[followingOrder]? with
  | none =>
      have following_after_prefix : prefixBound ≤ followingOrder := by
        have := List.getElem?_eq_none_iff.mp following_at
        omega
      cases previous_at : candidatePrefix[previousOrder]? with
      | none =>
          simp only [operationAtWithPrefix, following_at,
            previous_at] at following_follows_previous
          have order_decreases :=
            reaches_decreases_order
              (calculatedDependency_pointsBackward history)
              (weaker_is_subrelation _ _ following_follows_previous)
          have following_operation_order :=
            history.operationAtOfUnbounded_has_order history_is_unbounded
              followingOrder
          have previous_operation_order :=
            history.operationAtOfUnbounded_has_order history_is_unbounded
              previousOrder
          omega
      | some previousOperation =>
          have previous_before_length :
              previousOrder < candidatePrefix.length :=
            (getElem?_eq_some_iff.mp previous_at).choose
          omega
  | some followingOperation =>
      have following_candidate_member :
          followingOperation ∈ candidatePrefix :=
        List.mem_of_getElem? following_at
      have following_reference_member :
          followingOperation ∈ history.operationsBefore prefixBound :=
        candidate_permuted.mem_iff.mpr following_candidate_member
      have following_before_prefix :=
        history.operationsBefore_operationOrder_lt following_reference_member
      cases previous_at : candidatePrefix[previousOrder]? with
      | none =>
          have previous_after_prefix : prefixBound ≤ previousOrder := by
            have := List.getElem?_eq_none_iff.mp previous_at
            omega
          simp only [operationAtWithPrefix, following_at,
            previous_at] at following_follows_previous
          have order_decreases :=
            reaches_decreases_order
              (calculatedDependency_pointsBackward history)
              (weaker_is_subrelation _ _ following_follows_previous)
          have previous_operation_order :=
            history.operationAtOfUnbounded_has_order history_is_unbounded
              previousOrder
          omega
      | some previousOperation =>
          simp only [operationAtWithPrefix, following_at,
            previous_at] at following_follows_previous
          exact
            candidate_respects.index_lt weaker_irreflexive following_at
              previous_at following_follows_previous

/--
Any precedence-respecting permutation of an initial segment of an unbounded
valid resolved history extends to a complete unbounded schedule respecting the
same subrelation of calculated reachability.
-/
theorem exists_unboundedSchedule_with_prefix
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (history_is_unbounded :
      ∀ operationOrder, history.operationAt operationOrder ≠ none)
    {prefixBound : Nat} {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix)
    {weaker : ParticleOperation → ParticleOperation → Prop}
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous →
          Reaches (CalculatedDependency history) following previous)
    (candidate_respects : RespectsPrecedence weaker candidatePrefix) :
    ∃ schedule : UnboundedSchedule isOperation,
      schedule.occurrencesBefore prefixBound = candidatePrefix ∧
        schedule.RespectsPrecedence weaker := by
  let schedule :=
    history.unboundedScheduleWithPrefix history_is_unbounded candidatePrefix
      candidate_permuted
  exact
    ⟨schedule,
      history.unboundedScheduleWithPrefix_occurrencesBefore
        history_is_unbounded candidate_permuted,
      history.unboundedScheduleWithPrefix_respects history_is_unbounded
        candidate_permuted weaker_is_subrelation candidate_respects⟩

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation),
      (∀ operationOrder, history.operationAt operationOrder ≠ none) →
        ∀ (prefixBound : Nat) (candidatePrefix : List ParticleOperation),
          (history.operationsBefore prefixBound).Perm candidatePrefix →
            ∀ (weaker : ParticleOperation → ParticleOperation → Prop),
              (∀ following previous,
                  weaker following previous →
                    Reaches (CalculatedDependency history) following
                      previous) →
                RespectsPrecedence weaker candidatePrefix →
                  ∃ schedule : UnboundedSchedule isOperation,
                    schedule.occurrencesBefore prefixBound = candidatePrefix ∧
                      schedule.RespectsPrecedence weaker :=
  exists_unboundedSchedule_with_prefix

end TypeContracts

end ValidResolvedHistory

end Define.OperationGraph
