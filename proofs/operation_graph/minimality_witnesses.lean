import fill_dependency_removal_witness
import moved_child_entry_witness
import non_vacuity_witness
import vanished_child_name_witness

set_option warningAsError true
set_option autoImplicit false

/-!
# Operation Graph Minimality Witnesses

This aggregate imports the concrete models that support the universal proof
chain without supplying premises to its principal theorems.

`NonVacuity` applies the actual calculation to the Create-and-Destroy history
matching the create_and_destroy_of_an_implied_position integration test.

`VanishedChildName` demonstrates `latest_source_candidate` at a position name
that no longer refers to a position: an operation on the child position of a
destroyed and replaced parent particle is a keyed candidate that the Comparison
always excludes.

`MovedChildEntry` demonstrates a Move selected as the most-recent entry for a
moved particle's transitive child position, and a Move surviving the Move
Correction as a final dependency.

`FillDependencyRemoval` demonstrates the Move Rule: one Move keeps both an
Empty Dependency and an unrelated Fill Dependency as a two-dependency
reachability antichain, and a later Move's Fill Dependency is removed because a
remaining Empty Dependency reaches it. This is the redundancy family covered by
the move_excludes_create_fill_dependency_reached_through_source_dependency
integration test.
-/
