# Source Correspondence of the Specified Graph

## Statement and scope

Fix a finite valid serial execution as used by Particle Operation Recency,
including a permitted ordering of destructors. Keep its individual Particle
Operation occurrences, Action Executions, assigned qualities, and original
particles selected by destruction. Apply the current Particle Operation
Dependency Graph rules, excluding the Action Parent Rule.

The resulting graph is acyclic and transitively minimal. Every schedule
respecting it, starting from the reference execution's initial state, executes
those same Particle Operations with valid references, occupancy, and particle
existence. Removing any edge admits an execution that violates one of those
requirements. Thus the construction provides maximum safe concurrency within its
chosen dependency orientation, not all safe orientations of destructor
operations in one graph.

This is a statement about Particle Operations contributed by valid source, not a
proof of a parser, compiler implementation, value semantics, or external-call
semantics. The correspondence to source is proved below in English. The linked
Lean results check the mathematical representations and calculations; they do
not encode the whole source language.

## From source to the state observations

The [ordinary correspondence](ordinary-requirements-proof.md) derives the
observations of each written reference by induction on its chain. Local
positions are identified by declaration and Action Execution. Positions defined
by qualities are identified by their defining particle and declaration;
interface positions additionally distinguish the action declaration. These are
relative positions, not fixed spatial names. Each written intermediate requires
its actual selected particle. Direct implied and interface access requires the
particle supplying the declaration, without a lookup through the caller's
earlier reference. Assignment Semantics and Atomic Creation supply the fixed
qualities of those particles.

Create additionally requires an empty target and introduces a fresh identity.
Move requires its selected particle at its source and an empty target, and
changes those two relative occupancies together. Its transitive spatial effect
is obtained from the unchanged relationships of particles and positions it
defines. The [reference-shape proof](reference-shape-proof.md) derives geometric
validity from the source naming restrictions and the prohibition on moving a
particle into a position it defines; it is not a hypothesis on arbitrary
occupancy maps. This includes private local work occurring before the creation
of the particle assigned its action, without using the Action Parent Rule.

For destruction, [shared retained state](retained-state-proof.md) distinguishes
the selected ordinary vacancy from the original state still available to
destructors. The same original positions and particles are shared by all
destructors, including their subsequent changes. Each implicit child Vacate
keeps its selected particle and position without evaluating a new ancestor
reference. A written target retains its actual reference requirements.
Replacements do not identify their positions' occupancy with retained original
occupancy. Further destruction of temporary particles applies the same argument
to those new particles, not a second independent copy of an existing original.

Consequently an enabled source occurrence has the stated observations and
changes. Conversely, when those observations hold in a reachable represented
state, induction along the actual reference selects the required position and
particle, the endpoint requirements enable the operation, and the geometric
invariant makes its Move legal. Both executions give the same relevant relative
occupancy and spatial relationships. For saved vacancies, the observation is the
saved selection, not an invented present-day lookup. This is the two-direction
correspondence used by scheduling, rather than only a mapping from source
executions into a potentially more permissive model.

## From the spec's phases to the graph calculation

The correspondence for each phase is as follows. These facts are proved without
assuming safety or minimality of the resulting graph.

| Spec phase                        | Correspondence                                                                                                                                                                                                                                                                |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Position Setters and Readers      | A setter supplies the current occupancy. Readers are precisely the actual intermediate-position requirements since that setter. A child position's initial setter is its defining particle's Create; an initially empty local position has no such requirement.               |
| Collection                        | Target setters provide empty occupancy; intermediate setters provide the selected occupied state; source and Vacate readers protect uses of occupancy being ended. If readers exist, their paths already include the setter. Parent Creates provide the referenced qualities. |
| Collection omissions              | A collected reader covers its setter. A different setter or reader of a child position covers its defining particle's Create. Following any chain of omissions terminates at an unremoved candidate because every link follows reachability in the preceding acyclic graph.   |
| Comparison                        | The ordered scan retains an antichain covering every candidate. Its result is exactly the candidates not reached from another candidate, using only already calculated dependencies.                                                                                          |
| Recording the Operation's Effects | Setters and readers advance with the actual fills, emptyings, and intermediate uses. Optional reader removal retains a path to every removed reader, including readers that were collected but not kept as direct dependencies.                                               |
| Processing Destructor Operations  | Shared original state keeps the preceding setters and readers when the selected Vacates are processed. Actual destructor operations update that state using the same rules, without a Vacate barrier or independent copies per destructor.                                    |
| Recording Vanish Information      | Named positions and actions contribute exactly their parent particles as lifetime requirements. The direct-Move chain lets the most recent direct Move cover all earlier ones. Optional pruning preserves candidate closure.                                                  |
| Completing Vanishes               | Comparison covers the recorded candidates, selected Vacate, and most recent direct Move. Vanishes add no setter, reader, or prerequisite for another operation.                                                                                                               |

The [construction proof](requirement-construction.md) establishes the first six
rows, including the invariants needed by the omissions and by retained state.
The [Vanish proof](vanishment-proof.md) establishes the final two. Equal-recency
Vacates have distinct target positions and do not introduce references to one
another's selected positions, so processing one cannot change another's
candidates. Their enumeration supplies no dependency.

The complete occupancy candidates have exactly the oriented conflict
reachability of the corresponding effects: each collected edge protects a
genuine observation, and every earlier conflict is reached through successive
setters and readers. Initial child-position availability is represented by
particle existence, not by a fictitious empty-to-empty occupancy change at
Create. Collection omissions and Comparison preserve that reachability. The
proof characterizes the graph's result; it never applies a generic transitive
reduction algorithm to construct it.

## Discharging the scheduling hypotheses

The [scheduling proof](requirement-scheduling-proof.md) constructs the reference
effect execution from these source observations. Every changed component has its
required preceding value and genuinely changes: Create supplies a fresh
particle, Move exchanges occupied and empty endpoints, and Vacate makes its
selected ordinary occupancy empty. Shared-state components inherit those same
changes and preceding uses, rather than introducing an artificial readiness
condition. These facts discharge exact-effect validity and enabledness; they are
not extra assumptions about Define.

Conflict reachability is oriented by the serial execution. Therefore the serial
schedule respects it, and incomparable operations have independent effects.
Adjacent exchanges preserve the actual source requirements and spatial
relationships by the two-direction correspondence. Connectivity of finite linear
extensions then proves safety for every respecting schedule. This proof does not
assume that any graph edge is necessary.

Separately, Comparison produces transitive minimality: an alternative path for a
kept edge would begin with another kept candidate reaching its target, which
Comparison excludes. This argument does not assume source completeness or
safety.

For semantic necessity, make the endpoints of a cover edge adjacent in a
respecting schedule and reverse them. The genuine changed value no longer
supplies the subsequent reference or occupancy requirement, or the earlier use
loses the occupancy it needed. The scheduling proof checks these obstructions
for ordinary and shared destruction state, so the failure is a source failure,
not just disagreement with mathematical bookkeeping. This supplies the necessity
hypothesis independently of graph minimality.

## Inserting Vanishes

The Vanish correspondence derives the complete set of required particles from
actual references, directly moved particles, and selected Vacates. These
identities are preserved by the occupancy proof. Moving a parent does not add an
existence requirement for an otherwise unneeded child. Inserting one Vanish
therefore cannot erase another operation's reference requirement to justify
itself. Several Vanishes can be inserted independently after their required
operations.

The spec's recorded set has the same dependency closure as that complete set,
including after optional pruning and replacement of earlier direct Moves by the
most recent one. Final Comparison preserves that closure. An existing edge
cannot acquire an alternative path through a Vanish, and the retained Vanish
candidates are an antichain. The extended graph is consequently acyclic and
transitively minimal. Every new edge is necessary: removing it permits Vanish
before a required operation or before its Vacate. Removing an old edge still
permits the original invalid execution with Vanishes delayed.

This completes the stated source theorem. No combination of Vacate and Vanish is
part of this construction. For unbounded executions, the finite-prefix argument
in the scheduling proof proves safety of each finite execution prefix; it does
not promise termination or finish an infinite candidate collection.
