import characterization
import cover_order
import finite_history_schedule
import finite_schedule_order

set_option warningAsError true
set_option autoImplicit false

/-!
# Cover-Pair Schedule Order

This module formalizes the order-theoretic part of the necessity argument for
maximum safe concurrency. A cover pair is a reachable pair with no occurrence
strictly between its endpoints. The generic definition and omitted-cover-pair
theorem are in `cover_order`. For the calculated dependency relation, every
cover pair is a related-and-previous pair.

The schedule theorem constructs a finite dependency-respecting permutation of
the history prefix ending with the later operation. Every other predecessor of
that operation appears first, followed immediately by the covered pair. All
other operations retain their relative history order. The necessity theorem
then proves that every proper transitive subrelation omits some cover pair and
allows the schedule obtained by reversing that adjacent pair.
-/

namespace Define.OperationGraph

theorem calculated_coverPair_is_relatedPrevious
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {following previous : ParticleOperation}
    (cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) following previous) :
    isOperation following ∧
      isOperation previous ∧ RelatedPrevious following previous := by
  have related_previous_path :=
    (calculatedDependency_reaches_iff_reaches_relatedPrevious history).mp
      cover_pair.1
  cases related_previous_path with
  | direct related_previous => exact related_previous
  | @step _ intermediate _ first_relation remaining_path =>
      exfalso
      apply cover_pair.2 intermediate
      · exact
          (calculatedDependency_reaches_iff_reaches_relatedPrevious history).mpr
            (.direct first_relation)
      · exact
          (calculatedDependency_reaches_iff_reaches_relatedPrevious history).mpr
            remaining_path

/--
Every calculated cover pair can be made adjacent in a dependency-respecting
permutation of the finite history prefix ending with the later operation.
-/
theorem calculated_coverPair_has_adjacent_respecting_historyPrefix
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {following previous : ParticleOperation}
    (cover_pair :
      CoverPair (Reaches (CalculatedDependency history)) following previous) :
    ∃ preceding remaining,
      (history.operationsBefore (following.operationOrder + 1)).Perm
          (preceding ++ previous :: following :: remaining) ∧
        RespectsPrecedence (Reaches (CalculatedDependency history))
          (preceding ++ previous :: following :: remaining) := by
  classical
  have cover_facts :=
    calculated_coverPair_is_relatedPrevious history cover_pair
  have previous_before_following :
      previous.operationOrder < following.operationOrder :=
    cover_facts.2.2.1
  have reference_nodup :=
    history.operationsBefore_nodup (following.operationOrder + 1)
  have following_reference_member :
      following ∈
        history.operationsBefore (following.operationOrder + 1) :=
    history.operationAt_mem_operationsBefore
      (history.member_operation_at following cover_facts.1)
      (Nat.lt_succ_self following.operationOrder)
  have previous_reference_member :
      previous ∈
        history.operationsBefore (following.operationOrder + 1) :=
    history.operationAt_mem_operationsBefore
      (history.member_operation_at previous cover_facts.2.1)
      (Nat.lt_trans previous_before_following
        (Nat.lt_succ_self following.operationOrder))
  let otherPredecessors :=
    (history.operationsBefore (following.operationOrder + 1)).filter
      (fun operation =>
        decide
          (Reaches (CalculatedDependency history) following operation ∧
            operation ≠ previous))
  have other_predecessor_iff
      {operation : ParticleOperation} :
      operation ∈ otherPredecessors ↔
        operation ∈
            history.operationsBefore (following.operationOrder + 1) ∧
          Reaches (CalculatedDependency history) following operation ∧
            operation ≠ previous := by
    simp [otherPredecessors]
  have other_predecessors_are_sublist :
      List.Sublist otherPredecessors
        (history.operationsBefore (following.operationOrder + 1)) := by
    exact List.filter_sublist
  have other_predecessors_nodup : otherPredecessors.Nodup :=
    other_predecessors_are_sublist.nodup reference_nodup
  have previous_not_other_predecessor : previous ∉ otherPredecessors := by
    intro previous_member
    exact (other_predecessor_iff.mp previous_member).2.2 rfl
  have following_not_other_predecessor : following ∉ otherPredecessors := by
    intro following_member
    have following_reaches_itself :=
      (other_predecessor_iff.mp following_member).2.1
    have order_decreases :=
      reaches_decreases_order
        (calculatedDependency_pointsBackward history) following_reaches_itself
    exact Nat.lt_irrefl following.operationOrder order_decreases
  have operations_distinct : previous ≠ following := by
    intro operations_equal
    subst following
    exact Nat.lt_irrefl previous.operationOrder previous_before_following
  have adjacent_prefix_nodup :
      (otherPredecessors ++ [previous, following]).Nodup := by
    rw [List.nodup_append]
    refine ⟨other_predecessors_nodup, by simp [operations_distinct], ?_⟩
    intro otherOperation other_member pairOperation pair_member
    have pair_member_parts :
        pairOperation = previous ∨ pairOperation = following := by
      simpa only [List.mem_cons, List.mem_singleton, List.not_mem_nil, or_false]
        using pair_member
    rcases pair_member_parts with pair_is_previous | pair_is_following
    · subst pairOperation
      intro other_is_previous
      subst otherOperation
      exact previous_not_other_predecessor other_member
    · subst pairOperation
      intro other_is_following
      subst otherOperation
      exact following_not_other_predecessor other_member
  have adjacent_prefix_subset :
      ∀ operation,
        operation ∈ otherPredecessors ++ [previous, following] →
          operation ∈
            history.operationsBefore (following.operationOrder + 1) := by
    intro operation operation_member
    have operation_member_parts :
        operation ∈ otherPredecessors ∨
          operation = previous ∨ operation = following := by
      simpa only [List.mem_append, List.mem_cons, List.mem_singleton,
        List.not_mem_nil, or_false] using operation_member
    rcases operation_member_parts with
      other_member | operation_is_previous | operation_is_following
    · exact (other_predecessor_iff.mp other_member).1
    · subst operation
      exact previous_reference_member
    · subst operation
      exact following_reference_member
  have other_predecessors_respect :
      RespectsPrecedence (Reaches (CalculatedDependency history))
        otherPredecessors :=
    (history.operationsBefore_respects_calculatedDependency
        (following.operationOrder + 1)).sublist
      other_predecessors_are_sublist
  have through_previous_respects :
      RespectsPrecedence (Reaches (CalculatedDependency history))
        (otherPredecessors ++ [previous]) := by
    apply other_predecessors_respect.snoc
    intro otherOperation other_member other_reaches_previous
    exact
      cover_pair.2 otherOperation
        (other_predecessor_iff.mp other_member).2.1
        other_reaches_previous
  have adjacent_prefix_respects :
      RespectsPrecedence (Reaches (CalculatedDependency history))
        (otherPredecessors ++ [previous, following]) := by
    have through_following_respects :
        RespectsPrecedence (Reaches (CalculatedDependency history))
          ((otherPredecessors ++ [previous]) ++ [following]) := by
      apply through_previous_respects.snoc
      intro earlierOperation earlier_member earlier_reaches_following
      have earlier_reference_member :
          earlierOperation ∈
            history.operationsBefore (following.operationOrder + 1) := by
        rcases List.mem_append.mp earlier_member with
          other_member | previous_member
        · exact (other_predecessor_iff.mp other_member).1
        · have earlier_is_previous : earlierOperation = previous := by
            simpa using previous_member
          subst earlierOperation
          exact previous_reference_member
      have earlier_before_bound :=
        history.operationsBefore_operationOrder_lt earlier_reference_member
      have following_before_earlier :=
        reaches_decreases_order
          (calculatedDependency_pointsBackward history)
          earlier_reaches_following
      omega
    simpa [List.append_assoc] using through_following_respects
  rcases
      exists_order_preserving_complement adjacent_prefix_nodup
        adjacent_prefix_subset with
    ⟨remaining, remaining_is_sublist, schedules_permuted⟩
  have remaining_respects :=
    (history.operationsBefore_respects_calculatedDependency
        (following.operationOrder + 1)).sublist
      remaining_is_sublist
  have completed_nodup := schedules_permuted.nodup reference_nodup
  have prefix_disjoint_from_remaining :=
    (List.nodup_append.mp completed_nodup).2.2
  have adjacent_prefix_does_not_follow_remaining :
      ∀ prefixOperation,
        prefixOperation ∈ otherPredecessors ++ [previous, following] →
          ∀ remainingOperation,
            remainingOperation ∈ remaining →
              ¬Reaches (CalculatedDependency history) prefixOperation
                remainingOperation := by
    intro prefixOperation prefix_member remainingOperation remaining_member
    intro prefix_reaches_remaining
    have following_reaches_remaining :
        Reaches (CalculatedDependency history) following remainingOperation := by
      have prefix_member_parts :
          prefixOperation ∈ otherPredecessors ∨
            prefixOperation = previous ∨ prefixOperation = following := by
        simpa only [List.mem_append, List.mem_cons, List.mem_singleton,
          List.not_mem_nil, or_false] using prefix_member
      rcases prefix_member_parts with
        other_member | prefix_is_previous | prefix_is_following
      · exact
          ((other_predecessor_iff.mp other_member).2.1).trans
            prefix_reaches_remaining
      · subst prefixOperation
        exact cover_pair.1.trans prefix_reaches_remaining
      · subst prefixOperation
        exact prefix_reaches_remaining
    have remaining_prefix_member :
        remainingOperation ∈
          otherPredecessors ++ [previous, following] := by
      by_cases remaining_is_previous : remainingOperation = previous
      · subst remainingOperation
        simp
      · apply List.mem_append_left
        exact
          other_predecessor_iff.mpr
            ⟨remaining_is_sublist.subset remaining_member,
              following_reaches_remaining, remaining_is_previous⟩
    exact
      (prefix_disjoint_from_remaining remainingOperation
        remaining_prefix_member remainingOperation remaining_member) rfl
  have completed_respects :=
    adjacent_prefix_respects.append remaining_respects
      adjacent_prefix_does_not_follow_remaining
  exact
    ⟨otherPredecessors, remaining,
      by simpa [List.append_assoc] using schedules_permuted,
      by simpa [List.append_assoc] using completed_respects⟩

/--
Every proper transitive subrelation of calculated reachability allows a finite
history-prefix schedule obtained by reversing an adjacent cover pair that the
subrelation omits.
-/
theorem calculated_proper_subrelation_has_reversed_cover_schedule
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {weaker : ParticleOperation → ParticleOperation → Prop}
    (weaker_transitive :
      ∀ {following intermediate previous},
        weaker following intermediate →
          weaker intermediate previous → weaker following previous)
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous →
          Reaches (CalculatedDependency history) following previous)
    (subrelation_is_proper :
      ∃ following previous,
        Reaches (CalculatedDependency history) following previous ∧
          ¬weaker following previous) :
    ∃ following previous preceding remaining,
      CoverPair (Reaches (CalculatedDependency history)) following previous ∧
        ¬weaker following previous ∧
          (history.operationsBefore (following.operationOrder + 1)).Perm
            (preceding ++ previous :: following :: remaining) ∧
            RespectsPrecedence (Reaches (CalculatedDependency history))
                (preceding ++ previous :: following :: remaining) ∧
              RespectsPrecedence weaker
                (preceding ++ following :: previous :: remaining) := by
  rcases subrelation_is_proper with
    ⟨omittedFollowing, omittedPrevious, omitted_pair⟩
  have calculated_reachability_points_backward :
      PointsBackward ParticleOperation.operationOrder
        (Reaches (CalculatedDependency history)) := by
    intro following previous reachable
    exact
      reaches_decreases_order
        (calculatedDependency_pointsBackward history) reachable
  rcases
      omitted_pair_contains_omitted_coverPair
        ParticleOperation.operationOrder
        (precedence := Reaches (CalculatedDependency history))
        (weaker := weaker) calculated_reachability_points_backward
        weaker_transitive (following := omittedFollowing)
        (previous := omittedPrevious) omitted_pair with
    ⟨following, previous, cover_pair, pair_omitted⟩
  rcases
      calculated_coverPair_has_adjacent_respecting_historyPrefix history
        cover_pair with
    ⟨preceding, remaining, schedules_permuted, original_respects⟩
  have original_respects_weaker :
      RespectsPrecedence weaker
        (preceding ++ previous :: following :: remaining) :=
    original_respects.mono weaker_is_subrelation
  have reversed_respects_weaker :
      RespectsPrecedence weaker
        (preceding ++ following :: previous :: remaining) :=
    original_respects_weaker.swap_adjacent preceding pair_omitted
  exact
    ⟨following, previous, preceding, remaining, cover_pair, pair_omitted,
      schedules_permuted, original_respects, reversed_respects_weaker⟩

end Define.OperationGraph
