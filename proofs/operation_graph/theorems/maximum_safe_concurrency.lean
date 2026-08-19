import calculated_cover_graph
import calculated_schedule_execution
import cover_schedule_necessity
import stopped_dependency_edge_count

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
counterexample to a complete schedule for both stopped and unbounded histories.
`calculated_cover_graph` proves that the calculated relation consists exactly
of the cover pairs of its reachability and is the unique inclusion-minimal
relation with that reachability. `stopped_dependency_edge_count` proves that,
for a stopped history, it is also the unique relation with the fewest edges and
that reachability.
-/
