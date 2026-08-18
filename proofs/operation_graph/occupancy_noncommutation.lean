import finite_scheduling
import valid_history

set_option warningAsError true
set_option autoImplicit false

/-!
# Related Particle Operation Non-Commutation

This module proves the occupancy-semantic core of the cover-order necessity
argument. If two related Particle Operations execute consecutively from a
prefix-closed occupancy, they cannot both execute in the reverse order from the
same occupancy.
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
Executing an enabled finite schedule from a prefix-closed occupancy preserves
prefix closure.
-/
theorem ScheduleExecution.preserves_prefixClosure
    {observation : ParticleOperation → Position → Prop}
    {schedule : List ParticleOperation}
    {occupiedBefore occupiedAfter : Position → Prop}
    (execution :
      ScheduleExecution observation schedule occupiedBefore occupiedAfter)
    (prefix_closed : PrefixClosed occupiedBefore) :
    PrefixClosed occupiedAfter := by
  induction execution with
  | nil => exact prefix_closed
  | cons enabled observed remaining_execution induction_hypothesis =>
      apply induction_hypothesis
      apply occupancyAfter_preserves_prefixClosure prefix_closed
      · intro target fill_position
        exact
          operationEnabled_fillPosition_available enabled fill_position
      · intro source target move_kind
        exact
          operationEnabled_move_source_not_parent_of_target enabled move_kind

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

/--
Two related operations that are enabled consecutively from a prefix-closed
occupancy cannot both be enabled in the reverse order.
-/
theorem related_enabled_operations_not_reversible
    {firstOperation secondOperation : ParticleOperation}
    {occupiedBefore : Position → Prop}
    (prefix_closed : PrefixClosed occupiedBefore)
    (first_enabled : OperationEnabled firstOperation occupiedBefore)
    (second_enabled :
      OperationEnabled secondOperation
        (OccupancyAfter firstOperation occupiedBefore))
    (operations_related : OperationsRelated firstOperation secondOperation) :
    ¬(OperationEnabled secondOperation occupiedBefore ∧
      OperationEnabled firstOperation
        (OccupancyAfter secondOperation occupiedBefore)) := by
  rintro ⟨second_enabled_first, first_enabled_second⟩
  rcases operations_related with
    ⟨firstPosition, secondPosition, first_operates, second_operates,
      positions_related⟩
  rcases operatesOn_iff_emptyPosition_or_fillPosition.mp first_operates with
    first_empty_position | first_fill_position <;>
    rcases operatesOn_iff_emptyPosition_or_fillPosition.mp second_operates with
      second_empty_position | second_fill_position
  · rcases positions_related with
      first_parent_of_second | second_parent_of_first
    · have second_occupied_after_first :=
        operationEnabled_emptyPosition_occupied second_enabled
          second_empty_position
      exact
        (not_occupancyAfter_of_emptyPosition_parent prefix_closed first_enabled
          first_empty_position first_parent_of_second)
          second_occupied_after_first
    · have first_occupied_after_second :=
        operationEnabled_emptyPosition_occupied first_enabled_second
          first_empty_position
      exact
        (not_occupancyAfter_of_emptyPosition_parent prefix_closed
          second_enabled_first second_empty_position second_parent_of_first)
          first_occupied_after_second
  · have first_occupied :=
      operationEnabled_emptyPosition_occupied first_enabled
        first_empty_position
    have second_empty :=
      operationEnabled_fillPosition_empty second_enabled_first
        second_fill_position
    rcases positions_related with
      first_parent_of_second | second_parent_of_first
    · by_cases positions_equal : firstPosition = secondPosition
      · subst secondPosition
        exact second_empty first_occupied
      · have first_occupied_after :=
          operationEnabled_fillPosition_available second_enabled
            second_fill_position firstPosition first_parent_of_second
            positions_equal
        exact
          (not_occupancyAfter_of_emptyPosition_parent prefix_closed
            first_enabled first_empty_position List.prefix_rfl)
            first_occupied_after
    · exact
        second_empty
          (prefix_closed secondPosition firstPosition second_parent_of_first
            first_occupied)
  · have first_empty :=
      operationEnabled_fillPosition_empty first_enabled first_fill_position
    have second_occupied :=
      operationEnabled_emptyPosition_occupied second_enabled_first
        second_empty_position
    rcases positions_related with
      first_parent_of_second | second_parent_of_first
    · exact
        first_empty
          (prefix_closed firstPosition secondPosition first_parent_of_second
            second_occupied)
    · by_cases positions_equal : secondPosition = firstPosition
      · subst secondPosition
        exact first_empty second_occupied
      · have second_occupied_after :=
          operationEnabled_fillPosition_available first_enabled_second
            first_fill_position secondPosition second_parent_of_first
            positions_equal
        exact
          (not_occupancyAfter_of_emptyPosition_parent prefix_closed
            second_enabled_first second_empty_position List.prefix_rfl)
            second_occupied_after
  · have first_empty :=
      operationEnabled_fillPosition_empty first_enabled first_fill_position
    have second_empty :=
      operationEnabled_fillPosition_empty second_enabled_first
        second_fill_position
    rcases positions_related with
      first_parent_of_second | second_parent_of_first
    · by_cases positions_equal : firstPosition = secondPosition
      · subst secondPosition
        have first_occupied_after :=
          operationEnabled_fillPosition_occupiedAfter first_enabled
            first_fill_position
        exact
          (operationEnabled_fillPosition_empty second_enabled
            second_fill_position) first_occupied_after
      · exact
          first_empty
            (operationEnabled_fillPosition_available second_enabled_first
              second_fill_position firstPosition first_parent_of_second
              positions_equal)
    · by_cases positions_equal : secondPosition = firstPosition
      · subst secondPosition
        have first_occupied_after :=
          operationEnabled_fillPosition_occupiedAfter first_enabled
            first_fill_position
        exact
          (operationEnabled_fillPosition_empty second_enabled
            second_fill_position) first_occupied_after
      · exact
          second_empty
            (operationEnabled_fillPosition_available first_enabled
              first_fill_position secondPosition second_parent_of_first
              positions_equal)

end Define.OperationGraph
