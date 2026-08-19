import comparison_simultaneity_independence_witness
import empty_rule_child_positions_independence_witness
import fill_dependency_removal_independence_witness
import fill_rule_most_recent_independence_witness
import fill_rule_parent_positions_independence_witness
import move_child_entries_independence_witness
import move_correction_independence_witness

set_option warningAsError true
set_option autoImplicit false

/-!
# Independence Witnesses for the Particle Operation Dependency Graph Rules

This module aggregates the clause-specific independence witnesses. Each witness
compares the complete rules with a variant changing exactly one clause and
proves either that the variant misses a required ordering or that it introduces
a redundant dependency.

Every retained witness derives its complete side from a valid resolved history
and the universal calculation. The variant side uses the executable rule model
only to evaluate the single deliberately weakened clause.

There is no independence claim for the Empty Rule's transitive-parent
collection. An earlier proposed witness destroyed a child position that had
never been filled, so it was not a valid resolved history; adding the omitted
child operation also supplies a path to the parent operation.
-/
