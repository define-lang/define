import create_destroy_history
import minimality

set_option warningAsError true
set_option autoImplicit false

/-!
This file keeps concrete valid models separate from the minimality theorem
because they demonstrate that its semantic obligations are jointly satisfiable
but supply no premise to the theorem.

`NonVacuity` matches the valid create-and-destroy operation history in the
create_and_destroy_of_an_implied_position integration test.

`VanishedChildName` demonstrates `latest_source_candidate` at a position name
that no longer refers to a position: an operation on the child position of a
destroyed and replaced parent particle is a keyed candidate that the Comparison
always excludes.

`MovedChildEntry` demonstrates a Move selected as the most-recent entry for a
moved particle's transitive child position, and a Move surviving the Move
Correction as a final dependency.

`FillDependencyRemoval` demonstrates the Move Rule: one Move keeps both an
Empty Dependency and an unrelated Fill Dependency as a two-dependency
reachability antichain, and a later Move's Fill Dependency is removed because a
remaining Empty Dependency reaches it. This is the redundancy family covered by
the move_excludes_create_fill_dependency_reached_through_source_dependency
integration test.

`NonVacuity` reuses the create-and-destroy `ValidResolvedHistory` from
`valid_history.lean`, and
`NonVacuity.calculated_dependency` derives its nonempty graph through the
universal `CalculatedDependency`. The three larger namespaces still construct
the older `ResolvedDefineGraph` interface directly; they remain to be migrated
to the same end-to-end path.
-/

namespace Define.OperationGraph

theorem not_move_of_kind_create {operation : ParticleOperation} {target : Position}
    (kind_eq : operation.kind = .create target) : ¬IsMove operation := by
  rintro ⟨moveSource, moveTarget, move_kind⟩
  rw [kind_eq] at move_kind
  exact ParticleOperationKind.noConfusion move_kind

theorem not_move_of_kind_destroy {operation : ParticleOperation} {target : Position}
    (kind_eq : operation.kind = .destroy target) : ¬IsMove operation := by
  rintro ⟨moveSource, moveTarget, move_kind⟩
  rw [kind_eq] at move_kind
  exact ParticleOperationKind.noConfusion move_kind

theorem not_more_recent_of_le {newer older : ParticleOperation}
    (le : newer.operationOrder ≤ older.operationOrder) : ¬MoreRecent newer older :=
  fun more_recent => absurd more_recent (Nat.not_lt.mpr le)

theorem no_reaches_of_no_dependency {Vertex : Type} {dep : Vertex → Vertex → Prop}
    {source : Vertex} (no_edge : ∀ target, ¬dep source target) {target : Vertex} :
    ¬Reaches dep source target := by
  intro path
  cases path with
  | direct edge => exact no_edge _ edge
  | step edge _ => exact no_edge _ edge

theorem prefix_singleton_iff {head : Nat} {name : List Nat} :
    name <+: [head] ↔ name = [] ∨ name = [head] := by
  constructor
  · intro name_prefix
    rcases List.prefix_cons_iff.mp name_prefix with name_nil | ⟨tail, name_eq, tail_prefix⟩
    · exact Or.inl name_nil
    · have tail_nil := List.eq_nil_of_prefix_nil tail_prefix
      subst tail_nil
      exact Or.inr name_eq
  · rintro (rfl | rfl)
    · exact List.nil_prefix
    · exact List.prefix_rfl

theorem prefix_pair_iff {first second : Nat} {name : List Nat} :
    name <+: [first, second] ↔
      name = [] ∨ name = [first] ∨ name = [first, second] := by
  constructor
  · intro name_prefix
    rcases List.prefix_cons_iff.mp name_prefix with name_nil | ⟨tail, name_eq, tail_prefix⟩
    · exact Or.inl name_nil
    · rcases prefix_singleton_iff.mp tail_prefix with tail_nil | tail_single
      · subst tail_nil
        exact Or.inr (Or.inl name_eq)
      · subst tail_single
        exact Or.inr (Or.inr name_eq)
  · rintro (rfl | rfl | rfl)
    · exact List.nil_prefix
    · exact ⟨[second], rfl⟩
    · exact List.prefix_rfl

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
  operation = destroyOperation ∧ candidate = createOperation

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  sourceCandidate operation candidate ∧ candidatePosition = position

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := sourceCandidate operation
  fillCandidate := none

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
      (calculation operation).Dependency dependency candidate := by
  simp only [dependency, RuleCalculation.Dependency,
    RuleCalculation.AfterMoveCorrection, RuleCalculation.MoveRuleDependency,
    RuleCalculation.AfterComparison, RuleCalculation.InCollection,
    RuleCalculation.IsFillCandidate, calculation, sourceCandidate]
  cases operation_kind : operation.kind <;>
    simp [IsMove, MoreRecent, createOperation, destroyOperation]
  · intro operation_is_destroy
    subst operation_is_destroy
    simp at operation_kind
  · intro operation_is_destroy candidate_is_create
    subst operation_is_destroy
    subst candidate_is_create
    simp
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

example : dependency destroyOperation createOperation :=
  ⟨rfl, rfl⟩

example : Reaches (CalculatedDependency history) destroyOperation createOperation :=
  .direct calculated_dependency

example : ∃ operation candidate, CalculatedDependency history operation candidate :=
  ⟨destroyOperation, createOperation, calculated_dependency⟩

example : Acyclic (CalculatedDependency history) :=
  (calculatedDependency_isMinimalDAG history).1

example : TransitivelyMinimal (CalculatedDependency history) :=
  (calculatedDependency_isMinimalDAG history).2

end NonVacuity


namespace VanishedChildName

def parentPosition : Position := [0]

def childPosition : Position := [0, 0]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create parentPosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create childPosition

def destroyChild : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .destroy childPosition

def destroyParent : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy parentPosition

def recreateParent : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .create parentPosition

def destroyAgain : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .destroy parentPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild ∨ operation = destroyChild ∨
    operation = destroyParent ∨ operation = recreateParent ∨
    operation = destroyAgain

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | 2 => some destroyChild
  | 3 => some destroyParent
  | 4 => some recreateParent
  | 5 => some destroyAgain
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

theorem operationAt_tail (operationOrder : Nat) :
    operationAt (operationOrder + 6) = none := rfl

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = [0, 0] ∨ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔ position = [0] ∨ position = [] := by
  constructor
  · rintro ⟨not_under_child, occupied⟩
    rcases (occupied_two position).mp occupied with rfl | rfl | rfl
    · exact absurd List.prefix_rfl not_under_child
    · exact Or.inl rfl
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        (occupied_two _).mpr (Or.inr (Or.inl rfl))⟩
    · exact ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        (occupied_two _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_three position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([0] : List Nat) <+: []; decide,
      (occupied_three _).mpr (Or.inr rfl)⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔ position = [0] ∨ position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four position).mp occupied)
  · rintro (rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four _).mpr rfl)

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_five position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([0] : List Nat) <+: []; decide,
      (occupied_five _).mpr (Or.inr rfl)⟩

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 6) position ↔ occupiedBefore 6 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 6) position ↔
            occupiedBefore (extra + 6) position := by
        show occupiedBefore (extra + 6 + 1) position ↔ _
        simp [occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
        (Option.some.inj operation_at).symm))))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
        (Option.some.inj operation_at).symm))))
    · simp [operationAt_tail] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt_tail] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · rw [occupied_zero] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_one] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_two] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_three] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_four] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_five] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_tail, occupied_six] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · simp [EmptyPosition, createParent] at empty_position
    · simp [EmptyPosition, createChild] at empty_position
    · have source_is_child : source = childPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_two _).mpr (Or.inl rfl)
    · have source_is_parent : source = parentPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_parent
      exact (occupied_three _).mpr (Or.inl rfl)
    · simp [EmptyPosition, recreateParent] at empty_position
    · have source_is_parent : source = parentPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_parent
      exact (occupied_five _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro occupied
      simpa [parentPosition] using (occupied_zero parentPosition).mp occupied
    · have target_is_child : target = childPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro occupied
      rcases (occupied_one childPosition).mp occupied with child_eq | child_eq <;>
        simp [childPosition] at child_eq
    · simp [FillPosition, destroyChild] at fill_position
    · simp [FillPosition, destroyParent] at fill_position
    · have target_is_parent : target = parentPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_parent
      intro occupied
      simpa [parentPosition] using (occupied_four parentPosition).mp occupied
    · simp [FillPosition, destroyAgain] at fill_position
  operation_transition := by
    intro operationOrder operation operation_at position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [operation_at]
  no_operation_transition := by
    intro operationOrder no_operation position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [no_operation]

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  (operation = destroyChild ∧
    ((candidate = createChild ∧ candidatePosition = childPosition) ∨
      (candidate = createParent ∧ candidatePosition = parentPosition))) ∨
  (operation = destroyParent ∧
    ((candidate = destroyChild ∧ candidatePosition = childPosition) ∨
      (candidate = createParent ∧ candidatePosition = parentPosition))) ∨
  (operation = destroyAgain ∧
    ((candidate = destroyChild ∧ candidatePosition = childPosition) ∨
      (candidate = recreateParent ∧ candidatePosition = parentPosition)))

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := fun candidate =>
    ∃ candidatePosition, sourceCandidateAt operation candidate candidatePosition
  fillCandidate :=
    if operation = createChild then some createParent
    else if operation = recreateParent then some destroyParent
    else none

def dependency (operation candidate : ParticleOperation) : Prop :=
  (operation = createChild ∧ candidate = createParent) ∨
    (operation = destroyChild ∧ candidate = createChild) ∨
    (operation = destroyParent ∧ candidate = destroyChild) ∨
    (operation = recreateParent ∧ candidate = destroyParent) ∨
    (operation = destroyAgain ∧ candidate = recreateParent)

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rintro candidate ⟨candidatePosition, source_at⟩
      rcases source_at with ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ <;>
        simp [destroyChild, destroyParent, destroyAgain] at operation_kind
  | destroy target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rw [if_neg, if_neg]
      all_goals
        intro operation_is_filler
        subst operation_is_filler
        simp [createChild, recreateParent] at operation_kind
  | move source target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]


theorem fill_create_child :
    (calculation createChild).fillCandidate = some createParent := by
  show (if (createChild : ParticleOperation) = createChild then some createParent
    else if (createChild : ParticleOperation) = recreateParent then
      some destroyParent
    else none) = some createParent
  rw [if_pos rfl]

theorem fill_recreate :
    (calculation recreateParent).fillCandidate = some destroyParent := by
  show (if (recreateParent : ParticleOperation) = createChild then
      some createParent
    else if (recreateParent : ParticleOperation) = recreateParent then
      some destroyParent
    else none) = some destroyParent
  rw [if_neg (by decide), if_pos rfl]

theorem in_collection_shapes {operation candidate : ParticleOperation}
    (in_collection : (calculation operation).InCollection candidate) :
    (operation = destroyChild ∧
      (candidate = createChild ∨ candidate = createParent)) ∨
    (operation = destroyParent ∧
      (candidate = destroyChild ∨ candidate = createParent)) ∨
    (operation = destroyAgain ∧
      (candidate = destroyChild ∨ candidate = recreateParent)) ∨
    (operation = createChild ∧ candidate = createParent) ∨
    (operation = recreateParent ∧ candidate = destroyParent) := by
  rcases in_collection with ⟨candidatePosition, source_at⟩ | fill
  · rcases source_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · exact Or.inl ⟨rfl, shapes.imp And.left And.left⟩
    · exact Or.inr (Or.inl ⟨rfl, shapes.imp And.left And.left⟩)
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, shapes.imp And.left And.left⟩))
  · have fill_eq : (if operation = createChild then some createParent
        else if operation = recreateParent then some destroyParent
        else none) = some candidate := fill
    by_cases is_create_child : operation = createChild
    · rw [if_pos is_create_child] at fill_eq
      exact Or.inr (Or.inr (Or.inr (Or.inl
        ⟨is_create_child, (Option.some.inj fill_eq).symm⟩)))
    · rw [if_neg is_create_child] at fill_eq
      by_cases is_recreate : operation = recreateParent
      · rw [if_pos is_recreate] at fill_eq
        exact Or.inr (Or.inr (Or.inr (Or.inr
          ⟨is_recreate, (Option.some.inj fill_eq).symm⟩)))
      · rw [if_neg is_recreate] at fill_eq
        exact nomatch fill_eq

theorem related_child_parent : OperationsRelated createChild createParent :=
  ⟨childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem related_destroy_child_parent :
    OperationsRelated destroyChild createParent :=
  ⟨childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem related_recreate_destroy_child :
    OperationsRelated recreateParent destroyChild :=
  ⟨parentPosition, childPosition, rfl, rfl, Or.inl ⟨[0], rfl⟩⟩

theorem after_comparison_shapes {operation candidate : ParticleOperation}
    (after_comparison : (calculation operation).AfterComparison candidate) :
    (operation = destroyChild ∧ candidate = createChild) ∨
    (operation = destroyParent ∧ candidate = destroyChild) ∨
    (operation = destroyAgain ∧ candidate = recreateParent) ∨
    (operation = createChild ∧ candidate = createParent) ∨
    (operation = recreateParent ∧ candidate = destroyParent) := by
  rcases in_collection_shapes after_comparison.1 with
    ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | shape | shape
  · rcases shapes with rfl | rfl
    · exact Or.inl ⟨rfl, rfl⟩
    · exact (after_comparison.2 createChild
        (Or.inl ⟨childPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide : createParent.operationOrder < createChild.operationOrder)
        related_child_parent).elim
  · rcases shapes with rfl | rfl
    · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
    · exact (after_comparison.2 destroyChild
        (Or.inl ⟨childPosition, Or.inr (Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩)⟩)
        (by decide : createParent.operationOrder < destroyChild.operationOrder)
        related_destroy_child_parent).elim
  · rcases shapes with rfl | rfl
    · exact (after_comparison.2 recreateParent
        (Or.inl ⟨parentPosition, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩)⟩)
        (by decide : destroyChild.operationOrder < recreateParent.operationOrder)
        related_recreate_destroy_child).elim
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
  · exact Or.inr (Or.inr (Or.inr (Or.inl shape)))
  · exact Or.inr (Or.inr (Or.inr (Or.inr shape)))

theorem after_comparison_create_child :
    (calculation destroyChild).AfterComparison createChild := by
  refine ⟨Or.inl ⟨childPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_destroy_child :
    (calculation destroyParent).AfterComparison destroyChild := by
  refine ⟨Or.inl ⟨childPosition, Or.inr (Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩)⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_recreate :
    (calculation destroyAgain).AfterComparison recreateParent := by
  refine ⟨Or.inl ⟨parentPosition, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩)⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨_, rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem no_destroy_fill {operation candidate : ParticleOperation}
    (is_destroy : operation = destroyChild ∨ operation = destroyParent ∨
      operation = destroyAgain)
    (fill_candidate : (calculation operation).IsFillCandidate candidate) :
    False := by
  have fill_eq : (if operation = createChild then some createParent
      else if operation = recreateParent then some destroyParent
      else none) = some candidate := fill_candidate
  rcases is_destroy with rfl | rfl | rfl <;>
    (rw [if_neg (by decide), if_neg (by decide)] at fill_eq
     exact nomatch fill_eq)

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  constructor
  · rintro (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · exact fill_create_child
    · exact ⟨after_comparison_create_child,
        Or.inl (not_move_of_kind_create rfl)⟩
    · exact ⟨after_comparison_destroy_child,
        Or.inl (not_move_of_kind_destroy rfl)⟩
    · exact fill_recreate
    · exact ⟨after_comparison_recreate,
        Or.inl (not_move_of_kind_create rfl)⟩
  · intro rule_dependency
    rcases operation_kind : operation.kind with target | target | source_target
    · have fill : (calculation operation).IsFillCandidate candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases in_collection_shapes (Or.inr fill) with
        ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · simp [destroyChild] at operation_kind
      · simp [destroyParent] at operation_kind
      · simp [destroyAgain] at operation_kind
      · exact Or.inl ⟨rfl, rfl⟩
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩)))
    · have after_correction :
            (calculation operation).AfterMoveCorrection dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes after_correction.1 with
        ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
      · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩)))
      · simp [createChild] at operation_kind
      · simp [recreateParent] at operation_kind
    · have move_rule :
            (calculation operation).MoveRuleDependency dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes move_rule.1.1 with
        ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · simp [destroyChild] at operation_kind
      · simp [destroyParent] at operation_kind
      · simp [destroyAgain] at operation_kind
      · simp [createChild] at operation_kind
      · simp [recreateParent] at operation_kind

def graph : ResolvedDefineGraph where
  isOperation := isOperation
  dependency := dependency
  calculation := calculation
  calculation_operation := fun _ => rfl
  calculation_well_formed := calculation_well_formed
  exact_dependency := exact_dependency
  occupancy := occupancy
  sourceCandidateAt := sourceCandidateAt
  source_candidate_iff := fun _ _ => Iff.rfl
  source_candidate_empty_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨childPosition, rfl, Or.inl List.prefix_rfl⟩
      · exact ⟨childPosition, rfl, Or.inl ⟨[0], rfl⟩⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨parentPosition, rfl, Or.inr ⟨[0], rfl⟩⟩
      · exact ⟨parentPosition, rfl, Or.inl List.prefix_rfl⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨parentPosition, rfl, Or.inr ⟨[0], rfl⟩⟩
      · exact ⟨parentPosition, rfl, Or.inl List.prefix_rfl⟩
  source_candidate_operated_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨_, rfl, List.prefix_rfl⟩
  non_move_source_candidate_operates_on_position := by
    intro operation candidate candidatePosition candidate_at _
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;> rfl
  source_candidate_is_previous := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createChild.operationOrder < destroyChild.operationOrder)
      · exact (by decide :
          createParent.operationOrder < destroyChild.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          destroyChild.operationOrder < destroyParent.operationOrder)
      · exact (by decide :
          createParent.operationOrder < destroyParent.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          destroyChild.operationOrder < destroyAgain.operationOrder)
      · exact (by decide :
          recreateParent.operationOrder < destroyAgain.operationOrder)
  source_candidate_operations := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩
  latest_source_candidate := by
    intro operation emptyPosition position previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_child : emptyPosition = childPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_child
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_parent : position = parentPosition := previous_operates
        subst position_is_parent
        exact ⟨createParent, Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_child : position = childPosition := previous_operates
        subst position_is_child
        exact ⟨createChild, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · have empty_is_parent : emptyPosition = parentPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_parent
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_parent : position = parentPosition := previous_operates
        subst position_is_parent
        exact ⟨createParent, Or.inr (Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
          Or.inl rfl⟩
      · have position_is_child : position = childPosition := previous_operates
        subst position_is_child
        exact ⟨destroyChild, Or.inr (Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩),
          Or.inr (by decide :
            createChild.operationOrder < destroyChild.operationOrder)⟩
      · have position_is_child : position = childPosition := previous_operates
        subst position_is_child
        exact ⟨destroyChild, Or.inr (Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩),
          Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_parent : emptyPosition = parentPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_parent
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_parent : position = parentPosition := previous_operates
        subst position_is_parent
        exact ⟨recreateParent, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
          Or.inr (by decide :
            createParent.operationOrder < recreateParent.operationOrder)⟩
      · have position_is_child : position = childPosition := previous_operates
        subst position_is_child
        exact ⟨destroyChild, Or.inr (Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩),
          Or.inr (by decide :
            createChild.operationOrder < destroyChild.operationOrder)⟩
      · have position_is_child : position = childPosition := previous_operates
        subst position_is_child
        exact ⟨destroyChild, Or.inr (Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩),
          Or.inl rfl⟩
      · have position_is_parent : position = parentPosition := previous_operates
        subst position_is_parent
        exact ⟨recreateParent, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
          Or.inr (by decide :
            destroyParent.operationOrder < recreateParent.operationOrder)⟩
      · have position_is_parent : position = parentPosition := previous_operates
        subst position_is_parent
        exact ⟨recreateParent, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
          Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    rcases in_collection_shapes (Or.inr fill_candidate) with
      ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact (no_destroy_fill (Or.inl rfl) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inl rfl)) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inr rfl)) fill_candidate).elim
    · exact ⟨childPosition, parentPosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact ⟨parentPosition, parentPosition, rfl, rfl, List.prefix_rfl⟩
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    rcases in_collection_shapes (Or.inr fill_candidate) with
      ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact (no_destroy_fill (Or.inl rfl) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inl rfl)) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inr rfl)) fill_candidate).elim
    · exact (by decide :
        createParent.operationOrder < createChild.operationOrder)
    · exact (by decide :
        destroyParent.operationOrder < recreateParent.operationOrder)
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    rcases in_collection_shapes (Or.inr fill_candidate) with
      ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact (no_destroy_fill (Or.inl rfl) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inl rfl)) fill_candidate).elim
    · exact (no_destroy_fill (Or.inr (Or.inr rfl)) fill_candidate).elim
    · exact ⟨by simp [isOperation], by simp [isOperation]⟩
    · exact ⟨by simp [isOperation], by simp [isOperation]⟩

example : dependency destroyAgain recreateParent :=
  Or.inr (Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩)))

example : Acyclic graph.dependency := graph.acyclic

example : TransitivelyMinimal graph.dependency := graph.transitivelyMinimal

end VanishedChildName

namespace MovedChildEntry

def sourcePosition : Position := [0]

def sourceChild : Position := [0, 0]

def targetPosition : Position := [1]

def targetChild : Position := [1, 0]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create sourcePosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create sourceChild

def moveParent : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move sourcePosition targetPosition

def destroyMovedChild : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy targetChild

def destroyMovedParent : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .destroy targetPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createParent ∨ operation = createChild ∨ operation = moveParent ∨
    operation = destroyMovedChild ∨ operation = destroyMovedParent

def operationAt : Nat → Option ParticleOperation
  | 0 => some createParent
  | 1 => some createChild
  | 2 => some moveParent
  | 3 => some destroyMovedChild
  | 4 => some destroyMovedParent
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

theorem operationAt_tail (operationOrder : Nat) :
    operationAt (operationOrder + 5) = none := rfl

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = [0, 0] ∨ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔
      position = [1] ∨ position = [1, 0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_two _).mp source_occupied with
        extended | extended | extended
      · have relative_shape : relative = [0] := by
          simpa [sourcePosition] using extended
        subst relative_shape
        exact Or.inr (Or.inl rfl)
      · have relative_shape : relative = [] := by
          simpa [sourcePosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · exact nomatch extended
    · rcases (occupied_two position).mp occupied with rfl | rfl | rfl
      · exact absurd ⟨[0], rfl⟩ not_source
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inr rfl)
  · rintro (rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_two _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inl ⟨[0], rfl, (occupied_two _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0] : List Nat) <+: []; decide,
        by show ¬([1] : List Nat) <+: []; decide,
        (occupied_two _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔ position = [1] ∨ position = [] := by
  constructor
  · rintro ⟨not_under_child, occupied⟩
    rcases (occupied_three position).mp occupied with rfl | rfl | rfl
    · exact Or.inl rfl
    · exact absurd List.prefix_rfl not_under_child
    · exact Or.inr rfl
  · rintro (rfl | rfl)
    · exact ⟨by show ¬([1, 0] : List Nat) <+: [1]; decide,
        (occupied_three _).mpr (Or.inl rfl)⟩
    · exact ⟨by show ¬([1, 0] : List Nat) <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr rfl))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔ position = [] := by
  constructor
  · rintro ⟨not_under_parent, occupied⟩
    rcases (occupied_four position).mp occupied with rfl | rfl
    · exact absurd List.prefix_rfl not_under_parent
    · rfl
  · rintro rfl
    exact ⟨by show ¬([1] : List Nat) <+: []; decide,
      (occupied_four _).mpr (Or.inr rfl)⟩

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 5) position ↔ occupiedBefore 5 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 5) position ↔
            occupiedBefore (extra + 5) position := by
        show occupiedBefore (extra + 5 + 1) position ↔ _
        simp [occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Option.some.inj operation_at).symm)))
    · simp [operationAt_tail] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt_tail] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | operationOrder
    · rw [occupied_zero] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_one] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_two] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_three] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inl rfl
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_four] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_tail, occupied_five] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some source)
    · exact nomatch
        (empty_position : (none : Option Position) = some source)
    · have source_is_source : source = sourcePosition :=
        (Option.some.inj empty_position).symm
      subst source_is_source
      exact (occupied_two _).mpr (Or.inr (Or.inl rfl))
    · have source_is_child : source = targetChild :=
        (Option.some.inj empty_position).symm
      subst source_is_child
      exact (occupied_three _).mpr (Or.inr (Or.inl rfl))
    · have source_is_target : source = targetPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_target
      exact (occupied_four _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · have target_is_source : target = sourcePosition :=
        (Option.some.inj fill_position).symm
      subst target_is_source
      intro occupied
      simpa [sourcePosition] using (occupied_zero sourcePosition).mp occupied
    · have target_is_child : target = sourceChild :=
        (Option.some.inj fill_position).symm
      subst target_is_child
      intro occupied
      rcases (occupied_one sourceChild).mp occupied with child_eq | child_eq <;>
        simp [sourceChild] at child_eq
    · have target_is_target : target = targetPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_target
      intro occupied
      rcases (occupied_two targetPosition).mp occupied with
        target_eq | target_eq | target_eq <;>
        simp [targetPosition] at target_eq
    · exact nomatch
        (fill_position : (none : Option Position) = some target)
    · exact nomatch
        (fill_position : (none : Option Position) = some target)
  operation_transition := by
    intro operationOrder operation operation_at position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [operation_at]
  no_operation_transition := by
    intro operationOrder no_operation position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [no_operation]

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  (operation = moveParent ∧
    ((candidate = createChild ∧ candidatePosition = sourceChild) ∨
      (candidate = createParent ∧ candidatePosition = sourcePosition))) ∨
  (operation = destroyMovedChild ∧
    ((candidate = moveParent ∧ candidatePosition = targetChild) ∨
      (candidate = moveParent ∧ candidatePosition = targetPosition))) ∨
  (operation = destroyMovedParent ∧
    ((candidate = destroyMovedChild ∧ candidatePosition = targetChild) ∨
      (candidate = moveParent ∧ candidatePosition = targetPosition)))

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := fun candidate =>
    ∃ candidatePosition, sourceCandidateAt operation candidate candidatePosition
  fillCandidate := if operation = createChild then some createParent else none

def dependency (operation candidate : ParticleOperation) : Prop :=
  (operation = createChild ∧ candidate = createParent) ∨
    (operation = moveParent ∧ candidate = createChild) ∨
    (operation = destroyMovedChild ∧ candidate = moveParent) ∨
    (operation = destroyMovedParent ∧ candidate = destroyMovedChild)

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rintro candidate ⟨candidatePosition, source_at⟩
      rcases source_at with ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ <;>
        simp [moveParent, destroyMovedChild, destroyMovedParent] at operation_kind
  | destroy target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rw [if_neg]
      intro operation_is_create_child
      subst operation_is_create_child
      simp [createChild] at operation_kind
  | move source target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]

theorem fill_create_child :
    (calculation createChild).fillCandidate = some createParent := by
  show (if (createChild : ParticleOperation) = createChild then some createParent
    else none) = some createParent
  rw [if_pos rfl]

theorem no_fill_except_create_child {operation candidate : ParticleOperation}
    (not_create_child : operation ≠ createChild)
    (fill_candidate : (calculation operation).IsFillCandidate candidate) :
    False := by
  have fill_eq : (if operation = createChild then some createParent
      else none) = some candidate := fill_candidate
  rw [if_neg not_create_child] at fill_eq
  exact nomatch fill_eq

theorem in_collection_shapes {operation candidate : ParticleOperation}
    (in_collection : (calculation operation).InCollection candidate) :
    (operation = moveParent ∧
      (candidate = createChild ∨ candidate = createParent)) ∨
    (operation = destroyMovedChild ∧ candidate = moveParent) ∨
    (operation = destroyMovedParent ∧
      (candidate = destroyMovedChild ∨ candidate = moveParent)) ∨
    (operation = createChild ∧ candidate = createParent) := by
  rcases in_collection with ⟨candidatePosition, source_at⟩ | fill
  · rcases source_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · exact Or.inl ⟨rfl, shapes.imp And.left And.left⟩
    · rcases shapes with ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, shapes.imp And.left And.left⟩))
  · have fill_eq : (if operation = createChild then some createParent
        else none) = some candidate := fill
    by_cases is_create_child : operation = createChild
    · rw [if_pos is_create_child] at fill_eq
      exact Or.inr (Or.inr (Or.inr
        ⟨is_create_child, (Option.some.inj fill_eq).symm⟩))
    · rw [if_neg is_create_child] at fill_eq
      exact nomatch fill_eq

theorem related_child_parent : OperationsRelated createChild createParent :=
  ⟨sourceChild, sourcePosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem related_destroy_child_move :
    OperationsRelated destroyMovedChild moveParent :=
  ⟨targetChild, targetPosition, rfl, Or.inr rfl, Or.inr ⟨[0], rfl⟩⟩

theorem after_comparison_shapes {operation candidate : ParticleOperation}
    (after_comparison : (calculation operation).AfterComparison candidate) :
    (operation = moveParent ∧ candidate = createChild) ∨
    (operation = destroyMovedChild ∧ candidate = moveParent) ∨
    (operation = destroyMovedParent ∧ candidate = destroyMovedChild) ∨
    (operation = createChild ∧ candidate = createParent) := by
  rcases in_collection_shapes after_comparison.1 with
    ⟨rfl, shapes⟩ | ⟨rfl, rfl⟩ | ⟨rfl, shapes⟩ | shape
  · rcases shapes with rfl | rfl
    · exact Or.inl ⟨rfl, rfl⟩
    · exact (after_comparison.2 createChild
        (Or.inl ⟨sourceChild, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide : createParent.operationOrder < createChild.operationOrder)
        related_child_parent).elim
  · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
  · rcases shapes with rfl | rfl
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
    · exact (after_comparison.2 destroyMovedChild
        (Or.inl ⟨targetChild, Or.inr (Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩)⟩)
        (by decide :
          moveParent.operationOrder < destroyMovedChild.operationOrder)
        related_destroy_child_move).elim
  · exact Or.inr (Or.inr (Or.inr shape))

theorem after_comparison_move_source :
    (calculation moveParent).AfterComparison createChild := by
  refine ⟨Or.inl ⟨sourceChild, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_masked_child :
    (calculation destroyMovedChild).AfterComparison moveParent := by
  refine ⟨Or.inl ⟨targetChild, Or.inr (Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩)⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_destroy_child :
    (calculation destroyMovedParent).AfterComparison destroyMovedChild := by
  refine ⟨Or.inl ⟨targetChild, Or.inr (Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩)⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨_, rfl | rfl⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  constructor
  · rintro (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · exact fill_create_child
    · exact ⟨⟨after_comparison_move_source,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal => no_fill_except_create_child (by decide) removal.1⟩
    · exact ⟨after_comparison_masked_child,
        Or.inr fun other other_comparison other_ne _ => by
          rcases in_collection_shapes other_comparison.1 with
            ⟨op_eq, _⟩ | ⟨_, rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
          · exact absurd op_eq (by decide)
          · exact absurd rfl other_ne
          · exact absurd op_eq (by decide)
          · exact absurd op_eq (by decide)⟩
    · exact ⟨after_comparison_destroy_child,
        Or.inl (not_move_of_kind_destroy rfl)⟩
  · intro rule_dependency
    rcases operation_kind : operation.kind with target | target | source_target
    · have fill : (calculation operation).IsFillCandidate candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases in_collection_shapes (Or.inr fill) with
        ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, rfl⟩
      · simp [moveParent] at operation_kind
      · simp [destroyMovedChild] at operation_kind
      · simp [destroyMovedParent] at operation_kind
      · exact Or.inl ⟨rfl, rfl⟩
    · have after_correction :
            (calculation operation).AfterMoveCorrection dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes after_correction.1 with
        ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · simp [moveParent] at operation_kind
      · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
      · exact Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩))
      · simp [createChild] at operation_kind
    · have move_rule :
            (calculation operation).MoveRuleDependency dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes move_rule.1.1 with
        ⟨rfl, rfl⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
      · simp [destroyMovedChild] at operation_kind
      · simp [destroyMovedParent] at operation_kind
      · simp [createChild] at operation_kind

def graph : ResolvedDefineGraph where
  isOperation := isOperation
  dependency := dependency
  calculation := calculation
  calculation_operation := fun _ => rfl
  calculation_well_formed := calculation_well_formed
  exact_dependency := exact_dependency
  occupancy := occupancy
  sourceCandidateAt := sourceCandidateAt
  source_candidate_iff := fun _ _ => Iff.rfl
  source_candidate_empty_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨sourcePosition, rfl, Or.inr ⟨[0], rfl⟩⟩
      · exact ⟨sourcePosition, rfl, Or.inl List.prefix_rfl⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨targetChild, rfl, Or.inl List.prefix_rfl⟩
      · exact ⟨targetChild, rfl, Or.inl ⟨[0], rfl⟩⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨targetPosition, rfl, Or.inr ⟨[0], rfl⟩⟩
      · exact ⟨targetPosition, rfl, Or.inl List.prefix_rfl⟩
  source_candidate_operated_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨sourceChild, rfl, List.prefix_rfl⟩
      · exact ⟨sourcePosition, rfl, List.prefix_rfl⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨targetPosition, Or.inr rfl, ⟨[0], rfl⟩⟩
      · exact ⟨targetPosition, Or.inr rfl, List.prefix_rfl⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact ⟨targetChild, rfl, List.prefix_rfl⟩
      · exact ⟨targetPosition, Or.inr rfl, List.prefix_rfl⟩
  non_move_source_candidate_operates_on_position := by
    intro operation candidate candidatePosition candidate_at not_move
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;> rfl
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
        exact absurd ⟨sourcePosition, targetPosition, rfl⟩ not_move
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · rfl
      · exact absurd ⟨sourcePosition, targetPosition, rfl⟩ not_move
  source_candidate_is_previous := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createChild.operationOrder < moveParent.operationOrder)
      · exact (by decide :
          createParent.operationOrder < moveParent.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          moveParent.operationOrder < destroyMovedChild.operationOrder)
      · exact (by decide :
          moveParent.operationOrder < destroyMovedChild.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          destroyMovedChild.operationOrder < destroyMovedParent.operationOrder)
      · exact (by decide :
          moveParent.operationOrder < destroyMovedParent.operationOrder)
  source_candidate_operations := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩
  latest_source_candidate := by
    intro operation emptyPosition position previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    rcases operation_member with rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_source : emptyPosition = sourcePosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_source
      rcases previous_member with rfl | rfl | rfl | rfl | rfl
      · have position_is_source : position = sourcePosition := previous_operates
        subst position_is_source
        exact ⟨createParent, Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_child : position = sourceChild := previous_operates
        subst position_is_child
        exact ⟨createChild, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · have empty_is_child : emptyPosition = targetChild :=
        (Option.some.inj empty_position).symm
      subst empty_is_child
      rcases previous_member with rfl | rfl | rfl | rfl | rfl
      · have position_is_source : position = sourcePosition := previous_operates
        subst position_is_source
        exact absurd position_related
          (by decide : ¬(sourcePosition <+: targetChild ∨
            targetChild <+: sourcePosition))
      · have position_is_child : position = sourceChild := previous_operates
        subst position_is_child
        exact absurd position_related
          (by decide : ¬(sourceChild <+: targetChild ∨
            targetChild <+: sourceChild))
      · rcases previous_operates with rfl | rfl
        · exact absurd position_related
            (by decide : ¬(sourcePosition <+: targetChild ∨
              targetChild <+: sourcePosition))
        · exact ⟨moveParent, Or.inr (Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
            Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · have empty_is_target : emptyPosition = targetPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_target
      rcases previous_member with rfl | rfl | rfl | rfl | rfl
      · have position_is_source : position = sourcePosition := previous_operates
        subst position_is_source
        exact absurd position_related
          (by decide : ¬(sourcePosition <+: targetPosition ∨
            targetPosition <+: sourcePosition))
      · have position_is_child : position = sourceChild := previous_operates
        subst position_is_child
        exact absurd position_related
          (by decide : ¬(sourceChild <+: targetPosition ∨
            targetPosition <+: sourceChild))
      · rcases previous_operates with rfl | rfl
        · exact absurd position_related
            (by decide : ¬(sourcePosition <+: targetPosition ∨
              targetPosition <+: sourcePosition))
        · exact ⟨moveParent, Or.inr (Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩),
            Or.inl rfl⟩
      · have position_is_child : position = targetChild := previous_operates
        subst position_is_child
        exact ⟨destroyMovedChild, Or.inr (Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩),
          Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    by_cases is_create_child : operation = createChild
    · subst is_create_child
      have candidate_is_parent : candidate = createParent :=
        (Option.some.inj ((fill_create_child).symm.trans fill_candidate)).symm
      subst candidate_is_parent
      exact ⟨sourceChild, sourcePosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact (no_fill_except_create_child is_create_child fill_candidate).elim
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    by_cases is_create_child : operation = createChild
    · subst is_create_child
      have candidate_is_parent : candidate = createParent :=
        (Option.some.inj ((fill_create_child).symm.trans fill_candidate)).symm
      subst candidate_is_parent
      exact (by decide :
        createParent.operationOrder < createChild.operationOrder)
    · exact (no_fill_except_create_child is_create_child fill_candidate).elim
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    by_cases is_create_child : operation = createChild
    · subst is_create_child
      have candidate_is_parent : candidate = createParent :=
        (Option.some.inj ((fill_create_child).symm.trans fill_candidate)).symm
      subst candidate_is_parent
      exact ⟨by simp [isOperation], by simp [isOperation]⟩
    · exact (no_fill_except_create_child is_create_child fill_candidate).elim

example : dependency destroyMovedChild moveParent :=
  Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))

example : Acyclic graph.dependency := graph.acyclic

example : TransitivelyMinimal graph.dependency := graph.transitivelyMinimal

end MovedChildEntry

namespace FillDependencyRemoval

def boxPosition : Position := [0]

def itemPosition : Position := [0, 0]

def holderPosition : Position := [1]

def payPosition : Position := [1, 0]

def depositPosition : Position := [1, 1]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createItem : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create itemPosition

def createHolder : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .create holderPosition

def moveItemToPay : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move itemPosition payPosition

def createSecondItem : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .create itemPosition

def moveSecondToDeposit : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move itemPosition depositPosition

def isOperation (operation : ParticleOperation) : Prop :=
  operation = createBox ∨ operation = createItem ∨ operation = createHolder ∨
    operation = moveItemToPay ∨ operation = createSecondItem ∨
    operation = moveSecondToDeposit

def operationAt : Nat → Option ParticleOperation
  | 0 => some createBox
  | 1 => some createItem
  | 2 => some createHolder
  | 3 => some moveItemToPay
  | 4 => some createSecondItem
  | 5 => some moveSecondToDeposit
  | _ => none

def occupiedBefore : Nat → Position → Prop
  | 0, position => position = []
  | operationOrder + 1, position =>
      match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position

theorem operationAt_tail (operationOrder : Nat) :
    operationAt (operationOrder + 6) = none := rfl

theorem occupied_zero (position : Position) :
    occupiedBefore 0 position ↔ position = [] := Iff.rfl

theorem occupied_one (position : Position) :
    occupiedBefore 1 position ↔ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_two (position : Position) :
    occupiedBefore 2 position ↔
      position = [0, 0] ∨ position = [0] ∨ position = [] := Iff.rfl

theorem occupied_three (position : Position) :
    occupiedBefore 3 position ↔
      position = [1] ∨ position = [0, 0] ∨ position = [0] ∨ position = [] :=
  Iff.rfl

theorem occupied_four (position : Position) :
    occupiedBefore 4 position ↔
      position = [1, 0] ∨ position = [1] ∨ position = [0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_three _).mp source_occupied with
        extended | extended | extended | extended
      · simp [itemPosition] at extended
      · have relative_shape : relative = [] := by
          simpa [itemPosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · simp [itemPosition] at extended
      · exact nomatch extended
    · rcases (occupied_three position).mp occupied with rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr rfl))
  · rintro (rfl | rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_three _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1]; decide,
        by show ¬([1, 0] : List Nat) <+: [1]; decide,
        (occupied_three _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        by show ¬([1, 0] : List Nat) <+: [0]; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        by show ¬([1, 0] : List Nat) <+: []; decide,
        (occupied_three _).mpr (Or.inr (Or.inr (Or.inr rfl)))⟩

theorem occupied_five (position : Position) :
    occupiedBefore 5 position ↔
      position = [0, 0] ∨ position = [1, 0] ∨ position = [1] ∨
        position = [0] ∨ position = [] := by
  constructor
  · rintro (rfl | occupied)
    · exact Or.inl rfl
    · rcases (occupied_four position).mp occupied with rfl | rfl | rfl | rfl
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
  · rintro (rfl | rfl | rfl | rfl | rfl)
    · exact Or.inl rfl
    · exact Or.inr ((occupied_four _).mpr (Or.inl rfl))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inl rfl)))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inr (Or.inl rfl))))
    · exact Or.inr ((occupied_four _).mpr (Or.inr (Or.inr (Or.inr rfl))))

theorem occupied_six (position : Position) :
    occupiedBefore 6 position ↔
      position = [1, 1] ∨ position = [1, 0] ∨ position = [1] ∨
        position = [0] ∨ position = [] := by
  constructor
  · rintro (⟨relative, rfl, source_occupied⟩ | ⟨not_source, _, occupied⟩)
    · rcases (occupied_five _).mp source_occupied with
        extended | extended | extended | extended | extended
      · have relative_shape : relative = [] := by
          simpa [itemPosition] using extended
        subst relative_shape
        exact Or.inl rfl
      · simp [itemPosition] at extended
      · simp [itemPosition] at extended
      · simp [itemPosition] at extended
      · exact nomatch extended
    · rcases (occupied_five position).mp occupied with rfl | rfl | rfl | rfl | rfl
      · exact absurd List.prefix_rfl not_source
      · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
  · rintro (rfl | rfl | rfl | rfl | rfl)
    · exact Or.inl ⟨[], rfl, (occupied_five _).mpr (Or.inl rfl)⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1, 0]; decide,
        by show ¬([1, 1] : List Nat) <+: [1, 0]; decide,
        (occupied_five _).mpr (Or.inr (Or.inl rfl))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [1]; decide,
        by show ¬([1, 1] : List Nat) <+: [1]; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inl rfl)))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: [0]; decide,
        by show ¬([1, 1] : List Nat) <+: [0]; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inr (Or.inl rfl))))⟩
    · exact Or.inr ⟨by show ¬([0, 0] : List Nat) <+: []; decide,
        by show ¬([1, 1] : List Nat) <+: []; decide,
        (occupied_five _).mpr (Or.inr (Or.inr (Or.inr (Or.inr rfl))))⟩

theorem occupied_tail (extra : Nat) (position : Position) :
    occupiedBefore (extra + 6) position ↔ occupiedBefore 6 position := by
  induction extra with
  | zero => exact Iff.rfl
  | succ extra induction_hypothesis =>
      have step :
          occupiedBefore (extra + 1 + 6) position ↔
            occupiedBefore (extra + 6) position := by
        show occupiedBefore (extra + 6 + 1) position ↔ _
        simp [occupiedBefore, operationAt_tail]
      exact step.trans induction_hypothesis

def occupancy : ExactOccupancyExecution isOperation where
  operationAt := operationAt
  occupiedBefore := occupiedBefore
  member_operation_at := by
    intro operation operation_member
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl <;> rfl
  operation_at_is_member := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · exact Or.inl (Option.some.inj operation_at).symm
    · exact Or.inr (Or.inl (Option.some.inj operation_at).symm)
    · exact Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm))
    · exact Or.inr (Or.inr (Or.inr (Or.inl (Option.some.inj operation_at).symm)))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
        (Option.some.inj operation_at).symm))))
    · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
        (Option.some.inj operation_at).symm))))
    · simp [operationAt_tail] at operation_at
  operation_at_has_order := by
    intro operationOrder operation operation_at
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    all_goals first
      | (rw [← Option.some.inj operation_at]; rfl)
      | simp [operationAt_tail] at operation_at
  parent_position_is_occupied := by
    intro operationOrder parent child parent_of_child child_occupied
    rcases operationOrder with _ | _ | _ | _ | _ | _ | operationOrder
    · rw [occupied_zero] at child_occupied ⊢
      exact List.eq_nil_of_prefix_nil (child_occupied ▸ parent_of_child)
    · rw [occupied_one] at child_occupied ⊢
      rcases child_occupied with rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr rfl
        · exact Or.inl rfl
      · exact Or.inr (List.eq_nil_of_prefix_nil parent_of_child)
    · rw [occupied_two] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr rfl)
        · exact Or.inr (Or.inl rfl)
      · exact Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child))
    · rw [occupied_three] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child)))
    · rw [occupied_four] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inl rfl)
        · exact Or.inl rfl
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr rfl))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · exact Or.inr (Or.inr (Or.inr (List.eq_nil_of_prefix_nil parent_of_child)))
    · rw [occupied_five] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr
          (List.eq_nil_of_prefix_nil parent_of_child))))
    · rw [occupied_tail, occupied_six] at child_occupied ⊢
      rcases child_occupied with rfl | rfl | rfl | rfl | rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inl rfl
      · rcases prefix_pair_iff.mp parent_of_child with rfl | rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
        · exact Or.inr (Or.inl rfl)
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inl rfl))
      · rcases prefix_singleton_iff.mp parent_of_child with rfl | rfl
        · exact Or.inr (Or.inr (Or.inr (Or.inr rfl)))
        · exact Or.inr (Or.inr (Or.inr (Or.inl rfl)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr
          (List.eq_nil_of_prefix_nil parent_of_child))))
  empty_position_is_occupied := by
    intro operation source operation_member empty_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · have source_is_item : source = itemPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_item
      exact (occupied_three _).mpr (Or.inr (Or.inl rfl))
    · exact nomatch (empty_position : (none : Option Position) = some source)
    · have source_is_item : source = itemPosition :=
        (Option.some.inj empty_position).symm
      subst source_is_item
      exact (occupied_five _).mpr (Or.inl rfl)
  fill_position_is_empty := by
    intro operation target operation_member fill_position
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · have target_is_box : target = boxPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_box
      intro occupied
      simpa [boxPosition] using (occupied_zero boxPosition).mp occupied
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro occupied
      rcases (occupied_one itemPosition).mp occupied with item_eq | item_eq <;>
        simp [itemPosition] at item_eq
    · have target_is_holder : target = holderPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_holder
      intro occupied
      rcases (occupied_two holderPosition).mp occupied with
        holder_eq | holder_eq | holder_eq <;>
        simp [holderPosition] at holder_eq
    · have target_is_pay : target = payPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_pay
      intro occupied
      rcases (occupied_three payPosition).mp occupied with
        pay_eq | pay_eq | pay_eq | pay_eq <;>
        simp [payPosition] at pay_eq
    · have target_is_item : target = itemPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_item
      intro occupied
      rcases (occupied_four itemPosition).mp occupied with
        item_eq | item_eq | item_eq | item_eq <;>
        simp [itemPosition] at item_eq
    · have target_is_deposit : target = depositPosition :=
        (Option.some.inj fill_position).symm
      subst target_is_deposit
      intro occupied
      rcases (occupied_five depositPosition).mp occupied with
        deposit_eq | deposit_eq | deposit_eq | deposit_eq | deposit_eq <;>
        simp [depositPosition] at deposit_eq
  operation_transition := by
    intro operationOrder operation operation_at position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [operation_at]
  no_operation_transition := by
    intro operationOrder no_operation position
    show (match operationAt operationOrder with
      | some operation =>
          OccupancyAfter operation (occupiedBefore operationOrder) position
      | none => occupiedBefore operationOrder position) ↔ _
    rw [no_operation]

def sourceCandidateAt (operation candidate : ParticleOperation)
    (candidatePosition : Position) : Prop :=
  (operation = moveItemToPay ∧
    ((candidate = createItem ∧ candidatePosition = itemPosition) ∨
      (candidate = createBox ∧ candidatePosition = boxPosition))) ∨
  (operation = moveSecondToDeposit ∧
    ((candidate = createSecondItem ∧ candidatePosition = itemPosition) ∨
      (candidate = createBox ∧ candidatePosition = boxPosition)))

def calculation (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := fun candidate =>
    ∃ candidatePosition, sourceCandidateAt operation candidate candidatePosition
  fillCandidate :=
    if operation = createItem then some createBox
    else if operation = moveItemToPay then some createHolder
    else if operation = createSecondItem then some moveItemToPay
    else if operation = moveSecondToDeposit then some createHolder
    else none

def dependency (operation candidate : ParticleOperation) : Prop :=
  (operation = createItem ∧ candidate = createBox) ∨
    (operation = moveItemToPay ∧ candidate = createItem) ∨
    (operation = moveItemToPay ∧ candidate = createHolder) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧ candidate = createSecondItem)

theorem calculation_well_formed (operation : ParticleOperation) :
    (calculation operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rintro candidate ⟨candidatePosition, source_at⟩
      rcases source_at with ⟨rfl, _⟩ | ⟨rfl, _⟩ <;>
        simp [moveItemToPay, moveSecondToDeposit] at operation_kind
  | destroy target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]
      rw [if_neg, if_neg, if_neg, if_neg]
      all_goals
        intro operation_is_filler
        subst operation_is_filler
        simp [createItem, moveItemToPay, createSecondItem,
          moveSecondToDeposit] at operation_kind
  | move source target =>
      simp only [RuleCalculation.WellFormed, calculation, operation_kind]

theorem fill_item : (calculation createItem).fillCandidate = some createBox := by
  show (if (createItem : ParticleOperation) = createItem then some createBox
    else if (createItem : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (createItem : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (createItem : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createBox
  rw [if_pos rfl]

theorem fill_first_move :
    (calculation moveItemToPay).fillCandidate = some createHolder := by
  show (if (moveItemToPay : ParticleOperation) = createItem then some createBox
    else if (moveItemToPay : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (moveItemToPay : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (moveItemToPay : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createHolder
  rw [if_neg (by decide), if_pos rfl]

theorem fill_second_item :
    (calculation createSecondItem).fillCandidate = some moveItemToPay := by
  show (if (createSecondItem : ParticleOperation) = createItem then
      some createBox
    else if (createSecondItem : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (createSecondItem : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (createSecondItem : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some moveItemToPay
  rw [if_neg (by decide), if_neg (by decide), if_pos rfl]

theorem fill_second_move :
    (calculation moveSecondToDeposit).fillCandidate = some createHolder := by
  show (if (moveSecondToDeposit : ParticleOperation) = createItem then
      some createBox
    else if (moveSecondToDeposit : ParticleOperation) = moveItemToPay then
      some createHolder
    else if (moveSecondToDeposit : ParticleOperation) = createSecondItem then
      some moveItemToPay
    else if (moveSecondToDeposit : ParticleOperation) = moveSecondToDeposit then
      some createHolder
    else none) = some createHolder
  rw [if_neg (by decide), if_neg (by decide), if_neg (by decide), if_pos rfl]

theorem fill_shapes {operation candidate : ParticleOperation}
    (fill : (calculation operation).IsFillCandidate candidate) :
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = moveItemToPay ∧ candidate = createHolder) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧ candidate = createHolder) := by
  have fill_eq : (if operation = createItem then some createBox
      else if operation = moveItemToPay then some createHolder
      else if operation = createSecondItem then some moveItemToPay
      else if operation = moveSecondToDeposit then some createHolder
      else none) = some candidate := fill
  by_cases first : operation = createItem
  · rw [if_pos first] at fill_eq
    exact Or.inl ⟨first, (Option.some.inj fill_eq).symm⟩
  · rw [if_neg first] at fill_eq
    by_cases second : operation = moveItemToPay
    · rw [if_pos second] at fill_eq
      exact Or.inr (Or.inl ⟨second, (Option.some.inj fill_eq).symm⟩)
    · rw [if_neg second] at fill_eq
      by_cases third : operation = createSecondItem
      · rw [if_pos third] at fill_eq
        exact Or.inr (Or.inr (Or.inl ⟨third, (Option.some.inj fill_eq).symm⟩))
      · rw [if_neg third] at fill_eq
        by_cases fourth : operation = moveSecondToDeposit
        · rw [if_pos fourth] at fill_eq
          exact Or.inr (Or.inr (Or.inr
            ⟨fourth, (Option.some.inj fill_eq).symm⟩))
        · rw [if_neg fourth] at fill_eq
          exact nomatch fill_eq

theorem in_collection_shapes {operation candidate : ParticleOperation}
    (in_collection : (calculation operation).InCollection candidate) :
    (operation = moveItemToPay ∧
      (candidate = createItem ∨ candidate = createBox ∨
        candidate = createHolder)) ∨
    (operation = moveSecondToDeposit ∧
      (candidate = createSecondItem ∨ candidate = createBox ∨
        candidate = createHolder)) ∨
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) := by
  rcases in_collection with ⟨candidatePosition, source_at⟩ | fill
  · rcases source_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inl ⟨rfl, Or.inl rfl⟩
      · exact Or.inl ⟨rfl, Or.inr (Or.inl rfl)⟩
    · rcases shapes with ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, Or.inl rfl⟩)
      · exact Or.inr (Or.inl ⟨rfl, Or.inr (Or.inl rfl)⟩)
  · rcases fill_shapes fill with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
    · exact Or.inl ⟨rfl, Or.inr (Or.inr rfl)⟩
    · exact Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩))
    · exact Or.inr (Or.inl ⟨rfl, Or.inr (Or.inr rfl)⟩)

theorem related_item_box : OperationsRelated createItem createBox :=
  ⟨itemPosition, boxPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem related_second_box : OperationsRelated createSecondItem createBox :=
  ⟨itemPosition, boxPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

theorem after_comparison_item :
    (calculation moveItemToPay).AfterComparison createItem := by
  refine ⟨Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent newer_related
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · rcases newer_related with
      ⟨newerPosition, olderPosition, operates_newer, operates_older, related⟩
    have newer_is_holder : newerPosition = holderPosition := operates_newer
    have older_is_item : olderPosition = itemPosition := operates_older
    subst newer_is_holder
    subst older_is_item
    exact absurd related
      (by decide : ¬(holderPosition <+: itemPosition ∨
        itemPosition <+: holderPosition))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_holder_first :
    (calculation moveItemToPay).AfterComparison createHolder := by
  refine ⟨Or.inr fill_first_move, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_second_item :
    (calculation moveSecondToDeposit).AfterComparison createSecondItem := by
  refine ⟨Or.inl ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩, ?_⟩
  intro newer newer_in newer_recent _
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_holder_second :
    (calculation moveSecondToDeposit).AfterComparison createHolder := by
  refine ⟨Or.inr fill_second_move, ?_⟩
  intro newer newer_in newer_recent newer_related
  rcases in_collection_shapes newer_in with
    ⟨op_eq, _⟩ | ⟨_, rfl | rfl | rfl⟩ | ⟨op_eq, _⟩ | ⟨op_eq, _⟩
  · exact absurd op_eq (by decide)
  · rcases newer_related with
      ⟨newerPosition, olderPosition, operates_newer, operates_older, related⟩
    have newer_is_item : newerPosition = itemPosition := operates_newer
    have older_is_holder : olderPosition = holderPosition := operates_older
    subst newer_is_item
    subst older_is_holder
    exact absurd related
      (by decide : ¬(itemPosition <+: holderPosition ∨
        holderPosition <+: itemPosition))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd newer_recent (not_more_recent_of_le (by decide))
  · exact absurd op_eq (by decide)
  · exact absurd op_eq (by decide)

theorem after_comparison_shapes {operation candidate : ParticleOperation}
    (after_comparison : (calculation operation).AfterComparison candidate) :
    (operation = moveItemToPay ∧
      (candidate = createItem ∨ candidate = createHolder)) ∨
    (operation = moveSecondToDeposit ∧
      (candidate = createSecondItem ∨ candidate = createHolder)) ∨
    (operation = createItem ∧ candidate = createBox) ∨
    (operation = createSecondItem ∧ candidate = moveItemToPay) := by
  rcases in_collection_shapes after_comparison.1 with
    ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ | shape | shape
  · rcases shapes with rfl | rfl | rfl
    · exact Or.inl ⟨rfl, Or.inl rfl⟩
    · exact (after_comparison.2 createItem
        (Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide : createBox.operationOrder < createItem.operationOrder)
        related_item_box).elim
    · exact Or.inl ⟨rfl, Or.inr rfl⟩
  · rcases shapes with rfl | rfl | rfl
    · exact Or.inr (Or.inl ⟨rfl, Or.inl rfl⟩)
    · exact (after_comparison.2 createSecondItem
        (Or.inl ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
        (by decide :
          createBox.operationOrder < createSecondItem.operationOrder)
        related_second_box).elim
    · exact Or.inr (Or.inl ⟨rfl, Or.inr rfl⟩)
  · exact Or.inr (Or.inr (Or.inl shape))
  · exact Or.inr (Or.inr (Or.inr shape))

theorem box_no_dependencies (candidate : ParticleOperation) :
    ¬dependency createBox candidate := by
  rintro (⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩ | ⟨box_eq, _⟩) <;>
    exact absurd box_eq (by decide)

theorem item_dependency_is_box {candidate : ParticleOperation}
    (edge : dependency createItem candidate) : candidate = createBox := by
  rcases edge with
    ⟨_, rfl⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩ | ⟨item_eq, _⟩
  · rfl
  all_goals exact absurd item_eq (by decide)

theorem item_no_reach_holder : ¬Reaches dependency createItem createHolder := by
  intro path
  cases path with
  | direct edge =>
      exact absurd (item_dependency_is_box edge) (by decide)
  | step edge rest =>
      rw [item_dependency_is_box edge] at rest
      exact no_reaches_of_no_dependency box_no_dependencies rest

theorem second_item_reaches_holder :
    Reaches dependency createSecondItem createHolder :=
  .step (Or.inr (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))))
    (.direct (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))))

theorem exact_dependency (operation candidate : ParticleOperation) :
    dependency operation candidate ↔
      (calculation operation).Dependency dependency candidate := by
  constructor
  · rintro (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · exact fill_item
    · exact ⟨⟨after_comparison_item,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal =>
          absurd (Option.some.inj (fill_first_move.symm.trans removal.1))
            (by decide)⟩
    · exact ⟨⟨after_comparison_holder_first,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal => by
          rcases removal with
            ⟨_, src, src_candidate, src_correction, src_ne, src_reaches⟩
          rcases src_candidate with ⟨srcPosition, src_at⟩
          rcases src_at with ⟨_, ⟨rfl, _⟩ | ⟨rfl, _⟩⟩ | ⟨move_eq, _⟩
          · exact item_no_reach_holder src_reaches
          · exact src_correction.1.2 createItem
              (Or.inl ⟨itemPosition, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩)
              (by decide :
                createBox.operationOrder < createItem.operationOrder)
              related_item_box
          · exact absurd move_eq (by decide)⟩
    · exact fill_second_item
    · exact ⟨⟨after_comparison_second_item,
        Or.inl (not_move_of_kind_create rfl)⟩,
        fun removal =>
          absurd (Option.some.inj (fill_second_move.symm.trans removal.1))
            (by decide)⟩
  · intro rule_dependency
    rcases operation_kind : operation.kind with target | target | source_target
    · have fill : (calculation operation).IsFillCandidate candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases fill_shapes fill with
        ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact Or.inl ⟨rfl, rfl⟩
      · simp [moveItemToPay] at operation_kind
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩)))
      · simp [moveSecondToDeposit] at operation_kind
    · have after_correction :
            (calculation operation).AfterMoveCorrection dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes after_correction.1 with
        ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · simp [moveItemToPay] at operation_kind
      · simp [moveSecondToDeposit] at operation_kind
      · simp [createItem] at operation_kind
      · simp [createSecondItem] at operation_kind
    · have move_rule :
            (calculation operation).MoveRuleDependency dependency candidate := by
        simpa [RuleCalculation.Dependency, calculation,
          operation_kind] using rule_dependency
      rcases after_comparison_shapes move_rule.1.1 with
        ⟨rfl, rfl | rfl⟩ | ⟨rfl, rfl | rfl⟩ | ⟨rfl, _⟩ | ⟨rfl, _⟩
      · exact Or.inr (Or.inl ⟨rfl, rfl⟩)
      · exact Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨rfl, rfl⟩)))
      · exact (move_rule.2 ⟨fill_second_move, createSecondItem,
          ⟨itemPosition, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩⟩,
          ⟨after_comparison_second_item,
            Or.inl (not_move_of_kind_create rfl)⟩,
          (by decide), second_item_reaches_holder⟩).elim
      · simp [createItem] at operation_kind
      · simp [createSecondItem] at operation_kind

def graph : ResolvedDefineGraph where
  isOperation := isOperation
  dependency := dependency
  calculation := calculation
  calculation_operation := fun _ => rfl
  calculation_well_formed := calculation_well_formed
  exact_dependency := exact_dependency
  occupancy := occupancy
  sourceCandidateAt := sourceCandidateAt
  source_candidate_iff := fun _ _ => Iff.rfl
  source_candidate_empty_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl List.prefix_rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl ⟨[0], rfl⟩⟩
    · exact ⟨itemPosition, rfl, Or.inl List.prefix_rfl⟩
    · exact ⟨itemPosition, rfl, Or.inl ⟨[0], rfl⟩⟩
  source_candidate_operated_position := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨_, rfl, List.prefix_rfl⟩
  non_move_source_candidate_operates_on_position := by
    intro operation candidate candidatePosition candidate_at _
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;> rfl
  source_candidate_is_previous := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createItem.operationOrder < moveItemToPay.operationOrder)
      · exact (by decide :
          createBox.operationOrder < moveItemToPay.operationOrder)
    · rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
      · exact (by decide :
          createSecondItem.operationOrder < moveSecondToDeposit.operationOrder)
      · exact (by decide :
          createBox.operationOrder < moveSecondToDeposit.operationOrder)
  source_candidate_operations := by
    intro operation candidate candidatePosition candidate_at
    rcases candidate_at with ⟨rfl, shapes⟩ | ⟨rfl, shapes⟩ <;>
      rcases shapes with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩
  latest_source_candidate := by
    intro operation emptyPosition position previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    rcases operation_member with rfl | rfl | rfl | rfl | rfl | rfl
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_item : emptyPosition = itemPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_item
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_box : position = boxPosition := previous_operates
        subst position_is_box
        exact ⟨createBox, Or.inl ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createItem, Or.inl ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_holder : position = holderPosition := previous_operates
        subst position_is_holder
        exact absurd position_related
          (by decide : ¬(holderPosition <+: itemPosition ∨
            itemPosition <+: holderPosition))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
    · exact nomatch
        (empty_position : (none : Option Position) = some emptyPosition)
    · have empty_is_item : emptyPosition = itemPosition :=
        (Option.some.inj empty_position).symm
      subst empty_is_item
      rcases previous_member with rfl | rfl | rfl | rfl | rfl | rfl
      · have position_is_box : position = boxPosition := previous_operates
        subst position_is_box
        exact ⟨createBox, Or.inr ⟨rfl, Or.inr ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩,
          Or.inr (by decide :
            createItem.operationOrder < createSecondItem.operationOrder)⟩
      · have position_is_holder : position = holderPosition := previous_operates
        subst position_is_holder
        exact absurd position_related
          (by decide : ¬(holderPosition <+: itemPosition ∨
            itemPosition <+: holderPosition))
      · rcases previous_operates with rfl | rfl
        · exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩,
            Or.inr (by decide :
              moveItemToPay.operationOrder < createSecondItem.operationOrder)⟩
        · exact absurd position_related
            (by decide : ¬(payPosition <+: itemPosition ∨
              itemPosition <+: payPosition))
      · have position_is_item : position = itemPosition := previous_operates
        subst position_is_item
        exact ⟨createSecondItem, Or.inr ⟨rfl, Or.inl ⟨rfl, rfl⟩⟩, Or.inl rfl⟩
      · exact absurd operation_after_previous
          (not_more_recent_of_le (by decide))
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact ⟨itemPosition, boxPosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact ⟨payPosition, holderPosition, rfl, rfl, ⟨[0], rfl⟩⟩
    · exact ⟨itemPosition, itemPosition, rfl, Or.inl rfl, List.prefix_rfl⟩
    · exact ⟨depositPosition, holderPosition, rfl, rfl, ⟨[1], rfl⟩⟩
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
    · exact (by decide : createBox.operationOrder < createItem.operationOrder)
    · exact (by decide :
        createHolder.operationOrder < moveItemToPay.operationOrder)
    · exact (by decide :
        moveItemToPay.operationOrder < createSecondItem.operationOrder)
    · exact (by decide :
        createHolder.operationOrder < moveSecondToDeposit.operationOrder)
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    rcases fill_shapes fill_candidate with
      ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩ <;>
      exact ⟨by simp [isOperation], by simp [isOperation]⟩

example : dependency moveItemToPay createItem := Or.inr (Or.inl ⟨rfl, rfl⟩)

example : dependency moveItemToPay createHolder :=
  Or.inr (Or.inr (Or.inl ⟨rfl, rfl⟩))

example : ¬dependency moveSecondToDeposit createHolder := by
  rintro (⟨move_eq, _⟩ | ⟨move_eq, _⟩ | ⟨move_eq, _⟩ | ⟨move_eq, _⟩ |
    ⟨_, candidate_eq⟩)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd move_eq (by decide)
  · exact absurd candidate_eq (by decide)

example : Acyclic graph.dependency := graph.acyclic

example : TransitivelyMinimal graph.dependency := graph.transitivelyMinimal

end FillDependencyRemoval

end Define.OperationGraph
