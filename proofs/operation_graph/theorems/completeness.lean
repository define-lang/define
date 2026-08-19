import calculation_correctness

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Dependency Graph Completeness

This file formalizes `completeness-proof.md`: every previous Particle Operation
whose operated positions are related to an operation's positions is reachable
through the dependency graph. The English proof is the source of the
mathematical argument; the definitions and theorems here encode that argument
for Lean to check.

## Formalization boundary

`CompleteResolvedDefineGraph` extends `ResolvedDefineGraph` with the
consequences of the Fill Rule's candidate selection that the minimality
theorem does not need: whenever a previous Particle Operation exists on the
filled position or one of its transitive parent positions, the Fill Rule
selected a candidate at least as recent. The Empty Rule counterpart is already
a `ResolvedDefineGraph` obligation (`latest_source_candidate`).

`calculation_correctness.lean` derives both obligations from an arbitrary valid
resolved history and its exact rule calculation. This file consumes the
resulting interface without assuming the completeness conclusion.

The proof uses induction on a natural-number occurrence bound. Each rule-stage
survivor chase and each occupancy bridge lies in the finite prefix before the
operation under consideration, so neither the history nor its vertex set must
be finite. No premise states transitive minimality or the completeness
conclusion. Characterization and uniqueness are separate results that may later
combine this theorem with independent minimality.
-/

namespace Define.OperationGraph

universe u

namespace Reaches

theorem orEq_trans {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    {first second third : Vertex}
    (first_path : OrEq dependency first second)
    (second_path : OrEq dependency second third) :
    OrEq dependency first third := by
  rcases first_path with first_is_second | first_path
  · subst first_is_second
    exact second_path
  · rcases second_path with second_is_third | second_path
    · subst second_is_third
      exact Or.inr first_path
    · exact Or.inr (first_path.trans second_path)

theorem reaches_of_edge_of_orEq {Vertex : Type u}
    {dependency : Vertex → Vertex → Prop} {source next target : Vertex}
    (first_edge : dependency source next)
    (remaining_path : OrEq dependency next target) :
    Define.OperationGraph.Reaches dependency source target := by
  rcases remaining_path with next_is_target | remaining_path
  · subst next_is_target
    exact .direct first_edge
  · exact .step first_edge remaining_path

end Reaches

/-!
## Survivor chases

Each rule stage removes a candidate only in favor of another candidate that is
more recent, or that reaches the removed candidate. Following the removing
candidates therefore ascends strictly in operation order below the operation
itself, so the chase ends at a retained candidate. These lemmas package that
argument for the Comparison, the Move Correction, and the Move Rule's Fill
Dependency removal.
-/

namespace RuleCalculation

theorem exists_afterComparison_orEq_reaching (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidates_previous :
      ∀ candidate, calculation.InCollection candidate →
        MoreRecent calculation.operation candidate)
    (excluders_reach :
      ∀ excluder excluded,
        calculation.InCollection excluder →
        calculation.InCollection excluded →
        MoreRecent excluder excluded →
        OperationsRelated excluder excluded →
        Reaches dependency excluder excluded) :
    ∀ candidate, calculation.InCollection candidate →
      ∃ survivor,
        calculation.AfterComparison survivor ∧
          Reaches.OrEq dependency survivor candidate := by
  suffices chase :
      ∀ fuel candidate, calculation.InCollection candidate →
        calculation.operation.operationOrder - candidate.operationOrder ≤ fuel →
        ∃ survivor,
          calculation.AfterComparison survivor ∧
            Reaches.OrEq dependency survivor candidate by
    intro candidate in_collection
    exact chase _ candidate in_collection (Nat.le_refl _)
  intro fuel
  induction fuel with
  | zero =>
      intro candidate in_collection distance_le
      have candidate_previous := candidates_previous candidate in_collection
      rw [MoreRecent] at candidate_previous
      omega
  | succ fuel induction_hypothesis =>
      intro candidate in_collection distance_le
      by_cases retained : calculation.AfterComparison candidate
      · exact ⟨candidate, retained, Or.inl rfl⟩
      · have not_all :
            ¬∀ newerCandidate,
              calculation.InCollection newerCandidate →
              MoreRecent newerCandidate candidate →
              OperationsRelated newerCandidate candidate →
              False :=
          fun all => retained ⟨in_collection, all⟩
        rcases Classical.not_forall.mp not_all with ⟨excluder, excluder_property⟩
        rcases Classical.not_imp.mp excluder_property with
          ⟨excluder_in, remaining_property⟩
        rcases Classical.not_imp.mp remaining_property with
          ⟨excluder_recent, related_property⟩
        rcases Classical.not_imp.mp related_property with ⟨excluder_related, _⟩
        have excluder_previous := candidates_previous excluder excluder_in
        have candidate_previous := candidates_previous candidate in_collection
        have excluder_distance :
            calculation.operation.operationOrder -
              excluder.operationOrder ≤ fuel := by
          rw [MoreRecent] at excluder_previous excluder_recent candidate_previous
          omega
        rcases induction_hypothesis excluder excluder_in excluder_distance with
          ⟨survivor, survivor_retained, survivor_path⟩
        have excluder_reaches :=
          excluders_reach excluder candidate excluder_in in_collection
            excluder_recent excluder_related
        exact
          ⟨survivor, survivor_retained,
            Reaches.orEq_trans survivor_path (Or.inr excluder_reaches)⟩

theorem exists_afterMoveCorrection_orEq_reaching (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidates_previous :
      ∀ candidate, calculation.InCollection candidate →
        MoreRecent calculation.operation candidate)
    (reaches_is_more_recent :
      ∀ newer older, Reaches dependency newer older → MoreRecent newer older) :
    ∀ candidate, calculation.AfterComparison candidate →
      ∃ survivor,
        calculation.AfterMoveCorrection dependency survivor ∧
          Reaches.OrEq dependency survivor candidate := by
  suffices chase :
      ∀ fuel candidate, calculation.AfterComparison candidate →
        calculation.operation.operationOrder - candidate.operationOrder ≤ fuel →
        ∃ survivor,
          calculation.AfterMoveCorrection dependency survivor ∧
            Reaches.OrEq dependency survivor candidate by
    intro candidate after_comparison
    exact chase _ candidate after_comparison (Nat.le_refl _)
  intro fuel
  induction fuel with
  | zero =>
      intro candidate after_comparison distance_le
      have candidate_previous :=
        candidates_previous candidate after_comparison.1
      rw [MoreRecent] at candidate_previous
      omega
  | succ fuel induction_hypothesis =>
      intro candidate after_comparison distance_le
      by_cases retained : calculation.AfterMoveCorrection dependency candidate
      · exact ⟨candidate, retained, Or.inl rfl⟩
      · have no_others :
            ¬∀ otherCandidate,
              calculation.AfterComparison otherCandidate →
              otherCandidate ≠ candidate →
              ¬Reaches dependency otherCandidate candidate :=
          fun all => retained ⟨after_comparison, Or.inr all⟩
        rcases Classical.not_forall.mp no_others with ⟨remover, remover_property⟩
        rcases Classical.not_imp.mp remover_property with
          ⟨remover_retained, remaining_property⟩
        rcases Classical.not_imp.mp remaining_property with
          ⟨_, remover_not_not_reaches⟩
        have remover_reaches : Reaches dependency remover candidate :=
          Classical.byContradiction remover_not_not_reaches
        have remover_recent := reaches_is_more_recent remover candidate
          remover_reaches
        have candidate_previous :=
          candidates_previous candidate after_comparison.1
        have remover_previous :=
          candidates_previous remover remover_retained.1
        have remover_distance :
            calculation.operation.operationOrder -
              remover.operationOrder ≤ fuel := by
          rw [MoreRecent] at remover_recent candidate_previous remover_previous
          omega
        rcases induction_hypothesis remover remover_retained remover_distance with
          ⟨survivor, survivor_retained, survivor_path⟩
        exact
          ⟨survivor, survivor_retained,
            Reaches.orEq_trans survivor_path (Or.inr remover_reaches)⟩

theorem exists_moveRuleDependency_orEq_reaching (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (candidates_previous :
      ∀ candidate, calculation.InCollection candidate →
        MoreRecent calculation.operation candidate)
    (reaches_is_more_recent :
      ∀ newer older, Reaches dependency newer older → MoreRecent newer older) :
    ∀ candidate, calculation.AfterMoveCorrection dependency candidate →
      ∃ survivor,
        calculation.MoveRuleDependency dependency survivor ∧
          Reaches.OrEq dependency survivor candidate := by
  suffices chase :
      ∀ fuel candidate,
        calculation.AfterMoveCorrection dependency candidate →
        calculation.operation.operationOrder - candidate.operationOrder ≤ fuel →
        ∃ survivor,
          calculation.MoveRuleDependency dependency survivor ∧
            Reaches.OrEq dependency survivor candidate by
    intro candidate after_move_correction
    exact chase _ candidate after_move_correction (Nat.le_refl _)
  intro fuel
  induction fuel with
  | zero =>
      intro candidate after_move_correction distance_le
      have candidate_previous :=
        candidates_previous candidate after_move_correction.1.1
      rw [MoreRecent] at candidate_previous
      omega
  | succ fuel induction_hypothesis =>
      intro candidate after_move_correction distance_le
      by_cases retained : calculation.MoveRuleDependency dependency candidate
      · exact ⟨candidate, retained, Or.inl rfl⟩
      · have removal :
            calculation.IsFillCandidate candidate ∧
              ∃ sourceCandidate,
                calculation.sourceCandidate sourceCandidate ∧
                  calculation.AfterMoveCorrection dependency sourceCandidate ∧
                  sourceCandidate ≠ candidate ∧
                  Reaches dependency sourceCandidate candidate :=
          Classical.byContradiction fun no_removal =>
            retained ⟨after_move_correction, no_removal⟩
        rcases removal with
          ⟨_, remover, _, remover_retained, _, remover_reaches⟩
        have remover_recent := reaches_is_more_recent remover candidate
          remover_reaches
        have candidate_previous :=
          candidates_previous candidate after_move_correction.1.1
        have remover_previous :=
          candidates_previous remover remover_retained.1.1
        have remover_distance :
            calculation.operation.operationOrder -
              remover.operationOrder ≤ fuel := by
          rw [MoreRecent] at remover_recent candidate_previous remover_previous
          omega
        rcases induction_hypothesis remover remover_retained remover_distance with
          ⟨survivor, survivor_retained, survivor_path⟩
        exact
          ⟨survivor, survivor_retained,
            Reaches.orEq_trans survivor_path (Or.inr remover_reaches)⟩

end RuleCalculation

/-!
## Occupancy consequences

The bridge argument for a fill needs the operation that emptied the filled
position between an earlier operation on a strict child position and the fill.
These lemmas mirror `exists_occupancy_transition` and
`ValidOccupancyTrace.newly_occupied_has_operation` for the emptying direction.
-/

theorem exists_emptying_transition (occupied : Nat → Prop)
    {start finish : Nat} (start_le_finish : start ≤ finish)
    (occupied_at_start : occupied start)
    (unoccupied_at_finish : ¬occupied finish) :
    ∃ transition,
      start ≤ transition ∧
        transition < finish ∧
        occupied transition ∧
        ¬occupied (transition + 1) := by
  rcases Nat.exists_eq_add_of_le start_le_finish with ⟨distance, finish_eq⟩
  subst finish
  induction distance with
  | zero =>
      exact False.elim (unoccupied_at_finish occupied_at_start)
  | succ distance induction_hypothesis =>
      by_cases occupied_before_finish : occupied (start + distance)
      · refine ⟨start + distance, Nat.le_add_right start distance, ?_,
          occupied_before_finish, ?_⟩
        · omega
        · simpa [Nat.add_assoc] using unoccupied_at_finish
      · rcases
          induction_hypothesis (Nat.le_add_right start distance)
            occupied_before_finish with
          ⟨transition, start_le_transition, transition_before_previous,
            occupied_at_transition, unoccupied_after_transition⟩
        exact
          ⟨transition, start_le_transition,
            Nat.lt_trans transition_before_previous (by omega),
            occupied_at_transition, unoccupied_after_transition⟩

theorem ExactOccupancyExecution.newly_unoccupied_has_operation
    {isOperation : ParticleOperation → Prop}
    (execution : ExactOccupancyExecution isOperation)
    {operationOrder : Nat} {position : Position}
    (occupied_before : execution.occupiedBefore operationOrder position)
    (unoccupied_after : ¬execution.occupiedBefore (operationOrder + 1) position) :
    ∃ operation operatedPosition,
      isOperation operation ∧
        operation.operationOrder = operationOrder ∧
        OperatesOn operation operatedPosition ∧
        ParentOrSame operatedPosition position := by
  cases operation_at : execution.operationAt operationOrder with
  | none =>
      exact
        False.elim
          (unoccupied_after
            ((execution.no_operation_transition operationOrder operation_at
                position).mpr occupied_before))
  | some operation =>
      have operation_member :=
        execution.operation_at_is_member operationOrder operation operation_at
      have operation_order :=
        execution.operation_at_has_order operationOrder operation operation_at
      have after_semantics :
          ¬OccupancyAfter operation
            (execution.occupiedBefore operationOrder) position :=
        fun after =>
          unoccupied_after
            ((execution.operation_transition operationOrder operation
                operation_at position).mpr after)
      cases operation_kind : operation.kind with
      | create target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          exact False.elim (after_semantics.2 occupied_before)
      | destroy target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          have target_parent : ParentOrSame target position :=
            Classical.byContradiction fun not_parent =>
              after_semantics not_parent occupied_before
          exact
            ⟨operation, target, operation_member, operation_order,
              by simp [OperatesOn, operation_kind], target_parent⟩
      | move source target =>
          simp [OccupancyAfter, operation_kind] at after_semantics
          by_cases source_parent : ParentOrSame source position
          · exact
              ⟨operation, source, operation_member, operation_order,
                by simp [OperatesOn, operation_kind], source_parent⟩
          · have target_parent : ParentOrSame target position :=
              Classical.byContradiction fun not_parent =>
                after_semantics.2 source_parent not_parent occupied_before
            exact
              ⟨operation, target, operation_member, operation_order,
                by simp [OperatesOn, operation_kind], target_parent⟩

/--
After a Particle Operation on a child position, every strict transitive parent
position of that child position is occupied.
-/
theorem ExactOccupancyExecution.parent_occupied_after_child_operation
    {isOperation : ParticleOperation → Prop}
    (execution : ExactOccupancyExecution isOperation)
    {operation : ParticleOperation} {childPosition parentPosition : Position}
    (operation_member : isOperation operation)
    (operation_operates : OperatesOn operation childPosition)
    (parent_of_child : ParentOrSame parentPosition childPosition)
    (parent_is_strict : parentPosition ≠ childPosition) :
    execution.occupiedBefore (operation.operationOrder + 1) parentPosition := by
  have operation_at :=
    execution.member_operation_at operation operation_member
  have transition :=
    execution.operation_transition operation.operationOrder operation
      operation_at parentPosition
  have not_child_parent : ¬ParentOrSame childPosition parentPosition :=
    fun child_parent =>
      parent_is_strict (parentOrSame_antisymm parent_of_child child_parent)
  cases operation_kind : operation.kind with
  | create target =>
      have child_is_target : childPosition = target := by
        simpa [OperatesOn, operation_kind] using operation_operates
      subst child_is_target
      have child_occupied_after :
          execution.occupiedBefore
            (operation.operationOrder + 1) childPosition := by
        rw [execution.operation_transition operation.operationOrder operation
          operation_at childPosition]
        simp [OccupancyAfter, operation_kind]
      exact
        execution.parent_position_is_occupied (operation.operationOrder + 1)
          parentPosition childPosition parent_of_child child_occupied_after
  | destroy target =>
      have child_is_target : childPosition = target := by
        simpa [OperatesOn, operation_kind] using operation_operates
      subst child_is_target
      have child_occupied_before :
          execution.occupiedBefore operation.operationOrder childPosition :=
        execution.empty_position_is_occupied operation childPosition
          operation_member (by simp [EmptyPosition, operation_kind])
      have parent_occupied_before :=
        execution.parent_position_is_occupied operation.operationOrder
          parentPosition childPosition parent_of_child child_occupied_before
      rw [transition]
      simp only [OccupancyAfter, operation_kind]
      exact ⟨not_child_parent, parent_occupied_before⟩
  | move source target =>
      rcases (show childPosition = source ∨ childPosition = target by
          simpa [OperatesOn, operation_kind] using operation_operates) with
        child_is_source | child_is_target
      · subst child_is_source
        have child_occupied_before :
            execution.occupiedBefore operation.operationOrder childPosition :=
          execution.empty_position_is_occupied operation childPosition
            operation_member (by simp [EmptyPosition, operation_kind])
        have parent_occupied_before :=
          execution.parent_position_is_occupied operation.operationOrder
            parentPosition childPosition parent_of_child child_occupied_before
        have not_target_parent : ¬ParentOrSame target parentPosition := by
          intro target_parent
          have target_parent_of_child : ParentOrSame target childPosition :=
            target_parent.trans parent_of_child
          have target_occupied_before :=
            execution.parent_position_is_occupied operation.operationOrder
              target childPosition target_parent_of_child child_occupied_before
          exact
            execution.fill_position_is_empty operation target operation_member
              (by simp [FillPosition, operation_kind]) target_occupied_before
        rw [transition]
        simp only [OccupancyAfter, operation_kind]
        exact Or.inr ⟨not_child_parent, not_target_parent, parent_occupied_before⟩
      · subst child_is_target
        have source_occupied_before :
            execution.occupiedBefore operation.operationOrder source :=
          execution.empty_position_is_occupied operation source
            operation_member (by simp [EmptyPosition, operation_kind])
        have child_occupied_after :
            execution.occupiedBefore
              (operation.operationOrder + 1) childPosition := by
          rw [execution.operation_transition operation.operationOrder operation
            operation_at childPosition]
          simp only [OccupancyAfter, operation_kind]
          exact Or.inl ⟨[], by simp, by simpa using source_occupied_before⟩
        exact
          execution.parent_position_is_occupied (operation.operationOrder + 1)
            parentPosition childPosition parent_of_child child_occupied_after

namespace CompleteResolvedDefineGraph

theorem candidates_previous (graph : CompleteResolvedDefineGraph)
    {operation : ParticleOperation} :
    ∀ candidate, (graph.calculation operation).InCollection candidate →
      MoreRecent (graph.calculation operation).operation candidate := by
  intro candidate in_collection
  rw [graph.calculation_operation operation]
  rcases in_collection with source_candidate | fill_candidate
  · rcases (graph.source_candidate_iff operation candidate).mp
        source_candidate with ⟨position, candidate_at_position⟩
    exact
      graph.source_candidate_is_previous operation candidate position
        candidate_at_position
  · exact graph.fill_candidate_is_previous operation candidate fill_candidate

theorem inCollection_operations (graph : CompleteResolvedDefineGraph)
    {operation candidate : ParticleOperation}
    (in_collection : (graph.calculation operation).InCollection candidate) :
    graph.isOperation candidate := by
  rcases in_collection with source_candidate | fill_candidate
  · rcases (graph.source_candidate_iff operation candidate).mp
        source_candidate with ⟨candidatePosition, candidate_at_position⟩
    exact
      (graph.source_candidate_operations operation candidate candidatePosition
        candidate_at_position).2
  · exact (graph.fill_candidate_operations operation candidate fill_candidate).2

private theorem reaches_is_moreRecent_for_completeness
    (graph : CompleteResolvedDefineGraph)
    {newer older : ParticleOperation}
    (reaches : Reaches graph.dependency newer older) :
    MoreRecent newer older := by
  apply reaches_decreases_order ?_ reaches
  intro operation candidate direct_dependency
  have in_collection :=
    RuleCalculation.dependency_isInCollection
      ((graph.exact_dependency operation candidate).mp direct_dependency)
  have candidate_previous := graph.candidates_previous candidate in_collection
  rw [graph.calculation_operation operation] at candidate_previous
  exact candidate_previous

/--
The operation reaches every candidate in its Collection, provided every pair
of previous operations with related positions is already known to be ordered
by reachability. The proviso is the induction hypothesis of the completeness
theorem.
-/
theorem reaches_of_inCollection (graph : CompleteResolvedDefineGraph)
    {operation : ParticleOperation}
    (complete_below :
      ∀ newer older,
        graph.isOperation newer →
        graph.isOperation older →
        MoreRecent operation newer →
        MoreRecent newer older →
        OperationsRelated newer older →
        Reaches graph.dependency newer older) :
    ∀ candidate, (graph.calculation operation).InCollection candidate →
      Reaches graph.dependency operation candidate := by
  intro candidate in_collection
  have excluders_reach :
      ∀ excluder excluded,
        (graph.calculation operation).InCollection excluder →
        (graph.calculation operation).InCollection excluded →
        MoreRecent excluder excluded →
        OperationsRelated excluder excluded →
        Reaches graph.dependency excluder excluded := by
    intro excluder excluded excluder_in excluded_in excluder_recent
      excluder_related
    have excluder_previous := graph.candidates_previous excluder excluder_in
    rw [graph.calculation_operation operation] at excluder_previous
    exact
      complete_below excluder excluded (graph.inCollection_operations excluder_in)
        (graph.inCollection_operations excluded_in) excluder_previous
        excluder_recent excluder_related
  have reaches_is_more_recent :
      ∀ newer older, Reaches graph.dependency newer older →
        MoreRecent newer older :=
    fun _ _ reaches => reaches_is_moreRecent_for_completeness graph reaches
  cases operation_kind : operation.kind with
  | create target =>
      have well_formed := graph.calculation_well_formed operation
      rw [RuleCalculation.WellFormed, graph.calculation_operation operation,
        operation_kind] at well_formed
      have candidate_fill : (graph.calculation operation).IsFillCandidate
          candidate := by
        rcases in_collection with source_candidate | fill_candidate
        · exact False.elim (well_formed candidate source_candidate)
        · exact fill_candidate
      have rule_dependency :
          (graph.calculation operation).Dependency graph.dependency
            candidate := by
        rw [RuleCalculation.Dependency,
          graph.calculation_operation operation, operation_kind]
        exact candidate_fill
      exact
        .direct ((graph.exact_dependency operation candidate).mpr
          rule_dependency)
  | destroy target =>
      rcases
        (graph.calculation operation).exists_afterComparison_orEq_reaching
          graph.dependency graph.candidates_previous excluders_reach candidate
          in_collection with
        ⟨comparisonSurvivor, comparison_retained, comparison_path⟩
      rcases
        (graph.calculation operation).exists_afterMoveCorrection_orEq_reaching
          graph.dependency graph.candidates_previous reaches_is_more_recent
          comparisonSurvivor comparison_retained with
        ⟨survivor, survivor_retained, survivor_path⟩
      have rule_dependency :
          (graph.calculation operation).Dependency graph.dependency
            survivor := by
        rw [RuleCalculation.Dependency,
          graph.calculation_operation operation, operation_kind]
        exact survivor_retained
      exact
        Reaches.reaches_of_edge_of_orEq
          ((graph.exact_dependency operation survivor).mpr rule_dependency)
          (Reaches.orEq_trans survivor_path comparison_path)
  | move source target =>
      rcases
        (graph.calculation operation).exists_afterComparison_orEq_reaching
          graph.dependency graph.candidates_previous excluders_reach candidate
          in_collection with
        ⟨comparisonSurvivor, comparison_retained, comparison_path⟩
      rcases
        (graph.calculation operation).exists_afterMoveCorrection_orEq_reaching
          graph.dependency graph.candidates_previous reaches_is_more_recent
          comparisonSurvivor comparison_retained with
        ⟨correctionSurvivor, correction_retained, correction_path⟩
      rcases
        (graph.calculation operation).exists_moveRuleDependency_orEq_reaching
          graph.dependency graph.candidates_previous reaches_is_more_recent
          correctionSurvivor correction_retained with
        ⟨survivor, survivor_retained, survivor_path⟩
      have rule_dependency :
          (graph.calculation operation).Dependency graph.dependency
            survivor := by
        rw [RuleCalculation.Dependency,
          graph.calculation_operation operation, operation_kind]
        exact survivor_retained
      exact
        Reaches.reaches_of_edge_of_orEq
          ((graph.exact_dependency operation survivor).mpr rule_dependency)
          (Reaches.orEq_trans survivor_path
            (Reaches.orEq_trans correction_path comparison_path))

/--
The operation reaches every previous operation that operated on a position
related to the emptied position.
-/
theorem reaches_of_emptyPosition_related (graph : CompleteResolvedDefineGraph)
    {operation previousOperation : ParticleOperation}
    {emptyPosition operatedPosition : Position}
    (complete_below :
      ∀ newer older,
        graph.isOperation newer →
        graph.isOperation older →
        MoreRecent operation newer →
        MoreRecent newer older →
        OperationsRelated newer older →
        Reaches graph.dependency newer older)
    (operation_member : graph.isOperation operation)
    (previous_member : graph.isOperation previousOperation)
    (empty_position : EmptyPosition operation = some emptyPosition)
    (previous_operates : OperatesOn previousOperation operatedPosition)
    (position_related : Related operatedPosition emptyPosition)
    (operation_after_previous : MoreRecent operation previousOperation) :
    Reaches graph.dependency operation previousOperation := by
  rcases graph.latest_source_candidate operation emptyPosition operatedPosition
      previousOperation operation_member previous_member empty_position
      position_related previous_operates operation_after_previous with
    ⟨candidate, candidate_at_position, candidate_recency⟩
  have candidate_in_collection :
      (graph.calculation operation).InCollection candidate :=
    Or.inl ((graph.source_candidate_iff operation candidate).mpr
      ⟨operatedPosition, candidate_at_position⟩)
  have operation_reaches_candidate :=
    graph.reaches_of_inCollection complete_below candidate
      candidate_in_collection
  rcases candidate_recency with candidate_is_previous | candidate_recent
  · exact candidate_is_previous ▸ operation_reaches_candidate
  · rcases graph.source_candidate_operated_position operation candidate
        operatedPosition candidate_at_position with
      ⟨candidateOperatedPosition, candidate_operates, candidate_parent⟩
    have candidate_related : OperationsRelated candidate previousOperation :=
      ⟨candidateOperatedPosition, operatedPosition, candidate_operates,
        previous_operates, Or.inl candidate_parent⟩
    have candidate_previous :=
      graph.source_candidate_is_previous operation candidate operatedPosition
        candidate_at_position
    have candidate_member :=
      (graph.source_candidate_operations operation candidate operatedPosition
        candidate_at_position).2
    exact
      operation_reaches_candidate.trans
        (complete_below candidate previousOperation candidate_member
          previous_member candidate_previous candidate_recent candidate_related)

/--
The operation reaches every previous operation on the filled position or one
of its transitive parent positions.
-/
theorem reaches_of_fillPosition_parent (graph : CompleteResolvedDefineGraph)
    {operation previousOperation : ParticleOperation}
    {fillPosition operatedPosition : Position}
    (complete_below :
      ∀ newer older,
        graph.isOperation newer →
        graph.isOperation older →
        MoreRecent operation newer →
        MoreRecent newer older →
        OperationsRelated newer older →
        Reaches graph.dependency newer older)
    (operation_member : graph.isOperation operation)
    (previous_member : graph.isOperation previousOperation)
    (fill_position : FillPosition operation = some fillPosition)
    (previous_operates : OperatesOn previousOperation operatedPosition)
    (operated_parent : ParentOrSame operatedPosition fillPosition)
    (operation_after_previous : MoreRecent operation previousOperation) :
    Reaches graph.dependency operation previousOperation := by
  rcases graph.latest_fill_candidate operation fillPosition operatedPosition
      previousOperation operation_member previous_member fill_position
      previous_operates operated_parent operation_after_previous with
    ⟨candidate, candidate_fill, candidate_recency⟩
  have candidate_in_collection :
      (graph.calculation operation).InCollection candidate :=
    Or.inr candidate_fill
  have operation_reaches_candidate :=
    graph.reaches_of_inCollection complete_below candidate
      candidate_in_collection
  rcases candidate_recency with candidate_is_previous | candidate_recent
  · exact candidate_is_previous ▸ operation_reaches_candidate
  · rcases graph.fill_candidate_operated_position operation candidate
        candidate_fill with
      ⟨candidateFillPosition, candidateOperatedPosition, candidate_fill_position,
        candidate_operates, candidate_parent⟩
    have fill_positions_equal : candidateFillPosition = fillPosition :=
      Option.some.inj (candidate_fill_position.symm.trans fill_position)
    subst fill_positions_equal
    have candidate_related : OperationsRelated candidate previousOperation :=
      ⟨candidateOperatedPosition, operatedPosition, candidate_operates,
        previous_operates,
        related_of_parentOrSame_of_parentOrSame candidate_parent
          operated_parent⟩
    have candidate_previous :=
      graph.fill_candidate_is_previous operation candidate candidate_fill
    have candidate_member :=
      (graph.fill_candidate_operations operation candidate candidate_fill).2
    exact
      operation_reaches_candidate.trans
        (complete_below candidate previousOperation candidate_member
          previous_member candidate_previous candidate_recent candidate_related)

/--
The bridge case of the completeness proof: the operation fills a position, and
the previous operation operated on a strict transitive child position of it.
Between them the filled position went from occupied to empty, and the
operation that emptied it operated on the filled position or one of its
transitive parent positions.
-/
theorem reaches_of_fillPosition_strict_child (graph : CompleteResolvedDefineGraph)
    {operation previousOperation : ParticleOperation}
    {fillPosition operatedPosition : Position}
    (complete_below :
      ∀ newer older,
        graph.isOperation newer →
        graph.isOperation older →
        MoreRecent operation newer →
        MoreRecent newer older →
        OperationsRelated newer older →
        Reaches graph.dependency newer older)
    (operation_member : graph.isOperation operation)
    (previous_member : graph.isOperation previousOperation)
    (fill_position : FillPosition operation = some fillPosition)
    (previous_operates : OperatesOn previousOperation operatedPosition)
    (fill_parent : ParentOrSame fillPosition operatedPosition)
    (fill_is_strict : fillPosition ≠ operatedPosition)
    (operation_after_previous : MoreRecent operation previousOperation) :
    Reaches graph.dependency operation previousOperation := by
  have fill_occupied_after_previous :
      graph.occupancy.occupiedBefore
        (previousOperation.operationOrder + 1) fillPosition :=
    graph.occupancy.parent_occupied_after_child_operation previous_member
      previous_operates fill_parent fill_is_strict
  have fill_empty_before_operation :
      ¬graph.occupancy.occupiedBefore operation.operationOrder fillPosition :=
    graph.occupancy.fill_position_is_empty operation fillPosition
      operation_member fill_position
  have start_le_operation :
      previousOperation.operationOrder + 1 ≤ operation.operationOrder :=
    Nat.succ_le_of_lt operation_after_previous
  rcases exists_emptying_transition
      (fun operationOrder =>
        graph.occupancy.occupiedBefore operationOrder fillPosition)
      start_le_operation fill_occupied_after_previous
      fill_empty_before_operation with
    ⟨transition, start_le_transition, transition_before_operation,
      occupied_at_transition, unoccupied_after_transition⟩
  rcases graph.occupancy.newly_unoccupied_has_operation occupied_at_transition
      unoccupied_after_transition with
    ⟨emptier, emptierPosition, emptier_member, emptier_order, emptier_operates,
      emptier_parent⟩
  have operation_after_emptier : MoreRecent operation emptier := by
    rw [MoreRecent, emptier_order]
    exact transition_before_operation
  have emptier_after_previous : MoreRecent emptier previousOperation := by
    rw [MoreRecent, emptier_order]
    exact Nat.lt_of_succ_le start_le_transition
  have operation_reaches_emptier :=
    graph.reaches_of_fillPosition_parent complete_below operation_member
      emptier_member fill_position emptier_operates emptier_parent
      operation_after_emptier
  have emptier_related : OperationsRelated emptier previousOperation :=
    ⟨emptierPosition, operatedPosition, emptier_operates, previous_operates,
      Or.inl (emptier_parent.trans fill_parent)⟩
  exact
    operation_reaches_emptier.trans
      (complete_below emptier previousOperation emptier_member previous_member
        operation_after_emptier emptier_after_previous emptier_related)

/--
Completeness: the operation reaches every previous operation with a related
operated position. This is statement 1 of the English proof's ordering
invariants.
-/
theorem reaches_of_relatedPrevious (graph : CompleteResolvedDefineGraph) :
    ∀ operation previousOperation,
      graph.isOperation operation →
      graph.isOperation previousOperation →
      RelatedPrevious operation previousOperation →
      Reaches graph.dependency operation previousOperation := by
  suffices bounded :
      ∀ bound operation previousOperation,
        graph.isOperation operation →
        graph.isOperation previousOperation →
        operation.operationOrder < bound →
        RelatedPrevious operation previousOperation →
        Reaches graph.dependency operation previousOperation by
    intro operation previousOperation operation_member previous_member
      related_previous
    exact
      bounded (operation.operationOrder + 1) operation previousOperation
        operation_member previous_member (Nat.lt_succ_self _) related_previous
  intro bound
  induction bound with
  | zero =>
      intro operation previousOperation _ _ order_lt
      omega
  | succ bound induction_hypothesis =>
      intro operation previousOperation operation_member previous_member
        order_lt related_previous
      rcases Nat.lt_succ_iff_lt_or_eq.mp order_lt with
        order_below | order_is_bound
      · exact
          induction_hypothesis operation previousOperation operation_member
            previous_member order_below related_previous
      · have complete_below :
            ∀ newer older,
              graph.isOperation newer →
              graph.isOperation older →
              MoreRecent operation newer →
              MoreRecent newer older →
              OperationsRelated newer older →
              Reaches graph.dependency newer older := by
          intro newer older newer_member older_member newer_previous
            newer_after_older operations_related
          have newer_below : newer.operationOrder < bound := by
            rw [MoreRecent] at newer_previous
            omega
          exact
            induction_hypothesis newer older newer_member older_member
              newer_below ⟨newer_after_older, operations_related⟩
        rcases related_previous with
          ⟨operation_after_previous, operationPosition, operatedPosition,
            operation_operates, previous_operates, positions_related⟩
        cases operation_kind : operation.kind with
        | create target =>
            have operation_position_is_target : operationPosition = target := by
              simpa [OperatesOn, operation_kind] using operation_operates
            subst operation_position_is_target
            have fill_position : FillPosition operation = some operationPosition := by
              simp [FillPosition, operation_kind]
            by_cases operated_parent :
                ParentOrSame operatedPosition operationPosition
            · exact
                graph.reaches_of_fillPosition_parent complete_below
                  operation_member previous_member fill_position
                  previous_operates operated_parent operation_after_previous
            · have fill_parent : ParentOrSame operationPosition operatedPosition := by
                rcases positions_related with fill_first | operated_first
                · exact fill_first
                · exact False.elim (operated_parent operated_first)
              have fill_is_strict : operationPosition ≠ operatedPosition := by
                intro fill_is_operated
                subst fill_is_operated
                exact operated_parent List.prefix_rfl
              exact
                graph.reaches_of_fillPosition_strict_child complete_below
                  operation_member previous_member fill_position
                  previous_operates fill_parent fill_is_strict
                  operation_after_previous
        | destroy target =>
            have operation_position_is_target : operationPosition = target := by
              simpa [OperatesOn, operation_kind] using operation_operates
            subst operation_position_is_target
            exact
              graph.reaches_of_emptyPosition_related complete_below
                operation_member previous_member
                (by simp [EmptyPosition, operation_kind]) previous_operates
                (related_symm positions_related) operation_after_previous
        | move source target =>
            rcases (show operationPosition = source ∨ operationPosition = target by
                simpa [OperatesOn, operation_kind] using operation_operates) with
              operation_position_is_source | operation_position_is_target
            · subst operation_position_is_source
              exact
                graph.reaches_of_emptyPosition_related complete_below
                  operation_member previous_member
                  (by simp [EmptyPosition, operation_kind]) previous_operates
                  (related_symm positions_related) operation_after_previous
            · subst operation_position_is_target
              have fill_position :
                  FillPosition operation = some operationPosition := by
                simp [FillPosition, operation_kind]
              by_cases operated_parent :
                  ParentOrSame operatedPosition operationPosition
              · exact
                  graph.reaches_of_fillPosition_parent complete_below
                    operation_member previous_member fill_position
                    previous_operates operated_parent operation_after_previous
              · have fill_parent :
                    ParentOrSame operationPosition operatedPosition := by
                  rcases positions_related with fill_first | operated_first
                  · exact fill_first
                  · exact False.elim (operated_parent operated_first)
                have fill_is_strict : operationPosition ≠ operatedPosition := by
                  intro fill_is_operated
                  subst fill_is_operated
                  exact operated_parent List.prefix_rfl
                exact
                  graph.reaches_of_fillPosition_strict_child complete_below
                    operation_member previous_member fill_position
                    previous_operates fill_parent fill_is_strict
                    operation_after_previous

end CompleteResolvedDefineGraph

theorem calculatedDependency_reaches_of_relatedPrevious
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation)
    {operation previousOperation : ParticleOperation}
    (operation_member : isOperation operation)
    (previous_member : isOperation previousOperation)
    (related_previous : RelatedPrevious operation previousOperation) :
    Reaches (CalculatedDependency history) operation previousOperation :=
  (calculatedCompleteResolvedDefineGraph history).reaches_of_relatedPrevious
    operation previousOperation operation_member previous_member related_previous

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ (history : ValidResolvedHistory isOperation) operation previousOperation,
      isOperation operation →
        isOperation previousOperation →
        RelatedPrevious operation previousOperation →
        Reaches (CalculatedDependency history) operation previousOperation :=
  calculatedDependency_reaches_of_relatedPrevious

end TypeContracts

end Define.OperationGraph
