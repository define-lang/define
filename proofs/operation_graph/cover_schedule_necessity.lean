import calculated_schedule_execution
import cover_schedule_order
import occupancy_noncommutation

set_option warningAsError true
set_option autoImplicit false

/-!
# Cover-Pair Schedule Necessity

This module combines the cover-pair schedule construction with Particle
Operation occupancy semantics. Every calculated cover pair has a defined
adjacent execution whose reverse is not enabled. Consequently, every proper
transitive subrelation of calculated reachability permits a finite
history-prefix schedule that becomes undefined at a reversed cover pair.

Extending that finite counterexample to a full stopped or unbounded schedule is
the remaining formalization boundary.
-/

namespace Define.OperationGraph

/--
Every calculated cover pair occurs adjacently in a defined finite execution of
the history prefix ending with the later operation.
-/
theorem calculated_coverPair_has_adjacent_finite_execution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {following previous : ParticleOperation}
    (cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) following previous) :
    ∃ preceding remaining,
      ScheduleExecution history.observation
        (preceding ++ previous :: following :: remaining)
        (history.occupiedBefore 0)
        (history.occupiedBefore (following.operationOrder + 1)) := by
  rcases
      calculated_coverPair_has_adjacent_respecting_historyPrefix history
        cover_pair with
    ⟨preceding, remaining, schedules_permuted, candidate_respects⟩
  refine ⟨preceding, remaining, ?_⟩
  apply
    finite_respecting_schedule_execution history schedules_permuted
      (history.operationsBefore_nodup (following.operationOrder + 1))
  · exact fun _ operation_member =>
      history.operationsBefore_operation_is_member operation_member
  · exact
      history.operationsBefore_respects_calculatedDependency
        (following.operationOrder + 1)
  · exact candidate_respects
  · exact history.operationsBefore_execution (following.operationOrder + 1)

/--
If a defined execution has a calculated cover pair immediately after a finite
prefix, the two operations cannot execute in the reverse order from the
occupancy after that prefix.
-/
theorem calculated_coverPair_reverse_not_enabled
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {following previous : ParticleOperation}
    (cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) following previous)
    {preceding remaining : List ParticleOperation}
    {occupiedBeforePair occupiedAfter : Position → Prop}
    (preceding_execution :
      ScheduleExecution history.observation preceding
        (history.occupiedBefore 0) occupiedBeforePair)
    (pair_execution :
      ScheduleExecution history.observation
        (previous :: following :: remaining) occupiedBeforePair occupiedAfter) :
    ¬(OperationEnabled following occupiedBeforePair ∧
      OperationEnabled previous
        (OccupancyAfter following occupiedBeforePair)) := by
  have prefix_closed : PrefixClosed occupiedBeforePair :=
    preceding_execution.preserves_prefixClosure history.initial_prefix_closed
  cases pair_execution with
  | cons previous_enabled previous_observed following_execution =>
      cases following_execution with
      | cons following_enabled following_observed remaining_execution =>
          have operations_related : OperationsRelated previous following :=
            operationsRelated_symm
              (calculated_coverPair_is_relatedPrevious history cover_pair).2.2.2
          exact
            related_enabled_operations_not_reversible prefix_closed
              previous_enabled following_enabled operations_related

/--
Every calculated cover pair occurs adjacently in a defined finite execution,
but both operations cannot execute in the reverse order from the occupancy
before that pair.
-/
theorem calculated_coverPair_has_irreversible_adjacent_finite_execution
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {following previous : ParticleOperation}
    (cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) following previous) :
    ∃ preceding remaining occupiedBeforePair,
      ScheduleExecution history.observation preceding
          (history.occupiedBefore 0) occupiedBeforePair ∧
        ScheduleExecution history.observation
            (previous :: following :: remaining) occupiedBeforePair
            (history.occupiedBefore (following.operationOrder + 1)) ∧
          ¬(OperationEnabled following occupiedBeforePair ∧
            OperationEnabled previous
              (OccupancyAfter following occupiedBeforePair)) := by
  rcases
      calculated_coverPair_has_adjacent_finite_execution history cover_pair with
    ⟨preceding, remaining, execution⟩
  rcases
      ScheduleExecution.split (schedulePrefix := preceding)
        (scheduleSuffix := previous :: following :: remaining) execution with
    ⟨occupiedBeforePair, preceding_execution, pair_execution⟩
  exact
    ⟨preceding, remaining, occupiedBeforePair, preceding_execution,
      pair_execution,
      calculated_coverPair_reverse_not_enabled history cover_pair
        preceding_execution pair_execution⟩

/--
Every proper transitive subrelation of calculated reachability permits a finite
schedule of exactly one history prefix that becomes undefined at a reversed
cover pair.
-/
theorem proper_transitive_subrelation_allows_undefined_historyPrefix
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {weaker : ParticleOperation → ParticleOperation → Prop}
    (weaker_transitive :
      ∀ {following intermediate previous},
        weaker following intermediate →
          weaker intermediate previous → weaker following previous)
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous →
          Reaches (CalculatedDependency history) following previous)
    (subrelation_is_proper :
      ∃ following previous,
        Reaches (CalculatedDependency history) following previous ∧
          ¬weaker following previous) :
    ∃ following previous preceding remaining occupiedBeforePair,
      CoverPair (Reaches (CalculatedDependency history)) following previous ∧
        ¬weaker following previous ∧
          (history.operationsBefore (following.operationOrder + 1)).Perm
            (preceding ++ following :: previous :: remaining) ∧
            RespectsPrecedence weaker
                (preceding ++ following :: previous :: remaining) ∧
              ScheduleExecution history.observation preceding
                  (history.occupiedBefore 0) occupiedBeforePair ∧
                ¬(OperationEnabled following occupiedBeforePair ∧
                  OperationEnabled previous
                    (OccupancyAfter following occupiedBeforePair)) := by
  rcases
      calculated_proper_subrelation_has_reversed_cover_schedule history
        (weaker := weaker) weaker_transitive weaker_is_subrelation
        subrelation_is_proper with
    ⟨following, previous, preceding, remaining, cover_pair, pair_omitted,
      original_permuted, original_respects, reversed_respects⟩
  have original_execution :
      ScheduleExecution history.observation
        (preceding ++ previous :: following :: remaining)
        (history.occupiedBefore 0)
        (history.occupiedBefore (following.operationOrder + 1)) := by
    apply
      finite_respecting_schedule_execution history original_permuted
        (history.operationsBefore_nodup (following.operationOrder + 1))
    · exact fun _ operation_member =>
        history.operationsBefore_operation_is_member operation_member
    · exact
        history.operationsBefore_respects_calculatedDependency
          (following.operationOrder + 1)
    · exact original_respects
    · exact
        history.operationsBefore_execution (following.operationOrder + 1)
  rcases
      ScheduleExecution.split (schedulePrefix := preceding)
        (scheduleSuffix := previous :: following :: remaining)
        original_execution with
    ⟨occupiedBeforePair, preceding_execution, pair_execution⟩
  have reversed_permuted :
      (history.operationsBefore (following.operationOrder + 1)).Perm
        (preceding ++ following :: previous :: remaining) :=
    original_permuted.trans
      ((List.Perm.swap following previous remaining).append_left preceding)
  exact
    ⟨following, previous, preceding, remaining, occupiedBeforePair,
      cover_pair, pair_omitted, reversed_permuted, reversed_respects,
      preceding_execution,
      calculated_coverPair_reverse_not_enabled history cover_pair
        preceding_execution pair_execution⟩

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (following previous : ParticleOperation),
      CoverPair (Reaches (CalculatedDependency history)) following previous →
        ∃ preceding remaining,
          ScheduleExecution history.observation
            (preceding ++ previous :: following :: remaining)
            (history.occupiedBefore 0)
            (history.occupiedBefore (following.operationOrder + 1)) :=
  calculated_coverPair_has_adjacent_finite_execution

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (following previous : ParticleOperation),
      CoverPair (Reaches (CalculatedDependency history)) following previous →
        ∃ preceding remaining occupiedBeforePair,
          ScheduleExecution history.observation preceding
              (history.occupiedBefore 0) occupiedBeforePair ∧
            ScheduleExecution history.observation
                (previous :: following :: remaining) occupiedBeforePair
                (history.occupiedBefore (following.operationOrder + 1)) ∧
              ¬(OperationEnabled following occupiedBeforePair ∧
                OperationEnabled previous
                  (OccupancyAfter following occupiedBeforePair)) :=
  calculated_coverPair_has_irreversible_adjacent_finite_execution

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (following previous : ParticleOperation),
      CoverPair (Reaches (CalculatedDependency history)) following previous →
        ∀ (preceding remaining : List ParticleOperation)
          (occupiedBeforePair occupiedAfter : Position → Prop),
          ScheduleExecution history.observation preceding
              (history.occupiedBefore 0) occupiedBeforePair →
            ScheduleExecution history.observation
                (previous :: following :: remaining) occupiedBeforePair
                occupiedAfter →
              ¬(OperationEnabled following occupiedBeforePair ∧
                OperationEnabled previous
                  (OccupancyAfter following occupiedBeforePair)) :=
  calculated_coverPair_reverse_not_enabled

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (weaker : ParticleOperation → ParticleOperation → Prop),
      (∀ {following intermediate previous},
          weaker following intermediate →
            weaker intermediate previous → weaker following previous) →
        (∀ following previous,
            weaker following previous →
              Reaches (CalculatedDependency history) following previous) →
          (∃ following previous,
              Reaches (CalculatedDependency history) following previous ∧
                ¬weaker following previous) →
            ∃ following previous preceding remaining occupiedBeforePair,
              CoverPair (Reaches (CalculatedDependency history)) following
                    previous ∧
                ¬weaker following previous ∧
                  (history.operationsBefore
                      (following.operationOrder + 1)).Perm
                    (preceding ++ following :: previous :: remaining) ∧
                    RespectsPrecedence weaker
                        (preceding ++ following :: previous :: remaining) ∧
                      ScheduleExecution history.observation preceding
                          (history.occupiedBefore 0) occupiedBeforePair ∧
                        ¬(OperationEnabled following occupiedBeforePair ∧
                          OperationEnabled previous
                            (OccupancyAfter following occupiedBeforePair)) :=
  proper_transitive_subrelation_allows_undefined_historyPrefix

end TypeContracts

end Define.OperationGraph
