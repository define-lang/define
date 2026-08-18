import Std

set_option warningAsError true
set_option autoImplicit false

/-!
# Shared Operation Graph Definitions

This module formalizes the definitions in `definitions.md`: resolved positions,
Particle Operation occurrences, position relationships, previous-operation
ranks, occupancy transitions, dependency reachability, acyclicity, and
transitive minimality.

It assumes no Fill, Empty, or Move Rule and no finite vertex type.
Natural-number operation ranks make the predecessors of any particular
occurrence locally finite without requiring the complete history to stop.
-/

namespace Define.OperationGraph

universe u v

abbrev Position := List Nat

def ParentOrSame (parent child : Position) : Prop :=
  parent <+: child

def Related (first second : Position) : Prop :=
  ParentOrSame first second ∨ ParentOrSame second first

def PrefixClosed (occupied : Position → Prop) : Prop :=
  ∀ parent child, ParentOrSame parent child → occupied child → occupied parent

def Available (occupied : Position → Prop) (position : Position) : Prop :=
  ∀ parent,
    ParentOrSame parent position → parent ≠ position → occupied parent

theorem related_symm {first second : Position} :
    Related first second → Related second first := by
  intro related
  exact related.elim Or.inr Or.inl

theorem related_refl (position : Position) : Related position position :=
  Or.inl List.prefix_rfl

theorem related_of_parentOrSame_of_parentOrSame
    {first second sharedChild : Position}
    (first_parent : ParentOrSame first sharedChild)
    (second_parent : ParentOrSame second sharedChild) :
    Related first second :=
  List.prefix_or_prefix_of_prefix first_parent second_parent

theorem parentOrSame_antisymm {first second : Position}
    (first_parent : ParentOrSame first second)
    (second_parent : ParentOrSame second first) : first = second :=
  first_parent.eq_of_length_le second_parent.length_le

theorem related_to_child_is_related_to_parent {parent child other : Position}
    (parent_of_child : ParentOrSame parent child)
    (other_related_to_child : Related other child) :
    Related other parent := by
  rcases other_related_to_child with other_prefix | child_prefix
  · rcases List.prefix_or_prefix_of_prefix other_prefix parent_of_child with
      other_parent | parent_other
    · exact Or.inl other_parent
    · exact Or.inr parent_other
  · exact Or.inr (parent_of_child.trans child_prefix)

theorem parent_of_related_is_related {position relatedPosition parent : Position}
    (parent_of_position : ParentOrSame parent position)
    (positions_related : Related position relatedPosition) :
    Related parent relatedPosition := by
  rcases positions_related with position_prefix | related_prefix
  · exact Or.inl (parent_of_position.trans position_prefix)
  · rcases List.prefix_or_prefix_of_prefix parent_of_position related_prefix with
      parent_related | related_parent
    · exact Or.inl parent_related
    · exact Or.inr related_parent

theorem parent_of_position_related_to_child_is_related_to_parent
    {parent child position positionParent : Position}
    (parent_of_child : ParentOrSame parent child)
    (position_related_to_child : Related position child)
    (parent_of_position : ParentOrSame positionParent position) :
    Related positionParent parent := by
  apply related_to_child_is_related_to_parent parent_of_child
  exact parent_of_related_is_related parent_of_position position_related_to_child

inductive ParticleOperationKind where
  | create (target : Position)
  | destroy (target : Position)
  | move (source target : Position)
  deriving DecidableEq, Repr

structure ParticleOperation where
  operationOrder : Nat
  actionParent : Position
  kind : ParticleOperationKind
  deriving DecidableEq, Repr

def OperatesOn (operation : ParticleOperation) (position : Position) : Prop :=
  match operation.kind with
  | .create target | .destroy target => position = target
  | .move source target => position = source ∨ position = target

def OperationsRelated (first second : ParticleOperation) : Prop :=
  ∃ firstPosition secondPosition,
    OperatesOn first firstPosition ∧
      OperatesOn second secondPosition ∧
      Related firstPosition secondPosition

theorem operationsRelated_symm {first second : ParticleOperation} :
    OperationsRelated first second → OperationsRelated second first := by
  rintro ⟨firstPosition, secondPosition, first_operates, second_operates,
    positions_related⟩
  exact ⟨secondPosition, firstPosition, second_operates, first_operates,
    related_symm positions_related⟩

def MoreRecent (newer older : ParticleOperation) : Prop :=
  older.operationOrder < newer.operationOrder

/--
The rule-independent related-and-previous relation, written `R` in the English
proofs.
-/
def RelatedPrevious (operation previousOperation : ParticleOperation) : Prop :=
  MoreRecent operation previousOperation ∧
    OperationsRelated operation previousOperation

def IsMove (operation : ParticleOperation) : Prop :=
  ∃ source target, operation.kind = .move source target

def IsCreateOrDestroy (operation : ParticleOperation) : Prop :=
  (∃ target, operation.kind = .create target) ∨
    ∃ target, operation.kind = .destroy target

def EmptyPosition (operation : ParticleOperation) : Option Position :=
  match operation.kind with
  | .create _ => none
  | .destroy target | .move target _ => some target

def FillPosition (operation : ParticleOperation) : Option Position :=
  match operation.kind with
  | .create target | .move _ target => some target
  | .destroy _ => none

theorem operatesOn_emptyPosition {operation : ParticleOperation}
    {position : Position} (empty_position : EmptyPosition operation = some position) :
    OperatesOn operation position := by
  cases operation_kind : operation.kind <;>
    simp [EmptyPosition, operation_kind] at empty_position
  · simp [OperatesOn, operation_kind, empty_position]
  · simp [OperatesOn, operation_kind, empty_position]

theorem operatesOn_fillPosition {operation : ParticleOperation}
    {position : Position} (fill_position : FillPosition operation = some position) :
    OperatesOn operation position := by
  cases operation_kind : operation.kind <;>
    simp [FillPosition, operation_kind] at fill_position
  · simp [OperatesOn, operation_kind, fill_position]
  · simp [OperatesOn, operation_kind, fill_position]

theorem exists_operated_position (operation : ParticleOperation) :
    ∃ position, OperatesOn operation position := by
  cases operation_kind : operation.kind with
  | create target | destroy target =>
      exact ⟨target, by simp [OperatesOn, operation_kind]⟩
  | move source target =>
      exact ⟨source, by simp [OperatesOn, operation_kind]⟩

theorem operated_position_unique_of_not_move {operation : ParticleOperation}
    (not_move : ¬IsMove operation) {first second : Position}
    (operates_on_first : OperatesOn operation first)
    (operates_on_second : OperatesOn operation second) :
    first = second := by
  cases operation_kind : operation.kind with
  | create target =>
      have first_is_target : first = target := by
        simpa [OperatesOn, operation_kind] using operates_on_first
      have second_is_target : second = target := by
        simpa [OperatesOn, operation_kind] using operates_on_second
      exact first_is_target.trans second_is_target.symm
  | destroy target =>
      have first_is_target : first = target := by
        simpa [OperatesOn, operation_kind] using operates_on_first
      have second_is_target : second = target := by
        simpa [OperatesOn, operation_kind] using operates_on_second
      exact first_is_target.trans second_is_target.symm
  | move source target =>
      exact False.elim (not_move ⟨source, target, operation_kind⟩)

def resolvePosition (callerPrefix relativePosition : Position) : Position :=
  callerPrefix ++ relativePosition

def ParticleOperationKind.resolve (callerPrefix : Position) :
    ParticleOperationKind → ParticleOperationKind
  | .create target => .create (resolvePosition callerPrefix target)
  | .destroy target => .destroy (resolvePosition callerPrefix target)
  | .move source target =>
      .move (resolvePosition callerPrefix source)
        (resolvePosition callerPrefix target)

def ParticleOperation.resolve (callerPrefix : Position)
    (operation : ParticleOperation) : ParticleOperation where
  operationOrder := operation.operationOrder
  actionParent := resolvePosition callerPrefix operation.actionParent
  kind := operation.kind.resolve callerPrefix

theorem resolvePosition_injective (callerPrefix : Position) :
    Function.Injective (resolvePosition callerPrefix) := by
  intro first second positions_equal
  exact List.append_cancel_left positions_equal

theorem ParticleOperationKind.resolve_injective (callerPrefix : Position) :
    Function.Injective (ParticleOperationKind.resolve callerPrefix) := by
  intro first second kinds_equal
  cases first <;> cases second <;>
    simp [ParticleOperationKind.resolve, resolvePosition] at kinds_equal
  all_goals simp_all

theorem ParticleOperation.resolve_injective (callerPrefix : Position) :
    Function.Injective (ParticleOperation.resolve callerPrefix) := by
  rintro ⟨firstOrder, firstActionParent, firstKind⟩
    ⟨secondOrder, secondActionParent, secondKind⟩ operations_equal
  simp only [ParticleOperation.resolve, ParticleOperation.mk.injEq] at operations_equal
  rcases operations_equal with ⟨orders_equal, action_parents_equal, kinds_equal⟩
  have original_action_parents_equal :=
    resolvePosition_injective callerPrefix action_parents_equal
  have original_kinds_equal :=
    ParticleOperationKind.resolve_injective callerPrefix kinds_equal
  cases orders_equal
  cases original_action_parents_equal
  cases original_kinds_equal
  rfl

theorem parentOrSame_resolve_iff {callerPrefix first second : Position} :
    ParentOrSame (resolvePosition callerPrefix first)
        (resolvePosition callerPrefix second) ↔
      ParentOrSame first second := by
  simp [ParentOrSame, resolvePosition]

theorem related_resolve_iff {callerPrefix first second : Position} :
    Related (resolvePosition callerPrefix first)
        (resolvePosition callerPrefix second) ↔
      Related first second := by
  simp [Related, parentOrSame_resolve_iff]

theorem operatesOn_resolve_iff {callerPrefix position : Position}
    {operation : ParticleOperation} :
    OperatesOn (operation.resolve callerPrefix)
        (resolvePosition callerPrefix position) ↔
      OperatesOn operation position := by
  cases operation_kind : operation.kind <;>
    simp [OperatesOn, ParticleOperation.resolve, ParticleOperationKind.resolve,
      resolvePosition, operation_kind]

theorem operationsRelated_resolve_iff {callerPrefix : Position}
    {first second : ParticleOperation} :
    OperationsRelated (first.resolve callerPrefix) (second.resolve callerPrefix) ↔
      OperationsRelated first second := by
  constructor
  · rintro ⟨resolvedFirstPosition, resolvedSecondPosition, first_operates,
      second_operates, positions_related⟩
    cases first_kind : first.kind <;> cases second_kind : second.kind <;>
      simp [OperatesOn, ParticleOperation.resolve, ParticleOperationKind.resolve,
        first_kind, second_kind] at first_operates second_operates
    all_goals
      rcases first_operates with first_position | first_position <;>
        rcases second_operates with second_position | second_position <;>
          subst_vars <;>
          exact
            ⟨_, _, by simp [OperatesOn, first_kind], by simp [OperatesOn, second_kind],
              related_resolve_iff.mp positions_related⟩
  · rintro ⟨firstPosition, secondPosition, first_operates, second_operates,
      positions_related⟩
    exact
      ⟨resolvePosition callerPrefix firstPosition,
        resolvePosition callerPrefix secondPosition,
        operatesOn_resolve_iff.mpr first_operates,
        operatesOn_resolve_iff.mpr second_operates,
        related_resolve_iff.mpr positions_related⟩

theorem moreRecent_resolve_iff {callerPrefix : Position}
    {newer older : ParticleOperation} :
    MoreRecent (newer.resolve callerPrefix) (older.resolve callerPrefix) ↔
      MoreRecent newer older :=
  Iff.rfl

theorem positionComparison_resolve_iff {callerPrefix : Position}
    {moreRecent lessRecent : ParticleOperation} :
    (MoreRecent (moreRecent.resolve callerPrefix)
          (lessRecent.resolve callerPrefix) ∧
        OperationsRelated (moreRecent.resolve callerPrefix)
          (lessRecent.resolve callerPrefix)) ↔
      (MoreRecent moreRecent lessRecent ∧
        OperationsRelated moreRecent lessRecent) := by
  simp [moreRecent_resolve_iff, operationsRelated_resolve_iff]

theorem isMove_resolve_iff {callerPrefix : Position}
    {operation : ParticleOperation} :
    IsMove (operation.resolve callerPrefix) ↔ IsMove operation := by
  cases operation_kind : operation.kind <;>
    simp [IsMove, ParticleOperation.resolve, ParticleOperationKind.resolve,
      operation_kind]

theorem isCreateOrDestroy_resolve_iff {callerPrefix : Position}
    {operation : ParticleOperation} :
    IsCreateOrDestroy (operation.resolve callerPrefix) ↔
      IsCreateOrDestroy operation := by
  cases operation_kind : operation.kind <;>
    simp [IsCreateOrDestroy, ParticleOperation.resolve,
      ParticleOperationKind.resolve, operation_kind]

theorem emptyPosition_resolve {callerPrefix : Position}
    {operation : ParticleOperation} :
    EmptyPosition (operation.resolve callerPrefix) =
      (EmptyPosition operation).map (resolvePosition callerPrefix) := by
  cases operation_kind : operation.kind <;>
    simp [EmptyPosition, ParticleOperation.resolve, ParticleOperationKind.resolve,
      operation_kind]

theorem fillPosition_resolve {callerPrefix : Position}
    {operation : ParticleOperation} :
    FillPosition (operation.resolve callerPrefix) =
      (FillPosition operation).map (resolvePosition callerPrefix) := by
  cases operation_kind : operation.kind <;>
    simp [FillPosition, ParticleOperation.resolve, ParticleOperationKind.resolve,
      operation_kind]

inductive Reaches {Vertex : Type u} (dependency : Vertex → Vertex → Prop) :
    Vertex → Vertex → Prop where
  | direct {source target} :
      dependency source target → Reaches dependency source target
  | step {source next target} :
      dependency source next →
      Reaches dependency next target →
      Reaches dependency source target

namespace Reaches

theorem trans {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    {first second third : Vertex} :
    Define.OperationGraph.Reaches dependency first second →
    Define.OperationGraph.Reaches dependency second third →
    Define.OperationGraph.Reaches dependency first third := by
  intro first_path second_path
  induction first_path with
  | direct dependency_edge =>
      exact .step dependency_edge second_path
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step dependency_edge (induction_hypothesis second_path)

theorem mono {Vertex : Type u} {narrow wide : Vertex → Vertex → Prop}
    (includes : ∀ source target, narrow source target → wide source target)
    {source target : Vertex} :
    Define.OperationGraph.Reaches narrow source target →
    Define.OperationGraph.Reaches wide source target := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact .direct (includes _ _ dependency_edge)
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step (includes _ _ dependency_edge) induction_hypothesis

theorem map {Source : Type u} {Target : Type v}
    {sourceDependency : Source → Source → Prop}
    {targetDependency : Target → Target → Prop}
    (resolve : Source → Target)
    (resolve_edge :
      ∀ source target,
        sourceDependency source target →
          targetDependency (resolve source) (resolve target))
    {source target : Source} :
    Define.OperationGraph.Reaches sourceDependency source target →
      Define.OperationGraph.Reaches targetDependency (resolve source)
        (resolve target) := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact .direct (resolve_edge _ _ dependency_edge)
  | step dependency_edge remaining_path induction_hypothesis =>
      exact .step (resolve_edge _ _ dependency_edge) induction_hypothesis

def OrEq {Vertex : Type u} (dependency : Vertex → Vertex → Prop)
    (source target : Vertex) : Prop :=
  source = target ∨ Define.OperationGraph.Reaches dependency source target

theorem prepend_orEq {Vertex : Type u}
    {dependency : Vertex → Vertex → Prop} {source next target : Vertex}
    (first_edge : dependency source next) :
    OrEq dependency next target → OrEq dependency source target := by
  intro remaining_path
  rcases remaining_path with next_is_target | remaining_path
  · subst next_is_target
    exact Or.inr (.direct first_edge)
  · exact Or.inr (.step first_edge remaining_path)

theorem last_edge {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    {source target : Vertex} :
    Define.OperationGraph.Reaches dependency source target →
    ∃ beforeTarget,
      OrEq dependency source beforeTarget ∧ dependency beforeTarget target := by
  intro path
  induction path with
  | @direct source target dependency_edge =>
      exact ⟨source, Or.inl rfl, dependency_edge⟩
  | step first_edge _ induction_hypothesis =>
      rcases induction_hypothesis with ⟨beforeTarget, path_to_before, final_edge⟩
      exact ⟨beforeTarget, prepend_orEq first_edge path_to_before, final_edge⟩

end Reaches

theorem reaches_resolve {callerPrefix : Position}
    {localDependency resolvedDependency :
      ParticleOperation → ParticleOperation → Prop}
    (resolve_edge :
      ∀ source target,
        localDependency source target →
          resolvedDependency (source.resolve callerPrefix)
            (target.resolve callerPrefix))
    {source target : ParticleOperation} :
    Reaches localDependency source target →
      Reaches resolvedDependency (source.resolve callerPrefix)
        (target.resolve callerPrefix) :=
  Reaches.map (ParticleOperation.resolve callerPrefix) resolve_edge

def WithoutEdge {Vertex : Type u} (dependency : Vertex → Vertex → Prop)
    (removed_source removed_target : Vertex) : Vertex → Vertex → Prop :=
  fun source target =>
    dependency source target ∧
      ¬(source = removed_source ∧ target = removed_target)

def TransitivelyMinimal {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ source target,
    dependency source target →
    ¬Reaches (WithoutEdge dependency source target) source target

def DirectDependenciesAreAntichains {Vertex : Type u}
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation newer older,
    dependency operation newer →
    dependency operation older →
    newer ≠ older →
    ¬Reaches dependency newer older

theorem transitivelyMinimal_of_directDependenciesAreAntichains
    {Vertex : Type u} {dependency : Vertex → Vertex → Prop}
    (antichains : DirectDependenciesAreAntichains dependency) :
    TransitivelyMinimal dependency := by
  intro source target direct_dependency alternate_path
  cases alternate_path with
  | direct remaining_edge =>
      exact remaining_edge.2 ⟨rfl, rfl⟩
  | step first_edge remaining_path =>
      rename_i next
      have next_is_distinct : next ≠ target := by
        intro next_is_target
        exact first_edge.2 ⟨rfl, next_is_target⟩
      have original_remaining_path : Reaches dependency next target :=
        Reaches.mono (fun _ _ edge => edge.1) remaining_path
      exact
        antichains source next target first_edge.1 direct_dependency
          next_is_distinct original_remaining_path

def PointsBackward {Vertex : Type u} (operationOrder : Vertex → Nat)
    (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation dependencyOperation,
    dependency operation dependencyOperation →
    operationOrder dependencyOperation < operationOrder operation

theorem reaches_decreases_order {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency)
    {source target : Vertex} :
    Reaches dependency source target →
    operationOrder target < operationOrder source := by
  intro path
  induction path with
  | direct dependency_edge =>
      exact points_backward _ _ dependency_edge
  | step dependency_edge _ induction_hypothesis =>
      exact Nat.lt_trans induction_hypothesis (points_backward _ _ dependency_edge)

def Acyclic {Vertex : Type u} (dependency : Vertex → Vertex → Prop) : Prop :=
  ∀ operation, ¬Reaches dependency operation operation

theorem acyclic_of_pointsBackward {Vertex : Type u}
    {operationOrder : Vertex → Nat} {dependency : Vertex → Vertex → Prop}
    (points_backward : PointsBackward operationOrder dependency) :
    Acyclic dependency := by
  intro operation cycle
  have decreases := reaches_decreases_order points_backward cycle
  exact Nat.lt_irrefl _ decreases

def OccupancyAfter (operation : ParticleOperation)
    (occupiedBefore : Position → Prop) (position : Position) : Prop :=
  match operation.kind with
  | .create target => position = target ∨ occupiedBefore position
  | .destroy target => ¬ParentOrSame target position ∧ occupiedBefore position
  | .move source target =>
      (∃ relativePosition,
        position = target ++ relativePosition ∧
          occupiedBefore (source ++ relativePosition)) ∨
        (¬ParentOrSame source position ∧
          ¬ParentOrSame target position ∧
          occupiedBefore position)

end Define.OperationGraph
