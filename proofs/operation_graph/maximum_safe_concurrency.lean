import characterization

set_option warningAsError true
set_option autoImplicit false

/-!
# Commutation of Unrelated Particle Operations

This file formalizes the commutation lemma of
`maximum-safe-concurrency-proof.md`: two adjacent Particle
Operations whose operated positions are pairwise unrelated produce the same
occupancy state after either composition of their state transformations. That
lemma is the semantic core of the sufficiency half of the occupancy-concurrency
proof: any finite or natural-number-indexed execution schedule consistent with
the transitive closure of the related-and-previous relation can be constructed
prefix by prefix through adjacent exchanges of exactly such pairs.

The scheduling argument, its extension to unbounded histories, and the necessity
half (every cover pair of the closure is a mandatory ordering) remain in the
English document. Formalizing them requires a valid-schedule model that this
module does not yet encode.

An operation can change occupancy only at its operated positions and their
transitive child positions, and it reads occupancy only at the queried
position and at positions under its operated positions. Two operations with
pairwise unrelated operated positions therefore touch disjoint parts of the
occupancy state.
-/

namespace Define.OperationGraph

/--
The operation has an operated position that is the same as this position or a
transitive parent position of it. Occupancy changes made by the operation are
confined to such positions.
-/
def AffectsPosition (operation : ParticleOperation) (position : Position) :
    Prop :=
  ∃ operatedPosition,
    OperatesOn operation operatedPosition ∧
      ParentOrSame operatedPosition position

theorem occupancyAfter_of_not_affects {operation : ParticleOperation}
    {occupiedBefore : Position → Prop} {position : Position}
    (not_affected : ¬AffectsPosition operation position) :
    OccupancyAfter operation occupiedBefore position ↔
      occupiedBefore position := by
  cases operation_kind : operation.kind with
  | create target =>
      have position_is_not_target : position ≠ target := by
        intro position_is_target
        exact
          not_affected
            ⟨target, by simp [OperatesOn, operation_kind],
              position_is_target ▸ List.prefix_rfl⟩
      simp [OccupancyAfter, operation_kind, position_is_not_target]
  | destroy target =>
      have target_not_parent : ¬ParentOrSame target position := by
        intro target_parent
        exact
          not_affected
            ⟨target, by simp [OperatesOn, operation_kind], target_parent⟩
      simp [OccupancyAfter, operation_kind, target_not_parent]
  | move source target =>
      have source_not_parent : ¬ParentOrSame source position := by
        intro source_parent
        exact
          not_affected
            ⟨source, by simp [OperatesOn, operation_kind], source_parent⟩
      have target_not_parent : ¬ParentOrSame target position := by
        intro target_parent
        exact
          not_affected
            ⟨target, by simp [OperatesOn, operation_kind], target_parent⟩
      simp only [OccupancyAfter, operation_kind]
      constructor
      · intro after
        rcases after with ⟨relativePosition, position_is_target_child, _⟩ |
          ⟨_, _, occupied⟩
        · exact
            False.elim
              (target_not_parent ⟨relativePosition,
                position_is_target_child.symm⟩)
        · exact occupied
      · intro occupied
        exact Or.inr ⟨source_not_parent, target_not_parent, occupied⟩

/--
`OccupancyAfter` reads the previous occupancy only at the queried position and
at positions the operation affects, so occupancies that agree there yield the
same result.
-/
theorem occupancyAfter_congr {operation : ParticleOperation}
    {firstOccupied secondOccupied : Position → Prop} {position : Position}
    (reads_agree :
      ∀ readPosition,
        AffectsPosition operation readPosition ∨ readPosition = position →
        (firstOccupied readPosition ↔ secondOccupied readPosition)) :
    OccupancyAfter operation firstOccupied position ↔
      OccupancyAfter operation secondOccupied position := by
  cases operation_kind : operation.kind with
  | create target =>
      simp only [OccupancyAfter, operation_kind]
      rw [reads_agree position (Or.inr rfl)]
  | destroy target =>
      simp only [OccupancyAfter, operation_kind]
      rw [reads_agree position (Or.inr rfl)]
  | move source target =>
      simp only [OccupancyAfter, operation_kind]
      constructor
      · intro after
        rcases after with ⟨relativePosition, position_eq, occupied⟩ |
          ⟨source_clear, target_clear, occupied⟩
        · refine Or.inl ⟨relativePosition, position_eq, ?_⟩
          rw [← reads_agree (source ++ relativePosition)
            (Or.inl ⟨source, by simp [OperatesOn, operation_kind],
              relativePosition, rfl⟩)]
          exact occupied
        · refine Or.inr ⟨source_clear, target_clear, ?_⟩
          rw [← reads_agree position (Or.inr rfl)]
          exact occupied
      · intro after
        rcases after with ⟨relativePosition, position_eq, occupied⟩ |
          ⟨source_clear, target_clear, occupied⟩
        · refine Or.inl ⟨relativePosition, position_eq, ?_⟩
          rw [reads_agree (source ++ relativePosition)
            (Or.inl ⟨source, by simp [OperatesOn, operation_kind],
              relativePosition, rfl⟩)]
          exact occupied
        · refine Or.inr ⟨source_clear, target_clear, ?_⟩
          rw [reads_agree position (Or.inr rfl)]
          exact occupied

/--
Two operations with pairwise unrelated operated positions affect disjoint
positions: a shared affected position would make two operated positions both
transitive parent positions of it, hence related.
-/
theorem not_affects_of_affects_of_not_related
    {firstOperation secondOperation : ParticleOperation} {position : Position}
    (not_related : ¬OperationsRelated firstOperation secondOperation)
    (first_affects : AffectsPosition firstOperation position) :
    ¬AffectsPosition secondOperation position := by
  rintro ⟨secondOperated, second_operates, second_parent⟩
  rcases first_affects with ⟨firstOperated, first_operates, first_parent⟩
  exact
    not_related
      ⟨firstOperated, secondOperated, first_operates, second_operates,
        related_of_parentOrSame_of_parentOrSame first_parent second_parent⟩

theorem occupancyAfter_comm_of_not_affects
    {firstOperation secondOperation : ParticleOperation}
    {occupiedBefore : Position → Prop} {position : Position}
    (not_related : ¬OperationsRelated firstOperation secondOperation)
    (second_clear : ¬AffectsPosition secondOperation position) :
    (OccupancyAfter secondOperation
        (OccupancyAfter firstOperation occupiedBefore) position ↔
      OccupancyAfter firstOperation
        (OccupancyAfter secondOperation occupiedBefore) position) := by
  rw [occupancyAfter_of_not_affects second_clear]
  refine (occupancyAfter_congr ?_).symm
  intro readPosition read_reason
  rcases read_reason with first_affects | read_is_position
  · exact
      occupancyAfter_of_not_affects
        (not_affects_of_affects_of_not_related not_related first_affects)
  · subst read_is_position
    exact occupancyAfter_of_not_affects second_clear

/--
The commutation lemma: executing two Particle Operations with pairwise
unrelated operated positions in either order produces the same occupancy at
every position.
-/
theorem occupancyAfter_comm
    {firstOperation secondOperation : ParticleOperation}
    {occupiedBefore : Position → Prop}
    (not_related : ¬OperationsRelated firstOperation secondOperation)
    (position : Position) :
    (OccupancyAfter secondOperation
        (OccupancyAfter firstOperation occupiedBefore) position ↔
      OccupancyAfter firstOperation
        (OccupancyAfter secondOperation occupiedBefore) position) := by
  by_cases second_affects : AffectsPosition secondOperation position
  · have first_clear : ¬AffectsPosition firstOperation position := by
      intro first_affects
      exact
        not_affects_of_affects_of_not_related not_related first_affects
          second_affects
    exact
      (occupancyAfter_comm_of_not_affects
        (fun related => not_related (operationsRelated_symm related))
        first_clear).symm
  · exact occupancyAfter_comm_of_not_affects not_related second_affects

end Define.OperationGraph
