import calculated_schedule_execution
import cover_schedule_necessity

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Maximum Safe Concurrency

This aggregate module exposes the two independent components of maximum safe
concurrency. `calculated_schedule_execution` proves that every schedule allowed
by calculated reachability preserves the history's occupancy observations and,
for stopped histories, its final occupancy. `cover_schedule_necessity` proves
that every proper transitive subrelation permits a finite history-prefix
schedule that becomes undefined at an omitted cover pair, and extends that
counterexample to a schedule of every Particle Operation in a stopped history.

The corresponding extension to an unbounded schedule remains to be formalized
in `cover_schedule_necessity`.
-/
