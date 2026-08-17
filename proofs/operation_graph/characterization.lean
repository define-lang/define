import completeness
import minimality

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Dependency Graph Characterization

This file formalizes `characterization-proof.md`. It combines the independent
completeness and minimality theorems only after both have been established.

Dependency reachability is proved equal to the transitive closure of the
related-and-previous relation. A separate generic argument then proves that two
transitively minimal relations which point backward in the same natural-number
order and have the same reachability must have the same edges.

Neither result requires the complete vertex set to be finite. The occurrence
order bounds each path and each alternate-path argument locally. The
fewest-edge corollary for histories that stop is stated only in the English
proof and is not formalized here.
-/

namespace Define.OperationGraph

universe u

/--
The related-and-previous relation restricted to the graph's operations.
-/
def CompleteResolvedDefineGraph.MemberRelatedPrevious
    (graph : CompleteResolvedDefineGraph)
    (operation previousOperation : ParticleOperation) : Prop :=
  graph.isOperation operation ∧
    graph.isOperation previousOperation ∧
    RelatedPrevious operation previousOperation

/--
Dependency reachability is exactly the transitive closure of the
related-and-previous relation.
-/
theorem CompleteResolvedDefineGraph.reaches_iff_reaches_relatedPrevious
    (graph : CompleteResolvedDefineGraph)
    {operation previousOperation : ParticleOperation} :
    Reaches graph.dependency operation previousOperation ↔
      Reaches graph.MemberRelatedPrevious operation previousOperation := by
  constructor
  · intro path
    refine Reaches.mono ?_ path
    intro source target edge
    have operations := graph.directDependency_operations edge
    exact
      ⟨operations.1, operations.2,
        graph.directDependency_is_previous edge,
        graph.directDependencyPositionsRelated edge⟩
  · intro path
    induction path with
    | direct edge =>
        exact graph.reaches_of_relatedPrevious _ _ edge.1 edge.2.1 edge.2.2
    | step edge _ induction_hypothesis =>
        exact
          (graph.reaches_of_relatedPrevious _ _ edge.1 edge.2.1
            edge.2.2).trans induction_hypothesis

theorem reaches_withoutEdge_of_order_lt {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency)
    {removedSource removedTarget : Vertex} :
    ∀ source target, Reaches dependency source target →
      operationOrder source < operationOrder removedSource →
      Reaches (WithoutEdge dependency removedSource removedTarget) source
        target := by
  intro source target path
  induction path with
  | @direct pathSource pathTarget edge =>
      intro source_below
      refine .direct ⟨edge, ?_⟩
      rintro ⟨source_is_removed, -⟩
      subst source_is_removed
      exact Nat.lt_irrefl _ source_below
  | @step pathSource next pathTarget edge _ induction_hypothesis =>
      intro source_below
      have next_below : operationOrder next < operationOrder removedSource :=
        Nat.lt_trans (points_backward pathSource next edge) source_below
      refine .step ⟨edge, ?_⟩ (induction_hypothesis next_below)
      rintro ⟨source_is_removed, -⟩
      subst source_is_removed
      exact Nat.lt_irrefl _ source_below

theorem reaches_withoutEdge_from_removed_source {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency)
    {removedSource removedTarget target : Vertex}
    (target_above : operationOrder removedTarget < operationOrder target)
    (path : Reaches dependency removedSource target) :
    Reaches (WithoutEdge dependency removedSource removedTarget) removedSource
      target := by
  cases path with
  | direct edge =>
      refine .direct ⟨edge, ?_⟩
      rintro ⟨-, target_is_removed⟩
      subst target_is_removed
      exact Nat.lt_irrefl _ target_above
  | @step _ next _ edge remaining_path =>
      have next_below : operationOrder next < operationOrder removedSource :=
        points_backward removedSource next edge
      have next_not_removed_target :
          ¬(removedSource = removedSource ∧ next = removedTarget) := by
        rintro ⟨-, next_is_removed⟩
        subst next_is_removed
        have target_below :=
          reaches_decreases_order points_backward remaining_path
        omega
      exact
        .step ⟨edge, next_not_removed_target⟩
          (reaches_withoutEdge_of_order_lt points_backward next target
            remaining_path next_below)

theorem dependency_unique {Vertex : Type u} {operationOrder : Vertex → Nat}
    {firstDependency secondDependency : Vertex → Vertex → Prop}
    (first_points_backward : PointsBackward operationOrder firstDependency)
    (second_points_backward : PointsBackward operationOrder secondDependency)
    (first_minimal : TransitivelyMinimal firstDependency)
    (same_reachability :
      ∀ source target,
        Reaches firstDependency source target ↔
          Reaches secondDependency source target) :
    ∀ source target, firstDependency source target →
      secondDependency source target := by
  intro source target edge
  have second_path : Reaches secondDependency source target :=
    (same_reachability source target).mp (.direct edge)
  cases second_path with
  | direct second_edge =>
      exact second_edge
  | @step _ next _ second_edge remaining_path =>
      exfalso
      have next_below : operationOrder next < operationOrder source :=
        second_points_backward source next second_edge
      have target_below : operationOrder target < operationOrder next :=
        reaches_decreases_order second_points_backward remaining_path
      have first_to_next : Reaches firstDependency source next :=
        (same_reachability source next).mpr (.direct second_edge)
      have first_from_next : Reaches firstDependency next target :=
        (same_reachability next target).mpr remaining_path
      have alternate_path :
          Reaches (WithoutEdge firstDependency source target) source target :=
        (reaches_withoutEdge_from_removed_source first_points_backward
            target_below first_to_next).trans
          (reaches_withoutEdge_of_order_lt first_points_backward next target
            first_from_next next_below)
      exact first_minimal source target edge alternate_path

theorem dependency_iff_unique {Vertex : Type u} {operationOrder : Vertex → Nat}
    {firstDependency secondDependency : Vertex → Vertex → Prop}
    (first_points_backward : PointsBackward operationOrder firstDependency)
    (second_points_backward : PointsBackward operationOrder secondDependency)
    (first_minimal : TransitivelyMinimal firstDependency)
    (second_minimal : TransitivelyMinimal secondDependency)
    (same_reachability :
      ∀ source target,
        Reaches firstDependency source target ↔
          Reaches secondDependency source target) :
    ∀ source target,
      firstDependency source target ↔ secondDependency source target := by
  intro source target
  constructor
  · exact
      dependency_unique first_points_backward second_points_backward
        first_minimal same_reachability source target
  · exact
      dependency_unique second_points_backward first_points_backward
        second_minimal (fun source target =>
          (same_reachability source target).symm) source target

/--
Any relation that points to previous operations, is transitively minimal, and
has the same reachability as the calculated relation has exactly its edges.
-/
theorem CompleteResolvedDefineGraph.dependency_is_unique
    (graph : CompleteResolvedDefineGraph)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (other_points_backward :
      PointsBackward ParticleOperation.operationOrder otherDependency)
    (other_minimal : TransitivelyMinimal otherDependency)
    (same_reachability :
      ∀ source target,
        Reaches graph.dependency source target ↔
          Reaches otherDependency source target) :
    ∀ source target,
      graph.dependency source target ↔ otherDependency source target :=
  dependency_iff_unique graph.pointsBackward other_points_backward
    graph.transitivelyMinimal other_minimal same_reachability

theorem calculatedDependency_reaches_iff_reaches_relatedPrevious
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation previousOperation : ParticleOperation} :
    Reaches (CalculatedDependency history) operation previousOperation ↔
      Reaches
        (fun newer older =>
          isOperation newer ∧
            isOperation older ∧ RelatedPrevious newer older)
        operation previousOperation := by
  exact
    (calculatedCompleteResolvedDefineGraph history).reaches_iff_reaches_relatedPrevious

theorem calculatedDependency_is_unique
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (other_points_backward :
      PointsBackward ParticleOperation.operationOrder otherDependency)
    (other_minimal : TransitivelyMinimal otherDependency)
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target) :
    ∀ source target,
      CalculatedDependency history source target ↔
        otherDependency source target :=
  (calculatedCompleteResolvedDefineGraph history).dependency_is_unique
    other_points_backward other_minimal same_reachability

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation previousOperation,
      Reaches (CalculatedDependency history) operation previousOperation ↔
        Reaches
          (fun newer older =>
            isOperation newer ∧
              isOperation older ∧ RelatedPrevious newer older)
          operation previousOperation :=
  calculatedDependency_reaches_iff_reaches_relatedPrevious

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation)
      (otherDependency : ParticleOperation → ParticleOperation → Prop),
      PointsBackward ParticleOperation.operationOrder otherDependency →
        TransitivelyMinimal otherDependency →
        (∀ source target,
          Reaches (CalculatedDependency history) source target ↔
            Reaches otherDependency source target) →
        ∀ source target,
          CalculatedDependency history source target ↔
            otherDependency source target :=
  calculatedDependency_is_unique

end TypeContracts

end Define.OperationGraph
