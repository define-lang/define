import operation_effects

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.VanishmentRequirements

/-!
These lifetime components supplement, rather than replace, occupancy effects.
The English source correspondence in `vanishment-proof.md` determines which
particles an operation requires. Transitive movement alone adds no component
under the Vanish rules.
-/
inductive Key where
  | exists
  | vacated
  deriving DecidableEq

inductive Component where
  | create
  | use
  | vacate
  | vanish

def Component.required : Component → Key → Option Bool
  | .create, _ => some false
  | .use, .exists => some true
  | .use, .vacated => none
  | .vacate, .exists => some true
  | .vacate, .vacated => some false
  | .vanish, _ => some true

def Component.changed : Component → Key → Option Bool
  | .create, .exists => some true
  | .vacate, .vacated => some true
  | .vanish, .exists => some false
  | _, _ => none

def Component.effect (component : Component) : ExactEffects.Effect Key Bool where
  requires := component.required
  changes := component.changed

theorem component_effect_valid (component : Component) : component.effect.Valid := by
  intro key after changed
  cases component <;> cases key <;>
    simp_all [Component.effect, Component.changed, Component.required]

theorem use_enabled_iff (state : Key → Bool) :
    Component.use.effect.Enabled state ↔ state .exists = true := by
  constructor
  · intro enabled
    exact enabled .exists true rfl
  · intro alive key value required
    cases key <;> simp_all [Component.effect, Component.required]

theorem vanish_enabled_iff (state : Key → Bool) :
    Component.vanish.effect.Enabled state ↔
      state .exists = true ∧ state .vacated = true := by
  constructor
  · intro enabled
    exact ⟨enabled .exists true rfl, enabled .vacated true rfl⟩
  · rintro ⟨alive, vacated⟩ key value required
    cases key <;> simp_all [Component.effect, Component.required]

theorem vacate_preserves_existence (state : Key → Bool) :
    Component.vacate.effect.apply state .exists = state .exists := by
  rfl

theorem vanish_preserves_vacancy (state : Key → Bool) :
    Component.vanish.effect.apply state .vacated = state .vacated := by
  rfl

theorem use_after_vanish_invalid (state : Key → Bool) :
    ¬Component.use.effect.Enabled (Component.vanish.effect.apply state) := by
  rw [use_enabled_iff]
  simp [ExactEffects.Effect.apply, Component.effect, Component.changed]

theorem vacancy_and_use_independent :
    ExactEffects.Independent Component.vacate.effect Component.use.effect := by
  rintro (⟨key, written, required, change, requirement⟩ |
    ⟨key, written, required, change, requirement⟩) <;>
    cases key <;> simp_all [Component.effect, Component.changed, Component.required]

theorem vanish_conflicts_with_use :
    ExactEffects.Conflict Component.vanish.effect Component.use.effect := by
  exact Or.inl ⟨.exists, false, true, rfl, rfl⟩

theorem vanish_conflicts_with_vacate :
    ExactEffects.Conflict Component.vanish.effect Component.vacate.effect := by
  exact Or.inr ⟨.vacated, true, true, rfl, rfl⟩

def combinedEffect : ExactEffects.Effect Key Bool where
  requires := Component.vacate.required
  changes key := match key with
    | .exists => some false
    | .vacated => some true

theorem combined_enabled_iff (state : Key → Bool) :
    combinedEffect.Enabled state ↔ Component.vacate.effect.Enabled state := by
  rfl

theorem combined_apply_eq (state : Key → Bool) :
    combinedEffect.apply state =
      Component.vanish.effect.apply (Component.vacate.effect.apply state) := by
  funext key
  cases key <;> rfl

theorem combined_effect_valid : combinedEffect.Valid := by
  intro key after changed
  cases key <;> simp_all [combinedEffect, Component.required]

end Define.OperationGraph.VanishmentRequirements
