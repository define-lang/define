import comparison_simultaneity_independence_witness
import definitions
import empty_rule_child_positions_independence_witness
import fill_dependency_removal_witness
import fill_rule_most_recent_independence_witness
import fill_rule_parent_positions_independence_witness
import independence_witness_support
import minimality
import move_child_entries_independence_witness

set_option warningAsError true
set_option autoImplicit false

/-!
# Independence Witnesses for the Particle Operation Dependency Graph Rules

This module aggregates the clause-specific independence witnesses and contains
the witnesses that have not yet been extracted during the calculation
migration. Each witness compares the complete rules with a variant changing
exactly one clause.

- A *missing required ordering* is a pair of operations related by
  `RelatedPrevious` for which the weakened graph has no dependency path.
- A *redundant dependency* is a direct edge whose removal leaves reachability
  unchanged, exhibited by a path that avoids the edge.

The extracted Fill Rule parent-position and most-recent witnesses, Empty Rule
child-position witness, Move child-entry witness, and Comparison simultaneity
witness use the universal calculation for their complete side. The Fill
Dependency removal section below does the same by reusing its fully resolved
witness. The remaining sections still use the executable support model for both
sides and are migrated in subsequent increments.

This proof makes no independence claim for the Empty Rule's transitive-parent
collection. An earlier proposed witness destroyed a child position that had
never been filled, so it was not a valid resolved history; adding the omitted
child operation also supplies a path to the parent operation.
-/

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Move Correction

History: `create box`, `create box::origin`, `move box::origin holder_a`,
`move holder_a box::middle`, `move box::middle box::target`,
`move box::target holder_c`, `destroy box`. This is the history of
`test_destroy_excludes_earlier_child_move_reached_through_later_child_move`.

Complete Empty Rule at the box Destroy: after the Comparison, the remaining
candidates are the final Move (entry for `box::target`) and the first Move
(entry for `box::origin`, whose positions are unrelated to the final Move's
positions). The first Move is a Move Particle Statement that the final Move
depends on through the chain, so the Move Correction removes it and the
Destroy depends exactly on the final Move.

Weakened rule (no Move Correction): the Destroy keeps a second dependency on
the first Move. That edge is redundant: the final Move's chain already
reaches the first Move.
-/

namespace MoveCorrection

def boxPosition : Position := [0]

def originPosition : Position := [0, 0]

def middlePosition : Position := [0, 1]

def targetPosition : Position := [0, 2]

def holderAPosition : Position := [1]

def holderCPosition : Position := [2]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createOrigin : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create originPosition

def moveOriginToHolderA : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move originPosition holderAPosition

def moveHolderAToMiddle : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move holderAPosition middlePosition

def moveMiddleToTarget : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .move middlePosition targetPosition

def moveTargetToHolderC : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move targetPosition holderCPosition

def destroyBox : ParticleOperation where
  operationOrder := 6
  actionParent := []
  kind := .destroy boxPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createOrigin then some createBox
    else if operation = moveOriginToHolderA then some createOrigin
    else if operation = moveHolderAToMiddle then some moveOriginToHolderA
    else if operation = moveMiddleToTarget then some moveHolderAToMiddle
    else if operation = moveTargetToHolderC then some moveMiddleToTarget
    else if operation = destroyBox then some moveTargetToHolderC
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = destroyBox ∧ dependencyOperation = moveOriginToHolderA)

def history : List ParticleOperation :=
  [createBox, createOrigin, moveOriginToHolderA, moveHolderAToMiddle,
    moveMiddleToTarget, moveTargetToHolderC, destroyBox]

def weakenedRules : RuleVariant :=
  { completeRules with moveCorrection := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        destroyBox moveTargetToHolderC :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveTargetToHolderC moveMiddleToTarget :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveMiddleToTarget moveHolderAToMiddle :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_3 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveHolderAToMiddle moveOriginToHolderA :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal destroyBox moveOriginToHolderA (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.step edge_1 (.step edge_2 (.direct edge_3))))

end MoveCorrection

/-!
## The Move Rule's Fill Dependency removal

History: `create box`, `create box::item`, `create holder`,
`move box::item holder::pay`, `create box::item` again,
`move box::item holder::deposit`. This is the history of
`test_move_excludes_create_fill_dependency_reached_through_source_dependency`.

Complete Move Rule at the final Move: the Empty Dependencies leave the
second item Create; the Fill Dependency for `holder::deposit` is the holder
Create. Their positions are unrelated, so the Comparison keeps both, and
neither is a Move, so the Move Correction keeps both. The second item Create
depends on the holder Create through the first Move, so the Move Rule removes
the Fill Dependency and the final Move depends exactly on the second item
Create.

Weakened rule (no Fill Dependency removal): the final Move keeps a second
dependency on the holder Create. That edge is redundant: the second item
Create's chain already reaches the holder Create.
-/

namespace FillDependencyRemoval

def boxPosition : Position := [0]

def itemPosition : Position := [0, 0]

def holderPosition : Position := [1]

def payPosition : Position := [1, 0]

def depositPosition : Position := [1, 1]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createItem : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create itemPosition

def createHolder : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .create holderPosition

def moveItemToPay : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move itemPosition payPosition

def createSecondItem : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .create itemPosition

def moveSecondToDeposit : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move itemPosition depositPosition

abbrev ExpectedCompleteDependency
    (operation dependencyOperation : ParticleOperation) :
    Prop :=
  (operation = createItem ∧ dependencyOperation = createBox) ∨
    (operation = moveItemToPay ∧ dependencyOperation = createItem) ∨
    (operation = moveItemToPay ∧ dependencyOperation = createHolder) ∨
    (operation = createSecondItem ∧ dependencyOperation = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧
      dependencyOperation = createSecondItem)

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
  Prop :=
  ExpectedCompleteDependency operation dependencyOperation ∨
    (operation = moveSecondToDeposit ∧ dependencyOperation = createHolder)

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  Define.OperationGraph.FillDependencyRemoval.dependency

def history : List ParticleOperation :=
  [createBox, createItem, createHolder, moveItemToPay, createSecondItem,
    moveSecondToDeposit]

def weakenedRules : RuleVariant :=
  { completeRules with fillDependencyRemoval := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency := by
  exact Define.OperationGraph.FillDependencyRemoval.graph.transitivelyMinimal

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        moveSecondToDeposit createSecondItem :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        createSecondItem moveItemToPay :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        moveItemToPay createHolder :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal moveSecondToDeposit createHolder (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.step edge_1 (.direct edge_2)))

end FillDependencyRemoval

end IndependenceWitnesses

end Define.OperationGraph
