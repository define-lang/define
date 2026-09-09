import definitions

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.Comparison

universe u
variable {Operation : Type u}

/- The accumulator follows the specified scan; reachability is already calculated. -/
noncomputable def scan (reaches : Operation → Operation → Prop)
    (candidates kept : List Operation) : List Operation := by
  classical
  exact match candidates with
  | [] => kept
  | candidate :: remaining =>
      if ∃ previous ∈ kept, reaches previous candidate then scan reaches remaining kept
      else scan reaches remaining (candidate :: kept)

def Antichain (reaches : Operation → Operation → Prop) (kept : List Operation) : Prop :=
  ∀ first ∈ kept, ∀ second ∈ kept, ¬reaches first second

def Covers (reaches : Operation → Operation → Prop)
    (kept candidates : List Operation) : Prop :=
  ∀ candidate ∈ candidates,
    ∃ previous ∈ kept, previous = candidate ∨ reaches previous candidate

theorem scan_invariants (reaches : Operation → Operation → Prop)
    (irreflexive : ∀ operation, ¬reaches operation operation)
    (transitive : ∀ {first second third},
      reaches first second → reaches second third → reaches first third)
    (candidates kept : List Operation)
    (ordered : candidates.Pairwise (fun first second => ¬reaches second first))
    (separated : ∀ candidate ∈ candidates, ∀ previous ∈ kept, ¬reaches candidate previous)
    (antichain : Antichain reaches kept) :
    (∀ operation ∈ scan reaches candidates kept, operation ∈ candidates ∨ operation ∈ kept) ∧
      Antichain reaches (scan reaches candidates kept) ∧
      Covers reaches (scan reaches candidates kept) (candidates ++ kept) := by
  classical
  induction candidates generalizing kept with
  | nil =>
      simp only [scan, List.nil_append]
      exact ⟨fun _ member => Or.inr member, antichain,
        fun operation member => ⟨operation, member, Or.inl rfl⟩⟩
  | cons candidate remaining induction_hypothesis =>
      have order_parts := List.pairwise_cons.mp ordered
      by_cases covered : ∃ previous ∈ kept, reaches previous candidate
      · simp only [scan, if_pos covered]
        obtain ⟨subset, independent, coverage⟩ := induction_hypothesis kept order_parts.2
          (fun operation member => separated operation (by simp [member])) antichain
        refine ⟨?_, independent, ?_⟩
        · intro operation member
          rcases subset operation member with member | member
          · exact Or.inl (by simp [member])
          · exact Or.inr member
        · intro operation member
          rcases List.mem_append.mp member with member | member
          · rcases List.mem_cons.mp member with equal | member
            · subst operation
              obtain ⟨previous, previous_member, path⟩ := covered
              obtain ⟨retained, retained_member, equal | earlier_path⟩ :=
                coverage previous (List.mem_append_right _ previous_member)
              · exact ⟨retained, retained_member, Or.inr (equal ▸ path)⟩
              · exact ⟨retained, retained_member, Or.inr (transitive earlier_path path)⟩
            · exact coverage operation (List.mem_append_left _ member)
          · exact coverage operation (List.mem_append_right _ member)
      · simp only [scan, if_neg covered]
        have next_antichain : Antichain reaches (candidate :: kept) := by
          intro first first_member second second_member
          rcases List.mem_cons.mp first_member with equal | first_member
          · subst first
            rcases List.mem_cons.mp second_member with equal | second_member
            · subst second
              exact irreflexive candidate
            · exact separated candidate (by simp) second second_member
          · rcases List.mem_cons.mp second_member with equal | second_member
            · subst second
              exact fun path => covered ⟨first, first_member, path⟩
            · exact antichain first first_member second second_member
        have next_separated : ∀ operation ∈ remaining,
            ∀ previous ∈ candidate :: kept, ¬reaches operation previous := by
          intro operation member previous previous_member
          rcases List.mem_cons.mp previous_member with equal | previous_member
          · subst previous
            exact order_parts.1 operation member
          · exact separated operation (by simp [member]) previous previous_member
        obtain ⟨subset, independent, coverage⟩ := induction_hypothesis
          (candidate :: kept) order_parts.2 next_separated next_antichain
        refine ⟨?_, independent, ?_⟩
        · intro operation member
          have included := subset operation member
          simp only [List.mem_cons] at included ⊢
          rcases included with member | equal | member
          · exact Or.inl (Or.inr member)
          · exact Or.inl (Or.inl equal)
          · exact Or.inr member
        · intro operation member
          apply coverage operation
          simp only [List.mem_append, List.mem_cons] at member ⊢
          rcases member with (equal | member) | member
          · exact Or.inr (Or.inl equal)
          · exact Or.inl member
          · exact Or.inr (Or.inr member)

theorem scan_iff_maximal {base : Operation → Operation → Prop}
    (acyclic : Acyclic base) (candidates : List Operation)
    (ordered : candidates.Pairwise (fun first second => ¬Reaches base second first))
    (operation : Operation) :
    operation ∈ scan (Reaches base) candidates [] ↔
      operation ∈ candidates ∧ ∀ other ∈ candidates, ¬Reaches base other operation := by
  obtain ⟨subset, independent, coverage⟩ := scan_invariants (Reaches base) acyclic
    (fun first second => first.trans second) candidates [] ordered
    (by simp) (by simp [Antichain])
  simp only [List.append_nil] at coverage
  constructor
  · intro member
    refine ⟨(subset operation member).resolve_right (by simp), ?_⟩
    intro other other_member path
    obtain ⟨previous, previous_member, equal | earlier_path⟩ := coverage other other_member
    · subst previous
      exact independent other previous_member operation member path
    · exact independent previous previous_member operation member (earlier_path.trans path)
  · rintro ⟨member, maximal⟩
    obtain ⟨previous, previous_member, equal | path⟩ := coverage operation member
    · exact equal ▸ previous_member
    · exact False.elim (maximal previous
        ((subset previous previous_member).resolve_right (by simp)) path)

theorem maximal_iff_of_cover {base : Operation → Operation → Prop}
    {candidates pruned : List Operation}
    (subset : ∀ operation ∈ pruned, operation ∈ candidates)
    (coverage : Covers (Reaches base) pruned candidates) (operation : Operation) :
    (operation ∈ candidates ∧ ∀ other ∈ candidates, ¬Reaches base other operation) ↔
      (operation ∈ pruned ∧ ∀ other ∈ pruned, ¬Reaches base other operation) := by
  constructor
  · rintro ⟨member, maximal⟩
    have retained : operation ∈ pruned := by
      obtain ⟨previous, previous_member, equal | path⟩ := coverage operation member
      · exact equal ▸ previous_member
      · exact False.elim (maximal previous (subset previous previous_member) path)
    exact ⟨retained, fun other member => maximal other (subset other member)⟩
  · rintro ⟨member, maximal⟩
    refine ⟨subset operation member, ?_⟩
    intro other other_member path
    obtain ⟨previous, previous_member, equal | earlier_path⟩ := coverage other other_member
    · subst previous
      exact maximal other previous_member path
    · exact maximal previous previous_member (earlier_path.trans path)

end Define.OperationGraph.Comparison
