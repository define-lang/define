# Vacancy Selection and Shared Retained State

## Scope and premises

The premises are Simultaneous Transitive Destruction, Destructors and
Destruction Ordering, Destructor Action Guarantees, and the graph rules for
identified positions and Processing Destructor Operations. No order between
simultaneous Vacates is inferred from an enumeration or from parent/child names.

Distinguish three observations:

1. Which ordinary occupancy the Vacate releases.
2. Which particular particle and position the destruction selected.
3. Where the original particle currently is during its preserved destruction
   uses.

The selection is fixed by the serial interpretation. The current position can
change through destructor Moves. It is shared by all destructors using that
particle, not copied separately for each destructor.

## Selection is not a runtime barrier

A destruction selects particles from one serial preceding state. Each selected
particle gets its own Vacate. Identifying Particles and Positions makes this a
selection of particular objects, not a repeated traversal at runtime.

Consequently the Vacates do not require their entire group to coexist at a
runtime instant before any member can execute. A child's Vacate follows the
operation supplying that child's occupancy. It does not require every other
selected child to have been created or vacated. Similarly, the parent's Vacate
does not wait for a delayed constructor Create on a position belonging to an
already-created child.

Both explicit and transitive Vacates use their identified positions. Neither
requires a new lookup through all its serial ancestors. A parent Move therefore
does not order a child's Vacate merely because the child's displayed name uses
the Move's destination.

## Supplying and changing original occupancy

A destructor must receive the original state immediately preceding destruction.
For each original position, its last preceding setter supplies that state. A
destructor's first operation on the position follows that setter.

Subsequent operations use the same position and its changing setters, in the
chosen permitted ordering of sharing destructors. A destructor Move changes its
source and target occupancy just like another Move. Its source is not a snapshot
that remains occupied after another destructor has moved the particle.

For Particle Operations there are no read-only final-position occupancy uses:
Create and Move target fill the position they require empty; Move source empties
the position it requires occupied. Vacate is the selected ordinary release.
Intermediate references resolve identities rather than adding runtime readers.
Thus the setter chain preserves prior ordinary occupancy uses without an
additional collection of intermediate-position readers.

In particular, a destructor Move of a particle follows that particle's last
ordinary direct Move. It cannot take the particle from a source before the
ordinary Move supplies it. Operations on the particle's child positions are
different: they need the defining particle to exist, but need not wait for its
incoming occupancy to remain unchanged.

## Ordinary release and preserved occupancy

For a position defined by a selected particle, ordinary Vacation and the
occupancy used by destructors are different observations of the originals. The
Vacate does not change the setter used by those destructor operations. This
allows the Vacate and an otherwise independent destructor Move to execute in
either order.

The ordinary selection is not another current incoming position. If a destructor
has moved the particle, the pending Vacate still releases its selected ordinary
occupancy; it does not move the particle back, select a replacement, or give the
particle two current positions.

There is only one current incoming occupancy association for the original
particle. Before the final ordinary setter it follows ordinary changes; after
that setter it follows the shared destruction changes. This association, not the
saved selection, participates in the relationship conditions.

## When preservation ends

The specification ends preserved occupancy after both its Vacate and every
direct Move requiring that occupancy during destruction. The direct Moves of one
particle form a chain: each uses the source supplied by the preceding Move,
including the chosen ordering of sharing destructors. Completion of the last
direct Move therefore implies completion of all earlier ones.

The end is the conjunction of the Vacate and that last Move, or just the Vacate
when there is no such Move. It is not necessarily one fixed predecessor in every
runtime order: the Vacate can occur first or last. It also is not the particle's
Vanish. Uses of the particle's own positions can keep it alive after its
incoming occupancy has ended.

A Move must first produce its specified occupied target without creating a
cycle. If it is also the last direct destruction use and Vacation has already
occurred, preservation ends afterward. Skipping the occupied result would
replace the Move with source emptying alone, contrary to its specified effect.

A destructor's private local position is relative to the action's parent
particle. Moving a child from an implied position to such a local position does
not detach it from that same parent. Only a change of defining parent or the
actual end of occupancy removes the direct parent relationship.

The [relationship-period argument](relationship-ordering.md) models the end by
the later of the two required completions and distinguishes the final Move
effect from the subsequent release. Its interval characterization therefore
applies to these retained associations.

## Replacement and reuse

If a destroyed particle P defines q, replacing P does not give the replacement
P's original q. Subsequent source references through the replacement identify
the replacement's own positions. Earlier resolved operations and destruction
work still refer to the originals.

If instead P survives the destruction of a particle at q, reuse concerns the
same q and follows that particle's Vacate. A destructor assigned to the
destroyed child accesses its own qualities and positions, not its surviving
parent's incoming q merely because that was the child's former location. Serial
resolution cannot invent a reference from that child to its parent. Keeping the
child's own positions available therefore does not keep q occupied.

These cases preserve single occupancy without introducing per-destructor copies.
They also distinguish reuse of an actual position from reuse of a written
spatial name after replacement.

## Nested destruction

A destructor may create a temporary particle in an initially empty contracted
position or in one of its local positions, then destroy it. Its new destruction
selects that temporary particle and its then-current children from the serial
state of those operations.

The position containing the temporary particle belongs to the surrounding
destructor's parent particle, not to the temporary particle. Its defining
particle survives this nested selection. Reusing that position therefore waits
for the temporary particle's Vacate, while the temporary particle's own
destruction work can continue using its own defined positions.

Apply the same selection and setter construction to each further destruction. A
later temporary replacement has a fresh identity. Destructor Action Guarantees
do not permit destroying an originally occupied contracted particle and
substituting a fresh one: the guarantee requires the original identity.
Consequently nested destruction does not silently turn the retained original
into a replacement or create an additional destruction of that same original.

This argument follows the serial nesting to identify objects. It adds no runtime
barrier between independent operations at different levels.

## Final restoration of an original particle

Fix an original particle Q selected at position q. In the serial interpretation
of its destruction, each destructor that directly moves Q must obtain Q through
one of that destructor's contracted positions, possibly after moving another
original particle. Requirements Follow Particles keeps the identity of those
contracted positions through these Moves.

Destructor Action Guarantees requires the same original particle at the same
contracted position when that destructor completes. Thus its complete operation
sequence restores Q's occupancy at q. The argument concerns the identified
position, not its spatial name: q's defining particle may itself move.

Compose the destructors in the chosen permitted serial order. Each receives the
same original contracted state and restores it. Induction over this sequence
shows that the final direct Move of Q, if any, returns it to q. Transitively
triggered actions are included in their triggering destructor's complete effect.
Otherwise that destructor would fail its own guarantee.

This is not a runtime restoration barrier. Individual direct Moves retain their
source-setter ordering, so their final member still has that same identified
target in any permitted schedule. Q may vacate before it, and its incoming
occupancy then ends immediately after its legal target effect.

If q's defining particle is not selected for this destruction, none of its
selected particles' destructors can reach outward to move Q from q merely by
being assigned to Q or its descendants. Q's ordinary Vacate therefore releases q
without preserving that incoming occupancy for such a Move. This also applies to
temporary particles destroyed within an outer destructor: the outer destructor
does not become a member of the temporary particle's destruction.

## Lifetime and scheduling consequences

Each operation on an identified position requires its defining particle. Each
direct Move requires the moved particle. Vanish waits for all such uses and the
particle's own Vacate. These are individual operation dependencies, not
whole-destructor completion dependencies.

For example, a child can vacate, complete the last destructor Move preserving
its incoming occupancy, and remain alive for a later operation on its own leaf
position. Its former parent relationship has ended, so it must no longer block a
parent Move solely on the basis of that former relationship.

Conversely, restoration of the child into a position of one of its current
transitive children is prohibited even if preservation would end immediately
afterward. Another Move or Vacate can remove that relationship first; Vanish is
not required merely to release occupancy.

The ordinary setter chains determine the correct shared occupancy at each
operation. The lifetime dependencies determine which defining particles exist.
The relationship conditions separately determine which interleavings preserve
acyclic particle arrangements and admit completion. None of these three
arguments substitutes for either of the others.
