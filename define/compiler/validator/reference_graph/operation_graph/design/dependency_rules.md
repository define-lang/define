# Particle Operation Dependencies

This is a conceptual guide to the
[Particle Operation Dependency Graph](../../../../../spec/spec.md#the-particle-operation-dependency-graph).
The specification defines the rules; this document explains how they fit
together.

The central idea is: **an operation waits for what it needs, and an operation
that removes something waits for its uses.**

## What operations need

There are two kinds of requirements:

- **Particle requirements:** A particle must exist to access its assigned
  qualities.
- **Position requirements:** A position must have the required occupant—or be
  empty.

Specifically:

| Operation | Requirement                                                            |
| --------- | ---------------------------------------------------------------------- |
| Create    | The destination is empty.                                              |
| Move      | The source holds the particle being moved; the destination is empty.   |
| Vacate    | The selected particle occupies the selected position before Vacation.  |
| Vanish    | The particle has vacated and no remaining operation requires it alive. |

Written position references also require their intermediate positions to have
the appropriate particles. Direct implied access does **not** require the
particle to remain at the position through which the caller accessed it.

Moving a particle moves its defined positions, including empty ones. It does not
fill or empty those positions relative to that particle.

## How position dependencies are calculated

Process Creates, Moves, and Vacates in Particle Operation Recency order. Each
position has a **setter**, the last operation that filled or emptied it, and
**readers**, operations since that setter which used it as an intermediate
position. A child position initially has its parent particle's Create as its
setter; other positions initially have no setter. Readers are initially empty.

For each operation, collect candidates:

1. **Wait for creation:** Collect the Create of each particle whose assigned
   qualities the references use.
2. **Wait for the required occupancy:** Collect the setter of each intermediate
   position and of a Create's or Move's target position, when one exists.
3. **Wait for preceding uses:** For a Move's source or a Vacate's position,
   collect its readers. If there are none, collect its setter instead.
4. **Combine everything:** For a Move, this includes both references, the
   source, and the destination.

Some candidates are already covered by others: a setter or reader of a
particle's child position covers that particle's Create, provided they are
different operations; a collected reader of an intermediate position covers that
position's setter. Determine these omissions from the combined collection.

Then apply **Comparison**: examine the remaining candidates with dependent
operations before their dependencies. Keep a candidate unless an already-kept
candidate depends on it, directly or indirectly. The kept candidates are the
operation's dependencies. This is part of construction, not a later
graph-minimization pass.

Finally, record the operation as a reader of its intermediate positions. For
each position it fills or empties, make it the setter and clear its readers. A
reader may also be removed when another reader already depends on it.

## What changes for destruction

- **Vacating a position and ending a particle’s existence are different
  events:** Vacate and Vanish, respectively.
- Simultaneous Transitive Destruction selects the particles together. Their
  Vacates have identical recency and do not order one another merely because
  their particles have parent/child relationships. Transitive child Vacates have
  no Position References.
- Ordinary code may reuse the vacated positions.
- Destructors access the original particles’ **shared, changing state**, not
  separate copies. The selected particles' Vacates do not change the occupancy,
  setters, or readers used by destruction work on their child positions.
- Destructor changes must wait for preceding uses of the state they change.
- Where destructors conflict, the compiler may choose their ordering;
  independent operations need not wait for a whole destructor to finish.

## When a particle may vanish

After constructing the Create, Move, and Vacate dependencies, collect these
candidates for each particle's Vanish:

- Its Vacate.
- Every Move directly moving that particle.
- Every Create, Move, or Vacate whose Position References use its assigned
  qualities, including through intermediate positions.

These are the original particle identities selected when processing the
operations. Include uses in constructors, destructors, and actions they
transitively trigger. Moving with another particle transitively does not, by
itself, require a particle to remain alive after Vacation.

Apply Comparison to those candidates. Vanish has no Position References, does
not change setters or readers, and does not become another operation's
dependency. Reusing a vacated position therefore need not wait for its previous
particle to vanish.

If a Vanish's only direct dependency is its Vacate, the two may be combined. The
combined operation has the Vacate's dependencies and takes its place for
operations that depended on it. Otherwise, combining them could delay reuse of
the position unnecessarily.

## Scope

Recency describes the specified serial execution, not runtime execution order.
Actual execution follows the resulting dependencies.

This explanation describes whole-program dependencies. For modular calculation
within an action, the spec also provides the Action Parent Rule when Collection
and Comparison identify no dependency for a Create, Move, or Vacate.
