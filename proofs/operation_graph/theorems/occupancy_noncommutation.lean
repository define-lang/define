import occupancy_semantics

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
