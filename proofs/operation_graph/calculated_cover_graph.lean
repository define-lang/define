import characterization
import cover_graph

set_option warningAsError true
set_option autoImplicit false

/-!
# Calculated Cover Graph

This module specializes generic cover-graph theory to the Particle Operation
Dependency Graph. Characterization supplies calculated reachability and
transitive minimality; the generic cover results then identify every calculated
edge with a cover pair of that reachability.

Consequently, the calculated relation is contained in every relation with the
same reachability. It is therefore inclusion-minimal, and it is the unique
inclusion-minimal relation with that reachability. None of these results require
the valid resolved history to stop.
-/

namespace Define.OperationGraph

private theorem calculatedReachability_pointsBackward
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    PointsBackward ParticleOperation.operationOrder
      (Reaches (CalculatedDependency history)) :=
  fun _ _ path =>
    reaches_decreases_order (calculatedDependency_pointsBackward history) path

private theorem calculatedReachability_transitive
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    ∀ {source intermediate target},
      Reaches (CalculatedDependency history) source intermediate →
        Reaches (CalculatedDependency history) intermediate target →
          Reaches (CalculatedDependency history) source target :=
  fun first_path second_path => first_path.trans second_path

/--
A calculated direct dependency is exactly a cover pair of calculated
reachability.
-/
theorem calculatedDependency_iff_coverPair
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {source target : ParticleOperation} :
    CalculatedDependency history source target ↔
      CoverPair (Reaches (CalculatedDependency history)) source target := by
  apply
    calculatedDependency_is_unique history
      (coverPair_pointsBackward
        (calculatedReachability_pointsBackward history))
      (coverPair_transitivelyMinimal
        (Reaches (CalculatedDependency history))
        (calculatedReachability_transitive history))
  intro firstOperation secondOperation
  exact
    (reaches_coverPair_iff ParticleOperation.operationOrder
        (calculatedReachability_pointsBackward history)
        (calculatedReachability_transitive history)).symm

/--
The endpoints of a calculated dependency path are Particle Operations in the
history.
-/
theorem calculatedDependency_reaches_operations
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {source target : ParticleOperation}
    (path : Reaches (CalculatedDependency history) source target) :
    isOperation source ∧ isOperation target := by
  induction path with
  | direct edge => exact calculatedDependency_operations history edge
  | step edge _ induction_hypothesis =>
      exact
        ⟨(calculatedDependency_operations history edge).1,
          induction_hypothesis.2⟩

/--
Every relation with calculated reachability contains every calculated direct
dependency.
-/
theorem calculatedDependency_contained_in_sameReachability
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target) :
    ∀ source target,
      CalculatedDependency history source target →
        otherDependency source target := by
  intro source target calculated_edge
  have cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) source target :=
    (calculatedDependency_iff_coverPair history).mp calculated_edge
  exact
    coverPair_required (Reaches (CalculatedDependency history)) otherDependency
      (fun firstOperation secondOperation =>
        (same_reachability firstOperation secondOperation).symm)
      cover_pair

/--
The calculated dependency relation is inclusion-minimal among relations with
its reachability.
-/
theorem calculatedDependency_inclusionMinimal
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    InclusionMinimalForReachability (CalculatedDependency history) := by
  intro narrower _ same_reachability
  exact
    calculatedDependency_contained_in_sameReachability history
      (fun source target => (same_reachability source target).symm)

/--
The calculated dependency relation is the unique inclusion-minimal relation
with its reachability.
-/
theorem calculatedDependency_is_unique_inclusionMinimal
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (other_inclusion_minimal :
      InclusionMinimalForReachability otherDependency)
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target) :
    ∀ source target,
      CalculatedDependency history source target ↔
        otherDependency source target := by
  have calculated_is_subrelation :
      ∀ source target,
        CalculatedDependency history source target →
          otherDependency source target :=
    calculatedDependency_contained_in_sameReachability history
      same_reachability
  have other_is_subrelation :
      ∀ source target,
        otherDependency source target →
          CalculatedDependency history source target :=
    other_inclusion_minimal (CalculatedDependency history)
      calculated_is_subrelation same_reachability
  exact fun source target =>
    ⟨calculated_is_subrelation source target,
      other_is_subrelation source target⟩

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) source target,
      CalculatedDependency history source target ↔
        CoverPair (Reaches (CalculatedDependency history)) source target :=
  calculatedDependency_iff_coverPair

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (otherDependency : ParticleOperation → ParticleOperation → Prop),
      (∀ source target,
          Reaches (CalculatedDependency history) source target ↔
            Reaches otherDependency source target) →
        ∀ source target,
          CalculatedDependency history source target →
            otherDependency source target :=
  calculatedDependency_contained_in_sameReachability

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation),
      InclusionMinimalForReachability (CalculatedDependency history) :=
  calculatedDependency_inclusionMinimal

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (otherDependency : ParticleOperation → ParticleOperation → Prop),
      InclusionMinimalForReachability otherDependency →
        (∀ source target,
            Reaches (CalculatedDependency history) source target ↔
              Reaches otherDependency source target) →
          ∀ source target,
            CalculatedDependency history source target ↔
              otherDependency source target :=
  calculatedDependency_is_unique_inclusionMinimal

end TypeContracts

end Define.OperationGraph
