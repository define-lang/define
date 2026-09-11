# Requirements Derived from Particle Operations

## Premises and scope

The premises are the specification's Particle Operation effects, Identifying
Particles and Positions, Processing Destructor Operations, and Relationship
Conditions. Position requirements and particle requirements distinguish
occupancy from existence; neither category replaces the relationship conditions.

## The position identified by a reference

Resolve each written reference in the specified serial interpretation. Its
intermediate positions contain the particles supplying the following qualities.
This determines one particular final position. An implied reference begins with
a quality of the action's parent particle. An interface reference identifies a
declaration of the assigned action; a position declared in an Action Statements
Block additionally identifies its particular Action Execution.

The operation retains this identity during reordered execution. It does not
observe those intermediate positions again. Thus a caller's written chain and a
callee's implied reference can identify the same position and impose the same
final-position requirements. The spelling of the chain supplies no additional
runtime occupancy requirement.

Position identity includes its defining particle. Interface positions persist
across executions of the assigned action; positions declared in an Action
Statements Block are distinct for each execution. A replacement's defined
positions differ from the original particle's positions. Moving the original
particle changes their location, not their identity or defining particle.

## Final-position occupancy and particle identity

A Create requires an empty target and brings its fresh particle into existence
there. A Move requires its selected particle at the source and an empty target.
It removes that source occupancy and fills the target with the same particle.
The source and target differ; destination constraints were checked in the serial
interpretation, and the Move does not change the particle's qualities.

A Vacate releases the selected ordinary occupancy. Simultaneous Transitive
Destruction selects all its particles from one serial state, not from successive
runtime lookups after earlier Vacates. Source-ordered visits to the same actual
position must remain ordered, even when exchanging whole visits would leave the
same final vacancy.

During destruction, the original occupancy is shared by the destructors using
it. Vacation need not end that preserved occupancy. It ends after both the
Vacate and the last direct Move requiring it, across all sharing destructors.
The last Move must fill its target legally before preservation ends.

## Existence requirements

A Create needs its target position's defining particle. A Move needs the
particles defining its two endpoints and the selected particle. A Vacate needs
the selected position's defining particle and the selected particle. For a
position defined by an action, use that action's parent particle. Initially
available positions are treated as specified by Starting Define Programs.

These requirements apply to local, interface, implied, and chained references
alike. They do not propagate to every ancestor. Accessing a particle's own child
position requires that particle to exist, but does not require it to occupy its
former incoming position.

Vanish follows the particle's Vacate and all operations requiring its existence.
An ancestor Move does not separately use every transitive child's existence.
Conversely, an ordinary written chain can identify a child's position whose
defining particle must remain alive after Vacation; this is not limited to
destructor references.

## Spatial movement versus occupancy of a defined position

Let P define position q. Moving P moves q, including when q is empty. It does
not change q's occupant relative to P. Recording the defining particle of each
position and the direct occupancy of each particle therefore describes the
transitive spatial effect of a Move without changing every descendant record.

This distinction permits child-position operations to overlap ancestor Moves. It
does not make disjoint Move endpoints sufficient for independence: those Moves
can create a circular transitive relationship. The
[relationship argument](../theorems/relationship-ordering.md) handles that
additional restriction.

## An exchange proved from these requirements

Let P occupy `source`, let `destination` be empty, and let P define an empty
`/marker`. Consider creating a particle in that marker position and moving P
from `source` to `destination`.

Both operations require P to exist. The Create needs the marker position empty;
the Move changes neither that occupancy nor its defining particle. The Move
needs P at its source and its destination empty; the child Create changes
neither. A fresh child has no occupied descendant positions, so this particular
exchange introduces no circular relationship. Both orders create the same
particle relative to P and leave P at the same destination.

The result applies whether the marker is identified through an implied
reference, through `source::/marker` before the Move in source order, or through
`destination::/marker` afterward. Resolution identifies the position in each
case. The operation does not wait for the parent Move merely to traverse its
written destination name.

Likewise, an ordinary Move of a selected child can begin from that child's
identified position before an ancestor's Move. Its target and all relationship
conditions still matter. Identity resolution does not waive those conditions.

## Ancestor destruction does not extend every lifetime

Suppose P defines a position occupied by Q, and Q defines an empty leaf
position. A constructor creates R in the leaf position, and the caller's later
destruction selects P, Q, and R.

The leaf Create requires Q, not occupancy of Q's incoming position or existence
of every ancestor of Q. R's Vacate follows R's Create. Q's Vacate may precede
the leaf Create while Q remains alive for it. Once Q's incoming occupancy is
released, P need not remain alive merely because the leaf Create is pending.
Actual destructor operations can independently require P or Q to remain alive.

These conclusions do not order the simultaneous Vacates by parent/child names.
Each requirement comes from the selected position or particle on which an
operation acts.

## Scope of exchange arguments

Independent occupancy effects commute in the auxiliary componentwise model. That
fact proves equality of their effects, not that every intermediate particle
arrangement is permitted. The full scheduling argument must check relationship
conditions separately, including choices with no legal adjacent exchange path
from source order.

No unspecified value observations or external-call semantics are premises.
