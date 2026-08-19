import valid_history

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Dependency Graph Calculation

This module formalizes `calculation.md`. It defines the Fill, Empty, and Move
Rule stages without assuming minimality or completeness.

`WritesEntry` and `IsEntryBefore` give a closed form for the English entry
induction. A Create or Destroy writes its direct position. A Move writes its
source, target, and every renamed transitive child position whose source name
could be queried immediately before the Move. `IsEntryBefore` selects a previous
writer when no later writer precedes the current occurrence.

`calculationFor` instantiates the generic `RuleCalculation` with the entries from
one valid resolved history. `calculatedDependencyBefore` then constructs the
graph by natural-number recursion: the Move Correction and Fill Dependency
removal at index `i` inspect only the graph constructed before index `i`.

The Action Parent Rule is modular compiler-resolution behavior and is not part
of this resolved calculation.
-/

namespace Define.OperationGraph

structure RuleCalculation where
  operation : ParticleOperation
  sourceCandidate : ParticleOperation → Prop
  fillCandidate : Option ParticleOperation

def RuleCalculation.WellFormed (calculation : RuleCalculation) : Prop :=
  match calculation.operation.kind with
  | .create _ => ∀ candidate, ¬calculation.sourceCandidate candidate
  | .destroy _ => calculation.fillCandidate = none
  | .move _ _ => True

def RuleCalculation.IsFillCandidate (calculation : RuleCalculation)
    (candidate : ParticleOperation) : Prop :=
  calculation.fillCandidate = some candidate

def RuleCalculation.InCollection (calculation : RuleCalculation)
    (candidate : ParticleOperation) : Prop :=
  calculation.sourceCandidate candidate ∨ calculation.IsFillCandidate candidate

def RuleCalculation.AfterComparison (calculation : RuleCalculation)
    (candidate : ParticleOperation) : Prop :=
  calculation.InCollection candidate ∧
    ∀ newerCandidate,
      calculation.InCollection newerCandidate →
      MoreRecent newerCandidate candidate →
      OperationsRelated newerCandidate candidate →
      False

def RuleCalculation.AfterMoveCorrection (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidate : ParticleOperation) : Prop :=
  calculation.AfterComparison candidate ∧
    (¬IsMove candidate ∨
      ∀ otherCandidate,
        calculation.AfterComparison otherCandidate →
        otherCandidate ≠ candidate →
        ¬Reaches dependency otherCandidate candidate)

def RuleCalculation.MoveRuleDependency (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidate : ParticleOperation) : Prop :=
  calculation.AfterMoveCorrection dependency candidate ∧
    ¬(calculation.IsFillCandidate candidate ∧
      ∃ sourceCandidate,
        calculation.sourceCandidate sourceCandidate ∧
          calculation.AfterMoveCorrection dependency sourceCandidate ∧
          sourceCandidate ≠ candidate ∧
          Reaches dependency sourceCandidate candidate)

def RuleCalculation.Dependency (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidate : ParticleOperation) : Prop :=
  match calculation.operation.kind with
  | .create _ => calculation.IsFillCandidate candidate
  | .destroy _ => calculation.AfterMoveCorrection dependency candidate
  | .move _ _ => calculation.MoveRuleDependency dependency candidate

theorem RuleCalculation.dependency_isInCollection
    {calculation : RuleCalculation}
    {dependency : ParticleOperation → ParticleOperation → Prop}
    {candidate : ParticleOperation}
    (rule_dependency : calculation.Dependency dependency candidate) :
    calculation.InCollection candidate := by
  cases operation_kind : calculation.operation.kind with
  | create target =>
      exact Or.inr (by
        simpa [RuleCalculation.Dependency, operation_kind] using
          rule_dependency)
  | destroy target =>
      have after_move_correction :
          calculation.AfterMoveCorrection dependency candidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          rule_dependency
      exact after_move_correction.1.1
  | move source target =>
      have move_rule_dependency :
          calculation.MoveRuleDependency dependency candidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          rule_dependency
      exact move_rule_dependency.1.1.1

structure RuleGraph where
  isOperation : ParticleOperation → Prop
  dependency : ParticleOperation → ParticleOperation → Prop
  calculation : ParticleOperation → RuleCalculation
  calculation_operation :
    ∀ operation, (calculation operation).operation = operation
  calculation_well_formed :
    ∀ operation, (calculation operation).WellFormed
  exact_dependency :
    ∀ operation candidate,
      dependency operation candidate ↔
        (calculation operation).Dependency dependency candidate

def WritesEntry {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) (position : Position) : Prop :=
  match operation.kind with
  | .create target | .destroy target => position = target
  | .move source target =>
      position = source ∨ position = target ∨
        ∃ relativePosition,
          relativePosition ≠ [] ∧
            position = target ++ relativePosition ∧
            history.queryableBefore operation.operationOrder
              (source ++ relativePosition)

def IsEntryBefore {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (position : Position) (candidate : ParticleOperation) : Prop :=
  isOperation candidate ∧
    candidate.operationOrder < operationOrder ∧
    WritesEntry history candidate position ∧
    ∀ newerCandidate,
      isOperation newerCandidate →
        MoreRecent newerCandidate candidate →
        newerCandidate.operationOrder < operationOrder →
        ¬WritesEntry history newerCandidate position

theorem IsEntryBefore.candidate_is_operation
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation} {operationOrder : Nat}
    {position : Position} {candidate : ParticleOperation}
    (entry : IsEntryBefore history operationOrder position candidate) :
    isOperation candidate :=
  entry.1

theorem IsEntryBefore.candidate_is_previous
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation} {operationOrder : Nat}
    {position : Position} {candidate : ParticleOperation}
    (entry : IsEntryBefore history operationOrder position candidate) :
    candidate.operationOrder < operationOrder :=
  entry.2.1

theorem not_isEntryBefore_zero
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (position : Position)
    (candidate : ParticleOperation) :
    ¬IsEntryBefore history 0 position candidate := by
  intro entry
  exact Nat.not_lt_zero candidate.operationOrder entry.2.1

theorem IsEntryBefore.unique
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (position : Position) {first second : ParticleOperation}
    (first_entry : IsEntryBefore history operationOrder position first)
    (second_entry : IsEntryBefore history operationOrder position second) :
    first = second := by
  rcases Nat.lt_trichotomy first.operationOrder second.operationOrder with
    first_before_second | same_order | second_before_first
  · exact
      False.elim
        (first_entry.2.2.2 second second_entry.1 first_before_second
          second_entry.2.1 second_entry.2.2.1)
  · have first_at_order := history.member_operation_at first first_entry.1
    have second_at_order := history.member_operation_at second second_entry.1
    rw [same_order] at first_at_order
    exact Option.some.inj (first_at_order.symm.trans second_at_order)
  · exact
      False.elim
        (second_entry.2.2.2 first first_entry.1 second_before_first
          first_entry.2.1 first_entry.2.2.1)

theorem isEntryBefore_after_operation_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (operation candidate : ParticleOperation) (position : Position)
    (operation_at : history.operationAt operationOrder = some operation) :
    IsEntryBefore history (operationOrder + 1) position candidate ↔
      (candidate = operation ∧ WritesEntry history operation position) ∨
        (¬WritesEntry history operation position ∧
          IsEntryBefore history operationOrder position candidate) := by
  classical
  have operation_member : isOperation operation :=
    history.operation_at_is_member operationOrder operation operation_at
  have operation_order : operation.operationOrder = operationOrder :=
    history.operation_at_has_order operationOrder operation operation_at
  constructor
  · intro entry_after
    by_cases candidate_is_operation : candidate = operation
    · exact
        Or.inl
          ⟨candidate_is_operation,
            candidate_is_operation ▸ entry_after.2.2.1⟩
    · have candidate_order_is_not_current :
          candidate.operationOrder ≠ operationOrder := by
        intro candidate_order
        have candidate_at :=
          history.member_operation_at candidate entry_after.1
        rw [candidate_order] at candidate_at
        exact
          candidate_is_operation
            (Option.some.inj (candidate_at.symm.trans operation_at))
      have candidate_before_operation :
          candidate.operationOrder < operationOrder := by
        exact
          Nat.lt_of_le_of_ne (Nat.le_of_lt_succ entry_after.2.1)
            candidate_order_is_not_current
      have operation_does_not_write :
          ¬WritesEntry history operation position := by
        intro operation_writes
        exact
          entry_after.2.2.2 operation operation_member
            (by simp [MoreRecent, operation_order, candidate_before_operation])
            (by omega) operation_writes
      refine Or.inr ⟨operation_does_not_write, entry_after.1,
        candidate_before_operation, entry_after.2.2.1, ?_⟩
      intro newerCandidate newer_member newer_than_candidate
        newer_before_operation newer_writes
      exact
        entry_after.2.2.2 newerCandidate newer_member newer_than_candidate
          (Nat.lt_trans newer_before_operation (Nat.lt_add_one operationOrder))
          newer_writes
  · rintro (⟨candidate_is_operation, operation_writes⟩ |
      ⟨operation_does_not_write, entry_before⟩)
    · subst candidate
      refine ⟨operation_member, ?_, operation_writes, ?_⟩
      · omega
      · intro newerCandidate newer_member newer_than_operation
          newer_before_next newer_writes
        simp only [MoreRecent, operation_order] at newer_than_operation
        omega
    · refine
        ⟨entry_before.1,
          Nat.lt_trans entry_before.2.1 (Nat.lt_add_one operationOrder),
          entry_before.2.2.1, ?_⟩
      intro newerCandidate newer_member newer_than_candidate
        newer_before_next newer_writes
      by_cases newer_before_operation :
          newerCandidate.operationOrder < operationOrder
      · exact
          entry_before.2.2.2 newerCandidate newer_member newer_than_candidate
            newer_before_operation newer_writes
      · have newer_order :
            newerCandidate.operationOrder = operationOrder := by
          omega
        have newer_at :=
          history.member_operation_at newerCandidate newer_member
        rw [newer_order] at newer_at
        have newer_is_operation : newerCandidate = operation :=
          Option.some.inj (newer_at.symm.trans operation_at)
        subst newerCandidate
        exact operation_does_not_write newer_writes

def IsSourceCandidateAt {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) (position : Position) : Prop :=
  isOperation operation ∧
    ∃ source,
      EmptyPosition operation = some source ∧
        history.queryableBefore operation.operationOrder position ∧
        Related position source ∧
        IsEntryBefore history operation.operationOrder position candidate

def IsSourceCandidate {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) : Prop :=
  ∃ position, IsSourceCandidateAt history operation candidate position

def IsFillEntry {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) : Prop :=
  isOperation operation ∧
    ∃ target position,
      FillPosition operation = some target ∧
        history.queryableBefore operation.operationOrder position ∧
        ParentOrSame position target ∧
        IsEntryBefore history operation.operationOrder position candidate

def IsMostRecent (candidatePredicate : ParticleOperation → Prop)
    (candidate : ParticleOperation) : Prop :=
  candidatePredicate candidate ∧
    ∀ newerCandidate,
      candidatePredicate newerCandidate →
        ¬MoreRecent newerCandidate candidate

def IsFillCandidateFor {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) : Prop :=
  IsMostRecent (IsFillEntry history operation) candidate

theorem exists_isMostRecent_of_bounded
    (candidatePredicate : ParticleOperation → Prop) (operationOrder : Nat)
    (candidate_is_previous :
      ∀ candidate,
        candidatePredicate candidate →
          candidate.operationOrder < operationOrder)
    (candidate_exists : ∃ candidate, candidatePredicate candidate) :
    ∃ candidate, IsMostRecent candidatePredicate candidate := by
  classical
  induction operationOrder with
  | zero =>
      rcases candidate_exists with ⟨candidate, candidate_property⟩
      exact
        False.elim
          (Nat.not_lt_zero candidate.operationOrder
            (candidate_is_previous candidate candidate_property))
  | succ previousOrder induction_hypothesis =>
      by_cases candidate_at_previous_order :
          ∃ candidate,
            candidatePredicate candidate ∧
              candidate.operationOrder = previousOrder
      · rcases candidate_at_previous_order with
          ⟨candidate, candidate_property, candidate_order⟩
        refine ⟨candidate, candidate_property, ?_⟩
        intro newerCandidate newer_property newer_than_candidate
        have newer_is_previous :=
          candidate_is_previous newerCandidate newer_property
        simp only [MoreRecent, candidate_order] at newer_than_candidate
        omega
      · have candidate_is_before_previous :
            ∀ candidate,
              candidatePredicate candidate →
                candidate.operationOrder < previousOrder := by
          intro candidate candidate_property
          have candidate_before_next :=
            candidate_is_previous candidate candidate_property
          have candidate_not_at_previous :
              candidate.operationOrder ≠ previousOrder := by
            intro candidate_order
            exact
              candidate_at_previous_order
                ⟨candidate, candidate_property, candidate_order⟩
          exact
            Nat.lt_of_le_of_ne (Nat.le_of_lt_succ candidate_before_next)
              candidate_not_at_previous
        exact
          induction_hypothesis candidate_is_before_previous

theorem isFillEntry_candidate_is_operation
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation}
    {operation candidate : ParticleOperation}
    (fill_entry : IsFillEntry history operation candidate) :
    isOperation candidate := by
  rcases fill_entry with ⟨_, target, position, _, _, _, entry⟩
  exact entry.candidate_is_operation

theorem isFillEntry_candidate_is_previous
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation}
    {operation candidate : ParticleOperation}
    (fill_entry : IsFillEntry history operation candidate) :
    candidate.operationOrder < operation.operationOrder := by
  rcases fill_entry with ⟨_, target, position, _, _, _, entry⟩
  exact entry.candidate_is_previous

theorem exists_isFillCandidateFor_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) :
    (∃ candidate, IsFillCandidateFor history operation candidate) ↔
      ∃ candidate, IsFillEntry history operation candidate := by
  constructor
  · rintro ⟨candidate, candidate_is_most_recent⟩
    exact ⟨candidate, candidate_is_most_recent.1⟩
  · intro fill_entry_exists
    exact
      exists_isMostRecent_of_bounded (IsFillEntry history operation)
        operation.operationOrder
        (fun _candidate fill_entry =>
          isFillEntry_candidate_is_previous fill_entry)
        fill_entry_exists

theorem mostRecent_unique
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (candidatePredicate : ParticleOperation → Prop)
    (candidate_is_operation :
      ∀ candidate, candidatePredicate candidate → isOperation candidate)
    {first second : ParticleOperation}
    (first_most_recent : IsMostRecent candidatePredicate first)
    (second_most_recent : IsMostRecent candidatePredicate second) :
    first = second := by
  rcases Nat.lt_trichotomy first.operationOrder second.operationOrder with
    first_before_second | same_order | second_before_first
  · exact
      False.elim
        (first_most_recent.2 second second_most_recent.1 first_before_second)
  · have first_at_order :=
      history.member_operation_at first
        (candidate_is_operation first first_most_recent.1)
    have second_at_order :=
      history.member_operation_at second
        (candidate_is_operation second second_most_recent.1)
    rw [same_order] at first_at_order
    exact Option.some.inj (first_at_order.symm.trans second_at_order)
  · exact
      False.elim
        (second_most_recent.2 first first_most_recent.1 second_before_first)

theorem isFillCandidateFor_unique
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) {first second : ParticleOperation}
    (first_candidate : IsFillCandidateFor history operation first)
    (second_candidate : IsFillCandidateFor history operation second) :
    first = second :=
  mostRecent_unique history (IsFillEntry history operation)
    (fun _candidate fill_entry =>
      isFillEntry_candidate_is_operation fill_entry)
    first_candidate second_candidate

noncomputable def uniqueOption
    (candidatePredicate : ParticleOperation → Prop) :
    Option ParticleOperation := by
  classical
  exact
    if candidates_exist : ∃ candidate, candidatePredicate candidate then
      some (Classical.choose candidates_exist)
    else
      none

theorem uniqueOption_eq_some_iff
    (candidatePredicate : ParticleOperation → Prop)
    (candidate_unique :
      ∀ first second,
        candidatePredicate first → candidatePredicate second → first = second)
    (candidate : ParticleOperation) :
    uniqueOption candidatePredicate = some candidate ↔
      candidatePredicate candidate := by
  classical
  unfold uniqueOption
  split
  next candidates_exist =>
    have selected_candidate := Classical.choose_spec candidates_exist
    constructor
    · intro selected_is_candidate
      have selected_equals_candidate := Option.some.inj selected_is_candidate
      simpa [selected_equals_candidate] using selected_candidate
    · intro candidate_property
      exact
        congrArg some
          (candidate_unique (Classical.choose candidates_exist) candidate
            selected_candidate candidate_property)
  next no_candidate =>
    constructor
    · intro none_is_candidate
      exact nomatch none_is_candidate
    · intro candidate_property
      exact False.elim (no_candidate ⟨candidate, candidate_property⟩)

theorem uniqueOption_eq_none_iff
    (candidatePredicate : ParticleOperation → Prop) :
    uniqueOption candidatePredicate = none ↔
      ∀ candidate, ¬candidatePredicate candidate := by
  classical
  simp [uniqueOption]

noncomputable def calculationFor
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) : RuleCalculation where
  operation := operation
  sourceCandidate := IsSourceCandidate history operation
  fillCandidate := uniqueOption (IsFillCandidateFor history operation)

theorem calculationFor_sourceCandidate_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    (calculationFor history operation).sourceCandidate candidate ↔
      IsSourceCandidate history operation candidate :=
  Iff.rfl

theorem calculationFor_fillCandidate_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    (calculationFor history operation).IsFillCandidate candidate ↔
      IsFillCandidateFor history operation candidate := by
  exact
    uniqueOption_eq_some_iff (IsFillCandidateFor history operation)
      (fun first second => isFillCandidateFor_unique history operation)
      candidate

theorem calculationFor_wellFormed
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation : ParticleOperation) :
    (calculationFor history operation).WellFormed := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [RuleCalculation.WellFormed, calculationFor, operation_kind]
      intro candidate source_candidate
      rcases source_candidate with
        ⟨position, _, source, empty_position, _⟩
      simp [EmptyPosition, operation_kind] at empty_position
  | destroy target =>
      simp only [RuleCalculation.WellFormed, calculationFor, operation_kind]
      change
        uniqueOption (IsFillCandidateFor history operation) = none
      rw [uniqueOption_eq_none_iff]
      intro candidate fill_candidate
      rcases fill_candidate.1 with
        ⟨_, fillTarget, position, fill_position, _⟩
      simp [FillPosition, operation_kind] at fill_position
  | move source target =>
      simp [RuleCalculation.WellFormed, calculationFor, operation_kind]

noncomputable def calculatedDependencyBefore
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    Nat → ParticleOperation → ParticleOperation → Prop
  | 0 => fun _source _target => False
  | operationOrder + 1 =>
      let earlierDependency := calculatedDependencyBefore history operationOrder
      match history.operationAt operationOrder with
      | none => earlierDependency
      | some operation =>
          fun source candidate =>
            earlierDependency source candidate ∨
              (source = operation ∧
                (calculationFor history operation).Dependency
                  earlierDependency candidate)

def CalculatedDependency {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (source candidate : ParticleOperation) : Prop :=
  ∃ operationCount,
    calculatedDependencyBefore history operationCount source candidate

theorem calculatedDependencyBefore_source_order_lt
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) {operationCount : Nat}
    {source candidate : ParticleOperation}
    (dependency :
      calculatedDependencyBefore history operationCount source candidate) :
    source.operationOrder < operationCount := by
  induction operationCount with
  | zero =>
      exact False.elim dependency
  | succ previousCount induction_hypothesis =>
      simp only [calculatedDependencyBefore] at dependency
      cases operation_at : history.operationAt previousCount with
      | none =>
          rw [operation_at] at dependency
          exact Nat.lt_succ_of_lt (induction_hypothesis dependency)
      | some operation =>
          rw [operation_at] at dependency
          rcases dependency with earlier_dependency | ⟨source_is_operation, _⟩
          · exact Nat.lt_succ_of_lt (induction_hypothesis earlier_dependency)
          · subst source
            rw [history.operation_at_has_order previousCount operation operation_at]
            exact Nat.lt_add_one previousCount

theorem calculatedDependencyBefore_add_operation_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (operation candidate : ParticleOperation)
    (operation_at : history.operationAt operationOrder = some operation) :
    calculatedDependencyBefore history (operationOrder + 1) operation candidate ↔
      (calculationFor history operation).Dependency
        (calculatedDependencyBefore history operationOrder) candidate := by
  have operation_order : operation.operationOrder = operationOrder :=
    history.operation_at_has_order operationOrder operation operation_at
  simp only [calculatedDependencyBefore, operation_at]
  constructor
  · rintro (earlier_dependency | ⟨_, final_dependency⟩)
    · have source_before_step :=
        calculatedDependencyBefore_source_order_lt history earlier_dependency
      omega
    · exact final_dependency
  · intro final_dependency
    exact Or.inr ⟨True.intro, final_dependency⟩

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationOrder position
      candidate,
      IsEntryBefore history operationOrder position candidate →
        isOperation candidate ∧ candidate.operationOrder < operationOrder :=
  fun _ _ _ _ entry =>
    ⟨entry.candidate_is_operation, entry.candidate_is_previous⟩

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) position candidate,
      ¬IsEntryBefore history 0 position candidate :=
  not_isEntryBefore_zero

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationOrder operation
      candidate position,
      history.operationAt operationOrder = some operation →
        (IsEntryBefore history (operationOrder + 1) position candidate ↔
          (candidate = operation ∧ WritesEntry history operation position) ∨
            (¬WritesEntry history operation position ∧
              IsEntryBefore history operationOrder position candidate)) :=
  isEntryBefore_after_operation_iff

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation candidate,
      (calculationFor history operation).sourceCandidate candidate ↔
        IsSourceCandidate history operation candidate :=
  calculationFor_sourceCandidate_iff

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation candidate,
      (calculationFor history operation).IsFillCandidate candidate ↔
        IsFillCandidateFor history operation candidate :=
  calculationFor_fillCandidate_iff

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation,
      ((∃ candidate, IsFillCandidateFor history operation candidate) ↔
        ∃ candidate, IsFillEntry history operation candidate) :=
  exists_isFillCandidateFor_iff

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation,
      (calculationFor history operation).WellFormed :=
  calculationFor_wellFormed

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationCount source
      candidate,
      calculatedDependencyBefore history operationCount source candidate →
        source.operationOrder < operationCount :=
  calculatedDependencyBefore_source_order_lt

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationOrder operation
      candidate,
      history.operationAt operationOrder = some operation →
        (calculatedDependencyBefore history (operationOrder + 1) operation
            candidate ↔
          (calculationFor history operation).Dependency
            (calculatedDependencyBefore history operationOrder) candidate) :=
  calculatedDependencyBefore_add_operation_iff

end TypeContracts

end Define.OperationGraph
