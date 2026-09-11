# Relationship Conditions and Finite Execution Orders

## Scope and premises

This argument concerns the specification's Collecting Parent Relationships,
Relationship Conditions, and Choosing Among Permitted Orders. Fix finitely many
resolved Particle Operations and an ordinary precedence relation. The operation
identities, position occupancy order, and particle existence requirements are
those specified by Identifying Particles and Positions and Collection.

The result characterizes the additional restrictions needed to avoid circular
parent relationships. It does not assume that acyclicity of the ordinary
dependency graph implies acyclicity of particle relationships. Nor does it
assert that the collected relationship conditions are irredundant. Ordinary
dependency minimality and redundancy through alternative conditions are separate
questions.

## Relationships determined by operation effects

A position has its specified defining particle. A local or interface position
uses the parent particle of its Action Execution. Position identity and this
defining particle do not change when that particle moves.

When a particle occupies a position, associate it with that position's defining
particle. Moving the particle changes this one direct association; moving an
ancestor does not change it. The transitive parent relationships are the
transitive closure of these direct associations. This representation preserves
the relative positions of occupied and empty child positions without treating an
ancestor Move as separate changes to every descendant.

Follow one particle's Create and direct Moves in their resolved order. Its
source occupancy orders its successive direct Moves. The position-setter rules
also preserve the order of visits by different particles to the same actual
position. Therefore reordering operations subject to the ordinary requirements
does not exchange the direct Moves of this particle.

Merge successive portions of this sequence having the same defining parent.
These are exactly the specification's uninterrupted relationship periods. A Move
between positions of that same parent cannot break a cycle: the direct
association is unchanged. A Move to a different parent's position ends one
period and begins another.

For the last period, incoming occupancy ends at Vacation, except where it is
preserved for destruction. The specification then requires completion of both
the Vacate and the last direct Move using that occupancy. Earlier direct Moves
already precede that last Move. Operations on the particle's own positions do
not extend this incoming relationship; their lifetime requirements are separate.
A graph boundary with no recorded end is represented by an interval extending
beyond its operations.

## Intervals for a fixed total order

Fix a total order respecting ordinary precedence, and number its operations from
zero. A relationship beginning at operation of rank `i` begins at `2i`. A
relationship removed by a subsequent Move of rank `j` ends at `2j`. A
relationship ending after its Vacate and final direct Move ends at
`2 max(j, k) + 1`, omitting `k` when there is no direct Move. The extra unit
distinguishes the Move's occupied result from the subsequent release.

Use half-open intervals: the relationship is present at its beginning and absent
at its end. An initially available relationship begins before all operations; a
relationship without a recorded end continues afterward.

The intervals match the direct associations by induction over operation effects.
A Create adds its one new association. A Move removes its old association and
adds its new one; same-parent Moves leave the merged interval unchanged. A
Vacate removes an unpreserved association. A preserved association ends only
when both required events have finished. A Vanish adds no association and
requires its particle's preceding Vacation and uses to have finished.

In particular, a final destructor restoration can have a nonempty interval even
if its Vacate has already executed. Checking only the state after release would
omit its occupied result and would not implement the specification.

## Exact cycle characterization

A finite directed graph has a directed cycle if and only if it has a simple
directed cycle. To see the nontrivial direction, take a shortest nonempty closed
directed walk. Repeating an intermediate vertex would give a shorter closed
walk, so the chosen walk is simple.

Thus an arrangement is circular exactly when there is a simple cycle of parent
relationships whose selected periods are all present at that observation. The
periods for such a cycle are intervals on the same ordered line.

A finite family of nonempty half-open intervals has empty common intersection
exactly when one interval ends no later than another begins. Indeed, let `b` be
the latest beginning and `e` the earliest end. The common intersection is
`[b, e)` when `b < e`, and is empty otherwise. Choosing intervals attaining
these two extrema supplies the required pair. Missing finite endpoints cannot
supply that pair, matching the specification's exclusions.

The periods in a simple cycle concern distinct particles. One Particle Operation
directly changes only one particle's incoming relationship. Therefore the
operation ending one period cannot simultaneously begin another particle's
period. The endpoint inequality is exactly strict precedence between the end
event and the other beginning operation. For an end requiring a Vacate and a
last Move, it is exactly the conjunction that **both** precede the beginning.

Consequently the specification's alternatives for one cycle hold exactly when
its periods have no common intersection. Requiring them for every simple cycle
is equivalent to absence of circular arrangements at every operation effect,
including before occupancy preservation ends. This proves completeness and
sufficiency of the relationship conditions for this property, independently of
any claim of dependency minimality.

## Exact finite choice search

A successful search chooses one alternative per condition. Add all the
alternative's precedence pairs, not just one member of a conjunction. If the
result is acyclic, any topological order satisfies ordinary precedence and the
chosen alternative of every condition. The cycle characterization therefore
excludes circular arrangements throughout that order.

Conversely, a total order satisfying all conditions satisfies at least one
alternative of each. Following those alternatives in the search never creates a
precedence cycle: all their pairs belong to that total order. The search
contains this successful branch. Finitely many conditions and alternatives make
the search terminate. The characterization concerns exactness, not a polynomial
bound on the search.

For a fixed prefix, its order and the condition that all its members precede all
unfinished operations are ordinary precedence pairs. A satisfying total order
extends the prefix, and every satisfying extension includes these pairs.
Applying the preceding equivalence proves that the search accepts a prefix
exactly when it has a permitted complete extension.

This accounts for compatibility among alternative choices. Testing each next
Move only for absence of an immediate cycle would not establish the existence of
that complete extension.

## Operations that need no relationship permission

Assume the executed prefix has a permitted completion, and an operation O has
all its ordinary prerequisites completed. Choose any such completion. Move O to
the first place after the prefix while retaining the relative order of all other
operations.

This preserves ordinary precedence. No unfinished prerequisite of O exists, and
all operations depending on O were after it in the chosen completion. The
position-projection argument therefore preserves endpoint enabledness. The
following cases additionally preserve relationship legality:

- **Create:** O introduces a fresh particle P. Before O's original place in the
  completion, no other operation could have acted on P or a position it defines:
  those operations follow its Create. Thus advancing O adds only P's one
  incoming association, with no particle occupying a position defined by P
  during that intervening part. A cycle cannot pass through this new particle.
  Later arrangements are unchanged.
- **Vacate:** advancing O either removes an incoming association earlier or
  leaves it preserved until its required destruction Moves finish. It adds no
  association. Direct Moves that need the preserved occupancy still determine
  its release, so this change cannot invalidate their source requirements.
- **Vanish:** its retained lifetime candidates have completed. Since the prefix
  has a permitted completion, the last-candidate theorem implies that every
  required use has completed too. The lifetime proof shows that no occupied
  position still requires it. Advancing O removes no required object and adds no
  association.
- **Move not beginning a period in a possible cycle:** its earlier effect either
  leaves its parent association unchanged, removes it, or begins an association
  that belongs to no possible cycle. Its source-setter chain orders all other
  direct Moves of this particle, so none can occur in the intervening part.
  Advancing it can only shorten the preceding period and extend the new,
  noncyclic one. Shortening a period cannot introduce a cycle; extending a
  period outside every possible cycle cannot introduce one either. An earlier
  end of occupancy preservation likewise only removes an association.

Each case therefore has a permitted completion with O next. This derives the
specification's exemptions from the prefix-completion test; it does not assume
that endpoint enabledness generally suffices for Moves.

The initial serial interpretation supplies a permitted completion. Induction
then shows that executing an exempt operation when its ordinary dependencies are
satisfied preserves the completion invariant, just as a successful exact test
does for a remaining Move.

These exemptions also explain why noncompeting work need not share the Move
permission mechanism. If an exempt operation and a permitted Move are both
ordinarily ready, start with a completion placing the Move next and advance the
exempt operation as above. The Move remains permitted afterward. Advancing any
finite sequence of such ready exempt operations preserves that fact. This
argument concerns legal operation effects, not publication or memory-ordering
details of a particular runtime.

## Completed sets determine continuation

Consider two permitted prefixes of the same finite resolved operation set that
have completed exactly the same operations. Their orders may differ. Every
actual position's operations nevertheless form the same completed initial
segment of its specified occupancy order. Its ordinary occupancy is therefore
the same in both prefixes. The same argument applies to the shared positions
used during destruction, with release determined by the selected Vacate and the
last required direct Move. Create and Vanish membership determines which
particles exist.

The relationship periods give this conclusion directly for parent associations.
A period is present after a prefix exactly when its beginning has occurred (or
it was initially present) and its end has not completed. A joined end has
completed exactly when all its events have occurred. These tests depend only on
the completed set. For an operation beginning a new period, check that period's
occupied result before removing it when that same operation completes its joined
end. This observation also depends only on the completed set and the proposed
next operation.

Ordinary readiness depends only on membership of prerequisites in that set. Thus
both prefixes permit exactly the same next effects. Induction over any proposed
suffix shows that they admit exactly the same legal suffixes, including the same
complete suffixes. Their earlier orders need not be retained when answering the
specification's continuation question. This does not identify their execution
orders, require them to be connected by legal exchanges, or permit forgetting
which operations completed.

For a finite operation set this gives another exact search: from a completed
set, try each ordinarily ready operation, reject an effect that makes a circular
arrangement, and search from the enlarged set. The full set succeeds; a set
whose every permitted successor fails also fails. Each step increases the set's
cardinality, so the recursion terminates. Caching a result by completed set is
sound by the preceding equivalence. There are at most `2^n` such sets for `n`
operations, rather than one state per permutation prefix. This is an exponential
upper bound, not a scalability claim for a large interacting graph.

## Discovering violated cycles instead of enumerating them

Begin with ordinary precedence and any proposed prefix. Find a total order
satisfying the relationship conditions already collected. If none exists, no
permitted extension exists, because every collected condition is necessary.

Otherwise check that order's associations. If they remain acyclic, the order is
a certificate satisfying all relationship conditions. If a simple cycle appears,
collect its interval condition and repeat.

Every added condition is necessary by the cycle characterization and false in
the order that exposed it. It removes that candidate without removing a
permitted order. In particular it cannot be a condition already satisfied by the
current candidate. There are only finitely many total orders, so this procedure
terminates with the same answer as full collection. It need not enumerate
unrelated possible cycles to validate an already permitted order.

## Restricting cycle analysis to mutually reachable particles

Form the finite graph of all possible direct parent relationships. Partition its
particles into strongly connected components: two particles belong to the same
component exactly when each is reachable from the other. Every directed cycle
lies entirely in one component, since following the cycle supplies both
directions of reachability between any two of its particles.

Discarding periods whose child and parent belong to different components
therefore removes no possible cycle and changes no cycle condition. The same
restriction is valid when checking an individual execution certificate: every
cycle in its active relationships would also be a cycle of possible
relationships. An acyclic possible-relationship graph needs no interval choice
conditions at all. This does not omit any ordinary position or lifetime
requirement.

There is a cheaper sufficient acyclicity certificate. If a fixed integer rank
strictly increases on every possible parent edge, following a cycle would
strictly increase the rank and return to its starting value, a contradiction.
The same holds with strictly decreasing rank. Such a certificate permits
omitting all cycle conditions without computing components. Failure to find this
certificate proves nothing about cyclicity; use the complete calculation in that
case. Particle numbers can supply a candidate rank, but their numbering does not
itself impose an execution order.

## Factoring the finite choice search

Partition operations so that every collected condition refers only to operations
in one part. Add a directed edge between parts for every ordinary precedence
crossing them, and merge strongly connected components of this graph of parts.
The resulting quotient is acyclic.

All alternative precedences remain internal to a part. An ordinary path cannot
leave a part and return: that would give a cycle in the quotient. Thus keeping
its internal ordinary edges loses no ordinary precedence between its members.

If each part admits a total order satisfying its internal requirements, add the
successive pairs of those local orders to the ordinary graph. The resulting
graph is acyclic. A cycle confined to one part contradicts its local order; a
cycle crossing parts contradicts quotient acyclicity. Any topological order of
this graph supplies a full certificate. Conversely, restricting any full
certificate to a part proves that part satisfiable.

This establishes exact composition of local certificates. Their successive pairs
are temporary choices made by the search, not new mandatory runtime
dependencies. A different query may choose different local certificates.
Ordinary prefix constraints can participate in the same factorization, so the
equivalence also holds when testing completion of a particular finite prefix.

The initial partition can also be obtained without enumerating cycle conditions.
For each strongly connected component of possible parent relationships, group
all operations beginning or ending its retained periods. Every cycle condition
refers only to members of one such group. Merge groups and intervening
operations when ordinary precedence gives a cycle in their quotient, as above.
This can make a part larger than clause-by-clause grouping, but cannot separate
events needed by one condition.

Only ordinary paths between these boundary operations can couple their choices.
Keep the boundary operations and operations both reachable from a boundary and
able to reach a boundary. Every ordinary path between boundaries stays within
this set. To see that nothing else is needed for grouping, view each proposed
group as bidirectional connections between its boundary operations. A cycle in
this augmented graph must use such a connection because ordinary precedence is
acyclic. Every ordinary segment of that cycle is then a path between boundaries
and belongs to the kept set. Discarding other operations from the grouping
calculation therefore loses no coupling. Their actual ordinary dependencies
remain in the execution graph; this is not a minimization of that graph.

For an already legal prefix, the partition need not be rebuilt. Ask each part
for a legal suffix after its own completed operations. Add each chosen suffix's
successive pairs to the ordinary graph of unfinished operations. Its quotient
remains acyclic, and each internal order is acyclic, so a topological order
composes these suffixes. No unfinished ordinary predecessor can point to a
completed operation: that would contradict legality of the prefix. Every period
condition stays within its part, so the composite suffix is legal. Conversely,
any full suffix restricts to a valid local suffix. This proves equivalence of
the global continuation question and these local questions.

Consequently two ordinarily ready guarded Moves in different parts can have
their permissions resolved independently. Each changes only its own part's
completed set, preserving that part's legal continuation. The fixed ordinary
dependencies prevent the pair from reversing a required precedence, and the
composition result supplies a global continuation afterward. Moves in the same
part still require coordinated decisions; membership in different particle
components alone is insufficient if ordinary dependencies couple their choices.

## Limits of adjacent-exchange arguments

Ordinary precedence can be analyzed using linear extensions and exchanges of
incomparable operations. The additional relationship conditions do not in
general define one partial order.

For example, one pair of Moves temporarily makes the first particle a child of
the second and returns it; another pair temporarily makes the second a child of
the first and returns it. Either pair can execute first, but the pairs cannot
overlap. Their two permitted Move orders cannot be connected by legal adjacent
exchanges. The two target positions belong to different particles; this does not
exchange successive occupants of one actual position.

The interval argument characterizes both orders directly. Final-effect equality
may be proved separately using the ordered effects on each actual position. Any
auxiliary algebraic states in that argument must not be identified with
permitted intermediate particle arrangements.

## Unavoidable precedence need not have one fixed intermediate

Consider two nonoverlapping Move excursions. Write A and B for their beginning
Moves, and a and b for their ending Moves. Let H create the particle defining
both ending destinations. Let V be the Vanish of the particle defining both
starting positions. Ordinary requirements give:

- A precedes a, and B precedes b.
- H precedes both a and b.
- Both A and B precede V.

The relationship condition is that a precedes B or b precedes A. In the first
case H precedes a, B, and V. In the second it precedes b, A, and V. Hence H
precedes V in every permitted order.

Nevertheless no one of A, a, B, or b must lie between H and V. These two orders
satisfy every stated requirement:

```text
A, H, a, B, V, b
B, H, b, A, V, a
```

A and B can each precede H; a and b can each follow V. Thus H to V is a cover in
the intersection of the permitted total orders, even though its necessity is
already represented by alternative paths. Adding its cover edge to that
representation contributes no new restriction.

The valid source fixture `alternative_paths_imply_a_lifetime_order` realizes
this case. Two original children leave `parent`, temporarily occupy each other's
`/child`, and end at positions defined by `helper`. The operations H and V are
`test.create(helper)` and `test.vanish(parent)`. Other Creates, Vacates, and
Vanishes supply their own requirements without giving a fixed intermediate
between H and V; the finite oracle checks this over the full operation set.

Consequently constructing the cover graph of all universally necessary
precedences is not by itself a minimal representation when alternative
conditions are also retained. This is separate from the correctness of
Comparison for an ordinary candidate graph.
