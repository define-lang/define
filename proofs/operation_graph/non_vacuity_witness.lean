import calculation_correctness
import create_destroy_history
import witness_support

set_option warningAsError true
set_option autoImplicit false

/-!
# Non-vacuity Witness

This module applies the actual resolved operation graph calculation to the
concrete Create-then-Destroy history. It proves that the calculated graph has a
dependency without importing or assuming the minimality theorem.
-/

namespace Define.OperationGraph

namespace NonVacuity

open CreateDestroyHistory

abbrev position : Position :=
  CreateDestroyHistory.target

abbrev isOperation (operation : ParticleOperation) : Prop :=
  CreateDestroyHistory.IsOperation operation

abbrev occupancy : ExactOccupancyExecution isOperation :=
  CreateDestroyHistory.history.toExactOccupancyExecution

abbrev history : ValidResolvedHistory isOperation :=
  CreateDestroyHistory.history

theorem calculated_source_candidate :
    IsSourceCandidate history destroyOperation createOperation := by
  refine ⟨position, Or.inr rfl, position, rfl, Or.inr rfl,
    related_refl position, ?_⟩
  refine ⟨Or.inl rfl, by decide, ?_, ?_⟩
  · simp [WritesEntry, createOperation]
  · intro newerCandidate newer_member newer_than_create newer_before_destroy
      newer_writes
    rcases newer_member with newer_is_create | newer_is_destroy
    · subst newer_is_create
      exact (Nat.lt_irrefl _ newer_than_create)
    · subst newer_is_destroy
      exact (Nat.lt_irrefl _ newer_before_destroy)

theorem calculated_dependency :
    CalculatedDependency history destroyOperation createOperation := by
  apply
    (calculatedDependency_exact history destroyOperation createOperation).mpr
  change
    (calculationFor history destroyOperation).AfterMoveCorrection
      (CalculatedDependency history) createOperation
  refine ⟨⟨Or.inl calculated_source_candidate, ?_⟩, Or.inl ?_⟩
  · intro newerCandidate newer_in_collection newer_than_create
      operations_related
    rcases newer_in_collection with newer_source | newer_fill
    · rcases newer_source with
        ⟨candidatePosition, newer_operation_member, source, empty_position,
          candidate_queryable, candidate_related, entry⟩
      rcases entry.candidate_is_operation with
        newer_is_create | newer_is_destroy
      · subst newer_is_create
        exact Nat.lt_irrefl _ newer_than_create
      · subst newer_is_destroy
        exact Nat.lt_irrefl _ entry.candidate_is_previous
    · rcases
        ((calculationFor_fillCandidate_iff history destroyOperation
          newerCandidate).mp newer_fill).1 with
        ⟨operation_member, target, candidatePosition, fill_position,
          candidate_queryable, candidate_parent, entry⟩
      simp [FillPosition, destroyOperation] at fill_position
  · exact not_move_of_kind_create rfl

def sourceCandidate (operation candidate : ParticleOperation) : Prop :=
  (calculationFor history operation).sourceCandidate candidate

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  IsSourceCandidateAt history operation candidate candidatePosition

noncomputable def calculation (operation : ParticleOperation) : RuleCalculation :=
  calculationFor history operation

def dependency (operation candidate : ParticleOperation) : Prop :=
  CalculatedDependency history operation candidate

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  exact calculationFor_wellFormed history operation

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  change
    CalculatedDependency history operation candidate ↔
      (calculationFor history operation).Dependency
        (CalculatedDependency history) candidate
  exact calculatedDependency_exact history operation candidate

noncomputable def graph : ResolvedDefineGraph :=
  calculatedResolvedDefineGraph history

example : dependency destroyOperation createOperation :=
  calculated_dependency

example : Reaches dependency destroyOperation createOperation :=
  .direct calculated_dependency

example : ∃ operation candidate, dependency operation candidate :=
  ⟨destroyOperation, createOperation, calculated_dependency⟩

end NonVacuity

end Define.OperationGraph
