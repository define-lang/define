import calculation_correctness
import finite_schedule_order
import finite_scheduling

set_option warningAsError true
set_option autoImplicit false

/-!
# Finite Schedules from Valid Resolved Histories

This module extracts the previous-operation schedule before any natural-number
index of a valid resolved history. The schedule contains exactly the operations
encountered before that index, in their previous-operation order. It is
duplicate-free, respects calculated dependency reachability, and executes from
the history's initial occupancy to its occupancy at the chosen index with the
history's operation observations.

If the history has stopped at that index, the schedule contains every operation
in the history.
-/

namespace Define.OperationGraph

def operationOrderBound : List ParticleOperation → Nat
  | [] => 0
  | operation :: remaining =>
      Nat.max (operation.operationOrder + 1)
        (operationOrderBound remaining)

theorem operationOrder_lt_operationOrderBound
    {schedule : List ParticleOperation} {operation : ParticleOperation}
    (operation_member : operation ∈ schedule) :
    operation.operationOrder < operationOrderBound schedule := by
  induction schedule with
  | nil => simp at operation_member
  | cons firstOperation remaining induction_hypothesis =>
      simp only [List.mem_cons] at operation_member
      rcases operation_member with operation_is_first | operation_in_remaining
      · subst operation
        exact
          Nat.lt_of_lt_of_le (Nat.lt_succ_self firstOperation.operationOrder)
            (Nat.le_max_left _ _)
      · exact
          Nat.lt_of_lt_of_le
            (induction_hypothesis operation_in_remaining)
            (Nat.le_max_right _ _)

namespace ValidResolvedHistory

def operationsBefore {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) : Nat → List ParticleOperation
  | 0 => []
  | operationOrder + 1 =>
      match history.operationAt operationOrder with
      | some operation =>
          history.operationsBefore operationOrder ++ [operation]
      | none => history.operationsBefore operationOrder

def observation {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) : Position → Prop :=
  OperationObservation operation
    (history.occupiedBefore operation.operationOrder)

theorem operationsBefore_operationOrder_lt
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    ∀ {operationCount operation},
      operation ∈ history.operationsBefore operationCount →
        operation.operationOrder < operationCount := by
  intro operationCount
  induction operationCount with
  | zero => simp [operationsBefore]
  | succ operationCount induction_hypothesis =>
      intro operation operation_member
      cases operation_at : history.operationAt operationCount with
      | none =>
          exact
            Nat.lt_trans
              (induction_hypothesis (by
                simpa [operationsBefore, operation_at] using operation_member))
              (Nat.lt_succ_self operationCount)
      | some currentOperation =>
          have current_order :=
            history.operation_at_has_order operationCount currentOperation
              operation_at
          simp only [operationsBefore, operation_at, List.mem_append,
            List.mem_singleton] at operation_member
          rcases operation_member with earlier_member | operation_is_current
          · exact
              Nat.lt_trans (induction_hypothesis earlier_member)
                (Nat.lt_succ_self operationCount)
          · subst operation
            omega

theorem operationsBefore_operation_is_member
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    ∀ {operationCount operation},
      operation ∈ history.operationsBefore operationCount →
        isOperation operation := by
  intro operationCount
  induction operationCount with
  | zero => simp [operationsBefore]
  | succ operationCount induction_hypothesis =>
      intro operation operation_member
      cases operation_at : history.operationAt operationCount with
      | none =>
          exact
            induction_hypothesis (by
              simpa [operationsBefore, operation_at] using operation_member)
      | some currentOperation =>
          simp only [operationsBefore, operation_at, List.mem_append,
            List.mem_singleton] at operation_member
          rcases operation_member with earlier_member | operation_is_current
          · exact induction_hypothesis earlier_member
          · subst operation
            exact
              history.operation_at_is_member operationCount currentOperation
                operation_at

theorem operationAt_mem_operationsBefore
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operationOrder operationCount : Nat} {operation : ParticleOperation}
    (operation_at : history.operationAt operationOrder = some operation)
    (operation_before_count : operationOrder < operationCount) :
    operation ∈ history.operationsBefore operationCount := by
  induction operationCount with
  | zero => omega
  | succ operationCount induction_hypothesis =>
      by_cases operation_before_previous : operationOrder < operationCount
      · have earlier_member :=
          induction_hypothesis operation_before_previous
        cases previous_at : history.operationAt operationCount <;>
          simp [operationsBefore, previous_at, earlier_member]
      · have operation_is_previous : operationOrder = operationCount := by
          omega
        subst operationOrder
        simp [operationsBefore, operation_at]

theorem operationsBefore_nodup
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operationCount : Nat) :
    (history.operationsBefore operationCount).Nodup := by
  induction operationCount with
  | zero => simp [operationsBefore]
  | succ operationCount induction_hypothesis =>
      cases operation_at : history.operationAt operationCount with
      | none => simpa [operationsBefore, operation_at]
      | some currentOperation =>
          have current_order :=
            history.operation_at_has_order operationCount currentOperation
              operation_at
          simp only [operationsBefore, operation_at]
          rw [List.nodup_append]
          refine ⟨induction_hypothesis, by simp, ?_⟩
          intro earlierOperation earlier_member finalOperation final_member
          simp only [List.mem_singleton] at final_member
          subst finalOperation
          intro operations_equal
          subst earlierOperation
          have earlier_order :=
            history.operationsBefore_operationOrder_lt earlier_member
          omega

/--
Every earlier history schedule is a list prefix of every later history
schedule.
-/
theorem operationsBefore_append_of_le
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    ∀ {earlierCount laterCount},
      earlierCount ≤ laterCount →
        ∃ remaining,
          history.operationsBefore laterCount =
            history.operationsBefore earlierCount ++ remaining := by
  intro earlierCount laterCount earlier_le_later
  induction laterCount with
  | zero =>
      have earlier_is_zero : earlierCount = 0 := by omega
      subst earlierCount
      exact ⟨[], by simp⟩
  | succ laterCount induction_hypothesis =>
      by_cases earlier_is_later : earlierCount = laterCount + 1
      · subst earlierCount
        exact ⟨[], by simp⟩
      · have earlier_le_previous : earlierCount ≤ laterCount := by omega
        rcases induction_hypothesis earlier_le_previous with
          ⟨remaining, previous_schedule⟩
        cases operation_at : history.operationAt laterCount with
        | none =>
            exact
              ⟨remaining,
                by
                  simpa [operationsBefore, operation_at] using
                    previous_schedule⟩
        | some operation =>
            exact
              ⟨remaining ++ [operation],
                by
                  simp [operationsBefore, operation_at, previous_schedule,
                    List.append_assoc]⟩

theorem operationsBefore_execution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operationCount : Nat) :
    ScheduleExecution history.observation
      (history.operationsBefore operationCount) (history.occupiedBefore 0)
      (history.occupiedBefore operationCount) := by
  induction operationCount with
  | zero => exact .nil _
  | succ operationCount induction_hypothesis =>
      cases operation_at : history.operationAt operationCount with
      | none =>
          have occupancies_equal :
              history.occupiedBefore (operationCount + 1) =
                history.occupiedBefore operationCount := by
            funext position
            apply propext
            exact history.no_operation_transition operationCount operation_at _
          simp only [operationsBefore, operation_at]
          rw [occupancies_equal]
          exact induction_hypothesis
      | some operation =>
          have operation_member :=
            history.operation_at_is_member operationCount operation operation_at
          have operation_order :=
            history.operation_at_has_order operationCount operation operation_at
          have enabled :
              OperationEnabled operation
                (history.occupiedBefore operationCount) := by
            simpa only [operation_order] using
              history.operation_enabled operation_member
          have observed :
              OperationObservation operation
                  (history.occupiedBefore operationCount) =
                history.observation operation := by
            simp [observation, operation_order]
          have execution_to_transition :=
            induction_hypothesis.snoc enabled observed
          have final_occupancies_equal :
              OccupancyAfter operation
                  (history.occupiedBefore operationCount) =
                history.occupiedBefore (operationCount + 1) := by
            funext position
            apply propext
            exact
              (history.operation_transition operationCount operation operation_at
                position).symm
          simp only [operationsBefore, operation_at]
          rw [← final_occupancies_equal]
          exact execution_to_transition

theorem operationsBefore_respects_calculatedDependency
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operationCount : Nat) :
    RespectsPrecedence (Reaches (CalculatedDependency history))
      (history.operationsBefore operationCount) := by
  induction operationCount with
  | zero => exact .nil
  | succ operationCount induction_hypothesis =>
      cases operation_at : history.operationAt operationCount with
      | none => simpa [operationsBefore, operation_at]
      | some operation =>
          have operation_order :=
            history.operation_at_has_order operationCount operation operation_at
          simp only [operationsBefore, operation_at]
          apply induction_hypothesis.snoc
          intro earlierOperation earlier_member earlier_reaches_operation
          have earlier_order :=
            history.operationsBefore_operationOrder_lt earlier_member
          have operation_before_earlier :=
            reaches_decreases_order
              (calculatedDependency_pointsBackward history)
              earlier_reaches_operation
          omega

/--
A precedence-respecting permutation of one history prefix can be followed by
the later operations to form a respecting permutation of any longer prefix.
-/
theorem exists_respecting_operationsBefore_extension
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {weaker : ParticleOperation → ParticleOperation → Prop}
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous →
          Reaches (CalculatedDependency history) following previous)
    {prefixBound fullBound : Nat}
    (prefix_before_full : prefixBound ≤ fullBound)
    {candidatePrefix : List ParticleOperation}
    (candidate_permuted :
      (history.operationsBefore prefixBound).Perm candidatePrefix)
    (candidate_respects : RespectsPrecedence weaker candidatePrefix) :
    ∃ remaining,
      (history.operationsBefore fullBound).Perm
          (candidatePrefix ++ remaining) ∧
        RespectsPrecedence weaker (candidatePrefix ++ remaining) := by
  rcases history.operationsBefore_append_of_le prefix_before_full with
    ⟨remaining, full_schedule⟩
  have full_nodup_parts :
      (history.operationsBefore prefixBound).Nodup ∧
        remaining.Nodup ∧
          ∀ prefixOperation,
            prefixOperation ∈ history.operationsBefore prefixBound →
              ∀ remainingOperation,
                remainingOperation ∈ remaining →
                  prefixOperation ≠ remainingOperation := by
    have full_nodup := history.operationsBefore_nodup fullBound
    rw [full_schedule] at full_nodup
    exact List.nodup_append.mp full_nodup
  have full_respects_weaker :
      RespectsPrecedence weaker (history.operationsBefore fullBound) :=
    (history.operationsBefore_respects_calculatedDependency fullBound).mono
      weaker_is_subrelation
  have remaining_respects : RespectsPrecedence weaker remaining := by
    rw [full_schedule] at full_respects_weaker
    exact full_respects_weaker.right_of_append
  have candidate_does_not_follow_remaining :
      ∀ prefixOperation,
        prefixOperation ∈ candidatePrefix →
          ∀ remainingOperation,
            remainingOperation ∈ remaining →
              ¬weaker prefixOperation remainingOperation := by
    intro prefixOperation prefix_member remainingOperation remaining_member
    intro prefix_follows_remaining
    have prefix_reference_member :
        prefixOperation ∈ history.operationsBefore prefixBound :=
      candidate_permuted.mem_iff.mpr prefix_member
    have prefix_order_before_bound :=
      history.operationsBefore_operationOrder_lt prefix_reference_member
    have remaining_reference_member :
        remainingOperation ∈ history.operationsBefore fullBound := by
      rw [full_schedule]
      simp [remaining_member]
    have remaining_is_operation :=
      history.operationsBefore_operation_is_member remaining_reference_member
    have remaining_before_prefix :=
      reaches_decreases_order
        (calculatedDependency_pointsBackward history)
        (weaker_is_subrelation _ _ prefix_follows_remaining)
    have remaining_prefix_member :
        remainingOperation ∈ history.operationsBefore prefixBound :=
      history.operationAt_mem_operationsBefore
        (history.member_operation_at remainingOperation remaining_is_operation)
        (Nat.lt_trans remaining_before_prefix prefix_order_before_bound)
    exact
      (full_nodup_parts.2.2 remainingOperation remaining_prefix_member
        remainingOperation remaining_member) rfl
  refine ⟨remaining, ?_, ?_⟩
  · rw [full_schedule]
    exact candidate_permuted.append_right remaining
  · exact
      candidate_respects.append remaining_respects
        candidate_does_not_follow_remaining

theorem operationOrder_lt_of_stopped
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operationCount : Nat}
    (history_stopped : history.operationAt operationCount = none)
    {operation : ParticleOperation}
    (operation_member : isOperation operation) :
    operation.operationOrder < operationCount := by
  apply Nat.lt_of_not_ge
  intro count_before_operation
  have operation_absent :=
    history.no_operation_after_none operationCount operation.operationOrder
      count_before_operation history_stopped
  have operation_present :=
    history.member_operation_at operation operation_member
  rw [operation_present] at operation_absent
  simp at operation_absent

theorem operationsBefore_iff_of_stopped
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operationCount : Nat}
    (history_stopped : history.operationAt operationCount = none)
    {operation : ParticleOperation} :
    operation ∈ history.operationsBefore operationCount ↔
      isOperation operation := by
  constructor
  · exact history.operationsBefore_operation_is_member
  · intro operation_member
    exact
      history.operationAt_mem_operationsBefore
        (history.member_operation_at operation operation_member)
        (history.operationOrder_lt_of_stopped history_stopped operation_member)

end ValidResolvedHistory

end Define.OperationGraph
