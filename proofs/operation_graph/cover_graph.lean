import cover_order

set_option warningAsError true
set_option autoImplicit false

/-!
# Cover Graphs

This module proves the generic order-theoretic properties of a cover graph. If
a transitive precedence relation points backward through natural-number ranks,
then its cover pairs have exactly that reachability and form a transitively
minimal relation. Moreover, every relation with that reachability contains
every cover-pair edge.

These results depend only on the finite rank difference between the endpoints
of one related pair. The complete occurrence type may be infinite.
-/

namespace Define.OperationGraph

universe u

/--
A path in a transitive relation is itself an entry in that relation.
-/
theorem Reaches.collapse
    {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    (dependency_transitive :
      ∀ {source intermediate target},
        dependency source intermediate →
          dependency intermediate target → dependency source target)
    {source target : Vertex} (path : Reaches dependency source target) :
    dependency source target := by
  induction path with
  | direct edge => exact edge
  | step edge _ induction_hypothesis =>
      exact dependency_transitive edge induction_hypothesis

/--
Cover pairs inherit the direction of their underlying precedence relation.
-/
theorem coverPair_pointsBackward
    {Vertex : Type u} {operationOrder : Vertex → Nat}
    {precedence : Vertex → Vertex → Prop}
    (precedence_points_backward :
      PointsBackward operationOrder precedence) :
    PointsBackward operationOrder (CoverPair precedence) :=
  fun source target cover_pair =>
    precedence_points_backward source target cover_pair.1

/--
Every precedence entry decomposes into a finite path of cover pairs.
-/
theorem precedence_reaches_coverPair
    {Vertex : Type u} (operationOrder : Vertex → Nat)
    {precedence : Vertex → Vertex → Prop}
    (precedence_points_backward :
      PointsBackward operationOrder precedence)
    {source target : Vertex} (precedes : precedence source target) :
    Reaches (CoverPair precedence) source target := by
  apply Classical.byContradiction
  intro does_not_reach
  rcases
      omitted_pair_contains_omitted_coverPair operationOrder
        precedence_points_backward
        (weaker := Reaches (CoverPair precedence))
        (fun first_path second_path => first_path.trans second_path)
        ⟨precedes, does_not_reach⟩ with
    ⟨coverSource, coverTarget, cover_pair, cover_omitted⟩
  exact cover_omitted (.direct cover_pair)

/--
The cover graph of a transitive precedence relation has exactly that
reachability.
-/
theorem reaches_coverPair_iff
    {Vertex : Type u} (operationOrder : Vertex → Nat)
    {precedence : Vertex → Vertex → Prop}
    (precedence_points_backward :
      PointsBackward operationOrder precedence)
    (precedence_transitive :
      ∀ {source intermediate target},
        precedence source intermediate →
          precedence intermediate target → precedence source target)
    {source target : Vertex} :
    Reaches (CoverPair precedence) source target ↔
      precedence source target := by
  constructor
  · intro cover_path
    have precedence_path : Reaches precedence source target :=
      Reaches.mono
        (narrow := CoverPair precedence) (wide := precedence)
        (fun _ _ cover_pair => cover_pair.1) cover_path
    exact
      Reaches.collapse (dependency := precedence) precedence_transitive
        precedence_path
  · exact
      precedence_reaches_coverPair operationOrder precedence_points_backward

/--
No cover-pair edge can be removed without changing reachability.
-/
theorem coverPair_transitivelyMinimal
    {Vertex : Type u} (precedence : Vertex → Vertex → Prop)
    (precedence_transitive :
      ∀ {source intermediate target},
        precedence source intermediate →
          precedence intermediate target → precedence source target) :
    TransitivelyMinimal (CoverPair precedence) := by
  intro source target cover_pair alternate_path
  cases alternate_path with
  | direct remaining_edge =>
      exact remaining_edge.2 ⟨rfl, rfl⟩
  | @step _ intermediate _ first_edge remaining_path =>
      have remaining_precedence_path :
          Reaches precedence intermediate target :=
        Reaches.mono
          (narrow :=
            WithoutEdge (CoverPair precedence) source target)
          (wide := precedence)
          (fun _ _ edge => edge.1.1) remaining_path
      have intermediate_precedes_target : precedence intermediate target :=
        Reaches.collapse (dependency := precedence) precedence_transitive
          remaining_precedence_path
      exact
        cover_pair.2 intermediate first_edge.1.1
          intermediate_precedes_target

/--
Every relation with a given reachability contains every cover pair of that
reachability.
-/
theorem coverPair_required
    {Vertex : Type u} (precedence dependency : Vertex → Vertex → Prop)
    (same_reachability :
      ∀ source target,
        Reaches dependency source target ↔ precedence source target)
    {source target : Vertex}
    (cover_pair : CoverPair precedence source target) :
    dependency source target := by
  have dependency_path : Reaches dependency source target :=
    (same_reachability source target).mpr cover_pair.1
  cases dependency_path with
  | direct edge => exact edge
  | @step _ intermediate _ first_edge remaining_path =>
      have source_precedes_intermediate : precedence source intermediate :=
        (same_reachability source intermediate).mp (.direct first_edge)
      have intermediate_precedes_target : precedence intermediate target :=
        (same_reachability intermediate target).mp remaining_path
      exact
        False.elim
          (cover_pair.2 intermediate source_precedes_intermediate
            intermediate_precedes_target)

/--
A relation is inclusion-minimal for its reachability when every subrelation
with the same reachability contains all of its edges.
-/
def InclusionMinimalForReachability {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ narrower : Vertex → Vertex → Prop,
    (∀ source target, narrower source target → dependency source target) →
      (∀ source target,
        Reaches narrower source target ↔ Reaches dependency source target) →
        ∀ source target, dependency source target → narrower source target

section TypeContracts

example {Vertex : Type u} :
    ∀ (operationOrder : Vertex → Nat)
      (precedence : Vertex → Vertex → Prop),
      PointsBackward operationOrder precedence →
        (∀ {source intermediate target},
            precedence source intermediate →
              precedence intermediate target → precedence source target) →
          ∀ source target,
            Reaches (CoverPair precedence) source target ↔
              precedence source target :=
  reaches_coverPair_iff

example {Vertex : Type u} :
    ∀ (precedence : Vertex → Vertex → Prop),
      (∀ {source intermediate target},
          precedence source intermediate →
            precedence intermediate target → precedence source target) →
        TransitivelyMinimal (CoverPair precedence) :=
  coverPair_transitivelyMinimal

example {Vertex : Type u} :
    ∀ (precedence dependency : Vertex → Vertex → Prop),
      (∀ source target,
          Reaches dependency source target ↔ precedence source target) →
        ∀ source target,
          CoverPair precedence source target → dependency source target :=
  coverPair_required

end TypeContracts

end Define.OperationGraph
