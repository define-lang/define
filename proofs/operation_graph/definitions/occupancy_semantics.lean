import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Occupancy Semantics

This module derives reusable facts about Particle Operation preconditions and
occupancy effects directly from the shared definitions. It is independent of
resolved histories, finite schedules, and every operation graph rule.
-/

namespace Define.OperationGraph

theorem operatesOn_iff_emptyPosition_or_fillPosition
    {operation : ParticleOperation} {position : Position} :
    OperatesOn operation position ↔
      EmptyPosition operation = some position ∨
        FillPosition operation = some position := by
  cases operation_kind : operation.kind <;>
    simp [OperatesOn, EmptyPosition, FillPosition, operation_kind, eq_comm]

theorem operationEnabled_emptyPosition_occupied
    {operation : ParticleOperation} {occupied : Position → Prop}
    {position : Position}
    (enabled : OperationEnabled operation occupied)
    (empty_position : EmptyPosition operation = some position) :
    occupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      simp [EmptyPosition, operation_kind] at empty_position
  | destroy target =>
      have target_is_position : target = position := by
        simpa [EmptyPosition, operation_kind] using empty_position
      subst position
      simpa [OperationEnabled, operation_kind] using enabled
  | move source target =>
      have source_is_position : source = position := by
        simpa [EmptyPosition, operation_kind] using empty_position
      subst position
      have enabled_parts :
          occupied source ∧
            Available occupied target ∧
              ¬occupied target ∧ ¬ParentOrSame source target := by
        simpa [OperationEnabled, operation_kind] using enabled
      exact enabled_parts.1

theorem operationEnabled_fillPosition_available
    {operation : ParticleOperation} {occupied : Position → Prop}
    {position : Position}
    (enabled : OperationEnabled operation occupied)
    (fill_position : FillPosition operation = some position) :
    Available occupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      have target_is_position : target = position := by
        simpa [FillPosition, operation_kind] using fill_position
      subst position
      have enabled_parts : Available occupied target ∧ ¬occupied target := by
        simpa [OperationEnabled, operation_kind] using enabled
      exact enabled_parts.1
  | destroy target =>
      simp [FillPosition, operation_kind] at fill_position
  | move source target =>
      have target_is_position : target = position := by
        simpa [FillPosition, operation_kind] using fill_position
      subst position
      have enabled_parts :
          occupied source ∧
            Available occupied target ∧
              ¬occupied target ∧ ¬ParentOrSame source target := by
        simpa [OperationEnabled, operation_kind] using enabled
      exact enabled_parts.2.1

theorem operationEnabled_fillPosition_empty
    {operation : ParticleOperation} {occupied : Position → Prop}
    {position : Position}
    (enabled : OperationEnabled operation occupied)
    (fill_position : FillPosition operation = some position) :
    ¬occupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      have target_is_position : target = position := by
        simpa [FillPosition, operation_kind] using fill_position
      subst position
      have enabled_parts : Available occupied target ∧ ¬occupied target := by
        simpa [OperationEnabled, operation_kind] using enabled
      exact enabled_parts.2
  | destroy target =>
      simp [FillPosition, operation_kind] at fill_position
  | move source target =>
      have target_is_position : target = position := by
        simpa [FillPosition, operation_kind] using fill_position
      subst position
      have enabled_parts :
          occupied source ∧
            Available occupied target ∧
              ¬occupied target ∧ ¬ParentOrSame source target := by
        simpa [OperationEnabled, operation_kind] using enabled
      exact enabled_parts.2.2.1

theorem operationEnabled_fillPosition_occupiedAfter
    {operation : ParticleOperation} {occupied : Position → Prop}
    {position : Position}
    (enabled : OperationEnabled operation occupied)
    (fill_position : FillPosition operation = some position) :
    OccupancyAfter operation occupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      have position_is_target : position = target := by
        have target_is_position : target = position := by
          simpa [FillPosition, operation_kind] using fill_position
        exact target_is_position.symm
      subst position
      simp [OccupancyAfter, operation_kind]
  | destroy target =>
      simp [FillPosition, operation_kind] at fill_position
  | move source target =>
      have position_is_target : position = target := by
        have target_is_position : target = position := by
          simpa [FillPosition, operation_kind] using fill_position
        exact target_is_position.symm
      subst position
      have source_occupied : occupied source := by
        have enabled_parts :
            occupied source ∧
              Available occupied target ∧
                ¬occupied target ∧ ¬ParentOrSame source target := by
          simpa [OperationEnabled, operation_kind] using enabled
        exact enabled_parts.1
      simp [OccupancyAfter, operation_kind, source_occupied]

theorem operationEnabled_move_source_not_parent_of_target
    {operation : ParticleOperation} {occupied : Position → Prop}
    {source target : Position}
    (enabled : OperationEnabled operation occupied)
    (move_kind : operation.kind = .move source target) :
    ¬ParentOrSame source target := by
  cases operation_kind : operation.kind with
  | create actualTarget =>
      rw [operation_kind] at move_kind
      cases move_kind
  | destroy actualTarget =>
      rw [operation_kind] at move_kind
      cases move_kind
  | move actualSource actualTarget =>
      have kind_arguments : actualSource = source ∧ actualTarget = target := by
        simpa [operation_kind] using move_kind
      have enabled_parts :
          occupied actualSource ∧
            Available occupied actualTarget ∧
              ¬occupied actualTarget ∧
                ¬ParentOrSame actualSource actualTarget := by
        simpa [OperationEnabled, operation_kind] using enabled
      simpa [kind_arguments.1, kind_arguments.2] using enabled_parts.2.2.2

/--
Applying one operation to a prefix-closed occupancy preserves prefix closure
when its Fill Position is available and a Move does not target a child position
of its source.
-/
theorem occupancyAfter_preserves_prefixClosure
    {operation : ParticleOperation} {occupiedBefore : Position → Prop}
    (prefix_closed : PrefixClosed occupiedBefore)
    (fill_available :
      ∀ target,
        FillPosition operation = some target → Available occupiedBefore target)
    (move_source_not_parent_of_target :
      ∀ source target,
        operation.kind = .move source target →
          ¬ParentOrSame source target) :
    PrefixClosed (OccupancyAfter operation occupiedBefore) := by
  intro parent child parent_of_child child_occupied
  cases operation_kind : operation.kind with
  | create target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      rcases child_occupied with child_is_target | child_occupied
      · subst child
        by_cases parent_is_target : parent = target
        · exact Or.inl parent_is_target
        · exact
            Or.inr
              (fill_available target (by simp [FillPosition, operation_kind])
                parent parent_of_child parent_is_target)
      · exact Or.inr (prefix_closed parent child parent_of_child child_occupied)
  | destroy target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      exact
        ⟨fun target_parent =>
          child_occupied.1 (target_parent.trans parent_of_child),
          prefix_closed parent child parent_of_child child_occupied.2⟩
  | move source target =>
      simp only [OccupancyAfter, operation_kind] at child_occupied ⊢
      rcases child_occupied with
        ⟨relativePosition, child_is_target_child, source_child_occupied⟩ |
        ⟨source_not_parent, target_not_parent, child_occupied⟩
      · have target_of_child : ParentOrSame target child :=
          ⟨relativePosition, child_is_target_child.symm⟩
        rcases
            List.prefix_or_prefix_of_prefix parent_of_child target_of_child with
          parent_of_target | target_of_parent
        · by_cases parent_is_target : parent = target
          · subst parent_is_target
            exact
              Or.inl
                ⟨[], by simp,
                  by
                    simpa using
                      prefix_closed source (source ++ relativePosition)
                        ⟨relativePosition, rfl⟩ source_child_occupied⟩
          · refine Or.inr ⟨?_, ?_, ?_⟩
            · intro source_of_parent
              exact
                move_source_not_parent_of_target source target operation_kind
                  (source_of_parent.trans parent_of_target)
            · intro target_of_parent_again
              exact
                parent_is_target
                  (parentOrSame_antisymm parent_of_target
                    target_of_parent_again)
            · exact
                fill_available target (by simp [FillPosition, operation_kind])
                  parent parent_of_target parent_is_target
        · rcases target_of_parent with ⟨parentRelative, parent_is_target_child⟩
          subst parent_is_target_child
          subst child_is_target_child
          have relative_parent :
              ParentOrSame parentRelative relativePosition :=
            parentOrSame_resolve_iff.mp parent_of_child
          exact
            Or.inl
              ⟨parentRelative, rfl,
                prefix_closed (source ++ parentRelative)
                  (source ++ relativePosition)
                  (parentOrSame_resolve_iff.mpr relative_parent)
                  source_child_occupied⟩
      · exact
          Or.inr
            ⟨fun source_of_parent =>
              source_not_parent (source_of_parent.trans parent_of_child),
              fun target_of_parent =>
                target_not_parent (target_of_parent.trans parent_of_child),
              prefix_closed parent child parent_of_child child_occupied⟩

/--
An operation's Empty Position and every one of its child positions is empty
after the operation, provided the starting occupancy is prefix-closed.
-/
theorem not_occupancyAfter_of_emptyPosition_parent
    {operation : ParticleOperation} {occupied : Position → Prop}
    {emptyPosition position : Position}
    (prefix_closed : PrefixClosed occupied)
    (enabled : OperationEnabled operation occupied)
    (empty_position : EmptyPosition operation = some emptyPosition)
    (empty_parent_of_position : ParentOrSame emptyPosition position) :
    ¬OccupancyAfter operation occupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      simp [EmptyPosition, operation_kind] at empty_position
  | destroy target =>
      have empty_is_target : emptyPosition = target := by
        have target_is_empty : target = emptyPosition := by
          simpa [EmptyPosition, operation_kind] using empty_position
        exact target_is_empty.symm
      subst emptyPosition
      simp [OccupancyAfter, operation_kind, empty_parent_of_position]
  | move source target =>
      have empty_is_source : emptyPosition = source := by
        have source_is_empty : source = emptyPosition := by
          simpa [EmptyPosition, operation_kind] using empty_position
        exact source_is_empty.symm
      subst emptyPosition
      have enabled_parts :
          occupied source ∧
            Available occupied target ∧
              ¬occupied target ∧ ¬ParentOrSame source target := by
        simpa [OperationEnabled, operation_kind] using enabled
      have target_not_parent_of_source : ¬ParentOrSame target source := by
        intro target_parent_of_source
        exact
          enabled_parts.2.2.1
            (prefix_closed target source target_parent_of_source
              enabled_parts.1)
      simp only [OccupancyAfter, operation_kind]
      intro occupied_after
      rcases occupied_after with moved_from_source | unchanged
      · rcases moved_from_source with
          ⟨relativePosition, position_is_target_child, _⟩
        have target_parent_of_position : ParentOrSame target position :=
          ⟨relativePosition, position_is_target_child.symm⟩
        rcases
            List.prefix_or_prefix_of_prefix empty_parent_of_position
              target_parent_of_position with
          source_parent_of_target | target_parent_of_source
        · exact enabled_parts.2.2.2 source_parent_of_target
        · exact target_not_parent_of_source target_parent_of_source
      · exact unchanged.1 empty_parent_of_position

end Define.OperationGraph
