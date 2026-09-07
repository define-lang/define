import operation_effects

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ParticleRequirements

inductive Position where
  | viewPoint
  | local (execution declaration : Nat)
  | defined (particle declaration : Nat)
  | interface (particle action declaration : Nat)
  deriving DecidableEq

inductive Key where
  | occupancy (position : Position)
  | existence (particle : Nat)
  deriving DecidableEq

abbrev State := Key → Option Nat

/-!
These mathematical references preserve each selected intermediate particle.
A child still requires that particle at its preceding position: recording an
identity does not replace the actual chained reference by independent access.
Static permission to write each reference and Move geometry are separate from
this reference-observation lemma, as in `ordinary-requirements-proof.md`.
-/
inductive Reference where
  | viewPoint
  | local (execution declaration : Nat)
  | implied (particle declaration : Nat)
  | interface (particle action declaration : Nat)
  | child (parent : Reference) (particle declaration : Nat)
  | childInterface (parent : Reference) (particle action declaration : Nat)

def Reference.position : Reference → Position
  | .viewPoint => .viewPoint
  | .local execution declaration => .local execution declaration
  | .implied particle declaration => .defined particle declaration
  | .interface particle action declaration => .interface particle action declaration
  | .child _ particle declaration => .defined particle declaration
  | .childInterface _ particle action declaration => .interface particle action declaration

def Reference.keys : Reference → List Key
  | .viewPoint => []
  | .local _ _ => []
  | .implied particle _ => [.existence particle]
  | .interface particle _ _ => [.existence particle]
  | .child parent particle _ =>
      .occupancy parent.position :: .existence particle :: parent.keys
  | .childInterface parent particle _ _ =>
      .occupancy parent.position :: .existence particle :: parent.keys

def Reference.Enabled (qualities : Nat → Nat → Prop) (state : State) : Reference → Prop
  | .viewPoint => True
  | .local _ _ => True
  | .implied particle declaration =>
      state (.existence particle) = some particle ∧ qualities particle declaration
  | .interface particle action _ =>
      state (.existence particle) = some particle ∧ qualities particle action
  | .child parent particle declaration =>
      state (.occupancy parent.position) = some particle ∧
      state (.existence particle) = some particle ∧
      parent.Enabled qualities state ∧ qualities particle declaration
  | .childInterface parent particle action _ =>
      state (.occupancy parent.position) = some particle ∧
      state (.existence particle) = some particle ∧
      parent.Enabled qualities state ∧ qualities particle action

def Agrees (original current : State) (keys : List Key) : Prop :=
  ∀ key, key ∈ keys → current key = original key

theorem agrees_nil (original current : State) : Agrees original current [] := by
  intro key member
  cases member

theorem agrees_cons {original current : State} {key : Key} {keys : List Key} :
    Agrees original current (key :: keys) ↔
      current key = original key ∧ Agrees original current keys := by
  simp only [Agrees, List.mem_cons, forall_eq_or_imp]

theorem reference_enabled_iff_agrees {qualities : Nat → Nat → Prop}
    {original current : State} (reference : Reference)
    (valid : reference.Enabled qualities original) :
    reference.Enabled qualities current ↔ Agrees original current reference.keys := by
  induction reference with
  | viewPoint => simp [Reference.Enabled, Reference.keys, Agrees]
  | «local» execution declaration =>
      simp [Reference.Enabled, Reference.keys, Agrees]
  | implied particle declaration =>
      simp only [Reference.Enabled] at valid ⊢
      simp [Reference.keys, agrees_cons, agrees_nil, valid.1, valid.2]
  | interface particle action declaration =>
      simp only [Reference.Enabled] at valid ⊢
      simp [Reference.keys, agrees_cons, agrees_nil, valid.1, valid.2]
  | child parent particle declaration induction_hypothesis =>
      simp only [Reference.Enabled] at valid ⊢
      rw [induction_hypothesis valid.2.2.1]
      simp [Reference.keys, agrees_cons, valid.1, valid.2.1, valid.2.2.2]
  | childInterface parent particle action declaration induction_hypothesis =>
      simp only [Reference.Enabled] at valid ⊢
      rw [induction_hypothesis valid.2.2.1]
      simp [Reference.keys, agrees_cons, valid.1, valid.2.1, valid.2.2.2]

theorem agrees_append {original current : State} {first second : List Key} :
    Agrees original current (first ++ second) ↔
      Agrees original current first ∧ Agrees original current second := by
  simp only [Agrees, List.mem_append, or_imp, forall_and]

inductive VacancyTarget where
  | selected (position : Position)
  | written (reference : Reference)

def VacancyTarget.position : VacancyTarget → Position
  | .selected position => position
  | .written reference => reference.position

def VacancyTarget.keys : VacancyTarget → List Key
  | .selected _ => []
  | .written reference => reference.keys

def VacancyTarget.Enabled (qualities : Nat → Nat → Prop) (state : State) : VacancyTarget → Prop
  | .selected _ => True
  | .written reference => reference.Enabled qualities state

theorem vacancy_target_enabled_iff_agrees {qualities : Nat → Nat → Prop}
    {original current : State} (target : VacancyTarget)
    (valid : target.Enabled qualities original) :
    target.Enabled qualities current ↔ Agrees original current target.keys := by
  cases target with
  | selected position => simp [VacancyTarget.Enabled, VacancyTarget.keys, Agrees]
  | written reference => exact reference_enabled_iff_agrees reference valid

inductive Operation where
  | create (target : Reference) (particle : Nat)
  | move (source target : Reference) (particle : Nat)
  | vacate (target : VacancyTarget) (particle : Nat)

def Operation.Enabled (qualities : Nat → Nat → Prop) (state : State) : Operation → Prop
  | .create target particle =>
      target.Enabled qualities state ∧ state (.occupancy target.position) = none ∧
        state (.existence particle) = none
  | .move source target particle =>
      source.Enabled qualities state ∧ target.Enabled qualities state ∧
        state (.occupancy source.position) = some particle ∧
        state (.occupancy target.position) = none
  | .vacate target particle =>
      target.Enabled qualities state ∧ state (.occupancy target.position) = some particle

def Operation.keys : Operation → List Key
  | .create target particle =>
      .occupancy target.position :: .existence particle :: target.keys
  | .move source target _ =>
      .occupancy source.position :: .occupancy target.position :: (source.keys ++ target.keys)
  | .vacate target _ => .occupancy target.position :: target.keys

def Operation.changes : Operation → Key → Option (Option Nat)
  | .create target particle, key =>
      if key = .occupancy target.position then some (some particle)
      else if key = .existence particle then some (some particle) else none
  | .move source target particle, key =>
      if key = .occupancy source.position then some none
      else if key = .occupancy target.position then some (some particle) else none
  | .vacate target _, key => if key = .occupancy target.position then some none else none

def Operation.effect (operation : Operation) (original : State) :
    ExactEffects.Effect Key (Option Nat) where
  requires key := if key ∈ operation.keys then some (original key) else none
  changes := operation.changes

theorem effect_enabled_iff_agrees {operation : Operation} {original current : State} :
    (operation.effect original).Enabled current ↔ Agrees original current operation.keys := by
  constructor
  · intro enabled key member
    exact enabled key (original key) (by simp [Operation.effect, member])
  · intro agrees key value requirement
    by_cases member : key ∈ operation.keys
    · have equal : original key = value := by
        simpa [Operation.effect, member] using requirement
      exact (agrees key member).trans equal
    · simp [Operation.effect, member] at requirement

theorem operation_enabled_iff_agrees {qualities : Nat → Nat → Prop}
    {original current : State} (operation : Operation)
    (valid : operation.Enabled qualities original) :
    operation.Enabled qualities current ↔ Agrees original current operation.keys := by
  cases operation with
  | create target particle =>
      simp only [Operation.Enabled] at valid ⊢
      rw [reference_enabled_iff_agrees target valid.1]
      simp [Operation.keys, agrees_cons, valid.2.1, valid.2.2, and_comm, and_left_comm, and_assoc]
  | move source target particle =>
      simp only [Operation.Enabled] at valid ⊢
      rw [reference_enabled_iff_agrees source valid.1,
        reference_enabled_iff_agrees target valid.2.1]
      simp [Operation.keys, agrees_cons, agrees_append, valid.2.2.1, valid.2.2.2,
        and_comm, and_left_comm, and_assoc]
  | vacate target particle =>
      simp only [Operation.Enabled] at valid ⊢
      rw [vacancy_target_enabled_iff_agrees target valid.1]
      simp [Operation.keys, agrees_cons, valid.2, and_comm]

theorem operation_enabled_iff_effect_enabled {qualities : Nat → Nat → Prop}
    {original current : State} (operation : Operation)
    (valid : operation.Enabled qualities original) :
    operation.Enabled qualities current ↔ (operation.effect original).Enabled current :=
  (operation_enabled_iff_agrees operation valid).trans effect_enabled_iff_agrees.symm

theorem operation_effect_valid {qualities : Nat → Nat → Prop}
    {original : State} (operation : Operation)
    (valid : operation.Enabled qualities original) : (operation.effect original).Valid := by
  intro key after change
  cases operation with
  | create target particle =>
      simp only [Operation.Enabled] at valid
      by_cases target_key : key = .occupancy target.position
      · subst key
        have after_equal : after = some particle := by
          simpa [Operation.effect, Operation.changes] using change.symm
        subst after
        exact ⟨none, by simp [Operation.effect, Operation.keys, valid.2.1], by simp⟩
      · by_cases existence_key : key = .existence particle
        · subst key
          have after_equal : after = some particle := by
            simpa [Operation.effect, Operation.changes] using change.symm
          subst after
          exact ⟨none, by simp [Operation.effect, Operation.keys, valid.2.2], by simp⟩
        · simp [Operation.effect, Operation.changes, target_key, existence_key] at change
  | move source target particle =>
      simp only [Operation.Enabled] at valid
      by_cases source_key : key = .occupancy source.position
      · subst key
        have after_equal : after = none := by
          simpa [Operation.effect, Operation.changes] using change.symm
        subst after
        exact ⟨some particle, by simp [Operation.effect, Operation.keys, valid.2.2.1], by simp⟩
      · by_cases target_key : key = .occupancy target.position
        · subst key
          have after_equal : after = some particle := by
            simpa [Operation.effect, Operation.changes, source_key] using change.symm
          subst after
          exact ⟨none, by simp [Operation.effect, Operation.keys, valid.2.2.2], by simp⟩
        · simp [Operation.effect, Operation.changes, source_key, target_key] at change
  | vacate target particle =>
      simp only [Operation.Enabled] at valid
      by_cases target_key : key = .occupancy target.position
      · subst key
        have after_equal : after = none := by
          simpa [Operation.effect, Operation.changes] using change.symm
        subst after
        exact ⟨some particle, by simp [Operation.effect, Operation.keys, valid.2], by simp⟩
      · simp [Operation.effect, Operation.changes, target_key] at change

def State.set (state : State) (key : Key) (value : Option Nat) : State :=
  fun other => if other = key then value else state other

def Operation.execute : Operation → State → State
  | .create target particle, state =>
      (state.set (.existence particle) (some particle)).set
        (.occupancy target.position) (some particle)
  | .move source target particle, state =>
      (state.set (.occupancy source.position) none).set
        (.occupancy target.position) (some particle)
  | .vacate target _, state => state.set (.occupancy target.position) none

theorem enabled_move_positions_differ {qualities : Nat → Nat → Prop}
    {state : State} {source target : Reference} {particle : Nat}
    (valid : (Operation.move source target particle).Enabled qualities state) :
    source.position ≠ target.position := by
  intro equal
  have occupied := valid.2.2.1
  rw [equal, valid.2.2.2] at occupied
  contradiction

theorem effect_apply_eq_execute {qualities : Nat → Nat → Prop}
    {original : State} (operation : Operation)
    (valid : operation.Enabled qualities original) (current : State) :
    (operation.effect original).apply current = operation.execute current := by
  funext key
  cases operation with
  | create target particle =>
      cases key <;>
        simp [Operation.effect, ExactEffects.Effect.apply, Operation.changes,
          Operation.execute, State.set] <;> split <;> rfl
  | move source target particle =>
      have different := enabled_move_positions_differ valid
      by_cases at_source : key = .occupancy source.position
      · subst key
        simp [Operation.effect, ExactEffects.Effect.apply, Operation.changes,
          Operation.execute, State.set, different]
      · simp [Operation.effect, ExactEffects.Effect.apply, Operation.changes,
          Operation.execute, State.set, at_source]
        split <;> rfl
  | vacate target particle =>
      simp [Operation.effect, ExactEffects.Effect.apply, Operation.changes,
        Operation.execute, State.set]
      split <;> rfl

theorem independent_operations_exchange {qualities : Nat → Nat → Prop}
    {first second : Operation} {first_original second_original current : State}
    (first_valid : first.Enabled qualities first_original)
    (second_valid : second.Enabled qualities second_original)
    (independent : ExactEffects.Independent (first.effect first_original) (second.effect second_original))
    (first_enabled : first.Enabled qualities current)
    (second_enabled : second.Enabled qualities (first.execute current)) :
    second.Enabled qualities current ∧
      first.Enabled qualities (second.execute current) ∧
      second.execute (first.execute current) = first.execute (second.execute current) := by
  have first_effect := (operation_enabled_iff_effect_enabled first first_valid).mp first_enabled
  have second_effect := (operation_enabled_iff_effect_enabled second second_valid).mp second_enabled
  rw [← effect_apply_eq_execute first first_valid] at second_effect
  obtain ⟨second_first, first_second, equal⟩ :=
    ExactEffects.independent_enabled_exchange (operation_effect_valid second second_valid)
      independent first_effect second_effect
  refine ⟨(operation_enabled_iff_effect_enabled second second_valid).mpr second_first, ?_, ?_⟩
  · rw [effect_apply_eq_execute second second_valid] at first_second
    exact (operation_enabled_iff_effect_enabled first first_valid).mpr first_second
  · simpa only [effect_apply_eq_execute first first_valid,
      effect_apply_eq_execute second second_valid] using equal

def State.WellFormed (state : State) : Prop :=
  (∀ position particle, state (.occupancy position) = some particle →
    state (.existence particle) = some particle) ∧
  (∀ first second particle,
    state (.occupancy first) = some particle →
    state (.occupancy second) = some particle → first = second)

theorem empty_state_wellFormed : State.WellFormed (fun _ => none) := by
  constructor <;> intros <;> contradiction

theorem execute_preserves_wellFormed {qualities : Nat → Nat → Prop}
    {state : State} (operation : Operation)
    (well_formed : state.WellFormed) (valid : operation.Enabled qualities state) :
    (operation.execute state).WellFormed := by
  cases operation with
  | create target particle =>
      obtain ⟨reference_valid, target_empty, fresh⟩ := valid
      simp only [State.WellFormed, Operation.execute, State.set] at *
      grind
  | move source target particle =>
      obtain ⟨source_valid, target_valid, source_occupied, target_empty⟩ := valid
      simp only [State.WellFormed, Operation.execute, State.set] at *
      grind
  | vacate target particle =>
      simp only [State.WellFormed, Operation.execute, State.set] at *
      grind

end Define.OperationGraph.ParticleRequirements
