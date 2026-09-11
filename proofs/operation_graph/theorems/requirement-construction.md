# Construction from Operation Requirements

## Scope

This argument proves ordinary Collection, Comparison, and Recording the
Operation's Effects. Particle lifetime is treated in the
[Vanish proof](vanishment-proof.md), and restrictions on parent relationships in
the [relationship proof](relationship-ordering.md).

Fix finitely many resolved operations from a valid serial interpretation,
including a permitted order of operations in sharing destructors. Exclude the
Action Parent Rule. Edges below point from operations to their prerequisites.
Identical-recency Vacates acquire no ordering from their enumeration.

## Position identities and setters

A record belongs to an actual position, not its written reference. Its identity
includes its defining particle and declaration; interface positions additionally
identify the assigned action, and positions declared in an Action Statements
Block distinguish Action Executions. An ancestor Move changes none of these
identities. A replacement particle supplies different positions.

Initially the setter is the defining particle's Create, including the parent
particle of an action defining the position. An initially supplied position
without a Create has no initial setter. Each operation filling or emptying the
position then becomes its setter. The record is therefore exactly the preceding
operation affecting that position in the processed interpretation.

There are no intermediate-reference readers: serial resolution identifies the
endpoints, and execution does not traverse those references again.

## Collection and occupancy completeness

A Create collects its target setter. A Move collects its source and target
setters. A Vacate collects its selected position's setter. Repeated collection
of one operation gives one candidate. An ordinary operation has at most two
distinct candidates.

For a fixed position, project the interpretation onto operations filling or
emptying it. Each consecutive pair is a candidate pair. Induction on projection
length shows that all earlier effects precede every later effect through this
relation. Conversely, each candidate pair orders effects on that same position;
it does not order an unrelated position merely because its name was used during
serial resolution.

The projection begins with the specified initial state. Induction along its
ordered effects supplies exactly the selected occupant or vacancy required by
each operation. Whole occupancy visits retain their source order, not just the
position's final state. A Move participates in two projections but remains one
operation.

## Required Creates are already reached

Induct on processed operations. A position's initial setter is its defining
particle's Create when that Create belongs to the calculation. Each subsequent
setter collects its predecessor, so every operation on the position follows the
same Create. This supplies the defining particles of all endpoints.

An occupied source's setter is either the selected particle's Create or a Move
placing it there. That earlier Move already follows the particle's Create by
induction through its own source setter. Thus a Move or Vacate also follows the
selected particle's Create. Initially supplied particles use their stipulated
existence instead.

This proof does not use Vanish completion or relationship conditions. Endpoint
setters suffice without separately collecting these Creates.

## Simultaneous and nested destruction

Selection retains each particle and its particular position from the common
serial state; it introduces no runtime traversal through ancestors. Different
selected particles have distinct positions, so equal-recency Vacates query and
update different records. Their enumeration changes none of their candidates.

When a position's defining particle is selected for the same destruction,
Processing Destructor Operations preserves its original setter for destructors
and their triggered actions. Subsequent operations share and update that record,
rather than receiving independent copies or a barrier on the selected Vacate.
The setter invariant applies to their sequence starting at the inherited
original setter.

When the defining particle is not selected, the same position survives. A
following fill of it must follow its Vacate. Destroying a temporary child
therefore does not let a second temporary particle bypass the first Vacate.
Replacing a destroyed defining particle differs: the replacement supplies new
position identities and initial setters.

The [retained-state proof](retained-state-proof.md) distinguishes logical
vacancy from preserved incoming occupancy. Ending preservation is not an extra
setter changing another position's projection. Relationship periods account
separately for its effect on parent relationships.

## Comparison invariants

Examine candidates in topological order with dependents before prerequisites.
Maintain two invariants:

1. Retained candidates are pairwise unrelated by reachability.
2. Every examined candidate is retained or reached from a retained candidate.

Skipping a candidate preserves both invariants by the skip condition. When
adding one, that test excludes reachability from retained candidates, and the
scan order excludes reachability in the opposite direction. Starting from the
empty set proves both invariants by induction.

At completion, a candidate reached by another candidate was covered by an
earlier retained candidate and skipped. A candidate reached by no other
candidate could not be skipped. The scan thus retains exactly the maximal
candidates under prerequisite reachability. This characterizes its result; it
does not introduce a transitive-minimization pass.

## Reachability preservation

Induct on the constructed prefix. Earlier reachability is unchanged because only
outgoing edges from the new operation are added. Every collected candidate is
retained or reached from a retained candidate by the second scan invariant. The
new operation therefore reaches every collected candidate. Each retained edge is
itself a candidate edge, so no additional reachability is invented.

This establishes equality with the full setter candidate relation independently
of minimality. In particular all occupancy and creation-supply paths proved
above survive Comparison. The scan argument also applies to optional pruning of
Vanish candidates before their separate last-candidate tests.

## Acyclicity and transitive minimality

Every ordinary candidate is already processed, including inherited destruction
setters. Equal-recency Vacates do not collect each other. Edges strictly
decrease processing index and therefore cannot cycle.

Suppose a retained edge from the new operation to A had another path to A. It
would start at another retained candidate B, followed by a path from B to A in
the preceding graph. That contradicts the first scan invariant. An older edge
cannot gain an alternative path through the new operation because edges point
backward. Induction proves ordinary transitive minimality without assuming
semantic completeness or safety.

The generic scan and incremental graph results in `comparison.lean` and
`effect_graph.lean` formalize this graph-theoretic argument. Applying them to
source requires the setter correspondence above; a model treating written
intermediates as runtime readers has different candidates.

## Ordinary versus combined minimality

The preceding minimality result concerns ordinary edges. Relationship conditions
can imply additional ordering and can make an ordinary edge unnecessary in the
combined representation. The scan proof does not establish semantic irredundancy
after those conditions are added.

Likewise, not every linear extension of ordinary precedence is a legal particle
arrangement. The relationship proof supplies that separate check. Necessity
arguments using adjacent exchanges must not assume that an exchange also
respects relationship conditions.
