import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Concrete Operation Graph Witness Support

This module contains general lemmas used only to verify concrete operation graph
histories. It contains no particular history and assumes no graph property.
-/

namespace Define.OperationGraph

theorem not_move_of_kind_create {operation : ParticleOperation} {target : Position}
    (kind_eq : operation.kind = .create target) : ¬IsMove operation := by
  rintro ⟨moveSource, moveTarget, move_kind⟩
  rw [kind_eq] at move_kind
  exact ParticleOperationKind.noConfusion move_kind

theorem not_move_of_kind_destroy {operation : ParticleOperation} {target : Position}
    (kind_eq : operation.kind = .destroy target) : ¬IsMove operation := by
  rintro ⟨moveSource, moveTarget, move_kind⟩
  rw [kind_eq] at move_kind
  exact ParticleOperationKind.noConfusion move_kind

theorem not_more_recent_of_le {newer older : ParticleOperation}
    (le : newer.operationOrder ≤ older.operationOrder) : ¬MoreRecent newer older :=
  fun more_recent => absurd more_recent (Nat.not_lt.mpr le)

theorem no_reaches_of_no_dependency {Vertex : Type} {dep : Vertex → Vertex → Prop}
    {source : Vertex} (no_edge : ∀ target, ¬dep source target) {target : Vertex} :
    ¬Reaches dep source target := by
  intro path
  cases path with
  | direct edge => exact no_edge _ edge
  | step edge _ => exact no_edge _ edge

theorem prefix_singleton_iff {head : Nat} {name : List Nat} :
    name <+: [head] ↔ name = [] ∨ name = [head] := by
  constructor
  · intro name_prefix
    rcases List.prefix_cons_iff.mp name_prefix with name_nil | ⟨tail, name_eq, tail_prefix⟩
    · exact Or.inl name_nil
    · have tail_nil := List.eq_nil_of_prefix_nil tail_prefix
      subst tail_nil
      exact Or.inr name_eq
  · rintro (rfl | rfl)
    · exact List.nil_prefix
    · exact List.prefix_rfl

theorem prefix_pair_iff {first second : Nat} {name : List Nat} :
    name <+: [first, second] ↔
      name = [] ∨ name = [first] ∨ name = [first, second] := by
  constructor
  · intro name_prefix
    rcases List.prefix_cons_iff.mp name_prefix with name_nil | ⟨tail, name_eq, tail_prefix⟩
    · exact Or.inl name_nil
    · rcases prefix_singleton_iff.mp tail_prefix with tail_nil | tail_single
      · subst tail_nil
        exact Or.inr (Or.inl name_eq)
      · subst tail_single
        exact Or.inr (Or.inr name_eq)
  · rintro (rfl | rfl | rfl)
    · exact List.nil_prefix
    · exact ⟨[second], rfl⟩
    · exact List.prefix_rfl

theorem prefix_triple_iff {first second third : Nat} {name : List Nat} :
    name <+: [first, second, third] ↔
      name = [] ∨ name = [first] ∨ name = [first, second] ∨
        name = [first, second, third] := by
  constructor
  · intro name_prefix
    rcases List.prefix_cons_iff.mp name_prefix with
      name_nil | ⟨tail, name_eq, tail_prefix⟩
    · exact Or.inl name_nil
    · rcases prefix_pair_iff.mp tail_prefix with
        tail_nil | tail_single | tail_pair
      · subst tail_nil
        exact Or.inr (Or.inl name_eq)
      · subst tail_single
        exact Or.inr (Or.inr (Or.inl name_eq))
      · subst tail_pair
        exact Or.inr (Or.inr (Or.inr name_eq))
  · rintro (rfl | rfl | rfl | rfl)
    · exact List.nil_prefix
    · exact ⟨[second, third], rfl⟩
    · exact ⟨[third], rfl⟩
    · exact List.prefix_rfl

end Define.OperationGraph
