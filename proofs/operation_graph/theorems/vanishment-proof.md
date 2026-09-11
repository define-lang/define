# Particle Lifetime and Vanish

## Scope

The premises are the Particle Operation effects, Identifying Particles and
Positions, Recording Vanish Information, Completing Vanishes, and Processing
Destructor Operations. The Action Parent Rule is excluded.

Vanish ends existence, not occupancy. Its prerequisites must protect the
particles actually used by pending operations, without adding a requirement to
keep every serial ancestor alive.

## Exact lifetime requirements

For each particle P selected for destruction, let L(P) contain its Vacate and
every operation requiring P to exist. The specification determines these uses
from the identified operation effects:

- A Create needs the particle defining its target position.
- A Move needs the particle it moves and the particles defining its source and
  target positions.
- A Vacate needs its selected particle and the particle defining its selected
  position, including for a transitive Vacate.
- A position defined by an action uses that action's parent particle.

Initially available positions with no defining particle add no such use.
Repeated interface accesses use the same position of the assigned action;
positions declared in an Action Statements Block identify separate executions.

These requirements do not include every particle named during serial reference
resolution. A reference identifies its final position before scheduling; its
intermediate occupancy need not be observed again. Nor does a Move use each
particle that happens to move transitively with it.

The selected identities are fixed by the serial interpretation. Reordering
cannot remove a pending requirement by silently selecting a replacement or
treating its old written path as inaccessible.

## Last direct Move

Consecutive direct Moves of P use the occupancy supplied by their predecessors.
The ordinary setter chain orders them. Destruction operations inherit the
original setter and share its subsequent changes; Vacation does not reset their
chain.

Consequently the last direct Move follows every earlier direct Move of P.
Recording all these Moves or retaining just their last member gives the same
predecessor closure for Vanish. Moves of an ancestor are not members of this
chain.

For the end of occupancy preservation, the last destruction Move and the Vacate
are both required. For Vanish, all remaining uses of P's own positions are
required too. The two completion conditions must not be identified.

## Sufficiency of the collected uses

Insert P's Vanish after every member of L(P). No subsequent operation requires P
or a position it defines: such an operation would itself be an unfinished
member. P's Vacate has occurred, and every direct Move preserving its incoming
occupancy has finished, so P has no remaining incoming occupancy.

The positions defined by P cannot retain a current occupant at this point.
Consider any visit to such a position. Its ordinary emptying is a Move or Vacate
requiring P, and therefore precedes P's Vanish. If that visit is preserved for
destruction, its original Vacate and final direct restoration both require P.
The
[restoration argument](retained-state-proof.md#final-restoration-of-an-original-particle)
is important here: the final restoration targets the same selected position, so
its defining particle is the one required by the Vacate. This is not an
assumption that an arbitrary last Move happens to return to that position. The
end of preservation therefore also precedes P's Vanish. A temporary visit to a
different position must end by its source emptying or its own automatic Vacate.
Destructor Action Guarantees exclude leaving a different particle in an
originally occupied contracted position or retaining a temporary occupant in one
required to be empty.

These cases exhaust visits to P's positions in the finite resolved source
execution. Their setter order preserves the same visits in reordered execution.
Thus no current child occupancy loses its defining particle when P vanishes.

Vanish changes no ordinary or preserved occupancy of another particle. It cannot
create a cycle, select a replacement, or erase a pending operation. The
occupancy and relationship arguments therefore remain valid after its insertion.

## Necessity of the uses

If P's Vacate has not occurred, Vanish violates its specified prerequisite. If
an operation requiring P is still pending, that operation cannot execute after P
vanishes: it requires P or a position defined by P to exist. A fresh replacement
cannot supply the same identity.

Thus completion of L(P) is necessary as well as sufficient for inserting Vanish
while preserving the remaining resolved operations. This is a statement about
the required uses. It is not by itself a proof that every separately drawn
dependency edge is necessary in a graph with alternative relationship
conditions.

## Independent insertion

Apply the preceding argument successively to Vanishes of different particles.
Before a Create, Move, or Vacate executes, none of its required particles can
have vanished, because that occurrence belongs to their lifetime collections.
After each Vanish, no current occupancy or pending use needs the removed
particle.

The requirements were fixed before insertion. An earlier Vanish cannot make a
later Vanish legal by deleting one of its pending requirements. Therefore
multiple Vanishes can be inserted independently once their own prerequisites
hold, without ordering Vanishes by parent and child names.

A permitted complete order of Creates, Moves, and Vacates can always be extended
by appending its Vanishes. This proves that terminal lifetime operations remove
no order of the existing operations; it does not instruct the implementation to
delay them all.

## Direct construction of semantically minimal Vanish dependencies

Fix the complete finite family T of permitted orders of Creates, Moves, and
Vacates. Its ordinary dependencies and relationship conditions are constructed
without Vanishes. The earlier insertion result shows that this family is
unchanged by adding the required Vanishes. In particular it is not defined by
assuming the Vanish dependencies now being calculated.

Let C be one Vanish's candidate set. It is finite and nonempty because it
contains the selected Vacate. Define K to contain exactly the candidates that
are last among C in at least one order in T. This is the specification's
candidate test: for A, require every member of C other than A to precede A and
ask the exact finite completion question. The test is true precisely when such
an order witnesses A's membership in K. Its added precedences are constraints of
that query, not additional runtime dependencies.

### Completeness

Take any order in T. Its last member of C belongs to K, using this very order as
the witness. Therefore inserting Vanish after every member of K places it after
the last member of C, and hence after all of C. Conversely, inserting it after
all of C certainly places it after K. The two sets of prerequisites allow
exactly the same insertions in every permitted ordinary order.

This establishes completeness without appealing to dependency necessity. It also
shows why all candidates failing the test may be omitted together: none can be
the last outstanding candidate in any permitted order. There is no mutual
reliance on separately removing redundant edges.

### Necessity

For each A in K, choose a witnessing order in T with A last among C. Insert
Vanish just before A, after all other candidates. All other retained Vanish
dependencies are satisfied. Moving this Vanish there does not change an ordinary
dependency or relationship condition: it participates in neither and no other
operation depends on it.

If A is the selected Vacate, this insertion violates Vanish's required Vacation.
Otherwise A is a pending operation requiring the particle to exist. The
insertion makes that operation impossible without changing its identified
particle or position. The prefix preceding the premature Vanish is a prefix of a
permitted execution, so this is a reachable necessity witness, not merely a
permutation satisfying an unrelated graph.

Thus every retained edge is semantically necessary independently of the
completeness argument. Adding the other particles' Vanishes afterward preserves
the witness's ordinary prefix; they cannot supply a missing use or precede it on
behalf of this particle.

### Why ordinary maximality is insufficient

Two candidates can be incomparable in ordinary reachability while relationship
conditions force one before the other. More generally a candidate can be
followed by another candidate in every permitted order without one fixed
candidate always following it. The last-candidate test includes both cases. It
does not construct the cover relation of all universally required precedences or
perform a generic transitive minimization.

This argument relies on the terminal nature of Vanish. It does not apply
unchanged to a Move that itself affects the relationship conditions. Ordinary
edge necessity in that combined system remains a separate obligation.

## Ordinary Comparison as candidate pruning

For the ordinary dependency graph G, Comparison keeps the reachability-maximal
members of each Vanish's candidate set. Every omitted candidate is reached from
a retained one. It therefore cannot be last in any permitted order. Removing
these candidates before the last-candidate tests changes neither those tests'
result nor the permitted Vanish insertions.

New dependencies go from a Vanish to existing operations in the proofs'
dependency direction. No existing operation depends on a Vanish, and no Vanish
depends on another Vanish. It follows that:

1. Existing reachability is unchanged.
2. A new edge cannot participate in a directed cycle.
3. Existing transitively necessary edges remain so.
4. A new edge to a retained candidate has no alternative path: such a path would
   begin through another retained candidate that already reaches it. A candidate
   reached in this way cannot be last, contradicting its retention.

This proves transitive minimality of the terminal extension when G is
transitively minimal, independently of completeness of the lifetime collection.
The exact lifetime argument above supplies completeness and safety separately.

The generic graph results in `vanishment_graph.lean` concern terminal extension
by an ordinary antichain. The last-candidate proof supplies the separate
semantic necessity result. Its completeness is not a claim that the remaining
ordinary edges alone reach every omitted use: relationship conditions can be
essential to that ordering.

## Optional candidate pruning

Suppose recorded uses are pruned with Comparison before completion. Each removed
use is covered by a retained use. Later candidates only add to that coverage;
the already-calculated ordinary dependencies do not disappear.

Final Comparison therefore has the same reachability-maximal candidates whether
earlier pruning was performed or not. The same argument justifies keeping only
the last direct Move. This is the coverage lemma used by Comparison, not a later
transitive minimization of the completed graph.

In each permitted order, the last original candidate survives this pruning, and
it is also the last pruned candidate. Thus the possible last candidates, and
hence the specified Vanish dependencies, are unchanged too.

There is also a bounded partial pruning step. When recording an operation U as a
use of P, remove any earlier uses of P in U's collected ordinary candidates.
Collection makes U follow those candidates even when Comparison omits their
direct edges. Replacing them by U preserves coverage of every recorded use. The
same last-candidate argument therefore gives identical Vanish predecessors.

Ordinary Collection contains only endpoint setters. A Create or Vacate has one
endpoint and a Move has two. The
[setter induction](ordinary-requirements-proof.md#ordered-position-effects)
shows that these already supply every required Create. Testing at most two
candidates for removal requires no empirical candidate-count cutoff, regardless
of reference length. The final Vanish collection can still contain arbitrarily
many independent uses; this bound does not apply to it or to relationship
conditions.

## Vacate and Vanish remain separate

The specification constructs separate operations. An implementation may
represent them together only if every lifetime requirement already precedes
Vacate in every permitted order. Finding one schedule in which they happen
consecutively is insufficient.

In particular, a written reference is no certificate that its use precedes the
defining particle's Vacate. It identifies the position in source and can require
the defining particle after Vacation. Likewise, absence of destructors does not
imply that no pending child-position work needs that particle.

No combination optimization is used in the specified construction or the safety
argument here.

## Unbounded execution

For a particle with finitely many required operations, its lifetime collection
can be finite even when unrelated execution is unbounded. Such unrelated work is
not a prerequisite for its Vanish.

If a particle has infinitely many required future operations, it cannot Vanish
in a finite prefix while preserving all of them. This is a semantic statement,
not an algorithm for completing an infinite collection or a claim that the
finite relationship-choice search decides unbounded completion.
