import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Finite Schedule Order

This module proves the finite order-theoretic exchange theorem used by the
maximum-safe-concurrency argument. Two duplicate-free schedules containing the
same occurrences and respecting the same precedence relation are connected by
a finite sequence of adjacent exchanges. Every exchanged pair is incomparable
in the precedence relation.

The theorem is independent of Particle Operation occupancy semantics and does
not require the precedence relation to be finite beyond the two schedule lists.
-/

namespace Define.OperationGraph

universe u

/--
A schedule respects a precedence relation when no occurrence appears before an
occurrence that the relation requires it to follow.
-/
inductive RespectsPrecedence {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) : List Occurrence → Prop where
  | nil : RespectsPrecedence precedence []
  | cons {occurrence : Occurrence} {remaining : List Occurrence}
      (occurrence_does_not_follow_remaining :
        ∀ laterOccurrence,
          laterOccurrence ∈ remaining →
            ¬precedence occurrence laterOccurrence)
      (remaining_respects : RespectsPrecedence precedence remaining) :
      RespectsPrecedence precedence (occurrence :: remaining)

/--
One schedule is obtained from another by exchanging two adjacent occurrences
that are incomparable in the precedence relation.
-/
inductive AdjacentIncomparableSwap {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) :
    List Occurrence → List Occurrence → Prop where
  | swap (schedulePrefix : List Occurrence)
      (firstOccurrence secondOccurrence : Occurrence)
      (scheduleSuffix : List Occurrence)
      (first_does_not_follow_second :
        ¬precedence firstOccurrence secondOccurrence)
      (second_does_not_follow_first :
        ¬precedence secondOccurrence firstOccurrence) :
      AdjacentIncomparableSwap precedence
        (schedulePrefix ++
          firstOccurrence :: secondOccurrence :: scheduleSuffix)
        (schedulePrefix ++
          secondOccurrence :: firstOccurrence :: scheduleSuffix)

/--
The reflexive transitive closure of adjacent incomparable exchanges.
-/
inductive IncomparableSwapSequence {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) :
    List Occurrence → List Occurrence → Prop where
  | refl (schedule : List Occurrence) :
      IncomparableSwapSequence precedence schedule schedule
  | tail {firstSchedule middleSchedule finalSchedule : List Occurrence}
      (earlier_exchanges :
        IncomparableSwapSequence precedence firstSchedule middleSchedule)
      (final_exchange :
        AdjacentIncomparableSwap precedence middleSchedule finalSchedule) :
      IncomparableSwapSequence precedence firstSchedule finalSchedule

theorem IncomparableSwapSequence.trans
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule middleSchedule finalSchedule : List Occurrence}
    (first_exchanges :
      IncomparableSwapSequence precedence firstSchedule middleSchedule)
    (remaining_exchanges :
      IncomparableSwapSequence precedence middleSchedule finalSchedule) :
    IncomparableSwapSequence precedence firstSchedule finalSchedule := by
  induction remaining_exchanges with
  | refl => exact first_exchanges
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact .tail induction_hypothesis final_exchange

theorem AdjacentIncomparableSwap.cons
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (precedingOccurrence : Occurrence)
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule) :
    AdjacentIncomparableSwap precedence
      (precedingOccurrence :: firstSchedule)
      (precedingOccurrence :: secondSchedule) := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix
      first_does_not_follow_second second_does_not_follow_first =>
      simpa only [List.cons_append] using
        AdjacentIncomparableSwap.swap
          (precedingOccurrence :: schedulePrefix) firstOccurrence
          secondOccurrence scheduleSuffix first_does_not_follow_second
          second_does_not_follow_first

theorem AdjacentIncomparableSwap.perm
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule) :
    firstSchedule.Perm secondSchedule := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix =>
      exact
        (List.Perm.swap secondOccurrence firstOccurrence
          scheduleSuffix).append_left schedulePrefix

theorem IncomparableSwapSequence.cons
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (precedingOccurrence : Occurrence)
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule) :
    IncomparableSwapSequence precedence
      (precedingOccurrence :: firstSchedule)
      (precedingOccurrence :: secondSchedule) := by
  induction exchanges with
  | refl => exact .refl _
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact .tail induction_hypothesis (final_exchange.cons precedingOccurrence)

theorem IncomparableSwapSequence.perm
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule) :
    firstSchedule.Perm secondSchedule := by
  induction exchanges with
  | refl => exact .rfl
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact induction_hypothesis.trans final_exchange.perm

theorem RespectsPrecedence.swap_head
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstOccurrence secondOccurrence : Occurrence}
    {remaining : List Occurrence}
    (second_does_not_follow_first :
      ¬precedence secondOccurrence firstOccurrence)
    (respects :
      RespectsPrecedence precedence
        (firstOccurrence :: secondOccurrence :: remaining)) :
    RespectsPrecedence precedence
      (secondOccurrence :: firstOccurrence :: remaining) := by
  cases respects with
  | cons first_does_not_follow_remaining after_first =>
      cases after_first with
      | cons second_does_not_follow_remaining remaining_respects =>
          exact
            .cons
              (by
                intro laterOccurrence later_member
                simp only [List.mem_cons] at later_member
                rcases later_member with later_is_first | later_member
                · subst laterOccurrence
                  exact second_does_not_follow_first
                · exact
                    second_does_not_follow_remaining laterOccurrence
                      later_member)
              (.cons
                (fun laterOccurrence later_member =>
                  first_does_not_follow_remaining laterOccurrence
                    (by
                      simp only [List.mem_cons]
                      exact Or.inr later_member))
                remaining_respects)

theorem RespectsPrecedence.swap_adjacent
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstOccurrence secondOccurrence : Occurrence}
    {scheduleSuffix : List Occurrence}
    (schedulePrefix : List Occurrence)
    (second_does_not_follow_first :
      ¬precedence secondOccurrence firstOccurrence)
    (respects :
      RespectsPrecedence precedence
        (schedulePrefix ++
          firstOccurrence :: secondOccurrence :: scheduleSuffix)) :
    RespectsPrecedence precedence
      (schedulePrefix ++
        secondOccurrence :: firstOccurrence :: scheduleSuffix) := by
  induction schedulePrefix with
  | nil => exact respects.swap_head second_does_not_follow_first
  | cons precedingOccurrence schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at respects ⊢
      cases respects with
      | cons preceding_does_not_follow_remaining remaining_respects =>
          exact
            .cons
              (by
                intro laterOccurrence later_member
                apply
                  preceding_does_not_follow_remaining laterOccurrence
                simpa only [List.mem_append, List.mem_cons, or_comm, or_left_comm,
                  or_assoc] using later_member)
              (induction_hypothesis remaining_respects)

theorem AdjacentIncomparableSwap.preserves_respect
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule)
    (respects : RespectsPrecedence precedence firstSchedule) :
    RespectsPrecedence precedence secondSchedule := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix
      _ second_does_not_follow_first =>
      exact
        respects.swap_adjacent schedulePrefix second_does_not_follow_first

theorem IncomparableSwapSequence.preserves_respect
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule)
    (respects : RespectsPrecedence precedence firstSchedule) :
    RespectsPrecedence precedence secondSchedule := by
  induction exchanges with
  | refl => exact respects
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact final_exchange.preserves_respect induction_hypothesis

private theorem move_occurrence_to_head
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {desiredOccurrence : Occurrence}
    {scheduleSuffix : List Occurrence}
    (schedulePrefix : List Occurrence)
    (respects :
      RespectsPrecedence precedence
        (schedulePrefix ++ desiredOccurrence :: scheduleSuffix))
    (desired_does_not_follow_prefix :
      ∀ prefixOccurrence,
        prefixOccurrence ∈ schedulePrefix →
          ¬precedence desiredOccurrence prefixOccurrence) :
    IncomparableSwapSequence precedence
      (schedulePrefix ++ desiredOccurrence :: scheduleSuffix)
      (desiredOccurrence :: schedulePrefix ++ scheduleSuffix) := by
  induction schedulePrefix with
  | nil => exact .refl _
  | cons precedingOccurrence schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at respects ⊢
      cases respects with
      | cons preceding_does_not_follow_remaining remaining_respects =>
          have earlier_exchanges :=
            (induction_hypothesis remaining_respects
              (fun prefixOccurrence prefix_member =>
                desired_does_not_follow_prefix prefixOccurrence
                  (by
                    simp only [List.mem_cons]
                    exact Or.inr prefix_member))).cons precedingOccurrence
          have final_exchange :
              AdjacentIncomparableSwap precedence
                (precedingOccurrence :: desiredOccurrence ::
                  schedulePrefix ++ scheduleSuffix)
                (desiredOccurrence :: precedingOccurrence ::
                  schedulePrefix ++ scheduleSuffix) := by
            exact
              .swap [] precedingOccurrence desiredOccurrence
                (schedulePrefix ++ scheduleSuffix)
                (preceding_does_not_follow_remaining desiredOccurrence
                  (by simp))
                (desired_does_not_follow_prefix precedingOccurrence
                  (by simp))
          exact .tail earlier_exchanges final_exchange

/--
Any two duplicate-free finite schedules containing the same occurrences and
respecting the same precedence relation are connected by adjacent exchanges of
incomparable occurrences.
-/
theorem respecting_permutations_connected
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop} :
    ∀ {firstSchedule secondSchedule : List Occurrence},
      firstSchedule.Perm secondSchedule →
        firstSchedule.Nodup →
          RespectsPrecedence precedence firstSchedule →
            RespectsPrecedence precedence secondSchedule →
              IncomparableSwapSequence precedence firstSchedule
                secondSchedule := by
  intro firstSchedule secondSchedule schedules_permuted first_nodup
    first_respects second_respects
  induction secondSchedule generalizing firstSchedule with
  | nil =>
      have first_is_empty := schedules_permuted.eq_nil
      subst firstSchedule
      exact .refl []
  | cons desiredOccurrence desiredRemaining induction_hypothesis =>
      have desired_member : desiredOccurrence ∈ firstSchedule :=
        schedules_permuted.mem_iff.mpr (by simp)
      obtain ⟨schedulePrefix, scheduleSuffix, first_schedule_shape⟩ :=
        List.append_of_mem desired_member
      subst first_schedule_shape
      have remaining_permuted :
          (schedulePrefix ++ scheduleSuffix).Perm desiredRemaining := by
        exact
          List.Perm.cons_inv
            (List.perm_middle.symm.trans schedules_permuted)
      have desired_does_not_follow_prefix :
          ∀ prefixOccurrence,
            prefixOccurrence ∈ schedulePrefix →
              ¬precedence desiredOccurrence prefixOccurrence := by
        cases second_respects with
        | cons desired_does_not_follow_remaining _ =>
            intro prefixOccurrence prefix_member
            apply desired_does_not_follow_remaining prefixOccurrence
            exact
              remaining_permuted.mem_iff.mp
                (by simp [prefix_member])
      have move_to_head :=
        move_occurrence_to_head schedulePrefix first_respects
          desired_does_not_follow_prefix
      have moved_respects := move_to_head.preserves_respect first_respects
      cases moved_respects with
      | cons _ moved_remaining_respects =>
          cases second_respects with
          | cons _ desired_remaining_respects =>
              have moved_nodup :
                  (desiredOccurrence :: schedulePrefix ++ scheduleSuffix).Nodup :=
                List.perm_middle.nodup first_nodup
              have remaining_exchanges :=
                induction_hypothesis remaining_permuted moved_nodup.tail
                  moved_remaining_respects desired_remaining_respects
              exact move_to_head.trans (remaining_exchanges.cons desiredOccurrence)

end Define.OperationGraph
