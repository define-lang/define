import characterization
import finite_schedule_order
import finite_scheduling

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Maximum Safe Concurrency

This module connects the calculated Particle Operation Dependency Graph to the
occupancy scheduling semantics. The characterization theorem makes two distinct
graph-incomparable operations unrelated, which is exactly the premise required
by the adjacent schedule-exchange theorem.

The remaining finite and unbounded scheduling arguments are developed here as
their order-theoretic components are formalized.
-/

namespace Define.OperationGraph

/--
Two distinct operations from one valid resolved history that are incomparable
in the calculated graph operate on pairwise unrelated positions.
-/
theorem incomparable_calculated_operations_are_unrelated
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {firstOperation secondOperation : ParticleOperation}
    (first_member : isOperation firstOperation)
    (second_member : isOperation secondOperation)
    (operations_distinct : firstOperation ≠ secondOperation)
    (first_does_not_reach_second :
      ¬Reaches (CalculatedDependency history) firstOperation secondOperation)
    (second_does_not_reach_first :
      ¬Reaches (CalculatedDependency history) secondOperation firstOperation) :
    ¬OperationsRelated firstOperation secondOperation := by
  intro operations_related
  rcases Nat.lt_trichotomy firstOperation.operationOrder
      secondOperation.operationOrder with
    first_before_second | same_order | second_before_first
  · exact
      second_does_not_reach_first
        (calculatedDependency_reaches_of_relatedPrevious history second_member
          first_member
          ⟨first_before_second, operationsRelated_symm operations_related⟩)
  · have first_at_order := history.member_operation_at firstOperation first_member
    have second_at_order :=
      history.member_operation_at secondOperation second_member
    rw [same_order] at first_at_order
    exact
      operations_distinct
        (Option.some.inj (first_at_order.symm.trans second_at_order))
  · exact
      first_does_not_reach_second
        (calculatedDependency_reaches_of_relatedPrevious history first_member
          second_member ⟨second_before_first, operations_related⟩)

end Define.OperationGraph
