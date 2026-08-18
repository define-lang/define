import occupancy_exchange

set_option warningAsError true
set_option autoImplicit false

/-!
# Finite Particle Operation Schedules

This module defines a finite schedule execution together with the occupancy
observation assigned to each resolved Particle Operation occurrence. It lifts
the local occupancy exchange theorem through an arbitrary finite schedule:
adjacent unrelated operations can exchange places without changing any recorded
observation or the final occupancy.

The order-theoretic argument that connects two schedules through a sequence of
such exchanges is kept separate from this execution semantics.
-/

namespace Define.OperationGraph

/--
A finite list of operations executes from one occupancy to another while each
operation is enabled and has its specified occupancy observation.
-/
inductive ScheduleExecution
    (observation : ParticleOperation → Position → Prop) :
    List ParticleOperation →
      (Position → Prop) → (Position → Prop) → Prop where
  | nil (occupied : Position → Prop) :
      ScheduleExecution observation [] occupied occupied
  | cons {operation : ParticleOperation}
      {remaining : List ParticleOperation}
      {occupiedBefore occupiedAfter : Position → Prop}
      (enabled : OperationEnabled operation occupiedBefore)
      (observed :
        OperationObservation operation occupiedBefore = observation operation)
      (remaining_execution :
        ScheduleExecution observation remaining
          (OccupancyAfter operation occupiedBefore) occupiedAfter) :
      ScheduleExecution observation (operation :: remaining) occupiedBefore
        occupiedAfter

/--
An enabled operation with its specified observation can be appended to a finite
schedule execution.
-/
theorem ScheduleExecution.snoc
    {observation : ParticleOperation → Position → Prop}
    {schedule : List ParticleOperation}
    {occupiedBefore occupiedAtEnd : Position → Prop}
    (execution :
      ScheduleExecution observation schedule occupiedBefore occupiedAtEnd)
    {operation : ParticleOperation}
    (enabled : OperationEnabled operation occupiedAtEnd)
    (observed :
      OperationObservation operation occupiedAtEnd = observation operation) :
    ScheduleExecution observation (schedule ++ [operation]) occupiedBefore
      (OccupancyAfter operation occupiedAtEnd) := by
  induction execution with
  | nil =>
      exact .cons enabled observed (.nil _)
  | cons first_enabled first_observed remaining_execution
      induction_hypothesis =>
      simp only [List.cons_append]
      exact
        .cons first_enabled first_observed
          (induction_hypothesis enabled observed)

/--
Every list prefix of a defined finite schedule is itself defined with the same
observations.
-/
theorem ScheduleExecution.prefix_execution
    {observation : ParticleOperation → Position → Prop}
    {schedulePrefix scheduleSuffix : List ParticleOperation}
    {occupiedBefore occupiedAfter : Position → Prop}
    (execution :
      ScheduleExecution observation (schedulePrefix ++ scheduleSuffix)
        occupiedBefore occupiedAfter) :
    ∃ occupiedAfterPrefix,
      ScheduleExecution observation schedulePrefix occupiedBefore
        occupiedAfterPrefix := by
  induction schedulePrefix generalizing occupiedBefore with
  | nil => exact ⟨occupiedBefore, .nil _⟩
  | cons operation schedulePrefix induction_hypothesis =>
      cases execution with
      | cons enabled observed remaining_execution =>
          rcases induction_hypothesis remaining_execution with
            ⟨occupiedAfterPrefix, prefix_execution⟩
          exact
            ⟨occupiedAfterPrefix,
              .cons enabled observed prefix_execution⟩

/--
A finite execution can be divided at any list prefix, retaining the occupancy
at the division and the executions on both sides.
-/
theorem ScheduleExecution.split
    {observation : ParticleOperation → Position → Prop}
    {schedulePrefix scheduleSuffix : List ParticleOperation}
    {occupiedBefore occupiedAfter : Position → Prop}
    (execution :
      ScheduleExecution observation (schedulePrefix ++ scheduleSuffix)
        occupiedBefore occupiedAfter) :
    ∃ occupiedAfterPrefix,
      ScheduleExecution observation schedulePrefix occupiedBefore
          occupiedAfterPrefix ∧
        ScheduleExecution observation scheduleSuffix occupiedAfterPrefix
          occupiedAfter := by
  induction schedulePrefix generalizing occupiedBefore with
  | nil =>
      exact ⟨occupiedBefore, .nil _, by simpa using execution⟩
  | cons operation schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at execution
      cases execution with
      | cons enabled observed remaining_execution =>
          rcases induction_hypothesis remaining_execution with
            ⟨occupiedAfterPrefix, prefix_execution, suffix_execution⟩
          exact
            ⟨occupiedAfterPrefix, .cons enabled observed prefix_execution,
              suffix_execution⟩

theorem ScheduleExecution.swap_head_unrelated
    {observation : ParticleOperation → Position → Prop}
    {firstOperation secondOperation : ParticleOperation}
    {remaining : List ParticleOperation}
    {occupiedBefore occupiedAfter : Position → Prop}
    (not_related : ¬OperationsRelated firstOperation secondOperation)
    (execution :
      ScheduleExecution observation
        (firstOperation :: secondOperation :: remaining) occupiedBefore
        occupiedAfter) :
    ScheduleExecution observation
      (secondOperation :: firstOperation :: remaining) occupiedBefore
      occupiedAfter := by
  cases execution with
  | cons first_enabled first_observed after_first =>
      cases after_first with
      | cons second_enabled second_observed remaining_execution =>
          have exchange :=
            exchange_unrelated_enabled_operations not_related first_enabled
              second_enabled
          have final_states_equal :
              OccupancyAfter secondOperation
                  (OccupancyAfter firstOperation occupiedBefore) =
                OccupancyAfter firstOperation
                  (OccupancyAfter secondOperation occupiedBefore) := by
            funext position
            apply propext
            exact exchange.final_occupancy_equal position
          have exchanged_remaining_execution :
              ScheduleExecution observation remaining
                (OccupancyAfter firstOperation
                  (OccupancyAfter secondOperation occupiedBefore))
                occupiedAfter := by
            rw [← final_states_equal]
            exact remaining_execution
          exact
            .cons exchange.exchanged_first_enabled
              (exchange.second_observation_preserved.symm.trans
                second_observed)
              (.cons exchange.exchanged_second_enabled
                (exchange.first_observation_preserved.symm.trans
                  first_observed)
                exchanged_remaining_execution)

/--
Adjacent unrelated operations may exchange places after any finite schedule
prefix without changing observations or final occupancy.
-/
theorem ScheduleExecution.swap_adjacent_unrelated
    {observation : ParticleOperation → Position → Prop}
    {firstOperation secondOperation : ParticleOperation}
    {remaining : List ParticleOperation}
    {occupiedBefore occupiedAfter : Position → Prop}
    (schedulePrefix : List ParticleOperation)
    (not_related : ¬OperationsRelated firstOperation secondOperation)
    (execution :
      ScheduleExecution observation
        (schedulePrefix ++ firstOperation :: secondOperation :: remaining)
        occupiedBefore occupiedAfter) :
    ScheduleExecution observation
      (schedulePrefix ++ secondOperation :: firstOperation :: remaining)
      occupiedBefore occupiedAfter := by
  induction schedulePrefix generalizing occupiedBefore with
  | nil =>
      exact execution.swap_head_unrelated not_related
  | cons preceding schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at execution ⊢
      cases execution with
      | cons preceding_enabled preceding_observed remaining_execution =>
          exact
            .cons preceding_enabled preceding_observed
              (induction_hypothesis remaining_execution)

end Define.OperationGraph
