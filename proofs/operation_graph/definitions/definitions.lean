import Std

set_option warningAsError true
set_option autoImplicit false

/-!
Shared graph-theoretic definitions. Dependencies point from an operation to
its prerequisites. No language-specific operation or occupancy model is assumed.
-/

namespace Define.OperationGraph

universe u v

inductive Reaches {Vertex : Type u} (dependency : Vertex → Vertex → Prop) :
    Vertex → Vertex → Prop where
  | direct {source target} :
      dependency source target → Reaches dependency source target
  | step {source next target} :
      dependency source next →
      Reaches dependency next target →
      Reaches dependency source target

namespace Reaches

theorem trans {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    {first second third : Vertex} :
    Define.OperationGraph.Reaches dependency first second →
    Define.OperationGraph.Reaches dependency second third →
    Define.OperationGraph.Reaches dependency first third := by
  intro first_path second_path
  induction first_path with
  | direct dependency_edge =>
      exact .step dependency_edge second_path
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step dependency_edge (induction_hypothesis second_path)

theorem mono {Vertex : Type u} {narrow wide : Vertex → Vertex → Prop}
    (includes : ∀ source target, narrow source target → wide source target)
    {source target : Vertex} :
    Define.OperationGraph.Reaches narrow source target →
    Define.OperationGraph.Reaches wide source target := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact .direct (includes _ _ dependency_edge)
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step (includes _ _ dependency_edge) induction_hypothesis

theorem map {Source : Type u} {Target : Type v}
    {sourceDependency : Source → Source → Prop}
    {targetDependency : Target → Target → Prop}
    (resolve : Source → Target)
    (resolve_edge :
      ∀ source target,
        sourceDependency source target →
          targetDependency (resolve source) (resolve target))
    {source target : Source} :
    Define.OperationGraph.Reaches sourceDependency source target →
      Define.OperationGraph.Reaches targetDependency (resolve source)
        (resolve target) := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact .direct (resolve_edge _ _ dependency_edge)
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step (resolve_edge _ _ dependency_edge) induction_hypothesis

def OrEq {Vertex : Type u} (dependency : Vertex → Vertex → Prop)
    (source target : Vertex) : Prop :=
  source = target ∨ Define.OperationGraph.Reaches dependency source target

theorem prepend_orEq {Vertex : Type u}
    {dependency : Vertex → Vertex → Prop} {source next target : Vertex}
    (first_edge : dependency source next) :
    OrEq dependency next target → OrEq dependency source target := by
  intro remaining_path
  rcases remaining_path with next_is_target | remaining_path
  · subst next_is_target
    exact Or.inr (.direct first_edge)
  · exact Or.inr (.step first_edge remaining_path)

theorem last_edge {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    {source target : Vertex} :
    Define.OperationGraph.Reaches dependency source target →
    ∃ beforeTarget,
      OrEq dependency source beforeTarget ∧ dependency beforeTarget target := by
  intro path
  induction path with
  | @direct source target dependency_edge =>
      exact ⟨source, Or.inl rfl, dependency_edge⟩
  | step first_edge _ induction_hypothesis =>
      rcases induction_hypothesis with ⟨beforeTarget, path_to_before, final_edge⟩
      exact ⟨beforeTarget, prepend_orEq first_edge path_to_before, final_edge⟩

end Reaches

def WithoutEdge {Vertex : Type u} (dependency : Vertex → Vertex → Prop)
    (removed_source removed_target : Vertex) : Vertex → Vertex → Prop :=
  fun source target =>
    dependency source target ∧
      ¬(source = removed_source ∧ target = removed_target)

def TransitivelyMinimal {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ source target,
    dependency source target →
    ¬Reaches (WithoutEdge dependency source target) source target

def DirectDependenciesAreAntichains {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation newer older,
    dependency operation newer →
    dependency operation older →
    newer ≠ older →
    ¬Reaches dependency newer older

theorem transitivelyMinimal_of_directDependenciesAreAntichains
    {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    (antichains : DirectDependenciesAreAntichains dependency) :
    TransitivelyMinimal dependency := by
  intro source target direct_dependency alternate_path
  cases alternate_path with
  | direct remaining_edge =>
      exact remaining_edge.2 ⟨rfl, rfl⟩
  | step first_edge remaining_path =>
      rename_i next
      have next_is_distinct : next ≠ target := by
        intro next_is_target
        exact first_edge.2 ⟨rfl, next_is_target⟩
      have original_remaining_path : Reaches dependency next target :=
        Reaches.mono (fun _ _ edge => edge.1) remaining_path
      exact
        antichains source next target first_edge.1 direct_dependency
          next_is_distinct original_remaining_path

def PointsBackward {Vertex : Type u} (operationOrder : Vertex → Nat)
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation dependencyOperation,
    dependency operation dependencyOperation →
    operationOrder dependencyOperation < operationOrder operation

theorem reaches_decreases_order {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency)
    {source target : Vertex} :
    Reaches dependency source target →
    operationOrder target < operationOrder source := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact points_backward _ _ dependency_edge
  | step dependency_edge _ induction_hypothesis =>
      exact Nat.lt_trans induction_hypothesis (points_backward _ _ dependency_edge)

def Acyclic {Vertex : Type u} (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation, ¬Reaches dependency operation operation

theorem acyclic_of_pointsBackward {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency) :
    Acyclic dependency := by
  intro operation cycle
  have decreases := reaches_decreases_order points_backward cycle
  exact Nat.lt_irrefl _ decreases

end Define.OperationGraph
