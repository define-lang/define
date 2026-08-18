import Std

set_option warningAsError true
set_option autoImplicit false

/-!
# Finite Relation Edge Counts

This module counts the entries of a relation whose two endpoints come from one
finite list. The list of candidate pairs is fixed, so a subrelation has no more
entries than its containing relation. If the containing relation has an
additional entry on the list, its count is strictly larger.
-/

namespace Define.OperationGraph

universe u

private def relationCandidates {Vertex : Type u}
    (vertices : List Vertex) : List (Vertex × Vertex) :=
  vertices.flatMap fun source =>
    vertices.map fun target => (source, target)

private theorem mem_relationCandidates_iff
    {Vertex : Type u} {vertices : List Vertex} {source target : Vertex} :
    (source, target) ∈ relationCandidates vertices ↔
      source ∈ vertices ∧ target ∈ vertices := by
  simp [relationCandidates]

private noncomputable def relationCountOn
    {Vertex : Type u} (candidates : List (Vertex × Vertex))
    (relation : Vertex → Vertex → Prop) : Nat := by
  classical
  exact
    match candidates with
    | [] => 0
    | edge :: remaining =>
      if relation edge.1 edge.2 then
        relationCountOn remaining relation + 1
      else
        relationCountOn remaining relation

private theorem relationCountOn_le
    {Vertex : Type u} (candidates : List (Vertex × Vertex))
    {narrow wide : Vertex → Vertex → Prop}
    (narrow_is_subrelation :
      ∀ source target, narrow source target → wide source target) :
    relationCountOn candidates narrow ≤ relationCountOn candidates wide := by
  classical
  induction candidates with
  | nil => simp [relationCountOn]
  | cons edge remaining induction_hypothesis =>
      by_cases narrow_edge : narrow edge.1 edge.2
      · have wide_edge := narrow_is_subrelation _ _ narrow_edge
        simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
        omega
      · by_cases wide_edge : wide edge.1 edge.2
        · simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
          omega
        · simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
          exact induction_hypothesis

private theorem relationCountOn_lt
    {Vertex : Type u} (candidates : List (Vertex × Vertex))
    {narrow wide : Vertex → Vertex → Prop}
    (narrow_is_subrelation :
      ∀ source target, narrow source target → wide source target)
    {difference : Vertex × Vertex}
    (difference_member : difference ∈ candidates)
    (difference_in_wide : wide difference.1 difference.2)
    (difference_not_in_narrow : ¬narrow difference.1 difference.2) :
    relationCountOn candidates narrow < relationCountOn candidates wide := by
  classical
  induction candidates generalizing difference with
  | nil => simp at difference_member
  | cons edge remaining induction_hypothesis =>
      simp only [List.mem_cons] at difference_member
      by_cases narrow_edge : narrow edge.1 edge.2
      · have wide_edge := narrow_is_subrelation _ _ narrow_edge
        have difference_in_remaining : difference ∈ remaining := by
          rcases difference_member with difference_is_edge | member
          · subst difference
            exact False.elim (difference_not_in_narrow narrow_edge)
          · exact member
        have remaining_strict :=
          induction_hypothesis difference_in_remaining difference_in_wide
            difference_not_in_narrow
        simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
        omega
      · by_cases wide_edge : wide edge.1 edge.2
        · have remaining_le :=
            relationCountOn_le remaining narrow_is_subrelation
          simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
          omega
        · have difference_in_remaining : difference ∈ remaining := by
            rcases difference_member with difference_is_edge | member
            · subst difference
              exact False.elim (wide_edge difference_in_wide)
            · exact member
          have remaining_strict :=
            induction_hypothesis difference_in_remaining difference_in_wide
              difference_not_in_narrow
          simp only [relationCountOn, narrow_edge, wide_edge, ↓reduceIte]
          omega

/--
The number of entries in a relation whose endpoints both belong to the given
finite list.
-/
noncomputable def relationEdgeCount {Vertex : Type u}
    (vertices : List Vertex) (relation : Vertex → Vertex → Prop) : Nat :=
  relationCountOn (relationCandidates vertices) relation

/--
A subrelation has no more entries on a finite vertex list than its containing
relation.
-/
theorem relationEdgeCount_le
    {Vertex : Type u} (vertices : List Vertex)
    {narrow wide : Vertex → Vertex → Prop}
    (narrow_is_subrelation :
      ∀ source target, narrow source target → wide source target) :
    relationEdgeCount vertices narrow ≤ relationEdgeCount vertices wide :=
  relationCountOn_le (relationCandidates vertices) narrow_is_subrelation

/--
If a containing relation has an additional entry on a finite vertex list, its
entry count is strictly larger than the subrelation's count.
-/
theorem relationEdgeCount_lt
    {Vertex : Type u} (vertices : List Vertex)
    {narrow wide : Vertex → Vertex → Prop}
    (narrow_is_subrelation :
      ∀ source target, narrow source target → wide source target)
    {source target : Vertex}
    (source_member : source ∈ vertices)
    (target_member : target ∈ vertices)
    (edge_in_wide : wide source target)
    (edge_not_in_narrow : ¬narrow source target) :
    relationEdgeCount vertices narrow < relationEdgeCount vertices wide :=
  relationCountOn_lt (relationCandidates vertices) narrow_is_subrelation
    (mem_relationCandidates_iff.mpr ⟨source_member, target_member⟩)
    edge_in_wide edge_not_in_narrow

section TypeContracts

example {Vertex : Type u} :
    ∀ (vertices : List Vertex)
      (narrow wide : Vertex → Vertex → Prop),
      (∀ source target, narrow source target → wide source target) →
        relationEdgeCount vertices narrow ≤ relationEdgeCount vertices wide :=
  relationEdgeCount_le

example {Vertex : Type u} :
    ∀ (vertices : List Vertex)
      {narrow wide : Vertex → Vertex → Prop},
      (∀ first second, narrow first second → wide first second) →
        ∀ {source target},
          source ∈ vertices →
            target ∈ vertices →
              wide source target →
                ¬narrow source target →
                  relationEdgeCount vertices narrow <
                    relationEdgeCount vertices wide :=
  relationEdgeCount_lt

end TypeContracts

end Define.OperationGraph
