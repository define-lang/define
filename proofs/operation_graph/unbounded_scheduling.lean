import finite_scheduling
import unbounded_schedule_order

set_option warningAsError true
set_option autoImplicit false

/-!
# Unbounded Particle Operation Schedules

An unbounded Particle Operation schedule executes when each of its finite
prefixes has a finite schedule execution from the common initial occupancy.
Each such execution records the history observation of every operation in the
prefix. There is deliberately no final occupancy for the unbounded schedule.
-/

namespace Define.OperationGraph

def UnboundedScheduleExecution {isOperation : ParticleOperation → Prop}
    (observation : ParticleOperation → Position → Prop)
    (schedule : UnboundedSchedule isOperation)
    (initiallyOccupied : Position → Prop) : Prop :=
  ∀ operationCount,
    ∃ occupiedAfter,
      ScheduleExecution observation
        (schedule.occurrencesBefore operationCount) initiallyOccupied
        occupiedAfter

end Define.OperationGraph
