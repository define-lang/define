# Construction from Operation Requirements

## Scope

This proves the specification's Collection, Comparison, and Recording the
Operation's Effects phases. The
[operation requirements](../definitions/operation-requirements.md) are derived
independently of the graph; the
[scheduling proof](requirement-scheduling-proof.md) establishes source safety
and edge necessity. Lean checks the component state models and the incremental
graph calculation. Source interpretation and geometric accessibility remain
English proofs.

## Objects used by the construction

Fix a valid serial reference execution, including a permitted serial order for
the destructors triggered by each simultaneous destruction. An occurrence is one
Particle Operation contributed by that execution. Simultaneous Vacates retain
identical recency; their enumeration is not an ordering premise.

For the mathematical calculation, distinguish positions by the particle and
quality that define them, or by the Action Execution and local declaration where
applicable. Retain the actual references used to reach those positions. These
identifiers describe positions; they do not replace their spatial meaning. Two
successively defining particles can give positions at the same spatial location
without making retained original occupancy available to a replacement.

An occupancy record states that a particular particle occupies a particular
position. A Create or a Move to that position supplies the record. Moving the
defining particle changes the spatial location of the position, not this
relative occupancy record. Empty positions are recorded separately from occupied
ones. A Move from the position or its ordinary vacancy supplies a subsequent
empty state.

For each current occupancy record, retain its supplying occurrence and the
preceding operations that have required it without ending it. These are
mathematical collections used for constructing dependencies, not new Define
operations. The source-to-record correspondence must show which requirements are
genuine before this calculation can be applied to Define.

## Ordinary operations

### Reading an occupied position

An intermediate position in an actual reference requires the occupied record
that lets the reference continue through the selected particle. Add its
supplying occurrence to the operation's candidates and record the operation as
requiring that occupancy. Reading does not end the record. Multiple operations
can therefore require the same occupancy without ordering each other.

A direct implied-position access does not read the caller's old position of the
action's assigned particle. Its particle and quality requirements are handled
separately. Replacing an actual reference by all spatial ancestors of its final
position before applying this rule would be incorrect.

### Filling a position

Create and a Move destination require the selected position to be empty. Add the
occurrence supplying its current empty state, when there is one. The operation
supplies the new occupied record. If the empty position has not been previously
operated on, its existence still follows from the applicable definition or
creation; an absence of an occupancy predecessor is not an absence of all
requirements.

### Emptying a position by Move

A Move source requires its current occupied record. Collect its readers if there
are any; otherwise collect its setter. Each reader already follows the setter,
so collecting both would add no reachability. The Move ends that occupancy and
supplies an empty source state and an occupied destination state.

Apply the reference checks to both source and destination, and combine their
candidates with those for both final positions. Count the Move as one
occurrence, not two independently executable changes. Do not add child-position
occupancy requirements merely because the moved particle defines those
positions. Physical movement of those positions follows from movement of their
defining particle.

The [reference-shape argument](reference-shape-proof.md) addresses distinct
endpoints and the prohibition against moving into a position the particle
defines for ordinary Moves. These conditions cannot be dropped on the assumption
that an arbitrary occupancy map must imply them. Destination qualities also
remain requirements of the same selected source particle.

The [ordinary correspondence proof](ordinary-requirements-proof.md) derives
enabledness in both directions, independent exchanges, and conflicting adjacent
reversals for Creates and Moves. Its scope does not include destruction.

## Simultaneous destruction

### Record selection from the common preceding state

Resolve the selected particles using the state immediately before destruction.
For each particle, retain its selected position relative to its defining
particle, or its local declaration where applicable, and that position's
occupied-state setter. Traversing ancestors to discover the selected set does
not make those traversals runtime requirements of every selected Vacate.

The Vacate of the statement's target still has the requirements of the
statement's actual position reference. Record its uses of occupied intermediate
positions just as for any written reference. These intermediates are outside the
selected transitive child positions. Preserving the selected particle does not
waive those reference requirements.

Do not insert the additional Vacates generated for transitive children into the
current readers of their selected ancestors. Those children do not each have a
newly written chained reference. In particular, their recorded selections do not
cause a parent's Vacate to wait for a child Vacate, or a child Vacate to wait
for its parent's Vacate.

The selected particles need not all have been created before the first vacancy
vertex executes at runtime. Each individual Vacate must wait for the occurrences
needed for its own selected particle and position. Selection is not an
additional runtime traversal that imposes a barrier before the entire group.

### Individual vacancies

For Automatic Destruction, the spec treats each applicable local position as the
target of a Destroy Particle Statement. Its local reference has no intermediate
positions or assigned-quality supplier. Its additional child Vacates have no
Position References. Destruction Contracts use the references from the action
performing the destruction, as specified, not new references from a later
caller.

For each individual Vacate, collect its selected position's readers if there are
any, or its setter otherwise. The Vacate supplies ordinary empty occupancy for
its own position.

These Vacates select distinct positions. Only statement targets introduce
references, whose intermediate positions are outside the selected destruction;
the child Vacates have no references. Recording one Vacate therefore changes
neither the setter nor the readers queried by another equal-recency Vacate. It
does not change which particle's Create supplies a referenced quality.
Processing equal-recency Vacates in any order consequently gives the same
candidates and effects; no separate batch-processing rule is needed.

For the statement's target, also apply the actual reference requirements above.

An ordinary reference through a position is invalidated by vacancy there. A
direct access to a position defined by the vacating particle does not, solely
for that reason, require occupancy at its former position. Its genuine particle
requirements must be considered separately. Neither kind of access may be
silently substituted for the other.

For example, a written `destroy ... parent::/child` requires occupancy at
`parent`. A subsequent Move from `parent` therefore waits for that target
Vacate. This differs from an implicitly selected child Vacate in the destruction
of `parent` itself. Saving a selection is not a general exemption for written
references to become invalid before their statements execute.

### Retained destructor operations

Continue calculation of destructor operations on the original particles and the
original position state preserved by the destruction semantics. The vacancies do
not empty that retained state. All destructors sharing an original particle
share subsequent changes to its positions; there is no private copy per
destructor. Apply the ordinary read, fill, and Move rules to their actual
references in this retained state, in the chosen serial reference order.

The initial retained records inherit their original setters and the preceding
ordinary operations that required them. For example, a retained Move that takes
an original particle out of a position must wait for preceding ordinary uses of
that occupied position, even though it does not wait for the vacancy merely to
obtain the original particle. Forgetting those uses would permit interference
between an ordinary action and a destructor.

An ordinary replacement is not a retained original particle. Where a destroyed
defining particle is replaced, its successor's defined positions do not share
the original particle's changing retained occupancy. Where the defining particle
is not destroyed, reuse of its vacated position must still follow the vacancy
that empties it. The proof must account for both cases; it may not give every
subsequent use of a position an independent state.

## Collection omissions and reader removal

The componentwise collection includes some candidates that the spec omits before
Comparison. Each omission preserves reachability in the already-calculated
graph:

- A reader of an intermediate position follows its setter. If both are
  candidates, retaining the reader covers the setter.
- A setter or reader of a position defined by `P`, other than `P`'s Create
  itself, follows that Create. The operation requires the position supplied by
  `P`'s assigned quality, whether by an actual reference or its selected
  vacancy. Its position's occupancy setter ultimately follows the same Create.
  Thus a collected such operation covers `P`'s Create, regardless of the reason
  that Create was collected.

These facts are maintained by induction over the processed occurrences.
Initially a particle's Create is its child positions' setter. Each later
reference use collects the needed quality supplier, and every change follows the
preceding setter or readers. Omitting that Create is justified only by an
already-processed operation with the established path; it does not assume the
current operation's dependencies. An implicit vacancy obtains the same path
through its selected occupancy, not through an invented parent reference.

The spec determines omissions from the combined collection before removing any
candidate. A candidate covering another may itself be omitted. Following the
covering candidates cannot cycle, because each link is a nonempty path in the
preceding acyclic graph. The collection is finite, so the chain ends at a
candidate not omitted. Every omitted candidate is therefore reachable through a
remaining candidate. These omissions preserve the componentwise collection's
reachability; Comparison then preserves it again while choosing direct edges.

Reader removal has the same invariant. If a remembered reader is removed because
another reader depends on it, the retained reader covers it for every subsequent
operation that empties that occupied position. A chain of such removals
preserves the path inductively. When recording the current operation as a
reader, it reaches every candidate it collected, including candidates omitted
before or during Comparison. Removing a previous reader collected in that way
therefore preserves the invariant even when it did not become a direct
dependency.

None of these arguments assumes semantic minimality. They establish the
correspondence between the spec's specific Collection and Recording phases and
the complete componentwise conflict relation.

## Particle requirements and Vanish

Actual Position References require the particle supplying each assigned quality,
without requiring that particle to remain at the caller's earlier position. A
Move also requires the particle it moves directly. The
[Vanish proof](vanishment-proof.md) collects these operations and the selected
particle's Vacate, applies Comparison, and proves that this suffices for
existence without changing the occupancy graph. Transitive movement alone adds
no lifetime requirement.

## Comparison and graph properties

The candidate sets can contain redundant dependencies. Comparison keeps
precisely the candidates that are not already required, directly or indirectly,
by another candidate. This completes the calculation for the current occurrence:
there is no subsequent minimization step. The proofs below show that these rules
themselves produce transitive minimality. Describing their result as the cover
graph of candidate reachability is a mathematical characterization, not an
instruction to construct that graph with a generic minimization algorithm.

Every candidate described above comes from the preceding reference execution;
none comes from a simultaneous peer. If source correspondence holds, this gives
strictly backward edges and hence acyclicity. The general cover-graph results
then supply transitive minimality independently of any claim that the semantic
candidate sets are complete.

For ordinary occupied records, the most-recent-setter and intervening-reader
calculation has the same conflict reachability as collecting every earlier
conflict. A read follows the last change; a change follows intervening readers
and the preceding change. Earlier conflicts are reached through successive
changes. This is the local completeness argument developed for
[exact effects](../definitions/operation-effects.md#collecting-conflicts-without-comparing-every-pair).
The [scheduling proof](requirement-scheduling-proof.md) applies it to selected
vacancies and retained state using their separate source correspondence.

### Reduction preserves candidate reachability

Fix an occurrence `O` and assume that reduction has preserved reachability in
the preceding graph. Its candidate collection is finite. If a candidate `A` is
excluded because another candidate `B` reaches it, either `B` is retained or
another candidate reaches `B`. Following these exclusions must end at a retained
candidate: each step strictly increases reference recency within the finite
collection. That retained candidate reaches `A` in the preceding graph, and
hence also in the reduced preceding graph by the induction hypothesis. Adding
`O`'s edge to it preserves reachability from `O` to `A`.

No new reachability is introduced, since every retained edge was a candidate
edge. Induction over occurrences therefore proves equality of candidate and
reduced reachability. An enumeration of simultaneous peers can be used for this
induction only because none of them supplies a candidate to another; changing
that enumeration changes neither candidate sets nor their reduction.

### Correspondence with already-calculated dependencies

The specification uses already-calculated dependencies during Comparison, not
the entire unreduced candidate graph. To represent that calculation explicitly,
let `G₀` have no edges. Having calculated `Gₙ`, calculate the candidates for
occurrence `n`. Retain a candidate `a` exactly when no other candidate reaches
`a` in `Gₙ`, and add precisely those edges from `n`, leaving every earlier
occurrence's edges unchanged. Call the result `Gₙ₊₁`.

Inductively, `Gₙ` is exactly the reduced graph restricted to occurrences before
`n`. Every edge points to an earlier occurrence. Consequently a path starting
before `n` stays before `n`, so its reachability in this restriction is the same
as in the full reduced graph. The reachability result above identifies that with
candidate reachability. Comparison at `n` therefore excludes exactly the same
candidates as the mathematical reduction. Its new row agrees with the reduced
graph, and all older rows agree by induction. This proves the next prefix
equality without assuming the incremental calculation is correct.

Taking the row for `n` from `Gₙ₊₁` gives the specification's calculated
dependencies. Thus the full incremental calculation equals the reduced graph;
the graph and scheduling theorems apply to the actual calculation, not just to
an alternative definition with the same intended result.

In `effect_graph.lean`, `CalculatedPrefix` is this incremental calculation and
`calculatedPrefix_iff` proves the prefix equality. The resulting
`calculated_transitively_minimal` theorem establishes minimality of the rules'
result. Its underlying minimality argument uses Comparison's exclusions
directly, independently of source safety or completeness. The
`calculated_reachability_iff` theorem separately proves preservation of
candidate reachability. Neither theorem runs a minimization algorithm.

### Transitive minimality independently of semantic completeness

Suppose a retained edge from `O` to `A` were redundant. An alternative path
would have to begin with an edge to another retained candidate `B`, followed by
a path from `B` to `A` entirely in the preceding graph. But the presence of that
path is exactly a reason to exclude `A`. This contradicts retention.

Thus the reduced graph is transitively minimal. This proof uses only the
candidate calculation, backward recency, and the reduction criterion. It does
not assume that the candidate graph is semantically complete, safe, or maximally
concurrent.

### The semantic necessity check is separate

Transitive minimality alone is not enough. For each retained cover edge, a
necessity proof must make its endpoints adjacent in a respecting schedule and
show that reversing them violates an actual source requirement. The finite
adjacent-cover theorem supplies the order-theoretic construction. The remaining
source checks are:

| Reason for the candidate                 | Source requirement that the adjacent reversal must violate                            |
| ---------------------------------------- | ------------------------------------------------------------------------------------- |
| Creation of a needed particle            | The particle, or the position quality supplied by it, does not yet exist              |
| Supply of current occupied state         | The actual reference or Move source does not yet have its selected particle           |
| Supply of current empty state            | A Create or Move destination is still occupied                                        |
| Ending occupancy after an ordinary use   | The earlier operation's occupied reference or source has become empty                 |
| Initial retained setter or inherited use | A destructor lacks its required original state, or changes it before the ordinary use |

A saved selection does not supply an additional row of ancestor-occupancy
requirements. Its final occupied-state setter belongs to the ordinary supply
case. For a written target, the actual reference requirements also apply. Adding
a dependency on every Move encountered while discovering an implicit child would
incorrectly fix that child's position in space while its defining particle
moves. The
[generated-child exchange](retained-state-proof.md#an-implicit-child-vacancy-and-an-ordinary-ancestor-move)
distinguishes that case from a written destination-based reference.

## Correspondence and verification

1. The [ordinary correspondence](ordinary-requirements-proof.md) describes
   relevant particle and position state, including the distinction between
   spatial movement and relative occupancy. Reference resolution must not
   conceal an assumption that an action's assigned particle stays still.
2. The [reference-shape proof](reference-shape-proof.md) shows that Moves
   preserving their recorded occupancy requirements also preserve the source
   language's geometric restrictions. A generic graph of particle-to-position
   associations can admit cycles; syntactic reference restrictions must
   correspond to the constructed states, not be assumed to rule out every such
   cycle automatically.
3. The [retained-state proof](retained-state-proof.md) separates the ordinary
   vacancy and retained mutable occupancy of the same original particles,
   including how inherited requirements prevent interference without introducing
   barriers between all operations at a destruction.
4. The [scheduling proof](requirement-scheduling-proof.md) checks each
   incomparable adjacent pair while preserving every actual requirement and
   effect, and checks that each cover ordering has an invalid adjacent reversal.
   The exact-effect lemmas apply only where their fixed requirements represent
   these semantics exactly.
5. The same proof applies the actual-interaction correspondence needed by the
   completion argument above, including retained originals and the varying
   transitive effects of Moves. The completion argument itself adds no ordering
   between Particle Operations.

The Lean modules `effect_collection.lean` and `effect_graph.lean` check
collection completeness, the local reduction's equality with the cover graph,
acyclicity, transitive minimality, respecting-permutation execution, and unsafe
reversal of a reduced edge. `particle_requirements.lean` and
`retained_requirements.lean` check the reference, occupancy, and shared-state
component correspondences, and `particle_scheduling.lean` transfers their
executions in both directions. The source interpretation and geometric and
lifetime arguments linked above remain English proofs. This is not a fully
checked source-language translation.

A compiler representation must not expand every Move into all transitive child
positions or copy a whole destruction structure for each ancestor. The
componentwise collection bound applies to explicit requirements and emitted
candidates. It is not a bound for arbitrary reachability queries used in local
candidate reduction. No implementation complexity claim is being inferred from
the mathematical cover-graph characterization.
