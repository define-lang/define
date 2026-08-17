import calculation

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Dependency Graph Calculation Correctness

This module formalizes `calculation-correctness-proof.md`. It derives the entry,
candidate, and complete-graph facts used by the downstream proofs from one
arbitrary `ValidResolvedHistory` and its recursive three-rule calculation.

It assumes neither minimality nor completeness. The graph interfaces in this
module contain only the history and calculation facts derived below; the
principal graph theorems consume those interfaces in later modules.
-/

namespace Define.OperationGraph

structure ResolvedDefineGraph extends RuleGraph where
  occupancy : ExactOccupancyExecution isOperation
  sourceCandidateAt :
    ParticleOperation → ParticleOperation → Position → Prop
  source_candidate_iff :
    ∀ operation candidate,
      (calculation operation).sourceCandidate candidate ↔
        ∃ position, sourceCandidateAt operation candidate position
  source_candidate_empty_position :
    ∀ operation candidate position,
      sourceCandidateAt operation candidate position →
        ∃ emptyPosition,
          EmptyPosition operation = some emptyPosition ∧
            Related position emptyPosition
  source_candidate_operated_position :
    ∀ operation candidate position,
      sourceCandidateAt operation candidate position →
        ∃ operatedPosition,
          OperatesOn candidate operatedPosition ∧
            ParentOrSame operatedPosition position
  non_move_source_candidate_operates_on_position :
    ∀ operation candidate position,
      sourceCandidateAt operation candidate position →
        ¬IsMove candidate →
        OperatesOn candidate position
  source_candidate_is_previous :
    ∀ operation candidate position,
      sourceCandidateAt operation candidate position →
        MoreRecent operation candidate
  source_candidate_operations :
    ∀ operation candidate position,
      sourceCandidateAt operation candidate position →
        isOperation operation ∧ isOperation candidate
  latest_source_candidate :
    ∀ operation emptyPosition position previousOperation,
      isOperation operation →
        isOperation previousOperation →
        EmptyPosition operation = some emptyPosition →
        Related position emptyPosition →
        OperatesOn previousOperation position →
        MoreRecent operation previousOperation →
        ∃ candidate,
          sourceCandidateAt operation candidate position ∧
            (candidate = previousOperation ∨
              MoreRecent candidate previousOperation)
  fill_candidate_operated_position :
    ∀ operation candidate,
      (calculation operation).IsFillCandidate candidate →
        ∃ fillPosition operatedPosition,
          FillPosition operation = some fillPosition ∧
            OperatesOn candidate operatedPosition ∧
            ParentOrSame operatedPosition fillPosition
  fill_candidate_is_previous :
    ∀ operation candidate,
      (calculation operation).IsFillCandidate candidate →
        MoreRecent operation candidate
  fill_candidate_operations :
    ∀ operation candidate,
      (calculation operation).IsFillCandidate candidate →
        isOperation operation ∧ isOperation candidate

/--
A resolved graph together with the Fill Rule counterpart of
`latest_source_candidate`: whenever a previous operation exists on the filled
position or one of its parent positions, the selected Fill Dependency is at
least as recent.
-/
structure CompleteResolvedDefineGraph extends ResolvedDefineGraph where
  latest_fill_candidate :
    ∀ operation fillPosition operatedPosition previousOperation,
      isOperation operation →
        isOperation previousOperation →
        FillPosition operation = some fillPosition →
        OperatesOn previousOperation operatedPosition →
        ParentOrSame operatedPosition fillPosition →
        MoreRecent operation previousOperation →
        ∃ candidate,
          (calculation operation).IsFillCandidate candidate ∧
            (candidate = previousOperation ∨
              MoreRecent candidate previousOperation)

theorem writesEntry_of_operatesOn
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation : ParticleOperation} {position : Position}
    (operates_on : OperatesOn operation position) :
    WritesEntry history operation position := by
  cases operation_kind : operation.kind with
  | create target =>
      simpa [OperatesOn, WritesEntry, operation_kind] using operates_on
  | destroy target =>
      simpa [OperatesOn, WritesEntry, operation_kind] using operates_on
  | move source target =>
      simp only [OperatesOn, operation_kind] at operates_on
      simp only [WritesEntry, operation_kind]
      rcases operates_on with position_is_source | position_is_target
      · exact Or.inl position_is_source
      · exact Or.inr (Or.inl position_is_target)

theorem WritesEntry.operated_position
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation}
    {operation : ParticleOperation} {position : Position}
    (writes_entry : WritesEntry history operation position) :
    ∃ operatedPosition,
      OperatesOn operation operatedPosition ∧
        ParentOrSame operatedPosition position := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [WritesEntry, operation_kind] at writes_entry
      subst position
      exact ⟨target, by simp [OperatesOn, operation_kind], List.prefix_rfl⟩
  | destroy target =>
      simp only [WritesEntry, operation_kind] at writes_entry
      subst position
      exact ⟨target, by simp [OperatesOn, operation_kind], List.prefix_rfl⟩
  | move source target =>
      simp only [WritesEntry, operation_kind] at writes_entry
      rcases writes_entry with
        position_is_source | position_is_target | ⟨relativePosition, _, position_shape, _⟩
      · subst position
        exact ⟨source, by simp [OperatesOn, operation_kind], List.prefix_rfl⟩
      · subst position
        exact ⟨target, by simp [OperatesOn, operation_kind], List.prefix_rfl⟩
      · subst position
        exact ⟨target, by simp [OperatesOn, operation_kind, ParentOrSame]⟩

theorem WritesEntry.operates_on_position_of_not_move
    {isOperation : ParticleOperation → Prop}
    {history : ValidResolvedHistory isOperation}
    {operation : ParticleOperation} {position : Position}
    (writes_entry : WritesEntry history operation position)
    (operation_not_move : ¬IsMove operation) :
    OperatesOn operation position := by
  cases operation_kind : operation.kind with
  | create target =>
      simpa [WritesEntry, OperatesOn, operation_kind] using writes_entry
  | destroy target =>
      simpa [WritesEntry, OperatesOn, operation_kind] using writes_entry
  | move source target =>
      exact False.elim (operation_not_move ⟨source, target, operation_kind⟩)

def WriterBefore {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationOrder : Nat)
    (position : Position) (candidate : ParticleOperation) : Prop :=
  isOperation candidate ∧
    candidate.operationOrder < operationOrder ∧
    WritesEntry history candidate position

theorem exists_isEntryBefore_at_least_as_recent
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation previousOperation : ParticleOperation) (position : Position)
    (previous_member : isOperation previousOperation)
    (operation_after_previous : MoreRecent operation previousOperation)
    (previous_operates : OperatesOn previousOperation position) :
    ∃ candidate,
      IsEntryBefore history operation.operationOrder position candidate ∧
        (candidate = previousOperation ∨
          MoreRecent candidate previousOperation) := by
  have previous_writer :
      WriterBefore history operation.operationOrder position
        previousOperation :=
    ⟨previous_member, operation_after_previous,
      writesEntry_of_operatesOn history previous_operates⟩
  rcases exists_isMostRecent_of_bounded
      (WriterBefore history operation.operationOrder position)
      operation.operationOrder
      (fun _candidate candidate_writer => candidate_writer.2.1)
      ⟨previousOperation, previous_writer⟩ with
    ⟨candidate, candidate_writer, no_newer_writer⟩
  have candidate_entry :
      IsEntryBefore history operation.operationOrder position candidate := by
    refine ⟨candidate_writer.1, candidate_writer.2.1,
      candidate_writer.2.2, ?_⟩
    intro newerCandidate newer_member newer_than_candidate
      newer_before_operation newer_writes
    exact
      no_newer_writer newerCandidate
        ⟨newer_member, newer_before_operation, newer_writes⟩
        newer_than_candidate
  refine ⟨candidate, candidate_entry, ?_⟩
  rcases Nat.lt_trichotomy candidate.operationOrder
      previousOperation.operationOrder with
    candidate_before_previous | same_order | previous_before_candidate
  · exact
      False.elim
        (no_newer_writer previousOperation previous_writer
          candidate_before_previous)
  · have candidate_at :=
      history.member_operation_at candidate candidate_writer.1
    have previous_at :=
      history.member_operation_at previousOperation previous_member
    rw [same_order] at candidate_at
    exact Or.inl (Option.some.inj (candidate_at.symm.trans previous_at))
  · exact Or.inr previous_before_candidate

theorem calculationFor_source_candidate_facts
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    (source_candidate :
      (calculationFor history operation).sourceCandidate candidate) :
    ∃ position emptyPosition operatedPosition,
      IsSourceCandidateAt history operation candidate position ∧
        EmptyPosition operation = some emptyPosition ∧
        OperatesOn candidate operatedPosition ∧
        ParentOrSame operatedPosition position ∧
        MoreRecent operation candidate ∧
        isOperation operation ∧ isOperation candidate := by
  rcases source_candidate with ⟨position, candidate_at_position⟩
  rcases candidate_at_position with
    ⟨operation_member, emptyPosition, empty_position, position_queryable,
      position_related, entry⟩
  rcases entry.2.2.1.operated_position with
    ⟨operatedPosition, candidate_operates, operated_parent⟩
  exact
    ⟨position, emptyPosition, operatedPosition,
      ⟨operation_member, emptyPosition, empty_position,
        position_queryable, position_related, entry⟩,
      empty_position, candidate_operates, operated_parent,
      entry.candidate_is_previous, operation_member,
      entry.candidate_is_operation⟩

theorem calculationFor_latest_source_candidate
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation previousOperation : ParticleOperation)
    (emptyPosition position : Position)
    (operation_member : isOperation operation)
    (previous_member : isOperation previousOperation)
    (empty_position : EmptyPosition operation = some emptyPosition)
    (position_related : Related position emptyPosition)
    (previous_operates : OperatesOn previousOperation position)
    (operation_after_previous : MoreRecent operation previousOperation) :
    ∃ candidate,
      IsSourceCandidateAt history operation candidate position ∧
        (candidate = previousOperation ∨
          MoreRecent candidate previousOperation) := by
  have position_queryable :
      history.queryableBefore operation.operationOrder position :=
    history.operated_position_remains_queryable operation.operationOrder
      previousOperation position previous_member operation_after_previous
      previous_operates
  rcases exists_isEntryBefore_at_least_as_recent history operation
      previousOperation position previous_member operation_after_previous
      previous_operates with
    ⟨candidate, entry, candidate_recency⟩
  exact
    ⟨candidate,
      ⟨operation_member, emptyPosition, empty_position, position_queryable,
        position_related, entry⟩,
      candidate_recency⟩

theorem isMostRecent_eq_or_moreRecent_of_candidate
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (candidatePredicate : ParticleOperation → Prop)
    (candidate_is_operation :
      ∀ candidate, candidatePredicate candidate → isOperation candidate)
    {mostRecent candidate : ParticleOperation}
    (most_recent : IsMostRecent candidatePredicate mostRecent)
    (candidate_property : candidatePredicate candidate) :
    mostRecent = candidate ∨ MoreRecent mostRecent candidate := by
  rcases Nat.lt_trichotomy mostRecent.operationOrder candidate.operationOrder with
    most_before_candidate | same_order | candidate_before_most
  · exact
      False.elim
        (most_recent.2 candidate candidate_property most_before_candidate)
  · have most_at :=
      history.member_operation_at mostRecent
        (candidate_is_operation mostRecent most_recent.1)
    have candidate_at :=
      history.member_operation_at candidate
        (candidate_is_operation candidate candidate_property)
    rw [same_order] at most_at
    exact Or.inl (Option.some.inj (most_at.symm.trans candidate_at))
  · exact Or.inr candidate_before_most

theorem calculationFor_fill_candidate_facts
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    (fill_candidate :
      (calculationFor history operation).IsFillCandidate candidate) :
    ∃ fillPosition operatedPosition,
      FillPosition operation = some fillPosition ∧
        OperatesOn candidate operatedPosition ∧
        ParentOrSame operatedPosition fillPosition ∧
        MoreRecent operation candidate ∧
        isOperation operation ∧ isOperation candidate := by
  have candidate_for :=
    (calculationFor_fillCandidate_iff history operation candidate).mp
      fill_candidate
  rcases candidate_for.1 with
    ⟨operation_member, fillPosition, position, fill_position, _, position_parent,
      entry⟩
  rcases entry.2.2.1.operated_position with
    ⟨operatedPosition, candidate_operates, operated_parent⟩
  exact
    ⟨fillPosition, operatedPosition, fill_position, candidate_operates,
      operated_parent.trans position_parent, entry.candidate_is_previous,
      operation_member, entry.candidate_is_operation⟩

theorem calculationFor_latest_fill_candidate
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation previousOperation : ParticleOperation)
    (fillPosition operatedPosition : Position)
    (operation_member : isOperation operation)
    (previous_member : isOperation previousOperation)
    (fill_position : FillPosition operation = some fillPosition)
    (previous_operates : OperatesOn previousOperation operatedPosition)
    (operated_parent : ParentOrSame operatedPosition fillPosition)
    (operation_after_previous : MoreRecent operation previousOperation) :
    ∃ candidate,
      (calculationFor history operation).IsFillCandidate candidate ∧
        (candidate = previousOperation ∨
          MoreRecent candidate previousOperation) := by
  have operated_queryable :
      history.queryableBefore operation.operationOrder operatedPosition :=
    history.operated_position_remains_queryable operation.operationOrder
      previousOperation operatedPosition previous_member
      operation_after_previous previous_operates
  rcases exists_isEntryBefore_at_least_as_recent history operation
      previousOperation operatedPosition previous_member
      operation_after_previous previous_operates with
    ⟨entryCandidate, entry, entry_recency⟩
  have fill_entry : IsFillEntry history operation entryCandidate :=
    ⟨operation_member, fillPosition, operatedPosition, fill_position,
      operated_queryable, operated_parent, entry⟩
  have fill_candidate_exists :
      ∃ candidate, IsFillCandidateFor history operation candidate :=
    (exists_isFillCandidateFor_iff history operation).mpr
      ⟨entryCandidate, fill_entry⟩
  rcases fill_candidate_exists with ⟨candidate, candidate_for⟩
  have candidate_after_entry :
      candidate = entryCandidate ∨ MoreRecent candidate entryCandidate :=
    isMostRecent_eq_or_moreRecent_of_candidate history
      (IsFillEntry history operation)
      (fun _candidate candidate_entry =>
        isFillEntry_candidate_is_operation candidate_entry)
      candidate_for fill_entry
  refine ⟨candidate,
    (calculationFor_fillCandidate_iff history operation candidate).mpr
      candidate_for, ?_⟩
  rcases candidate_after_entry with candidate_is_entry | candidate_after_entry
  · subst candidate
    exact entry_recency
  · rcases entry_recency with entry_is_previous | entry_after_previous
    · subst entryCandidate
      exact Or.inr candidate_after_entry
    · exact Or.inr (Nat.lt_trans entry_after_previous candidate_after_entry)

theorem calculationFor_inCollection_is_previous
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    (in_collection :
      (calculationFor history operation).InCollection candidate) :
    MoreRecent operation candidate := by
  rcases in_collection with source_candidate | fill_candidate
  · rcases calculationFor_source_candidate_facts history source_candidate with
      ⟨_, _, _, _, _, _, _, candidate_previous, _⟩
    exact candidate_previous
  · rcases calculationFor_fill_candidate_facts history fill_candidate with
      ⟨_, _, _, _, _, candidate_previous, _⟩
    exact candidate_previous

theorem calculationFor_inCollection_operations
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    (in_collection :
      (calculationFor history operation).InCollection candidate) :
    isOperation operation ∧ isOperation candidate := by
  rcases in_collection with source_candidate | fill_candidate
  · rcases calculationFor_source_candidate_facts history source_candidate with
      ⟨_, _, _, _, _, _, _, _, operation_member, candidate_member⟩
    exact ⟨operation_member, candidate_member⟩
  · rcases calculationFor_fill_candidate_facts history fill_candidate with
      ⟨_, _, _, _, _, _, operation_member, candidate_member⟩
    exact ⟨operation_member, candidate_member⟩

theorem calculationFor_dependency_is_previous
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    {dependency : ParticleOperation → ParticleOperation → Prop}
    (rule_dependency :
      (calculationFor history operation).Dependency dependency candidate) :
    MoreRecent operation candidate :=
  calculationFor_inCollection_is_previous history
    (RuleCalculation.dependency_isInCollection rule_dependency)

theorem calculatedDependencyBefore_pointsBackward
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationCount : Nat) :
    PointsBackward ParticleOperation.operationOrder
      (calculatedDependencyBefore history operationCount) := by
  intro source candidate direct_dependency
  induction operationCount with
  | zero =>
      exact False.elim direct_dependency
  | succ previousCount induction_hypothesis =>
      simp only [calculatedDependencyBefore] at direct_dependency
      cases operation_at : history.operationAt previousCount with
      | none =>
          rw [operation_at] at direct_dependency
          exact induction_hypothesis direct_dependency
      | some operation =>
          rw [operation_at] at direct_dependency
          rcases direct_dependency with
            earlier_dependency | ⟨source_is_operation, rule_dependency⟩
          · exact induction_hypothesis earlier_dependency
          · subst source
            exact calculationFor_dependency_is_previous history rule_dependency

theorem calculatedDependencyBefore_source_is_operation
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) {operationCount : Nat}
    {source candidate : ParticleOperation}
    (direct_dependency :
      calculatedDependencyBefore history operationCount source candidate) :
    isOperation source := by
  induction operationCount with
  | zero =>
      exact False.elim direct_dependency
  | succ previousCount induction_hypothesis =>
      simp only [calculatedDependencyBefore] at direct_dependency
      cases operation_at : history.operationAt previousCount with
      | none =>
          rw [operation_at] at direct_dependency
          exact induction_hypothesis direct_dependency
      | some operation =>
          rw [operation_at] at direct_dependency
          rcases direct_dependency with
            earlier_dependency | ⟨source_is_operation, _⟩
          · exact induction_hypothesis earlier_dependency
          · subst source
            exact
              history.operation_at_is_member previousCount operation
                operation_at

theorem calculatedDependencyBefore_step_mono
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationCount : Nat)
    {source candidate : ParticleOperation}
    (direct_dependency :
      calculatedDependencyBefore history operationCount source candidate) :
    calculatedDependencyBefore history (operationCount + 1) source candidate := by
  simp only [calculatedDependencyBefore]
  cases operation_at : history.operationAt operationCount with
  | none =>
      simpa using direct_dependency
  | some operation =>
      exact Or.inl direct_dependency

theorem calculatedDependencyBefore_mono
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) {firstCount laterCount : Nat}
    (first_le_later : firstCount ≤ laterCount)
    {source candidate : ParticleOperation}
    (direct_dependency :
      calculatedDependencyBefore history firstCount source candidate) :
    calculatedDependencyBefore history laterCount source candidate := by
  rcases Nat.exists_eq_add_of_le first_le_later with
    ⟨distance, later_count_shape⟩
  subst laterCount
  clear first_le_later
  induction distance with
  | zero =>
      simpa using direct_dependency
  | succ previousDistance induction_hypothesis =>
      simpa [Nat.add_assoc] using
        calculatedDependencyBefore_step_mono history
          (firstCount + previousDistance) induction_hypothesis

theorem calculatedDependencyBefore_step_stable
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationCount : Nat)
    {source candidate : ParticleOperation}
    (source_before_step : source.operationOrder < operationCount) :
    calculatedDependencyBefore history (operationCount + 1) source candidate ↔
      calculatedDependencyBefore history operationCount source candidate := by
  simp only [calculatedDependencyBefore]
  cases operation_at : history.operationAt operationCount with
  | none =>
      rfl
  | some operation =>
      constructor
      · rintro (earlier_dependency | ⟨source_is_operation, _⟩)
        · exact earlier_dependency
        · subst source
          have operation_order :=
            history.operation_at_has_order operationCount operation operation_at
          omega
      · exact Or.inl

theorem calculatedDependencyBefore_stable
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) {firstCount laterCount : Nat}
    (first_le_later : firstCount ≤ laterCount)
    {source candidate : ParticleOperation}
    (source_before_first : source.operationOrder < firstCount) :
    calculatedDependencyBefore history firstCount source candidate ↔
      calculatedDependencyBefore history laterCount source candidate := by
  rcases Nat.exists_eq_add_of_le first_le_later with
    ⟨distance, later_count_shape⟩
  subst laterCount
  clear first_le_later
  induction distance with
  | zero =>
      rfl
  | succ previousDistance induction_hypothesis =>
      have source_before_previous :
          source.operationOrder < firstCount + previousDistance :=
        Nat.lt_of_lt_of_le source_before_first
          (Nat.le_add_right firstCount previousDistance)
      have step_stable :=
        calculatedDependencyBefore_step_stable history
          (firstCount + previousDistance) (candidate := candidate)
          source_before_previous
      simpa [Nat.add_assoc] using induction_hypothesis.trans step_stable.symm

theorem calculatedDependency_iff_at_source
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (source candidate : ParticleOperation) :
    CalculatedDependency history source candidate ↔
      calculatedDependencyBefore history (source.operationOrder + 1)
        source candidate := by
  constructor
  · rintro ⟨operationCount, direct_dependency⟩
    have source_before_count :=
      calculatedDependencyBefore_source_order_lt history direct_dependency
    have source_step_le_count :
        source.operationOrder + 1 ≤ operationCount :=
      Nat.succ_le_of_lt source_before_count
    exact
      (calculatedDependencyBefore_stable history source_step_le_count
        (Nat.lt_add_one source.operationOrder)).mpr direct_dependency
  · intro direct_dependency
    exact ⟨source.operationOrder + 1, direct_dependency⟩

theorem calculatedDependency_pointsBackward
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    PointsBackward ParticleOperation.operationOrder
      (CalculatedDependency history) := by
  intro source candidate direct_dependency
  exact
    calculatedDependencyBefore_pointsBackward history
      (source.operationOrder + 1) source candidate
      ((calculatedDependency_iff_at_source history source candidate).mp
        direct_dependency)

theorem calculatedDependency_source_is_operation
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {source candidate : ParticleOperation}
    (direct_dependency : CalculatedDependency history source candidate) :
    isOperation source := by
  rcases direct_dependency with ⟨operationCount, prefix_dependency⟩
  exact
    calculatedDependencyBefore_source_is_operation history prefix_dependency

theorem calculatedDependencyBefore_reaches_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) (operationCount : Nat)
    {source target : ParticleOperation}
    (source_before_count : source.operationOrder < operationCount) :
    Reaches (calculatedDependencyBefore history operationCount) source target ↔
      Reaches (CalculatedDependency history) source target := by
  constructor
  · exact
      Reaches.mono fun _edgeSource _edgeTarget direct_dependency =>
        ⟨operationCount, direct_dependency⟩
  · intro complete_path
    have restrict_path :
        ∀ pathSource pathTarget,
          Reaches (CalculatedDependency history) pathSource pathTarget →
            pathSource.operationOrder < operationCount →
            Reaches (calculatedDependencyBefore history operationCount)
              pathSource pathTarget := by
      intro pathSource pathTarget path
      induction path with
      | direct direct_dependency =>
          intro path_source_before_count
          exact
            .direct
              (calculatedDependencyBefore_mono history
                (Nat.succ_le_of_lt path_source_before_count)
                ((calculatedDependency_iff_at_source history _ _).mp
                  direct_dependency))
      | @step pathSource next pathTarget direct_dependency remaining_path
          induction_hypothesis =>
          intro path_source_before_count
          have source_step_le_count :
              pathSource.operationOrder + 1 ≤ operationCount :=
            Nat.succ_le_of_lt path_source_before_count
          have prefix_dependency :
              calculatedDependencyBefore history operationCount pathSource
                next :=
            calculatedDependencyBefore_mono history source_step_le_count
              ((calculatedDependency_iff_at_source history pathSource next).mp
                direct_dependency)
          have next_before_source :
              next.operationOrder < pathSource.operationOrder :=
            calculatedDependency_pointsBackward history pathSource next
              direct_dependency
          exact
            .step prefix_dependency
              (induction_hypothesis
                (Nat.lt_trans next_before_source path_source_before_count))
    exact restrict_path source target complete_path source_before_count

theorem calculationFor_afterMoveCorrection_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    (calculationFor history operation).AfterMoveCorrection
        (calculatedDependencyBefore history operation.operationOrder)
        candidate ↔
      (calculationFor history operation).AfterMoveCorrection
        (CalculatedDependency history) candidate := by
  constructor
  · rintro ⟨after_comparison, candidate_not_move | no_prefix_reaches⟩
    · exact ⟨after_comparison, Or.inl candidate_not_move⟩
    · refine ⟨after_comparison, Or.inr ?_⟩
      intro otherCandidate other_after_comparison candidates_distinct
        complete_reaches
      have other_previous :
          otherCandidate.operationOrder < operation.operationOrder :=
        calculationFor_inCollection_is_previous history
          other_after_comparison.1
      exact
        no_prefix_reaches otherCandidate other_after_comparison
          candidates_distinct
          ((calculatedDependencyBefore_reaches_iff history
            operation.operationOrder other_previous).mpr complete_reaches)
  · rintro ⟨after_comparison, candidate_not_move | no_complete_reaches⟩
    · exact ⟨after_comparison, Or.inl candidate_not_move⟩
    · refine ⟨after_comparison, Or.inr ?_⟩
      intro otherCandidate other_after_comparison candidates_distinct
        prefix_reaches
      have other_previous :
          otherCandidate.operationOrder < operation.operationOrder :=
        calculationFor_inCollection_is_previous history
          other_after_comparison.1
      exact
        no_complete_reaches otherCandidate other_after_comparison
          candidates_distinct
          ((calculatedDependencyBefore_reaches_iff history
            operation.operationOrder other_previous).mp prefix_reaches)

theorem calculationFor_moveRuleDependency_iff
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    (calculationFor history operation).MoveRuleDependency
        (calculatedDependencyBefore history operation.operationOrder)
        candidate ↔
      (calculationFor history operation).MoveRuleDependency
        (CalculatedDependency history) candidate := by
  constructor
  · rintro ⟨candidate_prefix_correction, no_prefix_removal⟩
    refine
      ⟨(calculationFor_afterMoveCorrection_iff history operation candidate).mp
          candidate_prefix_correction,
        ?_⟩
    rintro ⟨fill_candidate, sourceCandidate, source_candidate,
      source_complete_correction, candidates_distinct, complete_reaches⟩
    have source_prefix_correction :=
      (calculationFor_afterMoveCorrection_iff history operation
        sourceCandidate).mpr source_complete_correction
    have source_previous :
        sourceCandidate.operationOrder < operation.operationOrder :=
      calculationFor_inCollection_is_previous history (Or.inl source_candidate)
    exact
      no_prefix_removal
        ⟨fill_candidate, sourceCandidate, source_candidate,
          source_prefix_correction, candidates_distinct,
          (calculatedDependencyBefore_reaches_iff history
            operation.operationOrder source_previous).mpr complete_reaches⟩
  · rintro ⟨candidate_complete_correction, no_complete_removal⟩
    refine
      ⟨(calculationFor_afterMoveCorrection_iff history operation candidate).mpr
          candidate_complete_correction,
        ?_⟩
    rintro ⟨fill_candidate, sourceCandidate, source_candidate,
      source_prefix_correction, candidates_distinct, prefix_reaches⟩
    have source_complete_correction :=
      (calculationFor_afterMoveCorrection_iff history operation
        sourceCandidate).mp source_prefix_correction
    have source_previous :
        sourceCandidate.operationOrder < operation.operationOrder :=
      calculationFor_inCollection_is_previous history (Or.inl source_candidate)
    exact
      no_complete_removal
        ⟨fill_candidate, sourceCandidate, source_candidate,
          source_complete_correction, candidates_distinct,
          (calculatedDependencyBefore_reaches_iff history
            operation.operationOrder source_previous).mp prefix_reaches⟩

theorem calculationFor_dependency_iff_complete
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    (calculationFor history operation).Dependency
        (calculatedDependencyBefore history operation.operationOrder)
        candidate ↔
      (calculationFor history operation).Dependency
        (CalculatedDependency history) candidate := by
  cases operation_kind : operation.kind with
  | create target =>
      simp [RuleCalculation.Dependency, calculationFor, operation_kind]
  | destroy target =>
      simpa [RuleCalculation.Dependency, calculationFor, operation_kind] using
        calculationFor_afterMoveCorrection_iff history operation candidate
  | move source target =>
      simpa [RuleCalculation.Dependency, calculationFor, operation_kind] using
        calculationFor_moveRuleDependency_iff history operation candidate

theorem calculatedDependency_exact_of_operation
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation)
    (operation_member : isOperation operation) :
    CalculatedDependency history operation candidate ↔
      (calculationFor history operation).Dependency
        (CalculatedDependency history) candidate := by
  have operation_at :=
    history.member_operation_at operation operation_member
  exact
    (calculatedDependency_iff_at_source history operation candidate).trans
      ((calculatedDependencyBefore_add_operation_iff history
        operation.operationOrder operation candidate operation_at).trans
        (calculationFor_dependency_iff_complete history operation candidate))

theorem calculatedDependency_exact
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    (operation candidate : ParticleOperation) :
    CalculatedDependency history operation candidate ↔
      (calculationFor history operation).Dependency
        (CalculatedDependency history) candidate := by
  by_cases operation_member : isOperation operation
  · exact
      calculatedDependency_exact_of_operation history operation candidate
        operation_member
  · constructor
    · intro direct_dependency
      exact
        False.elim
          (operation_member
            (calculatedDependency_source_is_operation history
              direct_dependency))
    · intro rule_dependency
      have in_collection :=
        RuleCalculation.dependency_isInCollection rule_dependency
      exact
        False.elim
          (operation_member
            (calculationFor_inCollection_operations history in_collection).1)

theorem calculatedDependency_operations
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation candidate : ParticleOperation}
    (direct_dependency : CalculatedDependency history operation candidate) :
    isOperation operation ∧ isOperation candidate := by
  have rule_dependency :=
    (calculatedDependency_exact history operation candidate).mp
      direct_dependency
  exact
    calculationFor_inCollection_operations history
      (RuleCalculation.dependency_isInCollection rule_dependency)

noncomputable def calculatedRuleGraph
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) : RuleGraph where
  isOperation := isOperation
  dependency := CalculatedDependency history
  calculation := calculationFor history
  calculation_operation := fun _operation => rfl
  calculation_well_formed := calculationFor_wellFormed history
  exact_dependency := calculatedDependency_exact history

noncomputable def calculatedResolvedDefineGraph
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) : ResolvedDefineGraph where
  toRuleGraph := calculatedRuleGraph history
  occupancy := history.toExactOccupancyExecution
  sourceCandidateAt := IsSourceCandidateAt history
  source_candidate_iff := fun _operation _candidate => Iff.rfl
  source_candidate_empty_position := by
    intro operation candidate position candidate_at_position
    rcases candidate_at_position with
      ⟨_, emptyPosition, empty_position, _, position_related, _⟩
    exact ⟨emptyPosition, empty_position, position_related⟩
  source_candidate_operated_position := by
    intro operation candidate position candidate_at_position
    rcases candidate_at_position with ⟨_, _, _, _, _, entry⟩
    exact entry.2.2.1.operated_position
  non_move_source_candidate_operates_on_position := by
    intro operation candidate position candidate_at_position candidate_not_move
    rcases candidate_at_position with ⟨_, _, _, _, _, entry⟩
    exact entry.2.2.1.operates_on_position_of_not_move candidate_not_move
  source_candidate_is_previous := by
    intro operation candidate position candidate_at_position
    rcases candidate_at_position with ⟨_, _, _, _, _, entry⟩
    exact entry.candidate_is_previous
  source_candidate_operations := by
    intro operation candidate position candidate_at_position
    rcases candidate_at_position with ⟨operation_member, _, _, _, _, entry⟩
    exact ⟨operation_member, entry.candidate_is_operation⟩
  latest_source_candidate := by
    intro operation emptyPosition position previousOperation operation_member
      previous_member empty_position position_related previous_operates
      operation_after_previous
    exact
      calculationFor_latest_source_candidate history operation previousOperation
        emptyPosition position operation_member previous_member empty_position
        position_related previous_operates operation_after_previous
  fill_candidate_operated_position := by
    intro operation candidate fill_candidate
    rcases calculationFor_fill_candidate_facts history fill_candidate with
      ⟨fillPosition, operatedPosition, fill_position, candidate_operates,
        operated_parent, _⟩
    exact
      ⟨fillPosition, operatedPosition, fill_position, candidate_operates,
        operated_parent⟩
  fill_candidate_is_previous := by
    intro operation candidate fill_candidate
    rcases calculationFor_fill_candidate_facts history fill_candidate with
      ⟨_, _, _, _, _, candidate_previous, _⟩
    exact candidate_previous
  fill_candidate_operations := by
    intro operation candidate fill_candidate
    rcases calculationFor_fill_candidate_facts history fill_candidate with
      ⟨_, _, _, _, _, _, operation_member, candidate_member⟩
    exact ⟨operation_member, candidate_member⟩

noncomputable def calculatedCompleteResolvedDefineGraph
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) : CompleteResolvedDefineGraph where
  toResolvedDefineGraph := calculatedResolvedDefineGraph history
  latest_fill_candidate := by
    intro operation fillPosition operatedPosition previousOperation
      operation_member previous_member fill_position previous_operates
      operated_parent operation_after_previous
    exact
      calculationFor_latest_fill_candidate history operation previousOperation
        fillPosition operatedPosition operation_member previous_member
        fill_position previous_operates operated_parent operation_after_previous

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation candidate,
      CalculatedDependency history operation candidate ↔
        (calculationFor history operation).Dependency
          (CalculatedDependency history) candidate :=
  calculatedDependency_exact

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operationCount,
      PointsBackward ParticleOperation.operationOrder
        (calculatedDependencyBefore history operationCount) :=
  calculatedDependencyBefore_pointsBackward

noncomputable example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation candidate,
      (calculatedCompleteResolvedDefineGraph history).dependency operation
          candidate ↔
        (calculationFor history operation).Dependency
          (calculatedCompleteResolvedDefineGraph history).dependency candidate :=
  fun history operation candidate =>
    calculatedDependency_exact history operation candidate

end TypeContracts

end Define.OperationGraph
