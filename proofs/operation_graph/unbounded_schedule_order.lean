import finite_schedule_order

set_option warningAsError true
set_option autoImplicit false

/-!
# Unbounded Schedule Order

This module represents a schedule indexed by the natural numbers. Such a
schedule contains every occurrence exactly once. Its finite prefixes are
duplicate-free and inherit the schedule's precedence order.

The completion theorem takes any finite prefix of the unbounded schedule and a
finite reference schedule containing it. When the reference is duplicate-free
and precedence-respecting, the prefix can be followed by the reference's other
occurrences without changing their relative reference order. The resulting
finite schedule is a precedence-respecting permutation of the reference.
-/

namespace Define.OperationGraph

universe u

structure UnboundedSchedule {Occurrence : Type u}
    (isOccurrence : Occurrence → Prop) where
  occurrenceAt : Nat → Occurrence
  occurrence_is_member : ∀ occurrenceOrder, isOccurrence (occurrenceAt occurrenceOrder)
  occurrenceAt_injective : Function.Injective occurrenceAt
  contains_every_occurrence :
    ∀ occurrence,
      isOccurrence occurrence →
        ∃ occurrenceOrder, occurrenceAt occurrenceOrder = occurrence

namespace UnboundedSchedule

def occurrencesBefore {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence) : Nat → List Occurrence
  | 0 => []
  | occurrenceCount + 1 =>
      schedule.occurrencesBefore occurrenceCount ++
        [schedule.occurrenceAt occurrenceCount]

def RespectsPrecedence {Occurrence : Type u}
    {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence)
    (precedence : Occurrence → Occurrence → Prop) : Prop :=
  ∀ {followingOrder previousOrder},
    precedence (schedule.occurrenceAt followingOrder)
        (schedule.occurrenceAt previousOrder) →
      previousOrder < followingOrder

theorem mem_occurrencesBefore_iff
    {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence) :
    ∀ {occurrenceCount occurrence},
      occurrence ∈ schedule.occurrencesBefore occurrenceCount ↔
        ∃ occurrenceOrder,
          occurrenceOrder < occurrenceCount ∧
            schedule.occurrenceAt occurrenceOrder = occurrence := by
  intro occurrenceCount
  induction occurrenceCount with
  | zero => simp [occurrencesBefore]
  | succ occurrenceCount induction_hypothesis =>
      intro occurrence
      constructor
      · intro occurrence_member
        have occurrence_member_parts :
            occurrence ∈ schedule.occurrencesBefore occurrenceCount ∨
              occurrence = schedule.occurrenceAt occurrenceCount := by
          simpa only [occurrencesBefore, List.mem_append, List.mem_singleton]
            using occurrence_member
        rcases occurrence_member_parts with
          earlier_member | occurrence_is_final
        · rcases induction_hypothesis.mp earlier_member with
            ⟨occurrenceOrder, order_before_count, occurrence_at⟩
          exact
            ⟨occurrenceOrder,
              Nat.lt_trans order_before_count
                (Nat.lt_succ_self occurrenceCount),
              occurrence_at⟩
        · exact
            ⟨occurrenceCount, Nat.lt_succ_self occurrenceCount,
              occurrence_is_final.symm⟩
      · rintro ⟨occurrenceOrder, order_before_count, occurrence_at⟩
        by_cases order_before_previous : occurrenceOrder < occurrenceCount
        · apply List.mem_append_left
          exact
            induction_hypothesis.mpr
              ⟨occurrenceOrder, order_before_previous, occurrence_at⟩
        · have occurrence_is_final : occurrenceOrder = occurrenceCount := by
            omega
          subst occurrenceOrder
          simp [occurrencesBefore, occurrence_at]

theorem occurrencesBefore_nodup
    {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence)
    (occurrenceCount : Nat) :
    (schedule.occurrencesBefore occurrenceCount).Nodup := by
  induction occurrenceCount with
  | zero => simp [occurrencesBefore]
  | succ occurrenceCount induction_hypothesis =>
      simp only [occurrencesBefore]
      rw [List.nodup_append]
      refine ⟨induction_hypothesis, by simp, ?_⟩
      intro earlierOccurrence earlier_member finalOccurrence final_member
      simp only [List.mem_singleton] at final_member
      subst finalOccurrence
      intro occurrences_equal
      rcases schedule.mem_occurrencesBefore_iff.mp earlier_member with
        ⟨earlierOrder, earlier_before_count, earlier_at⟩
      have orders_equal :=
        schedule.occurrenceAt_injective (earlier_at.trans occurrences_equal)
      omega

theorem occurrencesBefore_are_members
    {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence)
    {occurrenceCount occurrence}
    (occurrence_member :
      occurrence ∈ schedule.occurrencesBefore occurrenceCount) :
    isOccurrence occurrence := by
  rcases schedule.mem_occurrencesBefore_iff.mp occurrence_member with
    ⟨occurrenceOrder, _, occurrence_at⟩
  rw [← occurrence_at]
  exact schedule.occurrence_is_member occurrenceOrder

theorem occurrencesBefore_respects
    {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence)
    {precedence : Occurrence → Occurrence → Prop}
    (schedule_respects : schedule.RespectsPrecedence precedence)
    (occurrenceCount : Nat) :
    Define.OperationGraph.RespectsPrecedence precedence
      (schedule.occurrencesBefore occurrenceCount) := by
  induction occurrenceCount with
  | zero => exact .nil
  | succ occurrenceCount induction_hypothesis =>
      simp only [occurrencesBefore]
      apply induction_hypothesis.snoc
      intro earlierOccurrence earlier_member earlier_follows_final
      rcases schedule.mem_occurrencesBefore_iff.mp earlier_member with
        ⟨earlierOrder, earlier_before_count, earlier_at⟩
      have final_before_earlier : occurrenceCount < earlierOrder :=
        schedule_respects (by
          simpa only [earlier_at] using earlier_follows_final)
      omega

/--
A finite prefix of an unbounded precedence-respecting schedule can be completed
to a precedence-respecting permutation of any duplicate-free, respecting
reference schedule that contains the prefix.
-/
theorem exists_respecting_completion
    {Occurrence : Type u} {isOccurrence : Occurrence → Prop}
    (schedule : UnboundedSchedule isOccurrence)
    {precedence : Occurrence → Occurrence → Prop}
    (schedule_respects : schedule.RespectsPrecedence precedence)
    {occurrenceCount : Nat} {referenceSchedule : List Occurrence}
    (reference_nodup : referenceSchedule.Nodup)
    (reference_members :
      ∀ occurrence,
        occurrence ∈ referenceSchedule → isOccurrence occurrence)
    (reference_respects :
      Define.OperationGraph.RespectsPrecedence precedence referenceSchedule)
    (candidate_subset :
      ∀ occurrence,
        occurrence ∈ schedule.occurrencesBefore occurrenceCount →
          occurrence ∈ referenceSchedule) :
    ∃ remaining,
      referenceSchedule.Perm
          (schedule.occurrencesBefore occurrenceCount ++ remaining) ∧
        Define.OperationGraph.RespectsPrecedence precedence
          (schedule.occurrencesBefore occurrenceCount ++ remaining) := by
  rcases
      exists_order_preserving_complement
        (schedule.occurrencesBefore_nodup occurrenceCount) candidate_subset with
    ⟨remaining, remaining_is_sublist, schedules_permuted⟩
  have remaining_respects :=
    reference_respects.sublist remaining_is_sublist
  have completed_nodup := schedules_permuted.nodup reference_nodup
  have prefix_disjoint_from_remaining :=
    (List.nodup_append.mp completed_nodup).2.2
  have prefix_does_not_follow_remaining :
      ∀ prefixOccurrence,
        prefixOccurrence ∈ schedule.occurrencesBefore occurrenceCount →
          ∀ remainingOccurrence,
            remainingOccurrence ∈ remaining →
              ¬precedence prefixOccurrence remainingOccurrence := by
    intro prefixOccurrence prefix_member remainingOccurrence remaining_member
    intro prefix_follows_remaining
    rcases schedule.mem_occurrencesBefore_iff.mp prefix_member with
      ⟨prefixOrder, prefix_before_count, prefix_at⟩
    have remaining_reference_member :=
      remaining_is_sublist.subset remaining_member
    rcases
        schedule.contains_every_occurrence remainingOccurrence
          (reference_members remainingOccurrence remaining_reference_member) with
      ⟨remainingOrder, remaining_at⟩
    have remaining_before_prefix : remainingOrder < prefixOrder :=
      schedule_respects (by
        simpa only [prefix_at, remaining_at] using prefix_follows_remaining)
    have remaining_prefix_member :
        remainingOccurrence ∈
          schedule.occurrencesBefore occurrenceCount :=
      schedule.mem_occurrencesBefore_iff.mpr
        ⟨remainingOrder,
          Nat.lt_trans remaining_before_prefix prefix_before_count,
          remaining_at⟩
    exact
      (prefix_disjoint_from_remaining remainingOccurrence
        remaining_prefix_member remainingOccurrence remaining_member) rfl
  exact
    ⟨remaining, schedules_permuted,
      (schedule.occurrencesBefore_respects schedule_respects occurrenceCount).append
        remaining_respects prefix_does_not_follow_remaining⟩

end UnboundedSchedule

end Define.OperationGraph
