import comparison_simultaneity_witness
import independence_witness_support
import minimality

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph

namespace IndependenceWitnesses

/-!
## The Comparison's simultaneous exclusions

`ComparisonSimultaneityHistory.history` is the valid resolved history
`create parent`,
`create child`, `create child::x`, `destroy child::x`, `destroy child`,
`create child` again, `create child::y`, `destroy child::y`, and `destroy child`
again.

At the final Destroy, the complete Comparison evaluates every pair in the
Collection simultaneously. The `child::y` Destroy excludes the second child
Create, while that Create still excludes the earlier `child::x` Destroy. The
actual calculation therefore retains the `child::y` Destroy, and its universal
minimality theorem applies to the resulting graph.

The weakened variant changes only simultaneity: an excluded candidate can no
longer exclude another candidate. After the `child::y` Destroy excludes the
child Create, the `child::x` Destroy survives. The final Destroy gains a direct
dependency on it even though the dependency chain through `child::y` already
reaches it.
-/

namespace ComparisonSimultaneity

abbrev CompleteDependency : ParticleOperation → ParticleOperation → Prop :=
  CalculatedDependency ComparisonSimultaneityHistory.history

def weakenedDependencyTarget : ParticleOperation → List ParticleOperation :=
  fun operation =>
    if operation = ComparisonSimultaneityHistory.createChild then
      [ComparisonSimultaneityHistory.createParent]
    else if operation =
        ComparisonSimultaneityHistory.createGrandChildX then
      [ComparisonSimultaneityHistory.createChild]
    else if operation =
        ComparisonSimultaneityHistory.destroyGrandChildX then
      [ComparisonSimultaneityHistory.createGrandChildX]
    else if operation =
        ComparisonSimultaneityHistory.destroyChild then
      [ComparisonSimultaneityHistory.destroyGrandChildX]
    else if operation =
        ComparisonSimultaneityHistory.recreateChild then
      [ComparisonSimultaneityHistory.destroyChild]
    else if operation =
        ComparisonSimultaneityHistory.createGrandChildY then
      [ComparisonSimultaneityHistory.recreateChild]
    else if operation =
        ComparisonSimultaneityHistory.destroyGrandChildY then
      [ComparisonSimultaneityHistory.createGrandChildY]
    else if operation =
        ComparisonSimultaneityHistory.destroyRecreatedChild then
      [ComparisonSimultaneityHistory.destroyGrandChildX,
        ComparisonSimultaneityHistory.destroyGrandChildY]
    else
      []

abbrev WeakenedDependency
    (operation dependencyOperation : ParticleOperation) : Prop :=
  dependencyOperation ∈ weakenedDependencyTarget operation

def weakenedRules : RuleVariant :=
  { completeRules with simultaneousComparison := false }

theorem weakened_rules_derive_graph :
    calculate weakenedRules ComparisonSimultaneityHistory.operations =
      some (graphForDependency ComparisonSimultaneityHistory.operations
        fun operation dependencyOperation =>
          decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  (calculatedDependency_isMinimalDAG
    ComparisonSimultaneityHistory.history).2

theorem complete_final_dependency :
    CompleteDependency
      ComparisonSimultaneityHistory.destroyRecreatedChild
      ComparisonSimultaneityHistory.destroyGrandChildY :=
  ComparisonSimultaneityHistory.calculated_dependency

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have final_to_y :
      WithoutEdge WeakenedDependency
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildX
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildY := by
    exact ⟨by decide, by decide⟩
  have destroy_y_to_create_y :
      WithoutEdge WeakenedDependency
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildX
        ComparisonSimultaneityHistory.destroyGrandChildY
        ComparisonSimultaneityHistory.createGrandChildY := by
    exact ⟨by decide, by decide⟩
  have create_y_to_recreate_child :
      WithoutEdge WeakenedDependency
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildX
        ComparisonSimultaneityHistory.createGrandChildY
        ComparisonSimultaneityHistory.recreateChild := by
    exact ⟨by decide, by decide⟩
  have recreate_child_to_destroy_child :
      WithoutEdge WeakenedDependency
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildX
        ComparisonSimultaneityHistory.recreateChild
        ComparisonSimultaneityHistory.destroyChild := by
    exact ⟨by decide, by decide⟩
  have destroy_child_to_destroy_x :
      WithoutEdge WeakenedDependency
        ComparisonSimultaneityHistory.destroyRecreatedChild
        ComparisonSimultaneityHistory.destroyGrandChildX
        ComparisonSimultaneityHistory.destroyChild
        ComparisonSimultaneityHistory.destroyGrandChildX := by
    exact ⟨by decide, by decide⟩
  exact
    minimal ComparisonSimultaneityHistory.destroyRecreatedChild
      ComparisonSimultaneityHistory.destroyGrandChildX
      (by decide)
      (.step final_to_y
        (.step destroy_y_to_create_y
          (.step create_y_to_recreate_child
            (.step recreate_child_to_destroy_child
              (.direct destroy_child_to_destroy_x)))))

end ComparisonSimultaneity

end IndependenceWitnesses

end Define.OperationGraph
