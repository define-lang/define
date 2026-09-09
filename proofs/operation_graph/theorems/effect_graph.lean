import comparison
import cover_graph
import effect_collection
import effect_scheduling

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ExactEffects

universe u v

variable {Key : Type u} {Value : Type v}

/-- A characterization of Comparison's result, not a subsequent graph algorithm. -/
def Reduced (effects : Nat → Effect Key Value) (later earlier : Nat) : Prop :=
  Collected effects later earlier ∧
    ∀ other, Collected effects later other → ¬Reaches (Collected effects) other earlier

theorem reduced_iff_cover {effects : Nat → Effect Key Value} {later earlier : Nat} :
    Reduced effects later earlier ↔ CoverPair (Reaches (Collected effects)) later earlier := by
  constructor
  · rintro ⟨collected, maximal⟩
    refine ⟨.direct collected, ?_⟩
    intro middle first_path last_path
    cases first_path with
    | direct edge => exact maximal middle edge last_path
    | @step _ other _ edge remaining => exact maximal other edge (remaining.trans last_path)
  · rintro ⟨path, cover⟩
    have edge : Collected effects later earlier := by
      cases path with
      | direct edge => exact edge
      | @step _ middle _ edge remaining => exact False.elim (cover (.direct edge) remaining)
    refine ⟨edge, ?_⟩
    intro other other_edge remaining
    exact cover (.direct other_edge) remaining

theorem reduced_reachability_iff {effects : Nat → Effect Key Value} {later earlier : Nat} :
    Reaches (Reduced effects) later earlier ↔ Reaches (Collected effects) later earlier := by
  have equal : Reduced effects = CoverPair (Reaches (Collected effects)) := by
    funext source target
    exact propext reduced_iff_cover
  rw [equal]
  have backward : PointsBackward (fun operation : Nat => operation) (Collected effects) :=
    fun _ _ edge => edge.1
  exact reaches_coverPair_iff (fun operation => operation)
    (fun _ _ path => reaches_decreases_order backward path)
    (fun first second => first.trans second)

theorem reduced_transitively_minimal (effects : Nat → Effect Key Value) :
    TransitivelyMinimal (Reduced effects) := by
  intro source target retained alternate
  cases alternate with
  | direct edge => exact edge.2 ⟨rfl, rfl⟩
  | @step _ other _ first remaining =>
      exact retained.2 other first.1.1
        (Reaches.mono (fun _ _ edge => edge.1.1) remaining)

theorem reduced_acyclic (effects : Nat → Effect Key Value) : Acyclic (Reduced effects) :=
  acyclic_of_pointsBackward (operationOrder := fun operation => operation)
    (fun _ _ edge => edge.1.1)

def CalculatedPrefix (effects : Nat → Effect Key Value) : Nat → Nat → Nat → Prop
  | 0 => fun _ _ => False
  | count + 1 => fun later earlier =>
      if later = count then
        Collected effects count earlier ∧
          ∀ other, Collected effects count other →
            ¬Reaches (CalculatedPrefix effects count) other earlier
      else CalculatedPrefix effects count later earlier

private theorem restricted_reduced_reaches {effects : Nat → Effect Key Value}
    {count later earlier : Nat} (bound : later < count) :
    Reaches (fun source target => source < count ∧ Reduced effects source target) later earlier ↔
      Reaches (Reduced effects) later earlier := by
  constructor
  · intro path
    induction path with
    | direct edge => exact .direct edge.2
    | step edge _ remaining =>
        exact .step edge.2 (remaining (Nat.lt_trans edge.2.1.1 bound))
  · intro path
    induction path with
    | direct edge => exact .direct ⟨bound, edge⟩
    | @step source middle target edge _ remaining =>
        exact .step ⟨bound, edge⟩ (remaining (Nat.lt_trans edge.1.1 bound))

theorem calculatedPrefix_iff {effects : Nat → Effect Key Value}
    (count later earlier : Nat) :
    CalculatedPrefix effects count later earlier ↔ later < count ∧ Reduced effects later earlier := by
  induction count generalizing later earlier with
  | zero => simp [CalculatedPrefix]
  | succ count induction_hypothesis =>
      have prefix_equal : CalculatedPrefix effects count =
          fun source target => source < count ∧ Reduced effects source target := by
        funext source target
        exact propext (induction_hypothesis source target)
      by_cases latest : later = count
      · subst later
        simp only [CalculatedPrefix, Nat.lt_succ_self, true_and]
        unfold Reduced
        constructor
        · rintro ⟨candidate, maximal⟩
          refine ⟨candidate, ?_⟩
          intro other other_candidate path
          apply maximal other other_candidate
          rw [prefix_equal]
          exact (restricted_reduced_reaches other_candidate.1).mpr
            (reduced_reachability_iff.mpr path)
        · rintro ⟨candidate, maximal⟩
          refine ⟨candidate, ?_⟩
          intro other other_candidate path
          rw [prefix_equal] at path
          exact maximal other other_candidate
            (reduced_reachability_iff.mp
              ((restricted_reduced_reaches other_candidate.1).mp path))
      · simp only [CalculatedPrefix, if_neg latest]
        rw [induction_hypothesis]
        constructor
        · rintro ⟨bound, edge⟩
          exact ⟨Nat.lt_succ_of_lt bound, edge⟩
        · rintro ⟨bound, edge⟩
          exact ⟨Nat.lt_of_le_of_ne (Nat.le_of_lt_succ bound) latest, edge⟩

def Calculated (effects : Nat → Effect Key Value) (later earlier : Nat) : Prop :=
  CalculatedPrefix effects (later + 1) later earlier

theorem calculatedPrefix_acyclic (effects : Nat → Effect Key Value) (count : Nat) :
    Acyclic (CalculatedPrefix effects count) :=
  acyclic_of_pointsBackward (operationOrder := fun operation => operation)
    (fun source target edge => ((calculatedPrefix_iff count source target).mp edge).2.1.1)

theorem scan_iff_calculated {effects : Nat → Effect Key Value} (later : Nat)
    (candidates : List Nat)
    (members : ∀ earlier, earlier ∈ candidates ↔ Collected effects later earlier)
    (ordered : candidates.Pairwise
      (fun first second => ¬Reaches (CalculatedPrefix effects later) second first))
    (earlier : Nat) :
    earlier ∈ Comparison.scan (Reaches (CalculatedPrefix effects later)) candidates [] ↔
      Calculated effects later earlier := by
  rw [Comparison.scan_iff_maximal (calculatedPrefix_acyclic effects later) candidates ordered]
  simp [Calculated, CalculatedPrefix, members]

theorem calculated_iff_reduced {effects : Nat → Effect Key Value} {later earlier : Nat} :
    Calculated effects later earlier ↔ Reduced effects later earlier := by
  simpa [Calculated] using (calculatedPrefix_iff (effects := effects) (later + 1) later earlier)

theorem calculated_transitively_minimal (effects : Nat → Effect Key Value) :
    TransitivelyMinimal (Calculated effects) := by
  have equal : Calculated effects = Reduced effects := by
    funext source target
    exact propext calculated_iff_reduced
  rw [equal]
  exact reduced_transitively_minimal effects

theorem calculated_reachability_iff {effects : Nat → Effect Key Value} {later earlier : Nat} :
    Reaches (Calculated effects) later earlier ↔ Reaches (Collected effects) later earlier := by
  have equal : Calculated effects = Reduced effects := by
    funext source target
    exact propext calculated_iff_reduced
  rw [equal]
  exact reduced_reachability_iff

theorem calculated_acyclic (effects : Nat → Effect Key Value) : Acyclic (Calculated effects) :=
  acyclic_of_pointsBackward (operationOrder := fun operation => operation)
    (fun _ _ edge => (calculated_iff_reduced.mp edge).1.1)

theorem reduced_reaches_conflicts_iff {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {later earlier : Nat} :
    Reaches (Reduced effects) later earlier ↔
      Reaches (EarlierConflict effects) later earlier :=
  reduced_reachability_iff.trans (collected_reachability_iff valid)

theorem incomparable_reduced_independent {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {first second : Nat}
    (different : first ≠ second)
    (first_not_after : ¬Reaches (Reduced effects) first second)
    (second_not_after : ¬Reaches (Reduced effects) second first) :
    Independent (effects first) (effects second) := by
  apply incomparable_collected_independent valid different
  · intro path
    exact first_not_after (reduced_reachability_iff.mpr path)
  · intro path
    exact second_not_after (reduced_reachability_iff.mpr path)

theorem reduced_respecting_permutation_executes {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid)
    {original reordered : List Nat} {before after : Key → Value}
    (permuted : original.Perm reordered) (distinct : original.Nodup)
    (original_respects : RespectsPrecedence (Reaches (Reduced effects)) original)
    (reordered_respects : RespectsPrecedence (Reaches (Reduced effects)) reordered)
    (execution : Execution effects original before after) :
    Execution effects reordered before after := by
  apply respecting_permutation_executes valid ?_ permuted distinct
    original_respects reordered_respects execution
  exact fun _ _ => incomparable_reduced_independent valid

theorem calculated_respecting_permutation_executes {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid)
    {original reordered : List Nat} {before after : Key → Value}
    (permuted : original.Perm reordered) (distinct : original.Nodup)
    (original_respects : RespectsPrecedence (Reaches (Calculated effects)) original)
    (reordered_respects : RespectsPrecedence (Reaches (Calculated effects)) reordered)
    (execution : Execution effects original before after) :
    Execution effects reordered before after := by
  have equal : Calculated effects = Reduced effects := by
    funext source target
    exact propext calculated_iff_reduced
  rw [equal] at original_respects reordered_respects
  exact reduced_respecting_permutation_executes valid permuted distinct
    original_respects reordered_respects execution

theorem reduced_edge_has_unsafe_reversal {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid)
    {schedule : List Nat} {before after : Key → Value}
    (distinct : schedule.Nodup)
    (respects : RespectsPrecedence (Reaches (Reduced effects)) schedule)
    (execution : Execution effects schedule before after)
    {following previous : Nat} (edge : Reduced effects following previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence (Reaches (Reduced effects))
        (preceding ++ previous :: following :: remaining) ∧
      ∀ finalState,
        ¬Execution effects (preceding ++ following :: previous :: remaining) before finalState := by
  have cover := reduced_iff_cover.mp edge
  apply conflicting_cover_has_unsafe_reversal valid
    (fun _ _ => incomparable_reduced_independent valid) distinct respects execution
    (reduced_acyclic effects) (fun first second => first.trans second) (.direct edge)
    ?_ following_member previous_member (collected_is_conflict valid edge.1).2
  intro middle first last
  exact cover.2 (reduced_reachability_iff.mp first) (reduced_reachability_iff.mp last)

theorem calculated_edge_has_unsafe_reversal {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid)
    {schedule : List Nat} {before after : Key → Value}
    (distinct : schedule.Nodup)
    (respects : RespectsPrecedence (Reaches (Calculated effects)) schedule)
    (execution : Execution effects schedule before after)
    {following previous : Nat} (edge : Calculated effects following previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence (Reaches (Calculated effects))
        (preceding ++ previous :: following :: remaining) ∧
      ∀ finalState,
        ¬Execution effects (preceding ++ following :: previous :: remaining) before finalState := by
  have equal : Calculated effects = Reduced effects := by
    funext source target
    exact propext calculated_iff_reduced
  rw [equal] at respects edge ⊢
  exact reduced_edge_has_unsafe_reversal valid distinct respects execution edge
    following_member previous_member

end Define.OperationGraph.ExactEffects
