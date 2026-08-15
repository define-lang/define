import proofs.particle_operation_dependency_graph_minimality

set_option autoImplicit false

/-!
This file keeps concrete valid models separate from the minimality theorem
because they demonstrate that its semantic obligations are jointly satisfiable
but supply no premise to the theorem. The current model matches the valid
create-and-destroy operation history in the
create_and_destroy_of_an_implied_position integration test.
-/

namespace Define.OperationGraph

namespace NonVacuity

def position : Position := [0]

def createOperation : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create position

def destroyOperation : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .destroy position

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createOperation ∨ operation = destroyOperation

def operationAt : Nat → Option ParticleOperation
  | 0 => some createOperation
  | 1 => some destroyOperation
  | _ => none

def occupiedBefore (operationOrder : Nat) (occupiedPosition : Position) : Prop :=
  occupiedPosition = [] ∨
    (operationOrder = 1 ∧ occupiedPosition = position)

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      rfl
    · subst operation_is_destroy
      rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        exact Or.inl operation_at.symm
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            exact Or.inr operation_at.symm
        | succ operationOrder =>
            simp [operationAt] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        subst operation_at
        rfl
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            subst operation_at
            rfl
        | succ operationOrder =>
            simp [operationAt] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases child_occupied with child_is_action_parent | child_is_particle
    · subst child_is_action_parent
      have parent_is_action_parent := List.eq_nil_of_prefix_nil parent_of_child
      exact Or.inl parent_is_action_parent
    · rcases child_is_particle with ⟨order_is_one, child_is_position⟩
      subst child_is_position
      have parent_shape : parent = [] ∨ parent = position := by
        simpa [ParentOrSame, position, List.prefix_cons_iff] using parent_of_child
      rcases parent_shape with parent_is_action_parent | parent_is_position
      · exact Or.inl parent_is_action_parent
      · exact Or.inr ⟨order_is_one, parent_is_position⟩
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      simp [EmptyPosition, createOperation] at empty_position
    · subst operation_is_destroy
      simp [EmptyPosition, destroyOperation] at empty_position
      exact Or.inr ⟨rfl, empty_position.symm⟩
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      simp [FillPosition, createOperation] at fill_position
      subst target
      simp [occupiedBefore, position, createOperation]
    · subst operation_is_destroy
      simp [FillPosition, destroyOperation] at fill_position
  operation_transition := by
    intro operationOrder operation operation_at transitionedPosition
    cases operationOrder with
    | zero =>
        simp [operationAt] at operation_at
        subst operation_at
        simp [occupiedBefore, OccupancyAfter, createOperation]
        constructor <;> grind
    | succ operationOrder =>
        cases operationOrder with
        | zero =>
            simp [operationAt] at operation_at
            subst operation_at
            simp [occupiedBefore, OccupancyAfter, destroyOperation, ParentOrSame,
              position]
            constructor
            · intro transitioned_is_action_parent
              subst transitioned_is_action_parent
              simp
            · rintro ⟨_, transitioned_is_action_parent | transitioned_is_position⟩
              · exact transitioned_is_action_parent
              · subst transitioned_is_position
                simp_all
        | succ operationOrder =>
            simp [operationAt] at operation_at
  no_operation_transition := by
    intro operationOrder no_operation transitionedPosition
    cases operationOrder with
    | zero => simp [operationAt] at no_operation
    | succ operationOrder =>
        cases operationOrder with
        | zero => simp [operationAt] at no_operation
        | succ operationOrder =>
            simp [occupiedBefore]

def sourceCandidate (operation candidate : ParticleOperation) : Prop :=
  operation = destroyOperation ∧ candidate = createOperation

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  sourceCandidate operation candidate ∧ candidatePosition = position

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := sourceCandidate operation
  fillCandidate := none
  actionParentCandidate := none

def dependency (operation candidate : ParticleOperation) : Prop :=
  operation = destroyOperation ∧ candidate = createOperation

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      intro candidate source_candidate
      have operation_is_destroy := source_candidate.1
      subst operation_is_destroy
      simp [destroyOperation] at operation_kind
  | destroy target =>
      simp [RuleCalculation.WellFormed, calculation, operation_kind]
  | move source target =>
      simp [RuleCalculation.WellFormed, calculation, operation_kind]

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).FinalDependency dependency candidate := by
  simp only [dependency, RuleCalculation.FinalDependency,
    RuleCalculation.HasOrdinaryDependency, RuleCalculation.OrdinaryDependency,
    RuleCalculation.AfterMoveCorrection, RuleCalculation.MoveRuleDependency,
    RuleCalculation.AfterComparison, RuleCalculation.InCollection,
    RuleCalculation.IsFillCandidate, RuleCalculation.IsActionParentCandidate,
    calculation, sourceCandidate]
  cases operation_kind : operation.kind <;>
    simp [IsMove, MoreRecent, createOperation, destroyOperation]
  · intro operation_is_destroy
    subst operation_is_destroy
    simp at operation_kind
  · intro operation_is_destroy candidate_is_create
    subst operation_is_destroy
    subst candidate_is_create
    exact Or.inl (by simp)
  · intro operation_is_destroy
    subst operation_is_destroy
    simp at operation_kind

def graph : ResolvedDefineGraph where
  isOperation := isOperation
  dependency := dependency
  calculation := calculation
  calculation_operation := by
    intro operation
    rfl
  calculation_well_formed := calculation_well_formed
  exact_dependency := exact_dependency
  occupancy := occupancy
  sourceCandidateAt := sourceCandidateAt
  source_candidate_iff := by
    intro operation candidate
    constructor
    · intro source_candidate
      exact ⟨position, source_candidate, rfl⟩
    · rintro ⟨candidatePosition, source_candidate, _⟩
      exact source_candidate
  source_candidate_empty_position := by
    intro operation candidate candidatePosition candidate_at_position
    rcases candidate_at_position with
      ⟨⟨operation_is_destroy, candidate_is_create⟩, position_is_position⟩
    subst operation_is_destroy
    subst candidate_is_create
    subst position_is_position
    exact ⟨position, rfl, related_refl position⟩
  source_candidate_operated_position := by
    intro operation candidate candidatePosition candidate_at_position
    rcases candidate_at_position with
      ⟨⟨operation_is_destroy, candidate_is_create⟩, position_is_position⟩
    subst operation_is_destroy
    subst candidate_is_create
    subst position_is_position
    exact ⟨position, by simp [OperatesOn, createOperation], List.prefix_rfl⟩
  non_move_source_candidate_operates_on_position := by
    intro operation candidate candidatePosition candidate_at_position _
    rcases candidate_at_position with
      ⟨⟨operation_is_destroy, candidate_is_create⟩, position_is_position⟩
    subst operation_is_destroy
    subst candidate_is_create
    subst position_is_position
    simp [OperatesOn, createOperation]
  source_candidate_is_previous := by
    intro operation candidate candidatePosition candidate_at_position
    rcases candidate_at_position with
      ⟨⟨operation_is_destroy, candidate_is_create⟩, _⟩
    subst operation_is_destroy
    subst candidate_is_create
    exact Nat.zero_lt_succ 0
  source_candidate_operations := by
    intro operation candidate candidatePosition candidate_at_position
    exact ⟨Or.inr candidate_at_position.1.1, Or.inl candidate_at_position.1.2⟩
  latest_source_candidate := by
    intro operation emptyPosition candidatePosition previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      simp [EmptyPosition, createOperation] at empty_position
    · subst operation_is_destroy
      rcases previous_member with previous_is_create | previous_is_destroy
      · subst previous_is_create
        have candidate_position_is_position : candidatePosition = position := by
          simpa [OperatesOn, createOperation] using previous_operates
        subst candidate_position_is_position
        exact ⟨createOperation, ⟨⟨rfl, rfl⟩, rfl⟩, Or.inl rfl⟩
      · subst previous_is_destroy
        exact False.elim (Nat.lt_irrefl _ operation_after_previous)
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    simp [RuleCalculation.IsFillCandidate, calculation] at fill_candidate
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    simp [RuleCalculation.IsFillCandidate, calculation] at fill_candidate
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    simp [RuleCalculation.IsFillCandidate, calculation] at fill_candidate
  action_parent_candidate_operated_position := by
    intro operation candidate action_parent_candidate
    simp [RuleCalculation.IsActionParentCandidate, calculation] at action_parent_candidate
  action_parent_candidate_operations := by
    intro operation candidate action_parent_candidate
    simp [RuleCalculation.IsActionParentCandidate, calculation] at action_parent_candidate
  action_parent_candidate_is_previous := by
    intro operation candidate action_parent_candidate
    simp [RuleCalculation.IsActionParentCandidate, calculation] at action_parent_candidate
  action_parent_is_parent_or_same := by
    intro operation operatedPosition operation_member _
    rcases operation_member with operation_is_create | operation_is_destroy
    · subst operation_is_create
      exact List.nil_prefix
    · subst operation_is_destroy
      exact List.nil_prefix

example : dependency destroyOperation createOperation :=
  ⟨rfl, rfl⟩

example : Reaches graph.dependency destroyOperation createOperation :=
  .direct ⟨rfl, rfl⟩

example : ∃ operation candidate, graph.dependency operation candidate :=
  ⟨destroyOperation, createOperation, rfl, rfl⟩

example : Acyclic graph.dependency :=
  graph.acyclic

example : TransitivelyMinimal graph.dependency :=
  graph.transitivelyMinimal

end NonVacuity

end Define.OperationGraph
