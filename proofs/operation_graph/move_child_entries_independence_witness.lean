import independence_witness_support
import minimality
import moved_child_entry_witness

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## A Move's transitive child entries

`MovedChildEntry.history` is the valid resolved history `create parent`,
`create parent::child`, `move parent first`, `move first second`,
`destroy second::child`.

Under the complete rules, each Move writes an entry for the moved particle's
transitive child position. The final Destroy therefore depends on the second
Move. The universal minimality theorem applies directly to this calculated
dependency graph.

The weakened variant changes only the clause that writes those child entries.
The child's original Create remains the entry under its latest name. The second
Move's positions are unrelated to the child's original name, so the Comparison
retains both the second Move and the Create. The resulting direct dependency on
the Create is redundant because the two-Move dependency chain already reaches
it.
-/

namespace MoveChildEntries

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency MovedChildEntry.history

def weakenedDependencyTarget : ParticleOperation → List ParticleOperation :=
  fun operation =>
    if operation = MovedChildEntry.createChild then
      [MovedChildEntry.createParent]
    else if operation = MovedChildEntry.moveParent then
      [MovedChildEntry.createChild]
    else if operation = MovedChildEntry.moveParentAgain then
      [MovedChildEntry.moveParent]
    else if operation = MovedChildEntry.destroyMovedChild then
      [MovedChildEntry.createChild, MovedChildEntry.moveParentAgain]
    else
      []

abbrev WeakenedDependency
    (operation dependencyOperation : ParticleOperation) : Prop :=
  dependencyOperation ∈ weakenedDependencyTarget operation

def operations : List ParticleOperation :=
  [MovedChildEntry.createParent, MovedChildEntry.createChild,
    MovedChildEntry.moveParent, MovedChildEntry.moveParentAgain,
    MovedChildEntry.destroyMovedChild]

def weakenedRules : RuleVariant :=
  { completeRules with moveChildEntries := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules operations =
      some (graphForDependency operations fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG MovedChildEntry.history).2

theorem complete_destroy_dependency :
    CompleteDependency MovedChildEntry.destroyMovedChild
      MovedChildEntry.moveParentAgain :=
  MovedChildEntry.calculated_dependency

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have destroy_to_second_move :
      WithoutEdge WeakenedDependency MovedChildEntry.destroyMovedChild
        MovedChildEntry.createChild MovedChildEntry.destroyMovedChild
        MovedChildEntry.moveParentAgain := by
    exact ⟨by decide, by decide⟩
  have second_move_to_first_move :
      WithoutEdge WeakenedDependency MovedChildEntry.destroyMovedChild
        MovedChildEntry.createChild MovedChildEntry.moveParentAgain
        MovedChildEntry.moveParent := by
    exact ⟨by decide, by decide⟩
  have first_move_to_create_child :
      WithoutEdge WeakenedDependency MovedChildEntry.destroyMovedChild
        MovedChildEntry.createChild MovedChildEntry.moveParent
        MovedChildEntry.createChild := by
    exact ⟨by decide, by decide⟩
  exact
    minimal MovedChildEntry.destroyMovedChild MovedChildEntry.createChild
      (by decide)
      (.step destroy_to_second_move
        (.step second_move_to_first_move
          (.direct first_move_to_create_child)))

end MoveChildEntries

end IndependenceWitnesses

end Define.OperationGraph
