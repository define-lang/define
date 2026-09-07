# Extending the Graph to Vanish

## Scope and semantic obligations

The proof covers Create, Move, Vacate, and Vanish under the specification's
Particle Operation Dependency Graph rules. The Action Parent Rule is excluded. A
particle remains alive for operations requiring it or its assigned qualities,
not solely to participate in transitive movement. This applies equally to
constructors, destructors, and transitively triggered actions.

## Vanish construction

First construct the existing Create, Move, and Vacate graph without
modification. Resolve each operation's actual Position References using the same
serial execution and original particle identities as that construction.

For each particle selected for destruction, collect:

- Its own Vacate.
- Every Move whose source particle is that particle.
- Every operation whose actual Position References use a quality assigned to
  that particle, including the qualities used through intermediate positions.

Combine the candidates and apply the existing Comparison rule to them. The kept
candidates are the Vanish's dependencies. Calculate these dependencies against
the unchanged Create, Move, and Vacate graph. A Vanish does not become a
position setter or reader and does not supply a candidate for another operation.

An implicit child Vacate retains its selected position; it does not introduce a
new reference requiring the defining parent to remain alive. A written Vacate
does have its statement's actual reference requirements. No operation acquires
its caller's earlier reference merely because it belongs to a triggered action.

This rule examines the actual operations of every destructor and called action,
not just the action assigned directly to the particle. It does not collect whole
action executions, every spatial ancestor of a reference, or every particle
moved transitively by a Move. There is no ordering between Vanishes merely from
a parent-child relationship.

## An extension with fixed, exact prerequisites

First isolate a graph theorem. It does not assume that Define's interaction sets
are fixed across schedules.

Let `G` be a finite acyclic, transitively minimal graph of Create, Move, and
Vacate occurrences. Its executions must already be source-safe, and removing any
of its edges must already admit a source-invalid execution. These are separate
semantic premises supplied by the existing scheduling proof, not consequences of
acyclicity or transitive minimality. The graph-only conclusions below do not
require those semantic premises; safety and semantic necessity do.

For each selected particle `P`, suppose a finite set `L(P)` of occurrences has
been supplied with the following independently established semantic
correspondence:

- It includes `P`'s Vacate.
- Inserting `P`'s Vanish into any execution allowed by `G` is safe exactly when
  every member of `L(P)` has completed.
- Several such insertions preserve the same correspondence for the remaining
  operations. In particular, an earlier Vanish cannot make a required future
  interaction disappear and thereby justify its own placement.

These are hypotheses of this theorem, not facts already proved for arbitrary
Define source. The second condition includes necessity as well as sufficiency;
an over-approximation of possible interactions cannot discharge it.

For each Vanish, collect `L(P)` and apply the existing Comparison calculation
using reachability in `G`. Add dependencies from that Vanish to the candidates
Comparison keeps. Add no dependencies from existing occurrences to Vanishes, or
between Vanishes. No later transitive minimization is performed.

### Safety and acyclicity

Comparison preserves reachability to every collected candidate. Hence every
allowed placement of Vanish follows all its prerequisites and is safe by the
semantic correspondence. Repeated insertion is safe by its third condition.

Every new dependency points from a Vanish to an existing occurrence. No existing
occurrence depends on a Vanish. Thus no new dependency can participate in a
cycle. The relative execution orders admitted for the existing occurrences are
unchanged: any complete execution of `G` extends by placing all Vanishes after
it. This is an existence argument, not an instruction to delay them all.

### Transitive minimality

An existing edge cannot acquire an alternative path through a Vanish, since no
existing occurrence has a dependency on a Vanish. It therefore remains
transitively necessary.

For a new edge from Vanish to a kept candidate `A`, an alternative path would
have to start with another kept candidate `B` and continue through `G` to `A`.
Comparison would then have omitted `A`. Consequently no such alternative path
exists. This uses the existing Comparison result; it is not an additional
reduction algorithm.

### Semantic necessity

Remove the edge from Vanish to a kept candidate `A`. Complete the other kept
candidates and all their predecessors while leaving `A` unexecuted. Such a
prefix exists: if any of those candidates required `A`, Comparison would not
have kept `A`. Vanish is now enabled by the weakened graph even though a member
of `L(P)` has not completed. The necessity direction of the semantic
correspondence makes this execution invalid.

Removing an existing edge still admits its original invalid execution, with
Vanishes delayed until after the offending operations. Adding Vanishes therefore
does not repair an unnecessary or unsafe assumption in the original graph proof.

Under the stated correspondence, the extension is safe and every remaining edge
is necessary. It introduces no whole-destructor barrier, parent-child Vanish
order, or ordering between independent Vacates.

## Source correspondence for the refined Vanish rule

### The required particle identities are schedule-independent

A Position Reference's intermediate occupancy selects its particle, and that
particle supplies the quality used by the next part of the reference. The
existing graph preserves these selected particles, not merely whether those
positions are occupied. A direct implied reference obtains its quality from the
same assigned particle without traversing the caller's earlier reference.
Interface references likewise retain their actual quality setters.

A Move's source occupancy determines the particle it moves directly. The graph
preserves that identity through ordinary and shared destructor-state changes.
The list of particles moved transitively may change with operation order, but
neither the source identity nor the reference's required quality setters does.

Thus every collected operation requires the same selected particle in every
execution permitted by the existing graph. This follows from the reference and
occupancy correspondence, not from an assumed fixed list of spatial descendants.
The checked reference lemma in `particle_requirements.lean` records exactly the
existence observations made by the different reference forms. Direct movement
additionally requires the moved particle to exist, even if a retained occupancy
record still identifies it.

### These are all the existence requirements

A Create needs the positions and qualities used by its target reference; its new
particle does not exist beforehand. A Move needs both actual references and the
particle it moves directly. A written Vacate needs its actual reference and its
selected particle. An implicit Vacate needs its selected particle but does not
re-evaluate a reference through the defining parent. All operations therefore
have their actual existence requirements represented by the collection above.
The selected particle's own Vacate supplies its requirement to precede Vanish.

Moving an ancestor can change the spatial position of particles still present,
but it does not fill or empty their positions. Under the refined Vanish rule,
the absence of an already-vacated particle that no remaining operation needs
does not invalidate that Move. A reference that actually needs the original
particle is different and has already contributed a candidate.

Vanish does not vacate a second position, select a replacement, or reclaim other
particles with pending requirements. A saved child vacancy remains the selected
effect of the original destruction, not a fresh reference through a parent that
has vanished. These distinctions preserve the existing simultaneous-destruction
and retained-state interpretation.

### Safety after inserting Vanishes

For each particle `P`, let `L(P)` be the candidates specified above. Fix an
execution of the existing graph and insert Vanishes only after their collected
candidates. Induct over the resulting execution.

Before each Create, Move, or Vacate, its required particles have not vanished:
that operation would otherwise be an uncompleted candidate for their Vanishes.
Its actual position references and endpoint occupancy are therefore preserved by
the existing graph argument. A preceding Vanish does not change ordinary vacancy
or provide different occupancy for a replacement. Any historical retained record
for a vanished particle cannot be dereferenced by a later operation: doing so
would require that particle and prevent its Vanish.

Transitive spatial movement of an already-vacated, unneeded particle need not be
preserved. The induction preserves actual reference and occupancy requirements,
not the movement of every particle in an auxiliary execution that never reclaims
anything. Empty positions needed by later references remain protected through
the particle supplying their assigned qualities.

Before each Vanish, its own vacancy and every remaining requirement on its
particle have finished. Removing it therefore preserves the induction
hypothesis. This also proves that several Vanishes can be inserted
independently: the argument does not justify an early Vanish by having an
earlier Vanish erase a requirement. Requirements were resolved before any Vanish
was inserted.

### Necessity independently of safety

If the particle's Vacate has not occurred, Vanish violates its stipulated order
after Vacation. If a collected Move has not occurred, it still needs that same
source particle. If a collected reference use has not occurred, it still needs
the selected particle's assigned quality. Vanishing first makes that pending
operation invalid; changing its selected particle or replacing its quality
setter would not execute the same resolved operation.

These cases prove necessity without using the safety or minimality theorem. They
establish exactly the fixed-prerequisite correspondence above for the refined
Vanish rule. Comparison can omit candidates already implied by others;
collecting them does not require retaining them all as direct dependencies.

### Earlier and further destructions

Further destruction during a destructor changes which original particles and
occupancy records subsequent references use. It does not change how an actual
reference requires the particle supplying its quality. Each new particle has its
own Create, selected Vacate, and eventual Vanish. Replacement identities remain
distinct even when positions have the same names.

In the example where one destructor moves `/carrier` and its destructor creates
and destroys `/temporary::/leaf`, the Move of `/carrier` supplies no existence
requirement for the leaf. It neither moves the leaf directly nor uses one of its
qualities. Whether that leaf would move transitively while still present is
immaterial to its Vanish. A different destructor that actually accesses the leaf
would contribute its own candidates. No ordering between the temporary
particle's and leaf particle's Vacates is added.

The same reasoning applies to the delayed constructor that Creates `/leaf` while
a destructor moves its defining particle. That Create protects the defining
particle, not every earlier caller ancestor. The leaf's own Vacate follows its
Create. An ancestor Move alone does not prolong the leaf's lifetime.

### Unbounded executions

For a particle with finitely many required operations, the same finite
collection and Comparison calculation applies even when the overall execution is
unbounded. It need not wait for termination of unrelated work.

If a particle has infinitely many required future operations, it cannot Vanish
in a finite execution prefix. This is a semantic limit, not an instruction to
finish an infinite collection or add an infinitely distant occurrence to a
natural-number-indexed schedule. The finite construction establishes no compiler
termination bound for an infinitely expanded action execution.

## Combining Vacate and Vanish without losing concurrency

The optimization is applied to the resolved graph and must preserve its
concurrency. Merely finding one schedule with consecutive Vacate and Vanish
occurrences does not satisfy that requirement.

For the extension above, let `A` be a particle's Vacate and `V` its Vanish. A
sufficient condition is that `A` is `V`'s only direct dependency in the
transitively minimal graph. Vanish has no dependents in this extension. There is
no requirement that Vanish be Vacate's only dependent: ordinary operations may
also depend on the vacancy.

Every interaction required by `V` then already precedes `A`, directly or
indirectly. Whenever `A` is enabled, no interaction remains to prevent that
particle's Vanish. The combined operation can empty the position and end the
particle's existence together, as permitted by Particle Operations. It inherits
`A`'s dependencies, and every operation depending on `A` instead depends on the
combined operation. No additional prerequisite is introduced for vacancy or for
an operation that reuses the position.

To check reachability among all other occurrences, a path through the combined
operation expands to a path through `A` in the original graph. Conversely, every
original path between those occurrences remains after replacement: `V` cannot be
an intermediate vertex of such a path, since it has no dependents. Consequently
no new ordering between the other operations is added and none is removed. The
combined operation is enabled under exactly the same conditions as the original
Vacate. This establishes concurrency preservation, not merely safety in a
selected serial schedule.

The remaining graph is the original extended graph with the terminal `V` deleted
and `A` renamed as the combined operation. Since no path between other vertices
passes through `V`, deleting it neither creates nor removes alternate paths for
the remaining edges. Transitive minimality is preserved without a further
minimization step. This argument also permits repeated eligible fusions: each
preserves the graph properties required for the next one.

If `V` has another kept prerequisite `M`, then `M` does not already precede `A`:
Comparison would otherwise omit it. Combining the operations while retaining
that prerequisite would postpone vacancy in executions where `A` was enabled
before `M` finished. This fails the stated condition. Finishing `M` early in one
chosen schedule does not remove this distinction in the resolved graph.

### Replacement must not acquire a destructor dependency

For example, create a particle in `position<item>`, destroy it, then create its
replacement in `position<item>`. Give the original particle a destructor that
moves a particle in an occupied implied `position</child>` to a local position
and back. Let:

- `A` be the original particle's Vacate;
- `B` be the replacement's Create;
- `M` be the destructor's return Move, which requires the original particle's
  implied position;
- `V` be the original particle's Vanish.

`B` must follow `A` but does not use the original particle or its implied
position. `V` must follow `A` and `M`. The vacancy need not wait for `M`, and
neither must the replacement. The destructor acts on the original particles, not
those of the replacement.

There is an execution in which `M` finishes and then `A` and `V` occur
consecutively. Combining those consecutive steps preserves that execution.
However, combining their vertices makes the replacement wait for `M`, excluding
the otherwise allowed execution in which `A` and `B` finish while the original
destructor still runs.

This example does not satisfy the graph condition: `V` has the additional
prerequisite `M`, which does not precede `A`. The permission to combine Vacate
and Vanish therefore does not justify merging them here. The general permission
to choose less parallel execution is not used to justify this optimization.

## Checked mathematical representation

`vanishment_requirements.lean` represents one particle's existence and the
completion of its Vacate with two Boolean observations. The latter is a record
of that selected occurrence, not the current emptiness of a reusable position.
Create changes existence from false to true. Actual uses require true existence
without changing it. Vacate records its completion without ending existence.
Vanish requires existence and the completed Vacate, and ends existence without
changing the vacancy record. Fresh particle identities are never recreated.

Lean checks exact-effect validity, the enabling conditions of use and Vanish,
failure of a use after Vanish, and the independence of vacancy from a lifetime
use. It also checks that the combined lifetime effect has the same enabling
conditions as Vacate and the same result as Vacate followed by Vanish. Its
application is subject to the graph condition proved above, not permitted solely
by that state equality.

These components supplement the existing position effects. A Move combines its
source, target, and reference effects with lifetime uses for the directly moved
particle and quality setters. It remains one operation. Vanish changes only its
particle's existence component; it neither fills nor empties a position. The
source correspondence above explains this translation; the component definition
is not evidence for which source operations need it.

The existing `ExactEffects` theorems apply to these valid components and their
products. In particular, `independent_enabled_exchange` and
`conflicting_enabled_pair_cannot_reverse` supply the local mathematical facts;
the incremental Comparison calculation in `effect_graph.lean` already proves
reachability preservation and transitive minimality. These exact mathematical
results are reused rather than reproved as a second general graph algorithm.

`vanishment_graph.lean` checks the extension itself: existing occurrences and
Vanishes have distinct vertex kinds, existing edges are retained, and each new
edge is exactly a kept candidate. It proves that existing reachability is
unchanged, characterizes every path from a Vanish, excludes dependencies on
Vanishes, and proves acyclicity and transitive minimality. Both antichain
premises of the minimality theorem come from Comparison: one for the existing
operations and one for Vanish. They are mathematical results about that
calculation, not assumptions that lifetime candidates are semantically
necessary.

The source correspondence remains an English argument, as do the corresponding
source arguments for the existing occupancy construction. The formal graph
extension proves that no extra ordering among existing operations is introduced;
it does not by itself prove that their source requirements are complete. This is
not a fully Lean-formalized Define semantics.
