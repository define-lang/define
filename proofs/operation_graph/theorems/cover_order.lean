import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Cover Order

This module defines cover pairs for an arbitrary relation and proves the
well-founded order theorem used by maximum-safe-concurrency necessity. If a
transitive relation omits a pair from a relation that points backward through a
natural-number order, it omits a cover pair. The occurrence type itself need not
be finite.
-/

namespace Define.OperationGraph

universe u

def CoverPair {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop)
    (following previous : Occurrence) : Prop :=
  precedence following previous ∧
    ∀ intermediate,
      precedence following intermediate →
        precedence intermediate previous → False

/--
If a transitive relation omits one pair from a relation that points backward in
a natural-number order, then it omits a cover pair.
-/
theorem omitted_pair_contains_omitted_coverPair
    {Occurrence : Type u} (operationOrder : Occurrence → Nat)
    {precedence weaker : Occurrence → Occurrence → Prop}
    (precedence_points_backward : PointsBackward operationOrder precedence)
    (weaker_transitive :
      ∀ {following intermediate previous},
        weaker following intermediate →
          weaker intermediate previous → weaker following previous)
    {following previous : Occurrence}
    (omitted : precedence following previous ∧ ¬weaker following previous) :
    ∃ coverFollowing coverPrevious,
      CoverPair precedence coverFollowing coverPrevious ∧
        ¬weaker coverFollowing coverPrevious := by
  by_cases cover_pair : CoverPair precedence following previous
  · exact ⟨following, previous, cover_pair, omitted.2⟩
  · have has_intermediate :
        ∃ intermediate,
          precedence following intermediate ∧
            precedence intermediate previous := by
      rw [CoverPair, and_iff_right omitted.1] at cover_pair
      rcases Classical.not_forall.mp cover_pair with
        ⟨intermediate, not_all_relations⟩
      rcases Classical.not_imp.mp not_all_relations with
        ⟨following_precedes_intermediate,
          not_intermediate_precedes_previous⟩
      rcases Classical.not_imp.mp not_intermediate_precedes_previous with
        ⟨intermediate_precedes_previous, _⟩
      exact
        ⟨intermediate, following_precedes_intermediate,
          intermediate_precedes_previous⟩
    rcases has_intermediate with
      ⟨intermediate, following_precedes_intermediate,
        intermediate_precedes_previous⟩
    by_cases following_precedes_intermediate_in_weaker :
      weaker following intermediate
    · have intermediate_does_not_precede_previous_in_weaker :
          ¬weaker intermediate previous := by
        intro intermediate_precedes_previous_in_weaker
        exact
          omitted.2
            (weaker_transitive following_precedes_intermediate_in_weaker
              intermediate_precedes_previous_in_weaker)
      exact
        omitted_pair_contains_omitted_coverPair operationOrder
          precedence_points_backward weaker_transitive
          ⟨intermediate_precedes_previous,
            intermediate_does_not_precede_previous_in_weaker⟩
    · exact
        omitted_pair_contains_omitted_coverPair operationOrder
          precedence_points_backward weaker_transitive
          ⟨following_precedes_intermediate,
            following_precedes_intermediate_in_weaker⟩
termination_by
  operationOrder following - operationOrder previous
decreasing_by
  all_goals
    have intermediate_before_following :=
      precedence_points_backward following intermediate
        following_precedes_intermediate
    have previous_before_intermediate :=
      precedence_points_backward intermediate previous
        intermediate_precedes_previous
    omega

end Define.OperationGraph
