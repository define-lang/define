# Scheduling Identified Particle Operations

## Scope

Fix finitely many Particle Operation occurrences from a valid serial
interpretation, with a permitted ordering of sharing destructor operations.
Exclude the Action Parent Rule. Use the specified identified positions and
particles, rather than repeating written reference traversal at runtime.

The [construction proof](requirement-construction.md) establishes ordinary
setter reachability independently of schedule safety. The
[relationship proof](relationship-ordering.md) characterizes circularity
independently of ordinary graph minimality. The
[Vanish proof](vanishment-proof.md) supplies lifetime completeness.

## Endpoint requirements in any respecting order

For each actual position, its successive setters preserve its serial occupancy
visits. Project a proposed operation order onto those setters. Because it
respects candidate reachability, the projection has the same order as the serial
interpretation. Induction over this projection supplies the occupant or vacancy
required by each operation. An initial setter also supplies the defining
particle's Create.

For a selected particle, its Create and successive direct Moves form a chain
through occupied-source setters. Thus its creation precedes each direct use and
its Moves cannot execute on two different sources concurrently. Each Move has
one source-emptying and target-filling effect, not two independently executable
operations.

The same position argument applies to shared destruction state, beginning at its
inherited original setter. A selected Vacate does not change that shared setter.
It records release of the original selection, not another current position for
the particle. A later fill of a surviving position follows its ordinary Vacate;
a replacement-defined position has a different identity.

These arguments establish ordinary endpoint enabledness. They do not establish
absence of a transitive cycle: different particles' endpoint effects can each be
enabled while their combination gives a circular arrangement.

## Particle relationships at each effect

The actual occupant of a position has a direct association with its defining
particle. Positions defined by actions use the action's parent particle. These
associations are fixed by current occupancy, not by the written path used to
identify it.

The relationship-period construction records exactly these associations in each
proposed order. Moving between positions of the same defining particle preserves
the association. A Move to a different parent changes it. Ending preservation
removes it after both the Vacate and the last required direct destruction Move.

By the interval theorem, all relationships of a simple cycle coexist precisely
when that cycle's condition fails. Satisfying every condition is therefore
equivalent to acyclicity at every effect. In particular, a final destructor Move
must have a legal occupied result even when preservation ends immediately
afterward. Checking only the resulting vacancy would miss that effect.

## Lifetime and single occupancy

The last-candidate theorem makes Vanish follow every operation using its
particle or a position defined by it, including uses whose edges were omitted
because of relationship conditions. Before such a use, the supplying Create has
occurred and Vanish has not. Thus all endpoint positions and selected particles
exist.

There is at most one current incoming position for each particle: Create gives
it one, Move changes it, and the end of occupancy removes it. A saved
destruction selection is not a second occupancy. For each actual position,
ordered visits prevent two current occupants; a later visit to a surviving
position follows the prior ordinary Vacate. Destruction access uses the
originals, whereas replacement-defined positions are different positions.

The lifetime proof shows that no current child occupancy needs a defining
particle after its Vanish. Vanish adds no relationship and cannot create a
cycle. Several eligible Vanishes may therefore execute independently.

## Equality of final effects

All position projections and direct-particle operation sequences match those of
the serial interpretation. Consequently their final occupancies, particle
identities, and assigned qualities agree. Ending preservation removes the same
incoming occupancy after its required uses, regardless of which of the Vacate
and last direct Move finishes first.

Position-defining relationships remain unchanged through Moves. These identities
and final occupancies determine the same final relative arrangement. The set of
children moving transitively with a parent need not be the same in different
orders: a child can be created or moved independently before or after the parent
Move. That difference in intermediate participation does not change the final
relative arrangement.

This proof compares per-position effects directly. It does not connect all legal
schedules by adjacent exchanges. Opposing Move-and-return pairs provide legal
orders between which no such legal exchange sequence exists.

## Finite completion and runtime choices

A prefix can have enabled endpoints and no current cycle yet admit no complete
execution of the remaining occurrences. Local enabledness alone therefore does
not justify permission to extend it.

The finite choice search accepts a prefix exactly when some complete order
extends it and satisfies all ordinary and relationship requirements. Selecting
an extension accepted by that test preserves existence of a complete
continuation. Induction over accepted extensions gives a safe finite execution.

Conversely every complete legal order witnesses successful choices for each of
its prefixes. No such order is excluded by the test. Permission for competing
operations must be coordinated: tests against the same old prefix cannot
independently authorize a combination absent from every permitted completion.

This establishes exact sequential order semantics for logical operation effects.
A runtime implementation must preserve those permission decisions when
operations overlap; merely testing both effects against an earlier arrangement
does not implement this semantics.

## Dependency necessity is separate

The ordinary graph is transitively minimal by the Comparison proof. This does
not show that every ordinary edge is semantically necessary when relationship
conditions also apply.

An ordinary cover edge can be placed adjacently in a linear extension of
ordinary precedence, but that extension need not satisfy the relationship
conditions. Reversing it therefore cannot automatically serve as a reachable
semantic necessity witness. Likewise, two relationship conditions can jointly
imply another without either doing so alone.

Safety and exactness of the accepted orders do not depend on irredundancy of
their representation. A complete minimality result must analyze the combined
conditions rather than importing the ordinary adjacent-cover argument.

## Unbounded executions

Every completed finite prefix preserving the endpoint, lifetime, and
relationship invariants is safe at each of its steps. This local safety
statement does not supply an algorithm deciding whether an infinite future can
complete, nor does acyclicity imply termination.

Even arbitrarily long finite safe prefixes need not complete an infinite
operation set: a scheduler can continually postpone one enabled operation. An
eventual-execution conclusion must state and justify a progress condition in
addition to safety.

For a particle with a finite set of required uses, unrelated unbounded work adds
no lifetime prerequisite. For one with infinitely many required future uses, no
finite prefix can safely execute its Vanish while retaining all those uses.

The finite search theorem applies to a specified finite occurrence set. Applying
it to modular or expanding execution requires a separate correspondence showing
which future constraints a boundary preserves; truncating the occurrence set and
assuming the omitted constraints irrelevant is not that correspondence.
