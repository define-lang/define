import characterization
import finite_schedule_order
import finite_scheduling

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Maximum Safe Concurrency

This module connects the calculated Particle Operation Dependency Graph to the
occupancy scheduling semantics. The completeness component of the graph
characterization makes two distinct graph-incomparable operations unrelated,
which is exactly the premise required by the adjacent schedule-exchange theorem.

The finite theorem transfers a known reference execution to every
dependency-respecting permutation. Constructing that reference execution from a
stopped valid resolved history, the unbounded-history extension, and necessity
remain to be formalized.
-/

namespace Define.OperationGraph

/--
Two distinct operations from one valid resolved history that are incomparable
in the calculated graph operate on pairwise unrelated positions.
-/
theorem incomparable_calculated_operations_are_unrelated
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {firstOperation secondOperation : ParticleOperation}
    (first_member : isOperation firstOperation)
    (second_member : isOperation secondOperation)
    (operations_distinct : firstOperation ≠ secondOperation)
    (first_does_not_reach_second :
      ¬Reaches (CalculatedDependency history) firstOperation secondOperation)
    (second_does_not_reach_first :
      ¬Reaches (CalculatedDependency history) secondOperation firstOperation) :
    ¬OperationsRelated firstOperation secondOperation := by
  intro operations_related
  rcases Nat.lt_trichotomy firstOperation.operationOrder
      secondOperation.operationOrder with
    first_before_second | same_order | second_before_first
  · exact
      second_does_not_reach_first
        (calculatedDependency_reaches_of_relatedPrevious history second_member
          first_member
          ⟨first_before_second, operationsRelated_symm operations_related⟩)
  · have first_at_order := history.member_operation_at firstOperation first_member
    have second_at_order :=
      history.member_operation_at secondOperation second_member
    rw [same_order] at first_at_order
    exact
      operations_distinct
        (Option.some.inj (first_at_order.symm.trans second_at_order))
  · exact
      first_does_not_reach_second
        (calculatedDependency_reaches_of_relatedPrevious history first_member
          second_member ⟨second_before_first, operations_related⟩)

/--
A sequence of exchanges between operations incomparable in calculated graph
reachability preserves a finite schedule execution.
-/
theorem IncomparableSwapSequence.preserves_calculated_schedule_execution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {firstSchedule secondSchedule : List ParticleOperation}
    {observation : ParticleOperation → Position → Prop}
    {occupiedBefore occupiedAfter : Position → Prop}
    (exchanges :
      IncomparableSwapSequence (Reaches (CalculatedDependency history))
        firstSchedule secondSchedule)
    (all_operations :
      ∀ operation,
        operation ∈ firstSchedule → isOperation operation)
    (first_nodup : firstSchedule.Nodup)
    (execution :
      ScheduleExecution observation firstSchedule occupiedBefore
        occupiedAfter) :
    ScheduleExecution observation secondSchedule occupiedBefore
      occupiedAfter := by
  induction exchanges with
  | refl => exact execution
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      have middle_execution := induction_hypothesis
      have middle_nodup := earlier_exchanges.perm.nodup first_nodup
      cases final_exchange with
      | swap schedulePrefix firstOperation secondOperation scheduleSuffix
          first_does_not_reach_second second_does_not_reach_first =>
          have first_member : isOperation firstOperation := by
            apply all_operations firstOperation
            exact
              earlier_exchanges.perm.mem_iff.mpr
                (by simp)
          have second_member : isOperation secondOperation := by
            apply all_operations secondOperation
            exact
              earlier_exchanges.perm.mem_iff.mpr
                (by simp)
          have adjacent_nodup :
              (firstOperation :: secondOperation :: scheduleSuffix).Nodup :=
            (List.nodup_append.mp middle_nodup).2.1
          have operations_distinct : firstOperation ≠ secondOperation := by
            have first_not_in_remaining :=
              (List.nodup_cons.mp adjacent_nodup).1
            intro operations_equal
            subst secondOperation
            exact first_not_in_remaining (by simp)
          have not_related :=
            incomparable_calculated_operations_are_unrelated history
              first_member second_member operations_distinct
              first_does_not_reach_second second_does_not_reach_first
          exact
            middle_execution.swap_adjacent_unrelated schedulePrefix not_related

/--
Every dependency-respecting permutation of a defined finite schedule of
distinct operations from one valid resolved history is defined with the same
occupancy observations and final occupancy.
-/
theorem finite_respecting_schedule_execution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {referenceSchedule candidateSchedule : List ParticleOperation}
    {observation : ParticleOperation → Position → Prop}
    {occupiedBefore occupiedAfter : Position → Prop}
    (schedules_permuted : referenceSchedule.Perm candidateSchedule)
    (reference_nodup : referenceSchedule.Nodup)
    (all_operations :
      ∀ operation,
        operation ∈ referenceSchedule → isOperation operation)
    (reference_respects :
      RespectsPrecedence (Reaches (CalculatedDependency history))
        referenceSchedule)
    (candidate_respects :
      RespectsPrecedence (Reaches (CalculatedDependency history))
        candidateSchedule)
    (reference_execution :
      ScheduleExecution observation referenceSchedule occupiedBefore
        occupiedAfter) :
    ScheduleExecution observation candidateSchedule occupiedBefore
      occupiedAfter := by
  have exchanges :=
    respecting_permutations_connected schedules_permuted reference_nodup
      reference_respects candidate_respects
  exact
    exchanges.preserves_calculated_schedule_execution history all_operations
      reference_nodup reference_execution

end Define.OperationGraph
