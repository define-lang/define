import definitions

set_option warningAsError true
set_option autoImplicit false

/-!
# Independence Witness Support

This module contains the executable rule-variant evaluator used by concrete
independence witnesses and the general lemmas shared by those witnesses. It
contains no concrete history.

Migrated witnesses use the universal operation graph calculation for their
complete side. The evaluator here calculates only their deliberately changed
variant. During the incremental migration it also continues to calculate both
sides of the remaining older witnesses.
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

def prefixes (position : Position) : List Position :=
  [] :: nonemptyPrefixes position

def strictPrefixes (position : Position) : List Position :=
  (prefixes position).filter fun namePrefix => namePrefix != position

def knownPositions (operations : List ParticleOperation) : List Position :=
  (operations.flatMap fun operation =>
    (operationPositions operation).flatMap prefixes).eraseDups

structure HistoryState where
  entries : List (Position × Nat) := []
  occupied : List Position := [[]]
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
    if variant.fillParentPositions then prefixes target else [target]
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

def dependenciesForOperation (variant : RuleVariant)
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

def finalDependencies (variant : RuleVariant) (positions : List Position)
    (operations : List ParticleOperation) (state : HistoryState)
    (operation : ParticleOperation) : List Nat :=
  dependenciesForOperation variant positions operations state operation

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

end IndependenceWitnesses

end Define.OperationGraph
