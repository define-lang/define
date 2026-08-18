import fill_dependency_removal_witness
import independence_witness_support
import minimality

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Move Rule's Fill Dependency removal

`FillDependencyRemoval.history` is the valid resolved history `create box`,
`create box::item`, `create holder`, `move box::item holder::pay`,
`create box::item` again, and `move box::item holder::deposit`.

Under the complete rules, the universal calculation removes the final Move's
Fill Dependency on the holder Create because its dependency on the second item
Create already reaches the holder Create. The universal minimality theorem
applies directly to this calculated dependency graph.

The weakened variant changes only Fill Dependency removal. The final Move
retains a direct dependency on the holder Create even though its dependency on
the second item Create already reaches the holder Create through the first
Move.
-/

namespace FillDependencyRemoval

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency Define.OperationGraph.FillDependencyRemoval.history

def operations : List ParticleOperation :=
  [Define.OperationGraph.FillDependencyRemoval.createBox,
    Define.OperationGraph.FillDependencyRemoval.createItem,
    Define.OperationGraph.FillDependencyRemoval.createHolder,
    Define.OperationGraph.FillDependencyRemoval.moveItemToPay,
    Define.OperationGraph.FillDependencyRemoval.createSecondItem,
    Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit]

def weakenedDependencyTarget : ParticleOperation → List ParticleOperation :=
  fun operation =>
    if operation = Define.OperationGraph.FillDependencyRemoval.createItem then
      [Define.OperationGraph.FillDependencyRemoval.createBox]
    else if operation =
        Define.OperationGraph.FillDependencyRemoval.moveItemToPay then
      [Define.OperationGraph.FillDependencyRemoval.createItem,
        Define.OperationGraph.FillDependencyRemoval.createHolder]
    else if operation =
        Define.OperationGraph.FillDependencyRemoval.createSecondItem then
      [Define.OperationGraph.FillDependencyRemoval.moveItemToPay]
    else if operation =
        Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit then
      [Define.OperationGraph.FillDependencyRemoval.createSecondItem,
        Define.OperationGraph.FillDependencyRemoval.createHolder]
    else
      []

abbrev WeakenedDependency
    (operation dependencyOperation : ParticleOperation) : Prop :=
  dependencyOperation ∈ weakenedDependencyTarget operation

def weakenedRules : RuleVariant :=
  { completeRules with fillDependencyRemoval := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules operations =
      some (graphForDependency operations fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG
    Define.OperationGraph.FillDependencyRemoval.history).2

theorem complete_final_dependency :
    CompleteDependency
      Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
      Define.OperationGraph.FillDependencyRemoval.createSecondItem :=
  Define.OperationGraph.FillDependencyRemoval.calculated_second_move_item

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have final_move_to_second_item :
      WithoutEdge WeakenedDependency
        Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
        Define.OperationGraph.FillDependencyRemoval.createHolder
        Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
        Define.OperationGraph.FillDependencyRemoval.createSecondItem := by
    exact ⟨by decide, by decide⟩
  have second_item_to_first_move :
      WithoutEdge WeakenedDependency
        Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
        Define.OperationGraph.FillDependencyRemoval.createHolder
        Define.OperationGraph.FillDependencyRemoval.createSecondItem
        Define.OperationGraph.FillDependencyRemoval.moveItemToPay := by
    exact ⟨by decide, by decide⟩
  have first_move_to_holder :
      WithoutEdge WeakenedDependency
        Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
        Define.OperationGraph.FillDependencyRemoval.createHolder
        Define.OperationGraph.FillDependencyRemoval.moveItemToPay
        Define.OperationGraph.FillDependencyRemoval.createHolder := by
    exact ⟨by decide, by decide⟩
  exact
    minimal Define.OperationGraph.FillDependencyRemoval.moveSecondToDeposit
      Define.OperationGraph.FillDependencyRemoval.createHolder (by decide)
      (.step final_move_to_second_item
        (.step second_item_to_first_move (.direct first_move_to_holder)))

end FillDependencyRemoval

end IndependenceWitnesses

end Define.OperationGraph
