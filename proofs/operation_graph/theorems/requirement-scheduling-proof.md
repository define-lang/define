# Scheduling the Requirement-Based Construction

## Scope and premises

This proves scheduling properties of the
[requirement construction](requirement-construction.md). Fix a valid serial
reference execution, with a permitted serial order of destructors. Keep its
Particle Operation occurrences, assigned particles, and actual references.
Identical-recency Vacates remain unordered. No Action Parent Rule or
whole-action runtime barrier is used.

The source premises are the reference, creation, movement, detachment,
destructor, and contract rules used in the
[ordinary correspondence](ordinary-requirements-proof.md) and
[retained-state argument](retained-state-proof.md). This argument concerns the
Particle Operations contributed by that reference execution. It does not add
semantics for values or external calls.

## A finite exact-effect representation

Use the relative occupancy and particle-existence components of the ordinary
correspondence. When the defining particle of a position is selected for
destruction, additionally distinguish its ordinary vacancy from its retained
occupancy as derived in the retained-state argument. All destructors accessing
that original position share the latter component.

The initial retained value is supplied by the last preceding operation changing
that position's occupancy, or by its initial empty state. In the mathematical
effect representation, initialize the retained component to the occupancy
immediately before that setter. The setter makes the same genuine occupancy
change on this component as on the ordinary component. If no such setter exists,
initialize the retained component to empty; access to its defining particle
still requires that particle's creation.

This initialization is not a physical copy of an earlier state. Before the
setter no retained use of its resulting state can execute. Earlier ordinary
changes still operate on ordinary occupancy. At the setter the two observations
agree, and subsequent original accesses use their shared changing state. This
represents the inherited setter without an artificial unavailable value or a
runtime copying operation at destruction.

Ordinary reads of the last occupied state before destruction require the same
retained value, as well as their ordinary occupancy. A retained operation that
changes that value therefore waits for those ordinary uses. Once the retained
value changes, no such ordinary use remains pending. Its subsequent readers and
changes are calculated normally. This is exactly the inherited-reader
construction, not a requirement that ordinary code see a separate physical copy.

A selected Vacate changes its ordinary selected occupancy to empty. It does not
change the retained component. Its written reference requirements, when there is
a written target, remain actual occupancy requirements. An implicit child Vacate
has no newly written ancestor chain. Its selection identifies the original
position and particle, not a replacement obtained after a peer Vacate. It
requires the setter at that selected position, not every setter encountered
while discovering ancestors of the selection.

For an inbound position whose defining particle survives the destruction, no
retained copy of that inbound position is needed: the destroyed particle's own
destructors cannot obtain it through that particle. Reuse follows its ordinary
vacancy. If instead the defining particle is replaced, ordinary references
obtain the replacement's positions, not the original retained components.
Further destructions during destructor execution apply this same distinction to
the newly selected particles.

Every component change has a preceding required value different from its new
value. For ordinary occupancy and existence this is the ordinary proof. A
vacancy changes its selected particle to empty. Initial supply of a retained
component repeats the setter's actual occupied-to-empty or empty-to-occupied
change. Subsequent retained Creates and Moves change empty to occupied or
occupied to empty. A destructor can also Create a temporary particle and
subsequently Vacate it. When that new destruction does not select the position's
defining particle, its vacancy genuinely changes the current occupancy from that
temporary particle to empty, even when this occupancy is retained state from an
earlier destruction. The new particle's own retained state is handled separately
by the same construction. Being executed by a destructor does not make its
Vacate exempt from the vacancy requirements of this new destruction.

The source check below still matters: a component change must protect an actual
particle or occupancy requirement, not merely a value in this representation.

## The candidates have exactly the effect-conflict reachability

For each ordinary component, last setter and intervening readers are the
standard exact-effect collection. For a retained component, that collection
starts with the original setter and preceding ordinary readers, followed by the
destructor operations in their chosen reference order. This is precisely what
inheritance supplies. Shared destructor accesses do not start separate
collections.

Consequently the componentwise conflict-collection argument applies to both
kinds of component. Its two directions prove equality of reachability: every
collected edge is a conflict, and every earlier conflict is reached through the
last setter and intervening changes or readers. Combining components takes the
union of their edges. No minimality or scheduling conclusion is used here.

Distinct Vacates of the same simultaneous selection change distinct ordinary
components and do not change each other's retained state. An implicit child has
no ancestor-reference reads. A written target's strict intermediate positions
are outside its selected transitive children. Automatic Destruction likewise
does not invent chained target references between its selected local positions.
Thus these peers do not conflict. All oriented conflicts have strictly different
recency, independently of their enumeration.

## Safety of the respecting schedules

Start with the serial reference execution, keeping selected particles available
instead of prematurely reclaiming them. It gives an enabled execution of the
effects above. The selected vacancies are all taken from the common preceding
state; the retained state is shared by the serially ordered destructors.

Two incomparable occurrences have independent effects by conflict reachability.
The exact-effect exchange therefore preserves enabledness and the final
component state when they exchange. This exchange also preserves source
execution:

- For ordinary Creates and Moves, the actual references and final occupancies
  are exactly those in the ordinary correspondence. Relative occupancy also
  preserves the geometric restrictions and transitive spatial movement.
- For selected vacancies, the supplying occurrence and preceding ordinary uses
  remain before the vacancy. A peer vacancy neither selects a replacement nor
  removes the original positions used by pending destruction work. A retained
  Move may already have changed the original state; the vacancy still uses its
  saved selection rather than evaluating that changed state afresh.
- For retained accesses, their initial setter and earlier ordinary users have
  the required order. Subsequent accesses share the same changing original
  state. No ordinary use can observe an inconsistent retained copy: any such use
  would conflict with the retained change through its inherited requirement.
  Replacements obtain different originals, as proved above.

These cases also cover mixed exchanges. In particular, vacating an ancestor does
not empty a directly implied descendant position that a pending constructor or
destructor accesses on its original defining particle. Nor does a Move acquire a
fixed list of transitive child particles merely because a constructor can Create
one before or after it moves. Actual uses still require their particles to
exist; their creators remain predecessors.

The
[shared accessibility argument](retained-state-proof.md#accessibility-during-shared-state-changes)
is needed here. One must not apply the ordinary geometric argument to a union of
ordinary saved selections and current retained occupancy: that union can give
the same particle two apparent positions. Actual references instead use the
shared changing occupancy; the preceding-use invariant ensures that every
pending ordinary reference agrees with it. Saved vacancies are not additional
access paths. This derives the geometric premise of mixed exchanges without
assuming it from independence of mathematical components.

The
[finite linear-extension correspondence](external-results.md#finite-schedules-and-adjacent-exchanges)
applies: conflict reachability is a strict partial order, and both permutations
list the same finite occurrence set exactly once. The cited connectivity result
supplies incomparable adjacent exchanges between them. Induction over that
sequence, using the source-preserving exchange at each step, proves that the
same Particle Operations execute safely and have the same final relevant state.
This proves safety without assuming minimality.

## Exhausting the possible interference

The correspondence must also exclude interference not represented by a component
conflict. For the specified Particle Operations there are the following cases:

1. **An actual reference becomes invalid.** A written intermediate position has
   lost its required particle, or an assigned quality's particle does not yet
   exist. Those are respectively occupancy and existence requirements. Direct
   implied access has the latter requirement without a newly invented caller
   reference. Retained intermediate references use the shared original state,
   and pending ordinary references are protected by inherited uses.
2. **A final position has the wrong occupant.** Create and Move destination
   require empty; Move source requires its selected particle. Their changes
   conflict with every actual observation of the state they end. Simultaneous
   vacancy has its saved selection instead of re-evaluating a changed retained
   occupant. Reuse at a surviving defining particle's position follows vacancy;
   access through a replacement obtains that replacement's positions. It cannot
   use the original retained occupancy as an extra ordinary occupant.
3. **The same particle is affected at different positions.** Current shared
   occupancy has only one incoming association per particle. Two adjacent Moves
   directly moving the same particle therefore share the first Move's
   destination and the second Move's source; those effects conflict. A Move
   followed by an ordinary Vacate of its destination similarly conflicts. A
   selected vacancy and a retained Move are different: the vacancy releases the
   saved ordinary occupancy, while the Move changes the original state available
   to destruction work. They do not purport to move two copies of a particle. An
   intervening series of Moves is covered by the corresponding successive
   occupied-state setters.
4. **Movement changes spatial relationships transitively.** Relative positions
   move with their defining particles. The reference-shape and shared
   accessibility arguments show that preserving actual endpoint requirements
   preserves geometric legality. This does not freeze a Move's transitive
   participants to those of the reference execution or make a transitive child
   occupancy an additional endpoint requirement.
5. **A needed particle ceases to exist.** Vacancy is not that event. The
   [Vanish argument](vanishment-proof.md) retains particles through their actual
   uses, without retaining them solely for transitive movement, and only then
   permits them to vanish. No dependency on a vacancy is justified merely by
   this lifetime requirement.

Create, Move, and Vacate have no further particle effects in the stated scope.
Qualities required by a Move's destination remain qualities of the same selected
particle. Action Contracts determine the valid source occurrences under
consideration; they do not add a runtime operation or whole-action barrier. Thus
these cases justify using component independence for the particle-operation
claim. They do not settle the ordering of future value operations or external
calls.

## Necessity of each cover ordering

Take a cover pair in conflict reachability. It is a direct conflict; otherwise
an intermediate occurrence on its conflict path would contradict the cover
property. The adjacent-cover construction gives a respecting schedule with its
endpoints adjacent. Safety was proved independently above. Reverse only these
two occurrences; all other relative orders are unchanged.

For ordinary conflicts, the ordinary proof supplies the source obstruction. For
a vacancy after its selected occupancy setter, reversal omits the selected
particle or attempts to vacate a position before the Move supplying its
occupant. A Move of an ancestor is not such a setter. For a vacancy after an
actual ordinary use, reversal makes that use's occupied reference empty. For
reuse after vacancy at a surviving defining particle's position, reversal
attempts to fill that still-occupied position. A replacement's differently
defined child position does not create this conflict.

The additional retained conflicts have two possible origins:

1. The original state has not yet been supplied. If its setter Creates the
   needed particle or its defining particle, that particle or position does not
   yet exist. If its setter is a Move or an earlier vacancy, reversing the pair
   leaves the required position occupied instead of empty, or empty instead of
   occupied by the selected particle. The obstruction is the original source
   occupancy: the setter's preceding value differs from the value needed by the
   subsequent operation.
2. An inherited ordinary use precedes a retained change. Reversing this order
   moves the original particle out of the position that the ordinary use
   actually requires. The ordinary use cannot recover it from a copied value or
   from a replacement: it refers to that original occupancy. Thus the reversal
   fails the ordinary reference requirement.

After initial supply, retained operations have the same ordinary Create/Move
obstructions on their shared original state. For further destruction during a
destructor, the selected-setter, preceding-use, and reuse cases above apply to
that destruction's current occupancy. In particular, destroying a temporary
particle in an initially empty retained position supplies the empty state needed
by a subsequent Create there; those operations are not made independent by the
earlier destruction's detachment. Different destructors do not get independent
copies that could make the reversal safe.

The cover property excludes an intervening change supplying the required state:
such a change would lie strictly between the endpoints in conflict reachability.
In particular, an earlier departure and return cannot erase the obstruction to
reversing the final return and its immediately following use in this schedule.
Another globally safe orientation is not a counterexample to necessity within
the chosen orientation.

Hence removing a cover edge admits a source-invalid schedule. This is stronger
than graph-theoretic transitive minimality and is proved separately from it. It
does not claim that every safe graph must choose the same orientation.

## Completion of destruction and unbounded execution

The occupancy safety argument keeps required particles available. The
[Vanish proof](vanishment-proof.md) derives their exact lifetime dependencies
and proves that inserting Vanishes preserves those requirements. No additional
ordering between Create, Move, and Vacate occurrences is introduced.

For an unbounded reference execution indexed by natural numbers, take any finite
runtime prefix and a reference prefix containing all its occurrences. Edges
point strictly backward, so that finite reference prefix contains all their
predecessors. Extend the runtime prefix to a respecting permutation of this
finite set by repeatedly taking a remaining occurrence with no unmet
predecessor. Acyclicity ensures one exists. Finite safety then proves safety of
the original runtime prefix. Since it was arbitrary, no finite step of the
unbounded schedule violates an operation requirement.

This proves prefix safety, not termination or a fairness guarantee. Destruction
can complete for each particle whose vacancy and last actual interaction have
occurred, without waiting for the whole program to terminate.

## What remains outside this argument

These conclusions apply to the requirement construction now written in the
specification. The generic Lean modules `effect_collection.lean` and
`effect_graph.lean` check its collection, reduction, and effect-scheduling
results. `CalculatedPrefix` models Comparison using already-calculated
dependencies, and `calculated_respecting_permutation_executes` and
`calculated_edge_has_unsafe_reversal` apply the scheduling conclusions to that
incremental calculation itself. No subsequent minimization is performed.

The structured-reference and occupancy correspondence is checked in
`particle_requirements.lean`; the original-state component correspondence is
checked in `retained_requirements.lean`. Both derive exact-effect validity and
enabledness rather than assuming them. `particle_scheduling.lean` transfers
executions in both directions and derives schedule safety and invalid adjacent
reversals for these representations.

The derivation of source occurrences and their reference or component
representations, the geometric accessibility argument, and the completion of
destruction remain English proofs. The Lean results are not a fully checked
source-language translation. Integration expectations do not replace those
English arguments.
