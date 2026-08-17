import calculation_correctness

set_option warningAsError true
set_option autoImplicit false

/-!
# Particle Operation Dependency Graph Minimality

This file formalizes the English proof in
`minimality-proof.md`. The English proof is
the source of the mathematical argument; the definitions and theorems here
encode that argument for Lean to check.

## Formalization boundary

Positions are finite chained names. Graph vertices are only concrete Create,
Destroy, and Move Particle Operations. Action Requirements, Action Guarantees,
and modular destruction values are resolved before they can participate in the
dependency relation.

`RuleCalculation` encodes the current rules in this order:

1. the Empty Rule Collection and optional Fill Dependency;
2. the simultaneous Comparison;
3. the Empty Rule's Move Correction;
4. the Move Rule's Fill Dependency removal.

`RuleGraph.exact_dependency` requires an edge exactly when this calculation
retains the dependency. The generic graph lemmas establish that adding a vertex
whose dependencies form a reachability antichain preserves transitive
minimality. The Define-specific theorems prove that every `RuleCalculation`
produces such an antichain.

No premise states that direct dependencies form an antichain, that an edge is
necessary, that the graph is acyclic, or that the graph is transitively minimal.
Every edge is proved to point to a previous operation, from which acyclicity is
derived.

## Relation to valid Define programs

`ResolvedDefineGraph` records consequences of valid Define execution:

- candidates are previous concrete Particle Operations with their specified
  position provenance;
- the position history supplies a candidate at least as recent as every
  applicable earlier operation;
- Create, Destroy, and Move have their specified occupancy transitions.

`calculation_correctness.lean` machine-checks the construction of a
`ResolvedDefineGraph` from every `ValidResolvedHistory`. The remaining
source-to-history conversion is not machine-checked because complete Define
source and validation semantics are not modeled in Lean.

A valid resolved history assigns each Particle Operation occurrence its
natural-number index and encodes each fully resolved position as a finite
chained name. The history may stop or continue without end; the theorem does not
require a finite vertex type. The occupancy state immediately before each
occurrence supplies `ExactOccupancyExecution`. The source-to-history proof must
show that caller binding preserves and reflects equality and transitive
parent/child relationships and that caller and destruction resolution
contribute the concrete Particle Operations and resolved position names used by
the calculation.

`latest_source_candidate` also covers a position name that is empty when the
emptying operation runs. A valid resolved history retains every previously
operated resolved name for graph queries. The construction-correctness proof
therefore derives its most-recent entry directly, including a Move that became
the entry for a changed transitive-child name.

The structure omits validity constraints unrelated to dependency minimality.
It can therefore describe abstract values that no valid Define program produces,
but every valid program satisfies the obligations used by the theorem. Proving
the theorem for this larger class strengthens the result; those abstract values
do not supply a premise for the valid-program case.

The non-Move source-candidate result is derived from occupancy transitions. In
particular, after an earlier Create or Destroy on a strict parent position, an
occupied source must have changed from empty to occupied at an intervening
operation. The most-recent entry for that operation's position excludes the
earlier candidate. The remaining cases cover Move dependencies and the Fill
Dependency.

Caller-prefix resolution is injective and preserves position relationships,
Particle Operation kinds, operation order, and dependency paths. The final
theorem concerns a completely resolved graph, so automatic and contributed
Destroy Particle Statements use the same Destroy case.

The separate witness file constructs a nonempty valid occupancy execution with
a Create-to-Destroy dependency. It demonstrates that the semantic obligations
are jointly satisfiable without supplying any theorem premise.
-/

namespace Define.OperationGraph

universe u v

def NonMoveSourceCandidatesAreIrredundant (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop) : Prop :=
  ∀ olderCandidate newerCandidate,
    calculation.sourceCandidate olderCandidate →
    calculation.AfterComparison olderCandidate →
    ¬IsMove olderCandidate →
    calculation.AfterComparison newerCandidate →
    newerCandidate ≠ olderCandidate →
    ¬Reaches dependency newerCandidate olderCandidate

theorem dependenciesAreAntichain (calculation : RuleCalculation)
    (dependency : ParticleOperation → ParticleOperation → Prop)
    (well_formed : calculation.WellFormed)
    (non_move_source_candidates_are_irredundant :
      NonMoveSourceCandidatesAreIrredundant calculation dependency) :
    ∀ newerCandidate olderCandidate,
      calculation.Dependency dependency newerCandidate →
      calculation.Dependency dependency olderCandidate →
      newerCandidate ≠ olderCandidate →
      ¬Reaches dependency newerCandidate olderCandidate := by
  intro newerCandidate olderCandidate newer_final older_final distinct reaches_older
  cases operation_kind : calculation.operation.kind with
  | create target =>
      have newer_fill : calculation.fillCandidate = some newerCandidate := by
        simpa [RuleCalculation.Dependency,
          RuleCalculation.IsFillCandidate, operation_kind] using newer_final
      have older_fill : calculation.fillCandidate = some olderCandidate := by
        simpa [RuleCalculation.Dependency,
          RuleCalculation.IsFillCandidate, operation_kind] using older_final
      have candidates_equal : newerCandidate = olderCandidate := by
        exact Option.some.inj (newer_fill.symm.trans older_fill)
      exact distinct candidates_equal
  | destroy target =>
      have newer_empty :
          calculation.AfterMoveCorrection dependency newerCandidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          newer_final
      have older_empty :
          calculation.AfterMoveCorrection dependency olderCandidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          older_final
      rcases older_empty.2 with older_not_move | no_candidate_reaches_older
      · have no_fill : calculation.fillCandidate = none := by
          simpa [RuleCalculation.WellFormed, operation_kind] using well_formed
        have older_source : calculation.sourceCandidate olderCandidate := by
          rcases older_empty.1.1 with older_source | older_fill
          · exact older_source
          · simp [RuleCalculation.IsFillCandidate, no_fill] at older_fill
        exact
          non_move_source_candidates_are_irredundant olderCandidate
            newerCandidate older_source older_empty.1 older_not_move
            newer_empty.1 distinct reaches_older
      · exact no_candidate_reaches_older newerCandidate newer_empty.1 distinct reaches_older
  | move source target =>
      have newer_move :
          calculation.MoveRuleDependency dependency newerCandidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          newer_final
      have older_move :
          calculation.MoveRuleDependency dependency olderCandidate := by
        simpa [RuleCalculation.Dependency, operation_kind] using
          older_final
      rcases older_move.1.2 with older_not_move | no_candidate_reaches_older
      · rcases older_move.1.1.1 with older_source | older_fill
        · exact
            non_move_source_candidates_are_irredundant olderCandidate
              newerCandidate older_source older_move.1.1 older_not_move
              newer_move.1.1 distinct reaches_older
        · rcases newer_move.1.1.1 with newer_source | newer_fill
          · exact older_move.2 ⟨older_fill, newerCandidate, newer_source,
              newer_move.1, distinct, reaches_older⟩
          · have candidates_equal : newerCandidate = olderCandidate := by
              exact Option.some.inj (newer_fill.symm.trans older_fill)
            exact distinct candidates_equal
      · exact
          no_candidate_reaches_older newerCandidate newer_move.1.1 distinct
            reaches_older

theorem operationsRelated_symm {first second : ParticleOperation} :
    OperationsRelated first second → OperationsRelated second first := by
  rintro ⟨firstPosition, secondPosition, first_operates, second_operates,
    positions_related⟩
  exact ⟨secondPosition, firstPosition, second_operates, first_operates,
    related_symm positions_related⟩

theorem ResolvedDefineGraph.inCollection_is_previous
    (graph : ResolvedDefineGraph) {operation candidate : ParticleOperation}
    (in_collection :
      (graph.calculation operation).InCollection candidate) :
    MoreRecent operation candidate := by
  rcases in_collection with source_candidate | fill_candidate
  · rcases (graph.source_candidate_iff operation candidate).mp source_candidate with
      ⟨position, candidate_at_position⟩
    exact graph.source_candidate_is_previous operation candidate position
      candidate_at_position
  · exact graph.fill_candidate_is_previous operation candidate fill_candidate

theorem ResolvedDefineGraph.directDependency_is_previous
    (graph : ResolvedDefineGraph) {operation candidate : ParticleOperation}
    (direct_dependency : graph.dependency operation candidate) :
    MoreRecent operation candidate := by
  exact
    graph.inCollection_is_previous
      (RuleCalculation.dependency_isInCollection
        ((graph.exact_dependency operation candidate).mp direct_dependency))

theorem ResolvedDefineGraph.pointsBackward (graph : ResolvedDefineGraph) :
    PointsBackward ParticleOperation.operationOrder graph.dependency := by
  intro operation candidate direct_dependency
  exact graph.directDependency_is_previous direct_dependency

theorem ResolvedDefineGraph.directDependency_operations
    (graph : ResolvedDefineGraph) {operation candidate : ParticleOperation}
    (direct_dependency : graph.dependency operation candidate) :
    graph.isOperation operation ∧ graph.isOperation candidate := by
  rcases
      RuleCalculation.dependency_isInCollection
        ((graph.exact_dependency operation candidate).mp direct_dependency) with
    source_candidate | fill_candidate
  · rcases (graph.source_candidate_iff operation candidate).mp source_candidate with
      ⟨position, candidate_at_position⟩
    exact
      graph.source_candidate_operations operation candidate position
        candidate_at_position
  · exact graph.fill_candidate_operations operation candidate fill_candidate

theorem ResolvedDefineGraph.directDependencyPositionsRelated
    (graph : ResolvedDefineGraph) {operation candidate : ParticleOperation}
    (direct_dependency : graph.dependency operation candidate) :
    OperationsRelated operation candidate := by
  have rule_dependency :=
    (graph.exact_dependency operation candidate).mp direct_dependency
  have in_collection :=
    RuleCalculation.dependency_isInCollection rule_dependency
  rcases in_collection with source_candidate | fill_candidate
  · rcases (graph.source_candidate_iff operation candidate).mp source_candidate with
      ⟨candidatePosition, candidate_at_position⟩
    rcases graph.source_candidate_empty_position operation candidate
        candidatePosition candidate_at_position with
      ⟨emptyPosition, empty_position, candidate_position_related⟩
    rcases graph.source_candidate_operated_position operation candidate
        candidatePosition candidate_at_position with
      ⟨candidateOperatedPosition, candidate_operates,
        candidate_operated_parent⟩
    have candidate_operated_related_to_empty :
        Related candidateOperatedPosition emptyPosition :=
      parent_of_related_is_related candidate_operated_parent
        candidate_position_related
    exact
      ⟨emptyPosition, candidateOperatedPosition,
        operatesOn_emptyPosition empty_position, candidate_operates,
        related_symm candidate_operated_related_to_empty⟩
  · rcases graph.fill_candidate_operated_position operation candidate fill_candidate with
      ⟨fillPosition, candidateOperatedPosition, fill_position, candidate_operates,
        candidate_parent_of_fill⟩
    exact
      ⟨fillPosition, candidateOperatedPosition,
        operatesOn_fillPosition fill_position, candidate_operates,
        Or.inr candidate_parent_of_fill⟩

theorem moreRecent_trans {newest middle oldest : ParticleOperation}
    (newest_after_middle : MoreRecent newest middle)
    (middle_after_oldest : MoreRecent middle oldest) :
    MoreRecent newest oldest :=
  Nat.lt_trans middle_after_oldest newest_after_middle

theorem ResolvedDefineGraph.reaches_is_moreRecent
    (graph : ResolvedDefineGraph) {newer older : ParticleOperation}
    (reaches : Reaches graph.dependency newer older) :
    MoreRecent newer older :=
  reaches_decreases_order graph.pointsBackward reaches

theorem ResolvedDefineGraph.laterRelatedOperationExcludesNonMoveCandidate
    (graph : ResolvedDefineGraph)
    {operation olderCandidate laterOperation : ParticleOperation}
    {source candidatePosition laterPosition : Position}
    (older_candidate_at_position :
      graph.sourceCandidateAt operation olderCandidate candidatePosition)
    (empty_position : EmptyPosition operation = some source)
    (older_after_comparison :
      (graph.calculation operation).AfterComparison olderCandidate)
    (older_not_move : ¬IsMove olderCandidate)
    (later_after_older : MoreRecent laterOperation olderCandidate)
    (operation_after_later : MoreRecent operation laterOperation)
    (later_is_operation : graph.isOperation laterOperation)
    (later_operates : OperatesOn laterOperation laterPosition)
    (later_related_to_older_position :
      Related laterPosition candidatePosition)
    (later_related_to_source : Related laterPosition source) : False := by
  have operation_is_member :=
    (graph.source_candidate_operations operation olderCandidate candidatePosition
      older_candidate_at_position).1
  rcases graph.latest_source_candidate operation source laterPosition
      laterOperation operation_is_member later_is_operation empty_position
      later_related_to_source later_operates operation_after_later with
    ⟨latestCandidate, latest_candidate_at_position, latest_recency⟩
  have latest_source_candidate :
      (graph.calculation operation).sourceCandidate latestCandidate :=
    (graph.source_candidate_iff operation latestCandidate).mpr
      ⟨laterPosition, latest_candidate_at_position⟩
  have latest_in_collection :
      (graph.calculation operation).InCollection latestCandidate :=
    Or.inl latest_source_candidate
  have latest_after_older : MoreRecent latestCandidate olderCandidate := by
    rcases latest_recency with latest_is_later | latest_after_later
    · simpa [latest_is_later] using later_after_older
    · exact moreRecent_trans latest_after_later later_after_older
  rcases graph.source_candidate_operated_position operation latestCandidate
      laterPosition latest_candidate_at_position with
    ⟨latestOperatedPosition, latest_operates, latest_parent_of_position⟩
  have latest_operated_related_to_older_position :
      Related latestOperatedPosition candidatePosition :=
    parent_of_related_is_related latest_parent_of_position
      later_related_to_older_position
  have older_operates : OperatesOn olderCandidate candidatePosition :=
    graph.non_move_source_candidate_operates_on_position operation olderCandidate
      candidatePosition older_candidate_at_position older_not_move
  have operations_related :
      OperationsRelated latestCandidate olderCandidate :=
    ⟨latestOperatedPosition, candidatePosition, latest_operates, older_operates,
      latest_operated_related_to_older_position⟩
  exact
    older_after_comparison.2 latestCandidate latest_in_collection
      latest_after_older operations_related

theorem ResolvedDefineGraph.occupiedSourceBridge
    (graph : ResolvedDefineGraph)
    {operation olderCandidate : ParticleOperation}
    {source candidatePosition : Position}
    (older_candidate_at_position :
      graph.sourceCandidateAt operation olderCandidate candidatePosition)
    (empty_position : EmptyPosition operation = some source)
    (candidate_parent_of_source : ParentOrSame candidatePosition source)
    (candidate_position_is_not_source : candidatePosition ≠ source)
    (older_not_move : ¬IsMove olderCandidate) :
    ∃ bridgeOperation bridgePosition,
      graph.isOperation bridgeOperation ∧
        MoreRecent bridgeOperation olderCandidate ∧
        MoreRecent operation bridgeOperation ∧
        OperatesOn bridgeOperation bridgePosition ∧
        Related bridgePosition candidatePosition ∧
        Related bridgePosition source := by
  let validOccupancy := graph.occupancy.toValidOccupancyTrace
  have operation_members :=
    graph.source_candidate_operations operation olderCandidate candidatePosition
      older_candidate_at_position
  have older_operates : OperatesOn olderCandidate candidatePosition :=
    graph.non_move_source_candidate_operates_on_position operation olderCandidate
      candidatePosition older_candidate_at_position older_not_move
  have source_unoccupied_after_older :
      ¬validOccupancy.occupiedBefore
        (olderCandidate.operationOrder + 1) source :=
    validOccupancy.non_move_strict_child_unoccupied_after olderCandidate
      candidatePosition source operation_members.2 older_not_move older_operates
      candidate_parent_of_source candidate_position_is_not_source
  have source_occupied_before_operation :
      validOccupancy.occupiedBefore operation.operationOrder source :=
    validOccupancy.empty_position_is_occupied_before operation source
      operation_members.1 empty_position
  have start_le_operation :
      olderCandidate.operationOrder + 1 ≤ operation.operationOrder :=
    Nat.succ_le_of_lt
      (graph.source_candidate_is_previous operation olderCandidate
        candidatePosition older_candidate_at_position)
  rcases exists_occupancy_transition
      (fun operationOrder => validOccupancy.occupiedBefore operationOrder source)
      start_le_operation source_unoccupied_after_older
      source_occupied_before_operation with
    ⟨transition, start_le_transition, transition_before_operation,
      source_unoccupied_before_transition, source_occupied_after_transition⟩
  rcases validOccupancy.newly_occupied_has_operation transition source
      source_unoccupied_before_transition source_occupied_after_transition with
    ⟨bridgeOperation, bridgePosition, bridge_is_operation, bridge_order, bridge_operates,
      bridge_related_to_source⟩
  have bridge_after_older : MoreRecent bridgeOperation olderCandidate := by
    rw [MoreRecent, bridge_order]
    exact Nat.lt_of_succ_le start_le_transition
  have operation_after_bridge : MoreRecent operation bridgeOperation := by
    rw [MoreRecent, bridge_order]
    exact transition_before_operation
  have bridge_related_to_candidate :
      Related bridgePosition candidatePosition :=
    related_to_child_is_related_to_parent candidate_parent_of_source
      bridge_related_to_source
  exact
    ⟨bridgeOperation, bridgePosition, bridge_is_operation, bridge_after_older,
      operation_after_bridge, bridge_operates, bridge_related_to_candidate,
      bridge_related_to_source⟩

theorem ResolvedDefineGraph.nonMoveSourceCandidatesAreIrredundant
    (graph : ResolvedDefineGraph) (operation : ParticleOperation) :
    NonMoveSourceCandidatesAreIrredundant
      (graph.calculation operation) graph.dependency := by
  intro olderCandidate newerCandidate older_source older_after_comparison
    older_not_move newer_after_comparison candidates_distinct reaches_older
  rcases (graph.source_candidate_iff operation olderCandidate).mp older_source with
    ⟨candidatePosition, older_candidate_at_position⟩
  rcases graph.source_candidate_empty_position operation olderCandidate
      candidatePosition older_candidate_at_position with
    ⟨source, empty_position, candidate_position_related_to_source⟩
  have older_operates : OperatesOn olderCandidate candidatePosition :=
    graph.non_move_source_candidate_operates_on_position operation olderCandidate
      candidatePosition older_candidate_at_position older_not_move
  by_cases source_parent_of_candidate : ParentOrSame source candidatePosition
  · rcases Reaches.last_edge reaches_older with
      ⟨laterOperation, path_to_later, final_edge⟩
    have final_operations_related :=
      graph.directDependencyPositionsRelated final_edge
    rcases final_operations_related with
      ⟨laterPosition, olderPosition, later_operates, older_operates_again,
        later_related_to_older⟩
    have older_position_is_candidate_position :
        olderPosition = candidatePosition :=
      operated_position_unique_of_not_move older_not_move older_operates_again
        older_operates
    subst older_position_is_candidate_position
    have later_related_to_source : Related laterPosition source :=
      related_to_child_is_related_to_parent source_parent_of_candidate
        later_related_to_older
    have later_after_older : MoreRecent laterOperation olderCandidate :=
      graph.pointsBackward laterOperation olderCandidate final_edge
    have later_is_operation :=
      (graph.directDependency_operations final_edge).1
    have operation_after_newer : MoreRecent operation newerCandidate :=
      graph.inCollection_is_previous newer_after_comparison.1
    have operation_after_later : MoreRecent operation laterOperation := by
      rcases path_to_later with
        newer_is_later | newer_reaches_later
      · subst newer_is_later
        exact operation_after_newer
      · exact
          moreRecent_trans operation_after_newer
            (graph.reaches_is_moreRecent newer_reaches_later)
    exact
      graph.laterRelatedOperationExcludesNonMoveCandidate
        older_candidate_at_position empty_position older_after_comparison
        older_not_move later_after_older operation_after_later later_is_operation
        later_operates later_related_to_older later_related_to_source
  · have candidate_parent_of_source : ParentOrSame candidatePosition source := by
      rcases candidate_position_related_to_source with candidate_parent | source_parent
      · exact candidate_parent
      · exact False.elim (source_parent_of_candidate source_parent)
    have candidate_position_is_not_source : candidatePosition ≠ source := by
      intro candidate_is_source
      subst candidate_is_source
      exact source_parent_of_candidate List.prefix_rfl
    rcases newer_after_comparison.1 with newer_source | newer_fill
    · rcases (graph.source_candidate_iff operation newerCandidate).mp newer_source with
        ⟨newerCandidatePosition, newer_candidate_at_position⟩
      rcases graph.source_candidate_empty_position operation newerCandidate
          newerCandidatePosition newer_candidate_at_position with
        ⟨newerSource, newer_empty_position, newer_position_related_to_source⟩
      have newer_source_is_source : newerSource = source := by
        exact Option.some.inj (newer_empty_position.symm.trans empty_position)
      subst newer_source_is_source
      rcases graph.source_candidate_operated_position operation newerCandidate
          newerCandidatePosition newer_candidate_at_position with
        ⟨newerOperatedPosition, newer_operates, newer_parent_of_position⟩
      have newer_operated_related_to_older_position :
          Related newerOperatedPosition candidatePosition :=
        parent_of_position_related_to_child_is_related_to_parent
          candidate_parent_of_source newer_position_related_to_source
          newer_parent_of_position
      have operations_related : OperationsRelated newerCandidate olderCandidate :=
        ⟨newerOperatedPosition, candidatePosition, newer_operates, older_operates,
          newer_operated_related_to_older_position⟩
      exact
        older_after_comparison.2 newerCandidate newer_after_comparison.1
          (graph.reaches_is_moreRecent reaches_older) operations_related
    · rcases graph.occupiedSourceBridge older_candidate_at_position empty_position
          candidate_parent_of_source candidate_position_is_not_source older_not_move with
        ⟨bridgeOperation, bridgePosition, bridge_is_operation, bridge_after_older,
          operation_after_bridge, bridge_operates, bridge_related_to_older,
          bridge_related_to_source⟩
      exact
        graph.laterRelatedOperationExcludesNonMoveCandidate
          older_candidate_at_position empty_position older_after_comparison
          older_not_move bridge_after_older operation_after_bridge bridge_is_operation
          bridge_operates bridge_related_to_older bridge_related_to_source

theorem RuleGraph.directDependenciesAreAntichains
    (graph : RuleGraph)
    (non_move_source_candidates_are_irredundant :
      ∀ operation,
        NonMoveSourceCandidatesAreIrredundant
          (graph.calculation operation) graph.dependency) :
    DirectDependenciesAreAntichains graph.dependency := by
  intro operation newerCandidate olderCandidate newer_dependency older_dependency
    distinct
  apply
    dependenciesAreAntichain (graph.calculation operation) graph.dependency
      (graph.calculation_well_formed operation)
      (non_move_source_candidates_are_irredundant operation)
      newerCandidate olderCandidate
  · exact (graph.exact_dependency operation newerCandidate).mp newer_dependency
  · exact (graph.exact_dependency operation olderCandidate).mp older_dependency
  · exact distinct

theorem RuleGraph.transitivelyMinimal_of_nonMoveSourceCandidatesAreIrredundant
    (graph : RuleGraph)
    (non_move_source_candidates_are_irredundant :
      ∀ operation,
        NonMoveSourceCandidatesAreIrredundant
          (graph.calculation operation) graph.dependency) :
    TransitivelyMinimal graph.dependency :=
  transitivelyMinimal_of_directDependenciesAreAntichains
    (graph.directDependenciesAreAntichains
      non_move_source_candidates_are_irredundant)

theorem ResolvedDefineGraph.acyclic (graph : ResolvedDefineGraph) :
    Acyclic graph.dependency :=
  acyclic_of_pointsBackward graph.pointsBackward

theorem ResolvedDefineGraph.transitivelyMinimal
    (graph : ResolvedDefineGraph) :
    TransitivelyMinimal graph.dependency :=
  graph.toRuleGraph.transitivelyMinimal_of_nonMoveSourceCandidatesAreIrredundant
    graph.nonMoveSourceCandidatesAreIrredundant

theorem ResolvedDefineGraph.isMinimalDAG (graph : ResolvedDefineGraph) :
    Acyclic graph.dependency ∧ TransitivelyMinimal graph.dependency :=
  ⟨graph.acyclic, graph.transitivelyMinimal⟩

theorem calculatedDependency_isMinimalDAG
    {isOperation : ParticleOperation → Prop}
    (history : ValidResolvedHistory isOperation) :
    Acyclic (CalculatedDependency history) ∧
      TransitivelyMinimal (CalculatedDependency history) :=
  (calculatedResolvedDefineGraph history).isMinimalDAG

section TypeContracts

example {isOperation : ParticleOperation → Prop} :
    ∀ history : ValidResolvedHistory isOperation,
      Acyclic (CalculatedDependency history) ∧
        TransitivelyMinimal (CalculatedDependency history) :=
  calculatedDependency_isMinimalDAG

end TypeContracts

end Define.OperationGraph
