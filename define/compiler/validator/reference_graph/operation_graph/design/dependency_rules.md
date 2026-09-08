# Particle Operation Dependencies

This is a conceptual guide to the
[Particle Operation Dependency Graph](../../../../../spec/spec.md#the-particle-operation-dependency-graph).
The specification defines the rules; this document explains how they fit
together.

The central idea is: **an operation waits for what it needs, and an operation
that removes something waits for its uses.**

## What operations need

There are two kinds of requirements:

- **Particle requirements:** A particle must exist to move it directly or to
  access its assigned qualities. Those qualities include its positions and
  actions.
- **Position requirements:** A position must have the required occupant—or be
  empty.

Specifically:

| Operation | Requirement                                                            |
| --------- | ---------------------------------------------------------------------- |
| Create    | The destination is empty.                                              |
| Move      | The source holds the particle being moved; the destination is empty.   |
| Vacate    | The selected particle occupies the selected position before Vacation.  |
| Vanish    | The particle has vacated and no remaining operation requires it alive. |

Position References also require their intermediate positions to have the
appropriate particles. Access through an implied or interface position does
**not**, by itself, require the particle to remain at the position through which
the caller accessed it. The same operation may nevertheless have another
reference that requires that occupancy.

These requirements concern particular particles and positions, not just their
names. A replacement particle has its own assigned positions; those are not the
positions assigned to the previous particle, even when the same written name can
refer to them.

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
- The most recent Move directly moving that particle, if any. Earlier direct
  Moves are already dependencies of the later one.
- Every Create, Move, or Vacate whose Position References use its assigned
  qualities, including through intermediate positions.

These are the original particle identities selected when processing the
operations. Include uses in constructors, destructors, and actions they
transitively trigger. Moving with another particle transitively does not, by
itself, require a particle to remain alive after Vacation.

An operation's use of assigned qualities needs no separate Vanish candidate when
the same operation requires the particle to occupy an intermediate position
without relying on the occupancy preserved for destructors. The position
dependencies already put that operation before the particle leaves that
position, and therefore before its Vacate. This also applies to an implied or
interface reference when the same operation has that intermediate-position
requirement.

A candidate may be removed when another candidate for that Vanish already
depends on it. In particular, when recording an operation that needs the
particle, its Collection candidates may be removed from that particle's Vanish
candidates, even if Comparison omitted them from its direct dependencies.

Apply Comparison to those candidates. Vanish has no Position References, does
not change setters or readers, and does not become another operation's
dependency. Reusing a vacated position therefore need not wait for its previous
particle to vanish.

## When Vacate and Vanish can be combined

The two may be combined when every other operation that requires the particle or
its assigned qualities is already a direct or indirect dependency of its Vacate.
The combined operation has the Vacate's dependencies and takes its place for
operations that depended on it. Otherwise, combining them could delay reuse of
the position unnecessarily.

This can be known before constructing a separate Vanish whenever both of these
conditions hold:

- Every operation using the particle's assigned qualities also requires that
  particle to occupy an intermediate position, without relying on occupancy
  preserved for destructors.
- Every Move directly moving the particle is less recent than its Vacate.

Both checks must include all operations, including those in transitively
triggered actions that have not yet been processed. Merely having no destructor
on the particle is not enough: constructors and other actions can also use its
assigned qualities without requiring its ordinary occupancy.

Failing these checks does not rule out combination. After Comparison, a Vanish
whose only direct dependency is its Vacate can still be combined with it.

## Scope

Recency describes the specified serial execution, not runtime execution order.
Actual execution follows the resulting dependencies.

This explanation describes whole-program dependencies. For modular calculation
within an action, the spec also provides the Action Parent Rule when Collection
and Comparison identify no dependency for a Create, Move, or Vacate.
