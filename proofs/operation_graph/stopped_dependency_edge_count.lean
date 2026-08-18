import calculated_cover_graph
import finite_history_schedule
import finite_relation_edge_count

set_option warningAsError true
set_option autoImplicit false

/-!
# Edge Counts for Stopped Histories

This module turns the calculated graph's least-containment property into a
finite cardinality result. Before any history index, the calculated dependency
relation has no more edges between the preceding operations than any relation
with the same reachability. If the history stops at that index, those preceding
operations are every operation in the history. Equal edge counts then force
the other relation to equal the calculated relation; every different relation
with the same reachability has strictly more edges.
-/

namespace Define.OperationGraph

namespace ValidResolvedHistory

/--
The number of dependency edges whose endpoints occur before a history index.
-/
noncomputable def dependencyEdgeCount
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationCount : Nat)
    (dependency : ParticleOperation → ParticleOperation → Prop) : Nat :=
  relationEdgeCount (history.operationsBefore operationCount) dependency

end ValidResolvedHistory

/--
Before any history index, the calculated relation has no more edges than any
relation with the same reachability.
-/
theorem calculatedDependency_has_least_edgeCountBefore
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operationCount : Nat)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target) :
    history.dependencyEdgeCount operationCount (CalculatedDependency history) ≤
      history.dependencyEdgeCount operationCount otherDependency :=
  relationEdgeCount_le (history.operationsBefore operationCount)
    (calculatedDependency_contained_in_sameReachability history
      same_reachability)

/--
For a stopped history, a relation with calculated reachability has the same
number of edges as the calculated relation exactly when the two relations are
equal.
-/
theorem stopped_calculatedDependency_equal_edgeCount_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operationCount : Nat}
    (history_stopped : history.operationAt operationCount = none)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target) :
    history.dependencyEdgeCount operationCount (CalculatedDependency history) =
        history.dependencyEdgeCount operationCount otherDependency ↔
      ∀ source target,
        CalculatedDependency history source target ↔
          otherDependency source target := by
  have calculated_is_subrelation :=
    calculatedDependency_contained_in_sameReachability history
      same_reachability
  constructor
  · intro equal_edge_count source target
    constructor
    · exact calculated_is_subrelation source target
    · intro other_edge
      apply Classical.byContradiction
      intro not_calculated_edge
      have calculated_path :
          Reaches (CalculatedDependency history) source target :=
        (same_reachability source target).mpr (.direct other_edge)
      have endpoints_are_operations :=
        calculatedDependency_reaches_operations history calculated_path
      have source_member :
          source ∈ history.operationsBefore operationCount :=
        (history.operationsBefore_iff_of_stopped history_stopped).mpr
          endpoints_are_operations.1
      have target_member :
          target ∈ history.operationsBefore operationCount :=
        (history.operationsBefore_iff_of_stopped history_stopped).mpr
          endpoints_are_operations.2
      have strict_edge_count :=
        relationEdgeCount_lt (history.operationsBefore operationCount)
          calculated_is_subrelation source_member target_member other_edge
          not_calculated_edge
      exact (Nat.ne_of_lt strict_edge_count) equal_edge_count
  · intro same_relation
    have relations_equal : CalculatedDependency history = otherDependency := by
      funext source target
      exact propext (same_relation source target)
    exact
      congrArg (history.dependencyEdgeCount operationCount) relations_equal

/--
For a stopped history, every different relation with calculated reachability
has strictly more edges than the calculated relation.
-/
theorem stopped_calculatedDependency_has_fewerEdges_of_different
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operationCount : Nat}
    (history_stopped : history.operationAt operationCount = none)
    {otherDependency : ParticleOperation → ParticleOperation → Prop}
    (same_reachability :
      ∀ source target,
        Reaches (CalculatedDependency history) source target ↔
          Reaches otherDependency source target)
    (relations_different :
      ¬∀ source target,
        CalculatedDependency history source target ↔
          otherDependency source target) :
    history.dependencyEdgeCount operationCount (CalculatedDependency history) <
      history.dependencyEdgeCount operationCount otherDependency := by
  have least_edge_count :=
    calculatedDependency_has_least_edgeCountBefore history operationCount
      same_reachability
  have unequal_edge_count :
      history.dependencyEdgeCount operationCount
          (CalculatedDependency history) ≠
        history.dependencyEdgeCount operationCount otherDependency := by
    intro equal_edge_count
    exact
      relations_different
        ((stopped_calculatedDependency_equal_edgeCount_iff history
            history_stopped same_reachability).mp equal_edge_count)
  omega

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationCount
      (otherDependency : ParticleOperation → ParticleOperation → Prop),
      (∀ source target,
          Reaches (CalculatedDependency history) source target ↔
            Reaches otherDependency source target) →
        history.dependencyEdgeCount operationCount
            (CalculatedDependency history) ≤
          history.dependencyEdgeCount operationCount otherDependency :=
  calculatedDependency_has_least_edgeCountBefore

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationCount,
      history.operationAt operationCount = none →
        ∀ (otherDependency : ParticleOperation → ParticleOperation → Prop),
          (∀ source target,
              Reaches (CalculatedDependency history) source target ↔
                Reaches otherDependency source target) →
            (history.dependencyEdgeCount operationCount
                    (CalculatedDependency history) =
                  history.dependencyEdgeCount operationCount otherDependency ↔
              ∀ source target,
                CalculatedDependency history source target ↔
                  otherDependency source target) :=
  stopped_calculatedDependency_equal_edgeCount_iff

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationCount,
      history.operationAt operationCount = none →
        ∀ (otherDependency : ParticleOperation → ParticleOperation → Prop),
          (∀ source target,
              Reaches (CalculatedDependency history) source target ↔
                Reaches otherDependency source target) →
            (¬∀ source target,
                CalculatedDependency history source target ↔
                  otherDependency source target) →
              history.dependencyEdgeCount operationCount
                  (CalculatedDependency history) <
                history.dependencyEdgeCount operationCount otherDependency :=
  stopped_calculatedDependency_has_fewerEdges_of_different

end TypeContracts

end Define.OperationGraph
