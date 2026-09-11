# Deriving Ordering from Particle Operations

## Scope

This derives ordering requirements from the specification, with Vacate and
Vanish treated separately.

Safety and maximum concurrency concern the execution orders a construction
permits. Transitive minimality of its ordinary graph alone proves neither
property, especially when relationship conditions also constrain those orders.

The [operation requirements](../definitions/operation-requirements.md) separate
serial reference resolution, endpoint occupancy, particle existence, and
vacancy. The [requirement construction](requirement-construction.md) applies
those distinctions to ordinary operations, simultaneous selection, and retained
destructor state, with their semantic correspondence developed in the
[scheduling proof](requirement-scheduling-proof.md).

## Consequences that do not depend on a construction

1. A Create requires its identified target to exist and be empty. Written
   intermediate positions identify that target in the serial interpretation;
   they need not retain that occupancy during execution. Its new particle is not
   interchangeable with an earlier particle at the same position.
2. A Move requires a particle at its source and an empty destination. It changes
   the spatial positions of its defined positions and their particles
   transitively, including empty positions. It is not a deferred destruction or
   a change of spelling. An operation cannot assume the post-Move spatial
   relationships before that Move, or the preceding relationships after it. A
   later Move may restore a relationship; necessity must be proved for the
   proposed ordering, not assumed for every pair that ever affects the same
   particle.
3. A Vacate denotes vacancy. Its former particle can remain available to
   destructors after that vacancy. Reuse of the vacated position does not access
   the retained original particle. The vacancy must still follow ordinary
   operations whose required occupancy it would invalidate.
4. Identified endpoints and selected particles determine lifetime requirements.
   Neither a written intermediate nor transitive movement alone prolongs
   lifetime. Actions triggered by a destructor contribute their own endpoint and
   particle requirements.
5. Original particles are shared between destructors. Availability after vacancy
   does not make two conflicting Moves independent. A model that gives each
   destructor a separate copy of its required particle changes Define's
   semantics even if both copies are later discarded.

These statements follow from Identifying Particles and Positions, Moving
Particles, Simultaneous Transitive Destruction, and Processing Destructor
Operations. None uses graph reachability as evidence that an ordering is
necessary.

## An ordering choice remains even when every particle survives

Suppose two destructors, `A` and `B`, are assigned to the same particle. Each
implies the occupied position `/marker`. The particle there has no child
positions. Each destructor has an independent local position `held` and this
body:

```text
define the position<held>.
move the particle in position</marker> to position<held>.
move the particle in position<held> to position</marker>.
```

Denote their Moves by `Aout`, `Aback`, `Bout`, and `Bback`. All four Moves act
on the same original marker particle. Distinguish the local positions as
`A.held` and `B.held` for this mathematical argument. No constructor or
destructor is assigned to the marker particle itself. The outer vacancy can
already have occurred; the original marker remains available to both actions.

Both of these orders are valid, with exactly the same original particle restored
to `/marker` and both local positions empty:

```text
Aout, Aback, Bout, Bback
Bout, Bback, Aout, Aback
```

But this interleaving is invalid:

```text
Aout, Bout, Aback, Bback
```

After `Aout`, the particle is in `A.held` and `/marker` is empty, so `Bout` has
no particle at its source. Keeping the particle alive does not enable the Move.

### No precedence graph can admit both valid orders and exclude the bad order

Every graph edge must be respected by every admitted order. In the two valid
orders, each operation of `A` changes its relative order with every operation of
`B`. Therefore a graph admitting both orders can have no edge between the two
actions' Moves. It can require `Aout` before `Aback` and `Bout` before `Bback`,
but the invalid interleaving respects both requirements. The ordinary Creates
and vacancies can be placed in a common prefix of all three schedules. Edges
involving that prefix cannot distinguish their subsequent interleavings.

Thus a pure precedence graph must choose one of the two safe orientations. A
representation with alternative conditions need not make that choice. Either
resulting four-operation chain is transitively minimal and cannot be weakened
while preserving safety: reversing either destructor's adjacent Moves attempts
to return a particle from an empty local position, and reversing the adjacent
return and next departure attempts to depart from an empty `/marker`. Removing
any chain edge admits the corresponding adjacent reversal. Neither contains all
the safe executions admitted by the other. This is a limitation of precedence
graphs, not a missing lifetime edge.

The bounded Lean witness `destructor_order_choice.lean` represents the three
positions and the one original particle explicitly. Each Move is enabled exactly
when that particle occupies its source; the destination is then empty because
the three positions are distinct and no other particle occupies them. It
verifies both safe orders, failure of the interleaving, and the graph
obstruction for every binary dependency relation. This correspondence is exact
for these four Moves; it does not model all of Define or assume safety of a
general graph construction.

The existing integration test
[`test_multiple_constructors_and_destructors_modify_same_implied_position`](../../../define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)
contains this pair of destructor bodies. Its expectation chooses `B` before `A`.
That implementation choice is not a semantic premise for this proof.

## Consequence for the construction goal

A graph need not admit every safe ordering to be inclusion-minimal for safety.
The example above establishes that distinction while preserving particle
identity and the unchanged destructor guarantees.

The specification permits the compiler to choose any serial ordering of the
destructors triggered by a simultaneous destruction for determining recency. The
construction therefore takes one such ordering as input and must prove safety
and necessity relative to that choice. The unchanged Action Guarantees make each
complete destructor preserve the contracted state for the next one. They do not
make every interleaving of their Particle Operations safe, as the example
proves.

The chosen order is not a whole-destructor runtime barrier. Independent
operations from different destructors may interleave when the graph permits
them. The proof must establish that each remaining ordering is necessary within
the chosen orientation, not that one graph admits both serial orders above.
Different choices can give different transitively minimal graphs. No unique
precedence relation is claimed before that choice is fixed.

This choice does not move a destructor before the creation or destruction that
triggers it. For example, if a destructor creates a local particle with its own
destructor, that new destructor is triggered by a subsequent destruction. Its
serial execution remains within that subsequent destruction; it is not another
member of the earlier choice. The runtime graph can still relax this serial
placement wherever actual requirements permit.
