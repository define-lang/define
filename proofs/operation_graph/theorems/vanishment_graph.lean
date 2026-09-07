import definitions

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.VanishmentGraph

universe u v

variable {Operation : Type u} {Particle : Type v}

/-!
`kept` is the result of Comparison, not a second minimization algorithm.
The English proof establishes the semantic candidates; Comparison supplies
the antichain premise used below.
-/
inductive Extended (base : Operation → Operation → Prop)
    (kept : Particle → Operation → Prop) :
    Sum Operation Particle → Sum Operation Particle → Prop where
  | original {source target} : base source target → Extended base kept (.inl source) (.inl target)
  | vanish {particle target} : kept particle target → Extended base kept (.inr particle) (.inl target)

theorem path_cases {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop} {source target}
    (path : Reaches (Extended base kept) source target) :
    match source, target with
    | .inl first, .inl last => Reaches base first last
    | .inr particle, .inl last =>
        ∃ first, kept particle first ∧ (first = last ∨ Reaches base first last)
    | _, .inr _ => False := by
  induction path with
  | direct edge =>
      cases edge with
      | original edge => exact .direct edge
      | vanish edge => exact ⟨_, edge, Or.inl rfl⟩
  | @step source next target edge _ induction_hypothesis =>
      cases edge with
      | original edge =>
          cases target with
          | inl target => exact .step edge induction_hypothesis
          | inr particle => exact induction_hypothesis
      | vanish edge =>
          cases target with
          | inl target => exact ⟨_, edge, Or.inr induction_hypothesis⟩
          | inr particle => exact induction_hypothesis

theorem original_reachability_iff {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop} {source target : Operation} :
    Reaches (Extended base kept) (.inl source) (.inl target) ↔
      Reaches base source target := by
  constructor
  · exact path_cases
  · exact Reaches.map Sum.inl (fun _ _ edge => Extended.original edge)

theorem no_dependency_on_vanish {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop} (source : Sum Operation Particle)
    (particle : Particle) :
    ¬Reaches (Extended base kept) source (.inr particle) := by
  intro path
  cases source <;> exact path_cases path

theorem vanish_reachability_iff {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop} {particle : Particle} {target : Operation} :
    Reaches (Extended base kept) (.inr particle) (.inl target) ↔
      ∃ first, kept particle first ∧ (first = target ∨ Reaches base first target) := by
  constructor
  · exact path_cases
  · rintro ⟨first, selected, equal | path⟩
    · subst target
      exact .direct (.vanish selected)
    · exact .step (.vanish selected) (original_reachability_iff.mpr path)

theorem extended_acyclic {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop} (acyclic : Acyclic base) :
    Acyclic (Extended base kept) := by
  intro vertex path
  cases vertex with
  | inl operation => exact acyclic operation (path_cases path)
  | inr particle => exact no_dependency_on_vanish _ particle path

theorem extended_minimal {base : Operation → Operation → Prop}
    {kept : Particle → Operation → Prop}
    (original : DirectDependenciesAreAntichains base)
    (selected : ∀ particle first second,
      kept particle first → kept particle second → first ≠ second →
      ¬Reaches base first second) :
    TransitivelyMinimal (Extended base kept) := by
  apply transitivelyMinimal_of_directDependenciesAreAntichains
  intro source first second first_edge second_edge distinct path
  cases first_edge with
  | original first_edge =>
      cases second_edge with
      | original second_edge =>
          exact original _ _ _ first_edge second_edge
            (fun equal => distinct (congrArg Sum.inl equal)) (path_cases path)
  | vanish first_edge =>
      cases second_edge with
      | vanish second_edge =>
          exact selected _ _ _ first_edge second_edge
            (fun equal => distinct (congrArg Sum.inl equal)) (path_cases path)

end Define.OperationGraph.VanishmentGraph
