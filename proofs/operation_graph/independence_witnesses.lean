import completeness

set_option warningAsError true
set_option autoImplicit false

/-!
# Independence Witnesses for the Particle Operation Dependency Graph Rules

Each section of this file shows that one clause of the Fill, Empty, and Move
Rules is independent of the others: a concrete operation history on which the
complete rules produce a correct graph, while the rules with that one clause
removed produce a graph that violates one of the two defining properties.

- A *missing required ordering*: two operations related by `RelatedPrevious`
  (previous, with related operated positions) where the weakened graph has no
  dependency path. The weakened rules under-synchronize.
- A *redundant dependency*: an edge whose removal leaves reachability
  unchanged, exhibited by a path that avoids the edge. The weakened rules are
  not transitively minimal.

For each witness, an executable model checks that the history is valid and
derives the dependencies selected by the complete rules and by the rules with
one clause changed. The resulting concrete relations are then used to prove
the property contrast between the two graphs. Comments name the integration
test that pins the same history where one exists. Joint satisfiability of the
resolved-graph obligations is demonstrated separately in
`minimality_witnesses.lean`.

`calculate` returns `none` when an operation's order or occupancy transition
is invalid. Thus each `complete_rules_derive_graph` and
`weakened_rules_derive_graph` equality to `some ...` also proves that its
history is valid under both rule variants.

This file makes no independence claim for the Empty Rule's transitive-parent
collection. An earlier proposed witness destroyed a child position that had
never been filled, so it was not a valid resolved history; adding the omitted
child operation also supplies a path to the parent operation.

The Action Parent Rule has no independence witness at this level:
`CompleteResolvedDefineGraph.dependency_isOrdinary` in
`completeness.lean` proves that against
the complete resolved history the rule's condition never holds and its
candidate is covered by an ordinary dependency, so removing it changes nothing
in a model that already sees the whole history.
Its independence is modular: a callee-local calculation has no caller history
to scan and needs the rule to defer that selection to its callers, and the
resolved models in this file do not encode that callee-local level. Its
fallback-only restriction does have a witness here
(`ActionParentOnlyAsFallback` below): applying it when the other rules already
left a dependency adds a redundant edge.

Most complete-rule graphs in this file assign each operation at most one
dependency, so their transitive minimality follows immediately from
`transitivelyMinimal_of_at_most_one_dependency`. The Fill Dependency removal
witness reuses the corresponding fully resolved model's minimality proof.
-/

namespace Define.OperationGraph

universe u

theorem transitivelyMinimal_of_at_most_one_dependency {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop)
    (at_most_one :
      ∀ source first second,
        dependency source first → dependency source second → first = second) :
    TransitivelyMinimal dependency := by
  intro source target direct_dependency alternate_path
  cases alternate_path with
  | direct edge =>
      exact edge.2 ⟨rfl, rfl⟩
  | @step _ next _ edge remaining_path =>
      exact edge.2 ⟨rfl, at_most_one source next target edge.1 direct_dependency⟩

theorem moreRecent_of_order_lt {newer older : ParticleOperation}
    (order_lt : older.operationOrder < newer.operationOrder) :
    MoreRecent newer older :=
  order_lt

namespace IndependenceWitnesses

structure RuleVariant where
  fillParentPositions : Bool := true
  fillMostRecent : Bool := true
  emptyParentPositions : Bool := true
  emptyChildPositions : Bool := true
  moveChildEntries : Bool := true
  simultaneousComparison : Bool := true
  moveCorrection : Bool := true
  fillDependencyRemoval : Bool := true
  actionParentOnlyAsFallback : Bool := true
  deriving DecidableEq, Repr

def completeRules : RuleVariant := {}

def operationPositions (operation : ParticleOperation) : List Position :=
  match operation.kind with
  | .create target | .destroy target => [target]
  | .move source target => [source, target]

def nonemptyPrefixes : Position → List Position
  | [] => []
  | head :: tail =>
      [head] :: (nonemptyPrefixes tail).map (fun namePrefix => head :: namePrefix)

def strictPrefixes : Position → List Position
  | [] | [_] => []
  | head :: second :: tail =>
      [head] ::
        (strictPrefixes (second :: tail)).map (fun namePrefix => head :: namePrefix)

def knownPositions (operations : List ParticleOperation) : List Position :=
  (operations.flatMap fun operation =>
    (operation.actionParent :: operationPositions operation).flatMap
      nonemptyPrefixes).eraseDups

structure HistoryState where
  entries : List (Position × Nat) := []
  occupied : List Position := []
  dependencies : List (List Nat) := []
  reachable : List (List Nat) := []

def HistoryState.entryAt (state : HistoryState) (position : Position) : Option Nat :=
  (state.entries.find? fun entry => entry.1 == position).map Prod.snd

def HistoryState.setEntry (state : HistoryState) (position : Position)
    (operationOrder : Nat) : HistoryState :=
  { state with
    entries :=
      (position, operationOrder) ::
        state.entries.filter fun entry => entry.1 != position }

def HistoryState.isOccupied (state : HistoryState) (position : Position) : Bool :=
  state.occupied.contains position

def HistoryState.positionAvailable (state : HistoryState)
    (position : Position) : Bool :=
  (strictPrefixes position).all state.isOccupied

def HistoryState.hasOccupiedChild (state : HistoryState)
    (position : Position) : Bool :=
  state.occupied.any fun occupiedPosition =>
    occupiedPosition != position && position.isPrefixOf occupiedPosition

def validOperation (state : HistoryState) (operation : ParticleOperation) : Bool :=
  match operation.kind with
  | .create target =>
      state.positionAvailable target && !state.isOccupied target
  | .destroy target =>
      state.isOccupied target && !state.hasOccupiedChild target
  | .move source target =>
      state.isOccupied source && state.positionAvailable target &&
        !state.isOccupied target && !source.isPrefixOf target &&
        !target.isPrefixOf source

def latestCandidate (preferMostRecent : Bool) : List Nat → Option Nat
  | [] => none
  | candidate :: candidates =>
      some (candidates.foldl (fun selected other =>
        if preferMostRecent then max selected other else min selected other)
        candidate)

def entriesAt (state : HistoryState) (positions : List Position) : List Nat :=
  (positions.filterMap state.entryAt).eraseDups

def previousFillCandidates (operations : List ParticleOperation)
    (state : HistoryState) (target : Position) : List Nat :=
  (List.range state.dependencies.length).filter fun operationOrder =>
    match operations[operationOrder]? with
    | some operation =>
        (operationPositions operation).any fun operatedPosition =>
          operatedPosition.isPrefixOf target
    | none => false

def fillCandidate (variant : RuleVariant) (operations : List ParticleOperation)
    (state : HistoryState) (target : Position) : Option Nat :=
  let positions :=
    if variant.fillParentPositions then nonemptyPrefixes target else [target]
  if variant.fillMostRecent then
    latestCandidate true (entriesAt state positions)
  else
    let candidates := previousFillCandidates operations state target
    match latestCandidate true candidates with
    | none => none
    | some newest =>
        match latestCandidate true (candidates.erase newest) with
        | some older => some older
        | none => some newest

def emptyCollectionPositions (variant : RuleVariant)
    (positions : List Position) (state : HistoryState)
    (source : Position) : List Position :=
  let parents :=
    if variant.emptyParentPositions then strictPrefixes source else []
  let children :=
    if variant.emptyChildPositions then
      positions.filter fun position =>
        position != source && source.isPrefixOf position &&
          state.positionAvailable position
    else
      []
  (source :: parents ++ children).eraseDups

def emptyCollection (variant : RuleVariant) (positions : List Position)
    (state : HistoryState) (source : Position) : List Nat :=
  entriesAt state (emptyCollectionPositions variant positions state source)

def operationsRelatedAt (operations : List ParticleOperation)
    (firstOrder secondOrder : Nat) : Bool :=
  match operations[firstOrder]?, operations[secondOrder]? with
  | some first, some second =>
      (operationPositions first).any fun firstPosition =>
        (operationPositions second).any fun secondPosition =>
          firstPosition.isPrefixOf secondPosition ||
            secondPosition.isPrefixOf firstPosition
  | _, _ => false

def HistoryState.reaches (state : HistoryState) (source target : Nat) : Bool :=
  match state.reachable[source]? with
  | some reachable => reachable.contains target
  | none => false

def simultaneousComparison (operations : List ParticleOperation)
    (candidates : List Nat) : List Nat :=
  candidates.filter fun candidate =>
    !candidates.any fun newerCandidate =>
      decide (candidate < newerCandidate) &&
        operationsRelatedAt operations newerCandidate candidate

def survivingComparisonAux (operations : List ParticleOperation) :
    Nat → List Nat → List Nat
  | 0, _ => []
  | _ + 1, [] => []
  | fuel + 1, candidates =>
      match latestCandidate true candidates with
      | none => []
      | some newest =>
          newest :: survivingComparisonAux operations fuel
            (candidates.filter fun candidate =>
              candidate != newest &&
                !operationsRelatedAt operations newest candidate)

def survivingComparison (operations : List ParticleOperation)
    (candidates : List Nat) : List Nat :=
  survivingComparisonAux operations candidates.length candidates

def compareCandidates (variant : RuleVariant)
    (operations : List ParticleOperation) (candidates : List Nat) : List Nat :=
  if variant.simultaneousComparison then
    simultaneousComparison operations candidates
  else
    survivingComparison operations candidates

def isMoveAt (operations : List ParticleOperation) (operationOrder : Nat) : Bool :=
  match operations[operationOrder]? with
  | some { kind := .move _ _, .. } => true
  | _ => false

def correctMoves (variant : RuleVariant) (operations : List ParticleOperation)
    (state : HistoryState) (candidates : List Nat) : List Nat :=
  if variant.moveCorrection then
    candidates.filter fun candidate =>
      !(isMoveAt operations candidate &&
        candidates.any fun otherCandidate =>
          otherCandidate != candidate && state.reaches otherCandidate candidate)
  else
    candidates

def ordinaryDependencies (variant : RuleVariant)
    (positions : List Position) (operations : List ParticleOperation)
    (state : HistoryState) (operation : ParticleOperation) : List Nat :=
  match operation.kind with
  | .create target =>
      match fillCandidate variant operations state target with
      | some candidate => [candidate]
      | none => []
  | .destroy target =>
      correctMoves variant operations state
        (compareCandidates variant operations
          (emptyCollection variant positions state target))
  | .move source target =>
      let sourceCandidates := emptyCollection variant positions state source
      let targetCandidate := fillCandidate variant operations state target
      let candidates :=
        match targetCandidate with
        | some candidate => (candidate :: sourceCandidates).eraseDups
        | none => sourceCandidates
      let corrected :=
        correctMoves variant operations state
          (compareCandidates variant operations candidates)
      if variant.fillDependencyRemoval then
        match targetCandidate with
        | none => corrected
        | some targetDependency =>
            if corrected.contains targetDependency &&
                corrected.any fun candidate =>
                  candidate != targetDependency &&
                    sourceCandidates.contains candidate &&
                    state.reaches candidate targetDependency then
              corrected.erase targetDependency
            else
              corrected
      else
        corrected

def actionParentCandidate (state : HistoryState)
    (operation : ParticleOperation) : Option Nat :=
  latestCandidate true (entriesAt state (nonemptyPrefixes operation.actionParent))

def finalDependencies (variant : RuleVariant) (positions : List Position)
    (operations : List ParticleOperation) (state : HistoryState)
    (operation : ParticleOperation) : List Nat :=
  let ordinary := ordinaryDependencies variant positions operations state operation
  match actionParentCandidate state operation with
  | none => ordinary
  | some candidate =>
      if variant.actionParentOnlyAsFallback then
        if ordinary.isEmpty then [candidate] else ordinary
      else
        (candidate :: ordinary).eraseDups

def HistoryState.updateOccupancy (state : HistoryState)
    (operation : ParticleOperation) : HistoryState :=
  match operation.kind with
  | .create target =>
      { state with occupied := target :: state.occupied }
  | .destroy target =>
      { state with
        occupied := state.occupied.filter fun position =>
          !target.isPrefixOf position }
  | .move source target =>
      let moved := state.occupied.filter source.isPrefixOf
      let unchanged := state.occupied.filter fun position =>
        !source.isPrefixOf position
      let renamed := moved.map fun position =>
        target ++ position.drop source.length
      { state with occupied := renamed ++ unchanged }

def HistoryState.updateEntries (state : HistoryState) (variant : RuleVariant)
    (positions : List Position) (operation : ParticleOperation) : HistoryState :=
  let operationOrder := operation.operationOrder
  match operation.kind with
  | .create target | .destroy target =>
      state.setEntry target operationOrder
  | .move source target =>
      let direct := (state.setEntry source operationOrder).setEntry target operationOrder
      let movablePositions :=
        (positions ++ state.entries.map Prod.fst ++ state.occupied).eraseDups
      let children := movablePositions.filter fun position =>
        position != source && source.isPrefixOf position &&
          state.positionAvailable position
      if variant.moveChildEntries then
        children.foldl (fun updated position =>
          updated.setEntry (target ++ position.drop source.length) operationOrder)
          direct
      else
        children.foldl (fun updated position =>
          match state.entryAt position with
          | some previousOperation =>
              updated.setEntry (target ++ position.drop source.length)
                previousOperation
          | none => updated) direct

def insertOperationOrder (operationOrder : Nat) : List Nat → List Nat
  | [] => [operationOrder]
  | first :: remaining =>
      if operationOrder ≤ first then
        operationOrder :: first :: remaining
      else
        first :: insertOperationOrder operationOrder remaining

def sortOperationOrders (operationOrders : List Nat) : List Nat :=
  operationOrders.foldl
    (fun sorted operationOrder => insertOperationOrder operationOrder sorted) []

def HistoryState.addDependencies (state : HistoryState)
    (dependencies : List Nat) : HistoryState :=
  let dependencies := sortOperationOrders dependencies
  let reachable :=
    (dependencies.flatMap fun dependency =>
      dependency :: (state.reachable[dependency]?.getD [])).eraseDups
  { state with
    dependencies := state.dependencies ++ [dependencies]
    reachable := state.reachable ++ [reachable] }

def calculateAux (variant : RuleVariant) (positions : List Position)
    (operations : List ParticleOperation) :
    Nat → List ParticleOperation → HistoryState → Option HistoryState
  | _, [], state => some state
  | operationOrder, operation :: remaining, state =>
      if operation.operationOrder != operationOrder ||
          !validOperation state operation then
        none
      else
        let dependencies :=
          finalDependencies variant positions operations state operation
        let updated :=
          ((state.addDependencies dependencies).updateEntries variant positions
            operation).updateOccupancy operation
        calculateAux variant positions operations (operationOrder + 1) remaining
          updated

def calculate (variant : RuleVariant)
    (operations : List ParticleOperation) : Option (List (List Nat)) := do
  let state ←
    calculateAux variant (knownPositions operations) operations 0 operations {}
  pure state.dependencies

def graphForDependency (operations : List ParticleOperation)
    (dependency : ParticleOperation → ParticleOperation → Bool) : List (List Nat) :=
  operations.map fun operation =>
    (List.range operations.length).filter fun dependencyOrder =>
      match operations[dependencyOrder]? with
      | some dependencyOperation => dependency operation dependencyOperation
      | none => false

/-!
## The Fill Rule's transitive parent positions

History: `create parent` then `create parent::child`.

Complete Fill Rule: filling the child position depends on the most recent
previous operation among the ones on that position *and its transitive parent
positions*; the Create of the parent position is on the chain, so the child
Create depends on it.

Weakened rule (the Fill Rule consults only the filled position itself): the
child position has no previous operation, so the child Create has no
dependency, and nothing orders it after the Create that its parent particle
comes from. The pair is related and previous but unreachable.
-/

namespace FillRuleParentPositions

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

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (_ _ : ParticleOperation) : Prop := False

def history : List ParticleOperation := [createParent, createChild]

def weakenedRules : RuleVariant :=
  { completeRules with fillParentPositions := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem required_ordering : RelatedPrevious createChild createParent :=
  ⟨moreRecent_of_order_lt (by decide),
    childPosition, parentPosition, rfl, rfl, Or.inr ⟨[0], rfl⟩⟩

example : Reaches CompleteDependency createChild createParent :=
  .direct (by decide)

theorem weakened_misses_required_ordering :
    ¬Reaches WeakenedDependency createChild createParent := by
  intro path
  cases path with
  | direct edge => exact edge
  | step edge _ => exact edge

end FillRuleParentPositions

/-!
## The Fill Rule's most recent selection

History: `create parent`, `create child`, `destroy child`, `create child`
again.

Complete Fill Rule: the second child Create depends on the single *most
recent* previous operation on the chain, the Destroy.

Weakened rule (select an older chain operation instead, here the first child
Create): the second Create never reaches the Destroy that emptied the
position for it, so nothing orders the refill after the Destroy.
-/

namespace FillRuleMostRecent

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

def recreateChild : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .create childPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = destroyChild then some createChild
    else if operation = recreateChild then some destroyChild
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

def weakenedDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = destroyChild then some createChild
    else if operation = recreateChild then some createChild
    else none

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  weakenedDependencyTarget operation = some dependencyOperation

def history : List ParticleOperation :=
  [createParent, createChild, destroyChild, recreateChild]

def weakenedRules : RuleVariant :=
  { completeRules with fillMostRecent := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem required_ordering : RelatedPrevious recreateChild destroyChild :=
  ⟨moreRecent_of_order_lt (by decide),
    childPosition, childPosition, rfl, rfl, related_refl childPosition⟩

example : Reaches CompleteDependency recreateChild destroyChild :=
  .direct (by decide)

theorem weakened_misses_required_ordering :
    ¬Reaches WeakenedDependency recreateChild destroyChild := by
  have from_create_parent :
      ∀ target, ¬Reaches WeakenedDependency createParent target := by
    intro target path
    have no_edge : weakenedDependencyTarget createParent = none := by decide
    cases path with
    | direct edge => exact nomatch (no_edge.symm.trans edge)
    | step edge _ => exact nomatch (no_edge.symm.trans edge)
  have from_create_child :
      ¬Reaches WeakenedDependency createChild destroyChild := by
    intro path
    have only_edge :
        weakenedDependencyTarget createChild = some createParent := by decide
    cases path with
    | direct edge =>
        exact
          absurd (Option.some.inj (edge.symm.trans only_edge)) (by decide)
    | @step _ next _ edge remaining_path =>
        have next_is_parent : next = createParent :=
          Option.some.inj (edge.symm.trans only_edge)
        subst next_is_parent
        exact from_create_parent destroyChild remaining_path
  intro path
  have only_edge :
      weakenedDependencyTarget recreateChild = some createChild := by decide
  cases path with
  | direct edge =>
      exact absurd (Option.some.inj (edge.symm.trans only_edge)) (by decide)
  | @step _ next _ edge remaining_path =>
      have next_is_create : next = createChild :=
        Option.some.inj (edge.symm.trans only_edge)
      subst next_is_create
      exact from_create_child remaining_path

end FillRuleMostRecent

/-!
## The Empty Rule's transitive child positions

History: `create parent`, `create child`, `destroy child`, `destroy parent`.

Complete Empty Rule: the Collection for the parent Destroy includes the most
recent previous operation on each transitive child position, the child
Destroy. The Comparison then excludes the parent Create in its favor, so the
parent Destroy depends exactly on the child Destroy.

Weakened rule (collect only the emptied position and its parent positions):
the parent Destroy sees only the parent Create and depends on it, so it never
reaches the child Destroy, and destroying the parent is not ordered after the
operation that emptied its child position.
-/

namespace EmptyRuleChildPositions

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

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = destroyChild then some createChild
    else if operation = destroyParent then some destroyChild
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

def weakenedDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = destroyChild then some createChild
    else if operation = destroyParent then some createParent
    else none

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  weakenedDependencyTarget operation = some dependencyOperation

def history : List ParticleOperation :=
  [createParent, createChild, destroyChild, destroyParent]

def weakenedRules : RuleVariant :=
  { completeRules with emptyChildPositions := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem required_ordering : RelatedPrevious destroyParent destroyChild :=
  ⟨moreRecent_of_order_lt (by decide),
    parentPosition, childPosition, rfl, rfl, Or.inl ⟨[0], rfl⟩⟩

example : Reaches CompleteDependency destroyParent destroyChild :=
  .direct (by decide)

theorem weakened_misses_required_ordering :
    ¬Reaches WeakenedDependency destroyParent destroyChild := by
  have from_create_parent :
      ∀ target, ¬Reaches WeakenedDependency createParent target := by
    intro target path
    have no_edge : weakenedDependencyTarget createParent = none := by decide
    cases path with
    | direct edge => exact nomatch (no_edge.symm.trans edge)
    | step edge _ => exact nomatch (no_edge.symm.trans edge)
  intro path
  have only_edge :
      weakenedDependencyTarget destroyParent = some createParent := by decide
  cases path with
  | direct edge =>
      exact absurd (Option.some.inj (edge.symm.trans only_edge)) (by decide)
  | @step _ next _ edge remaining_path =>
      have next_is_parent : next = createParent :=
        Option.some.inj (edge.symm.trans only_edge)
      subst next_is_parent
      exact from_create_parent destroyChild remaining_path

end EmptyRuleChildPositions

/-!
## The Move as an operation on the moved particle's transitive child positions

History: `create box`, `create box::item`, `move box holder_a`,
`move holder_a holder_b`, `destroy holder_b::item`. This is the history of
`test_move_excludes_create_on_child_reached_through_parent_move_chain`.

Complete Empty Rule: each Move is also a Particle Operation on the moved
particle's transitive child positions, so the entry for the item's position is
the latest parent Move, and the item Destroy depends exactly on it.

Weakened rule (a Move is an operation only on its source and target
positions): the entry for the item remains the original Create under its
first name, whose position is unrelated to the Moves' positions, so the
Comparison cannot exclude it and the Destroy keeps a second dependency on the
Create. That edge is redundant: the Move chain already reaches the Create.
-/

namespace MoveChildEntries

def boxPosition : Position := [0]

def itemPosition : Position := [0, 0]

def holderAPosition : Position := [1]

def holderBPosition : Position := [2]

def movedItemPosition : Position := [2, 0]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createItem : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create itemPosition

def moveBoxToHolderA : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move boxPosition holderAPosition

def moveHolderAToHolderB : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move holderAPosition holderBPosition

def destroyMovedItem : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .destroy movedItemPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createItem then some createBox
    else if operation = moveBoxToHolderA then some createItem
    else if operation = moveHolderAToHolderB then some moveBoxToHolderA
    else if operation = destroyMovedItem then some moveHolderAToHolderB
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = destroyMovedItem ∧ dependencyOperation = createItem)

def history : List ParticleOperation :=
  [createBox, createItem, moveBoxToHolderA, moveHolderAToHolderB,
    destroyMovedItem]

def weakenedRules : RuleVariant :=
  { completeRules with moveChildEntries := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency destroyMovedItem createItem
        destroyMovedItem moveHolderAToHolderB :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency destroyMovedItem createItem
        moveHolderAToHolderB moveBoxToHolderA :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency destroyMovedItem createItem
        moveBoxToHolderA createItem :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal destroyMovedItem createItem (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.step edge_1 (.direct edge_2)))

end MoveChildEntries

/-!
## The Comparison's simultaneity

History: `create parent`, `create childA`, `create childA::x`,
`destroy childA::x`, `destroy childA`, `create childA` again,
`create childA::y`, `destroy childA::y`, `destroy childA` again.

Complete Comparison at the final childA Destroy: the Collection holds the
entries for `parent` (its Create), `childA` (the second Create), `childA::x`
(its Destroy), and `childA::y` (its Destroy). The `childA::y` Destroy excludes
the `childA` Create, and the `childA` Create — although itself excluded — still
excludes the `childA::x` Destroy, whose position is unrelated to
`childA::y`. Only the `childA::y` Destroy remains.

Weakened rule (only surviving candidates exclude): the `childA::x` Destroy's
only excluder is itself excluded, so the Destroy survives, and the final
childA Destroy keeps a second dependency on it. That edge is redundant: the
`childA::y` Destroy's chain already reaches the `childA::x` Destroy.
-/

namespace ComparisonSimultaneity

def parentPosition : Position := [0]

def childAPosition : Position := [0, 0]

def grandChildXPosition : Position := [0, 0, 0]

def grandChildYPosition : Position := [0, 0, 1]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create parentPosition

def createChildA : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create childAPosition

def createGrandChildX : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .create grandChildXPosition

def destroyGrandChildX : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .destroy grandChildXPosition

def destroyChildA : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .destroy childAPosition

def recreateChildA : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .create childAPosition

def createGrandChildY : ParticleOperation where
  operationOrder := 6
  actionParent := []
  kind := .create grandChildYPosition

def destroyGrandChildY : ParticleOperation where
  operationOrder := 7
  actionParent := []
  kind := .destroy grandChildYPosition

def destroyRecreatedChildA : ParticleOperation where
  operationOrder := 8
  actionParent := []
  kind := .destroy childAPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChildA then some createParent
    else if operation = createGrandChildX then some createChildA
    else if operation = destroyGrandChildX then some createGrandChildX
    else if operation = destroyChildA then some destroyGrandChildX
    else if operation = recreateChildA then some destroyChildA
    else if operation = createGrandChildY then some recreateChildA
    else if operation = destroyGrandChildY then some createGrandChildY
    else if operation = destroyRecreatedChildA then some destroyGrandChildY
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = destroyRecreatedChildA ∧
      dependencyOperation = destroyGrandChildX)

def history : List ParticleOperation :=
  [createParent, createChildA, createGrandChildX, destroyGrandChildX,
    destroyChildA, recreateChildA, createGrandChildY, destroyGrandChildY,
    destroyRecreatedChildA]

def weakenedRules : RuleVariant :=
  { completeRules with simultaneousComparison := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency destroyRecreatedChildA destroyGrandChildX
        destroyRecreatedChildA destroyGrandChildY :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency destroyRecreatedChildA destroyGrandChildX
        destroyGrandChildY createGrandChildY :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency destroyRecreatedChildA destroyGrandChildX
        createGrandChildY recreateChildA :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_3 :
      WithoutEdge WeakenedDependency destroyRecreatedChildA destroyGrandChildX
        recreateChildA destroyChildA :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_4 :
      WithoutEdge WeakenedDependency destroyRecreatedChildA destroyGrandChildX
        destroyChildA destroyGrandChildX :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal destroyRecreatedChildA destroyGrandChildX (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0
        (.step edge_1 (.step edge_2 (.step edge_3 (.direct edge_4)))))

end ComparisonSimultaneity

/-!
## The Move Correction

History: `create box`, `create box::origin`, `move box::origin holder_a`,
`move holder_a box::middle`, `move box::middle box::target`,
`move box::target holder_c`, `destroy box`. This is the history of
`test_destroy_excludes_earlier_child_move_reached_through_later_child_move`.

Complete Empty Rule at the box Destroy: after the Comparison, the remaining
candidates are the final Move (entry for `box::target`) and the first Move
(entry for `box::origin`, whose positions are unrelated to the final Move's
positions). The first Move is a Move Particle Statement that the final Move
depends on through the chain, so the Move Correction removes it and the
Destroy depends exactly on the final Move.

Weakened rule (no Move Correction): the Destroy keeps a second dependency on
the first Move. That edge is redundant: the final Move's chain already
reaches the first Move.
-/

namespace MoveCorrection

def boxPosition : Position := [0]

def originPosition : Position := [0, 0]

def middlePosition : Position := [0, 1]

def targetPosition : Position := [0, 2]

def holderAPosition : Position := [1]

def holderCPosition : Position := [2]

def createBox : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create boxPosition

def createOrigin : ParticleOperation where
  operationOrder := 1
  actionParent := []
  kind := .create originPosition

def moveOriginToHolderA : ParticleOperation where
  operationOrder := 2
  actionParent := []
  kind := .move originPosition holderAPosition

def moveHolderAToMiddle : ParticleOperation where
  operationOrder := 3
  actionParent := []
  kind := .move holderAPosition middlePosition

def moveMiddleToTarget : ParticleOperation where
  operationOrder := 4
  actionParent := []
  kind := .move middlePosition targetPosition

def moveTargetToHolderC : ParticleOperation where
  operationOrder := 5
  actionParent := []
  kind := .move targetPosition holderCPosition

def destroyBox : ParticleOperation where
  operationOrder := 6
  actionParent := []
  kind := .destroy boxPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createOrigin then some createBox
    else if operation = moveOriginToHolderA then some createOrigin
    else if operation = moveHolderAToMiddle then some moveOriginToHolderA
    else if operation = moveMiddleToTarget then some moveHolderAToMiddle
    else if operation = moveTargetToHolderC then some moveMiddleToTarget
    else if operation = destroyBox then some moveTargetToHolderC
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = destroyBox ∧ dependencyOperation = moveOriginToHolderA)

def history : List ParticleOperation :=
  [createBox, createOrigin, moveOriginToHolderA, moveHolderAToMiddle,
    moveMiddleToTarget, moveTargetToHolderC, destroyBox]

def weakenedRules : RuleVariant :=
  { completeRules with moveCorrection := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        destroyBox moveTargetToHolderC :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveTargetToHolderC moveMiddleToTarget :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveMiddleToTarget moveHolderAToMiddle :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_3 :
      WithoutEdge WeakenedDependency destroyBox moveOriginToHolderA
        moveHolderAToMiddle moveOriginToHolderA :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal destroyBox moveOriginToHolderA (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.step edge_1 (.step edge_2 (.direct edge_3))))

end MoveCorrection

/-!
## The Move Rule's Fill Dependency removal

History: `create box`, `create box::item`, `create holder`,
`move box::item holder::pay`, `create box::item` again,
`move box::item holder::deposit`. This is the history of
`test_move_excludes_create_fill_dependency_reached_through_source_dependency`.

Complete Move Rule at the final Move: the Empty Dependencies leave the
second item Create; the Fill Dependency for `holder::deposit` is the holder
Create. Their positions are unrelated, so the Comparison keeps both, and
neither is a Move, so the Move Correction keeps both. The second item Create
depends on the holder Create through the first Move, so the Move Rule removes
the Fill Dependency and the final Move depends exactly on the second item
Create.

Weakened rule (no Fill Dependency removal): the final Move keeps a second
dependency on the holder Create. That edge is redundant: the second item
Create's chain already reaches the holder Create.
-/

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

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  (operation = createItem ∧ dependencyOperation = createBox) ∨
    (operation = moveItemToPay ∧ dependencyOperation = createItem) ∨
    (operation = moveItemToPay ∧ dependencyOperation = createHolder) ∨
    (operation = createSecondItem ∧ dependencyOperation = moveItemToPay) ∨
    (operation = moveSecondToDeposit ∧
      dependencyOperation = createSecondItem)

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = moveSecondToDeposit ∧ dependencyOperation = createHolder)

def history : List ParticleOperation :=
  [createBox, createItem, createHolder, moveItemToPay, createSecondItem,
    moveSecondToDeposit]

def weakenedRules : RuleVariant :=
  { completeRules with fillDependencyRemoval := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency := by
  exact Define.OperationGraph.FillDependencyRemoval.graph.transitivelyMinimal

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        moveSecondToDeposit createSecondItem :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        createSecondItem moveItemToPay :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_2 :
      WithoutEdge WeakenedDependency moveSecondToDeposit createHolder
        moveItemToPay createHolder :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal moveSecondToDeposit createHolder (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.step edge_1 (.direct edge_2)))

end FillDependencyRemoval

/-!
## The Action Parent Rule only as a fallback

History: `create parent`, `create parent::child`, `create
parent::child::grandChild`, all within an action whose parent position is
`parent`.

Complete rules: each Create depends on the most recent previous operation on
its chain, and because those dependencies exist, the Action Parent Rule does
not apply.

Weakened rule (the Action Parent Rule applies to every operation instead of
only when the other rules identify no dependency): the grandchild Create
gains a second dependency on the parent Create, the most recent previous
operation on the action's parent position. That edge is redundant: the child
Create already reaches the parent Create.

Removing the Action Parent Rule entirely has no witness at this level; see
`CompleteResolvedDefineGraph.dependency_isOrdinary`.
-/

namespace ActionParentOnlyAsFallback

def parentPosition : Position := [0]

def childPosition : Position := [0, 0]

def grandChildPosition : Position := [0, 0, 0]

def createParent : ParticleOperation where
  operationOrder := 0
  actionParent := []
  kind := .create parentPosition

def createChild : ParticleOperation where
  operationOrder := 1
  actionParent := parentPosition
  kind := .create childPosition

def createGrandChild : ParticleOperation where
  operationOrder := 2
  actionParent := parentPosition
  kind := .create grandChildPosition

def completeDependencyTarget : ParticleOperation → Option ParticleOperation :=
  fun operation =>
    if operation = createChild then some createParent
    else if operation = createGrandChild then some createChild
    else none

abbrev CompleteDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  completeDependencyTarget operation = some dependencyOperation

abbrev WeakenedDependency (operation dependencyOperation : ParticleOperation) :
    Prop :=
  CompleteDependency operation dependencyOperation ∨
    (operation = createGrandChild ∧ dependencyOperation = createParent)

def history : List ParticleOperation :=
  [createParent, createChild, createGrandChild]

def weakenedRules : RuleVariant :=
  { completeRules with actionParentOnlyAsFallback := false }

theorem complete_rules_derive_graph :
    calculate completeRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (CompleteDependency operation dependencyOperation)) := by
  decide

theorem weakened_rules_derive_graph :
    calculate weakenedRules history =
      some (graphForDependency history fun operation dependencyOperation =>
        decide (WeakenedDependency operation dependencyOperation)) := by
  decide

theorem complete_transitively_minimal :
    TransitivelyMinimal CompleteDependency :=
  transitivelyMinimal_of_at_most_one_dependency CompleteDependency
    fun _ _ _ first_edge second_edge =>
      Option.some.inj (first_edge.symm.trans second_edge)

theorem weakened_not_transitively_minimal :
    ¬TransitivelyMinimal WeakenedDependency := by
  intro minimal
  have edge_0 :
      WithoutEdge WeakenedDependency createGrandChild createParent
        createGrandChild createChild :=
    ⟨Or.inl (by decide), by decide⟩
  have edge_1 :
      WithoutEdge WeakenedDependency createGrandChild createParent
        createChild createParent :=
    ⟨Or.inl (by decide), by decide⟩
  exact
    minimal createGrandChild createParent (Or.inr ⟨rfl, rfl⟩)
      (.step edge_0 (.direct edge_1))

end ActionParentOnlyAsFallback

end IndependenceWitnesses

end Define.OperationGraph
