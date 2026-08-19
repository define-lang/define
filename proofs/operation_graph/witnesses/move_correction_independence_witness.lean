import independence_witness_support
import minimality
import move_correction_witness

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Move Correction

`MoveCorrectionHistory.history` is the valid resolved history `create box`,
`create box::origin`, `move box::origin holder_a`,
`move holder_a box::middle`, `move box::middle box::target`,
`move box::target holder_c`, `destroy box`.

Under the complete rules, the universal calculation makes the final Move the
box Destroy's dependency. The universal minimality theorem applies directly to
this calculated dependency graph.

The weakened variant changes only Move Correction. The box Destroy retains a
second direct dependency on the first Move even though its dependency on the
final Move already reaches the first Move through the intervening Moves.
-/

namespace MoveCorrection

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency MoveCorrectionHistory.history

def weakenedDependencyTarget : ParticleOperation → List ParticleOperation :=
  fun operation =>
    if operation = MoveCorrectionHistory.createOrigin then
      [MoveCorrectionHistory.createBox]
    else if operation = MoveCorrectionHistory.moveOriginToHolderA then
      [MoveCorrectionHistory.createOrigin]
    else if operation = MoveCorrectionHistory.moveHolderAToMiddle then
      [MoveCorrectionHistory.moveOriginToHolderA]
    else if operation = MoveCorrectionHistory.moveMiddleToTarget then
      [MoveCorrectionHistory.moveHolderAToMiddle]
    else if operation = MoveCorrectionHistory.moveTargetToHolderC then
      [MoveCorrectionHistory.moveMiddleToTarget]
    else if operation = MoveCorrectionHistory.destroyBox then
      [MoveCorrectionHistory.moveOriginToHolderA,
        MoveCorrectionHistory.moveTargetToHolderC]
    else
      []

abbrev WeakenedDependency
    (operation dependencyOperation : ParticleOperation) : Prop :=
  dependencyOperation ∈ weakenedDependencyTarget operation

def weakenedRules : RuleVariant :=
  { completeRules with moveCorrection := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules MoveCorrectionHistory.operations =
      some (graphForDependency MoveCorrectionHistory.operations
        fun operation dependencyOperation =>
          decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG MoveCorrectionHistory.history).2

theorem complete_final_dependency :
    CompleteDependency MoveCorrectionHistory.destroyBox
      MoveCorrectionHistory.moveTargetToHolderC :=
  MoveCorrectionHistory.calculated_dependency

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have destroy_to_final_move :
      WithoutEdge WeakenedDependency MoveCorrectionHistory.destroyBox
        MoveCorrectionHistory.moveOriginToHolderA
        MoveCorrectionHistory.destroyBox
        MoveCorrectionHistory.moveTargetToHolderC := by
    exact ⟨by decide, by decide⟩
  have final_move_to_middle_move :
      WithoutEdge WeakenedDependency MoveCorrectionHistory.destroyBox
        MoveCorrectionHistory.moveOriginToHolderA
        MoveCorrectionHistory.moveTargetToHolderC
        MoveCorrectionHistory.moveMiddleToTarget := by
    exact ⟨by decide, by decide⟩
  have middle_move_to_holder_move :
      WithoutEdge WeakenedDependency MoveCorrectionHistory.destroyBox
        MoveCorrectionHistory.moveOriginToHolderA
        MoveCorrectionHistory.moveMiddleToTarget
        MoveCorrectionHistory.moveHolderAToMiddle := by
    exact ⟨by decide, by decide⟩
  have holder_move_to_origin_move :
      WithoutEdge WeakenedDependency MoveCorrectionHistory.destroyBox
        MoveCorrectionHistory.moveOriginToHolderA
        MoveCorrectionHistory.moveHolderAToMiddle
        MoveCorrectionHistory.moveOriginToHolderA := by
    exact ⟨by decide, by decide⟩
  exact
    minimal MoveCorrectionHistory.destroyBox
      MoveCorrectionHistory.moveOriginToHolderA (by decide)
      (.step destroy_to_final_move
        (.step final_move_to_middle_move
          (.step middle_move_to_holder_move
            (.direct holder_move_to_origin_move))))

end MoveCorrection

end IndependenceWitnesses

end Define.OperationGraph
