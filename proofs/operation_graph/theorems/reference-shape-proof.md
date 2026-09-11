# Particle Relationships and Move Legality

## Scope

The specification's Identifying Particles and Positions separates serial
reference resolution from execution. A proof cannot use the original spelling of
a Move's references to rule out cycles in every reordered execution. The runtime
positions may have moved since those references were resolved.

The relevant premises are position identity, the Particle Operation effects,
single occupancy, and the prohibition on occupying one's own transitive child
position. Relationship Conditions supply the additional ordering restrictions.

## Representation

Associate each position with its defining particle. A position defined by an
action uses that action's parent particle. Its assigned action and declaration
identify an interface position; an Action Execution additionally distinguishes a
position declared in the Action Statements Block. Local positions are not
unrelated locations whose lifetime or movement can be ignored.

For each occupied particle, record its one incoming position. Composing this
association with the position's defining particle gives a directed association
from child particle to parent particle. The initial view point position has no
such defining particle.

This is a representation of the particles' relative spatial relationships, not
of name traversal. Empty positions still have their defining particle and move
with it. A particle's descendants are determined from current occupancy, not
from a fixed list taken from the serial interpretation.

## Single occupancy

Initially the supplied position is empty. Create requires an empty target and a
fresh particle, so it cannot introduce two occupants of one position or put one
particle in two positions.

Move requires the selected particle at its source and its target empty. It
replaces the particle's one incoming position, emptying the source. Every other
direct occupancy stays unchanged.

A Vacate releases its selected ordinary occupancy. Preserved destruction
occupancy uses the original particle's one changing position, not a second copy
of that particle. Ending preservation removes that association; Vanish adds no
association. These observations separate single occupancy from circularity.

## Circularity

In a finite arrangement, a particle occupies one of its own transitive child
positions exactly when the direct child-to-parent associations have a directed
cycle. Following the associations from that particle returns to it; conversely a
directed cycle gives that prohibited transitive relationship.

Create introduces a fresh particle whose positions are empty. When the defining
particle exists, this cannot create a cycle. A Move can create one even when its
source and target are distinct, occupied and empty as required, and different
from another Move's endpoints.

For example, a child can move away from its parent while another Move puts that
parent in one of the child's positions. The parent Move cannot run before the
relationship has been removed. Resolving its destination identity does not make
that order legal.

The
[relationship-period theorem](relationship-ordering.md#exact-cycle-characterization)
proves that the specified conditions exclude exactly the orders with a circular
arrangement. It includes same-parent Moves, preserved destruction occupancy, and
a final Move's occupied result before preservation ends.

## Consequence for scheduling

A respecting order of the ordinary occupancy and lifetime dependencies has the
correct endpoint requirements. It is a permitted particle execution only if its
relationship conditions also hold. Neither ordinary dependency acyclicity nor
commutation of relative occupancy assignments can replace that check.

Different permitted complete orders need not be connected by legal adjacent
exchanges. Consequently geometric safety is proved from the interval
characterization at every operation, separately from the componentwise proof of
final-effect equality.
