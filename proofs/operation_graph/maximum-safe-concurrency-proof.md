# Particle Operation Maximum Safe Concurrency

## What This Proof Establishes

Consider any valid resolved Particle Operation history. The history may stop or
may continue without end. This document proves three results about occupancy:

1. Every execution schedule allowed by the relation defined below gives each
   operation the same occupancy that it has in the history's previous-operation
   order. When the history stops, every such schedule also leaves the same final
   occupancy.
2. No ordering constraint in that relation can simply be removed. Removing one
   allows an execution order in which two adjacent operations are reversed, and
   that execution is undefined.
3. The Particle Operation Dependency Graph represents the relation with exactly
   its cover edges. It is therefore the unique inclusion-minimal graph with the
   same reachability. For a history that stops, it is also the unique graph with
   the fewest edges and that reachability.

These results give a precise, limited meaning to “maximum safe concurrency.” The
relation is inclusion-minimal among occupancy-safe precedence relations obtained
by removing constraints that follow the program's operation order. It does not
follow that every occupancy-equivalent total order is allowed. The
counterexample in “Why the Result Is Not a Global Maximum” shows why that
stronger claim is false.

The Lean theorem `exchange_unrelated_enabled_operations` in
[`occupancy_exchange.lean`](occupancy_exchange.lean) formalizes the central
adjacent-exchange result: exchanging enabled operations on pairwise unrelated
positions preserves their preconditions, their occupancy observations, and the
occupancy state after the pair. `ScheduleExecution.swap_adjacent_unrelated` in
[`finite_scheduling.lean`](finite_scheduling.lean) lifts that exchange through
any finite schedule prefix and suffix. The theorem
`respecting_permutations_connected` in
[`finite_schedule_order.lean`](finite_schedule_order.lean) proves that any two
duplicate-free finite schedules containing the same occurrences and respecting
the same precedence relation are connected by such adjacent incomparable
exchanges. `finite_respecting_schedule_execution` in
[`maximum_safe_concurrency.lean`](maximum_safe_concurrency.lean) combines those
components for the calculated graph: every dependency-respecting permutation of
a defined finite schedule of distinct operations from one valid resolved history
has the same observations and final occupancy. The canonical schedule in
[`finite_history_schedule.lean`](finite_history_schedule.lean) lists the
occurrences before a stopping index directly from the history, proves that a
stopping index makes this exactly the history's complete operation set, and
proves that the schedule is duplicate-free, respects calculated reachability,
and executes with the history's observations and final occupancy.
`stopped_history_finite_schedule_execution` combines these results, formalizing
the stopped-history case of the theorem below. The natural-number schedule and
finite-prefix completion theorem in
[`unbounded_schedule_order.lean`](unbounded_schedule_order.lean), together with
`unbounded_respecting_schedule_execution`, formalize the unbounded-history case
one finite prefix at a time.
`calculated_coverPair_has_adjacent_finite_execution` formalizes the
dependency-respecting finite construction that makes each cover pair adjacent.
`related_enabled_operations_not_reversible` formalizes the four occupancy cases
showing that two related operations cannot execute consecutively in both orders.
`calculated_coverPair_has_irreversible_adjacent_finite_execution` combines those
results for every calculated cover pair. Deriving the final necessity result
from an arbitrary proper subrelation remains proved in this document rather than
in Lean.

## Definitions

### Operations and positions

Let `V` be the set of resolved Particle Operation occurrences in a
[valid resolved history](definitions.md#resolved-histories). Each execution of a
Particle Operation statement is a separate member of `V`. As in the
[shared definitions](definitions.md), index the occurrences by a finite initial
segment of the natural numbers or by all natural numbers. Assume that executing
the operations in index order is defined.

Let `<` be that strict linear order. For an operation `O`, let `positions(O)` be
the positions it operates on. A Create or Destroy operates on one position. A
Move operates on its source and target positions.

Write `p <= q` when `p` is `q` or a transitive parent position of `q`. Write
`p ~ q` when `p <= q` or `q <= p`.

Define `R` by

```text
(O, A) is in R exactly when A < O and
some position of O is related by ~ to some position of A.
```

Write `O >R A` when there is a nonempty `R` path from `O` to `A`. In execution
terms, `O >R A` requires `A` to execute before `O`. Every step in an `R` path
moves to an earlier operation, so `>R` is a strict partial order.

For readability, call `A` before `O` a _cover pair_ when `O >R A` and there is
no operation `X` for which both `O >R X` and `X >R A`. A cover pair is an
ordering with no required operation between its two members.

### Occupancy and equivalence

An occupancy state records which available resolved positions are occupied. A
child position is available only while every transitive parent position needed
to name it is occupied.

- A Create on `p` requires `p` to be available and empty, then makes `p`
  occupied.
- A Destroy on `p` requires `p` to be occupied, then empties `p` and all of its
  transitive child positions.
- A Move from `s` to `t` requires `s` to be occupied and `t` to be available and
  empty. It empties `s`, fills `t`, and replaces the source prefix of every
  occupied transitive child-position name with the target prefix.

The occupancy observed by an operation is the occupancy of its operated
positions immediately before it executes. An execution order is undefined if an
operated position is unavailable or if an operation's occupied-or-empty
requirement is not met.

An _execution schedule_ lists every member of `V` exactly once. For an unbounded
history, this means a sequence indexed by the natural numbers; in particular,
every scheduled operation has only finitely many operations before it. A
schedule respects `>R` when it places `A` before `O` whenever `O >R A`.

Two schedules of a history that stops are _occupancy-equivalent_ when both are
defined, each operation observes the same occupancy in both schedules, and both
schedules leave the same final occupancy. For an unbounded history, equivalence
means that both schedules are defined at every finite index and that each
operation observes the same occupancy; there is no final state to compare.

This definition deliberately ignores particle identity, qualities, Action
triggering, destructor effects, and every other possible observation.

## Lemma: Operations on Unrelated Positions Commute

Suppose `A` followed immediately by `O` is defined, and every position operated
on by `A` is unrelated to every position operated on by `O`. Then `O` followed
by `A` is also defined. The exchange preserves both operations' occupancy
observations and the occupancy state after the pair.

### Proof

For an operated position `p`, an operation can change occupancy only at `p` and
its transitive child positions. If a Move uses `p` as its source or target, the
same statement holds for the child-position names that the Move removes or
creates.

Now take unrelated positions `p` and `q`. Their sets of transitive child
positions are disjoint. Otherwise some position would have both `p` and `q` as
prefixes, and two prefixes of one position name are always related. This would
contradict `p` and `q` being unrelated.

It follows that `A` and `O` change disjoint sets of position names. Neither can
change the occupancy or availability required by the other: changing a parent
position of one of `O`'s operated positions would itself require operating on a
position related to that operated position, contrary to the hypothesis. The same
reasoning applies with `A` and `O` exchanged.

Both operations therefore have the same preconditions and observations after the
exchange. Because their changes are disjoint, applying the two changes in either
order also gives the same state after the pair. This includes two Moves: their
source-prefix removals and target-prefix replacements act on disjoint position
names. ∎

## Lemma: Moving a Particle Does Not Lose Its Orderings

Two operations on the same particle are ordered by `>R`, even if that particle's
position name changes between the operations.

### Proof

Let `A < O` operate on the same particle. If the particle has the same
applicable position name at both operations, then `A` and `O` operate on the
same position, so `(O, A)` is in `R`.

Otherwise, consider in order the Moves that change the particle's applicable
name. Such a Move either moves the particle itself or moves a particle that
defines one of its transitive parent positions.

Before the first such Move, `A` operates on the Move's source position or one of
its transitive child positions. After the last such Move, `O` operates on the
Move's target position or one of its transitive child positions. The same is
true between consecutive Moves: the earlier Move's target side and the later
Move's source side describe the particle between those Moves.

Each consecutive pair in the sequence consisting of `A`, those Moves, and `O`
therefore operates on related positions. The later and earlier operations of
each pair form a member of `R`. Chaining those members gives `O >R A`. ∎

## Theorem: Every Consistent Schedule Is Occupancy-Equivalent

Every execution schedule that respects `>R` is occupancy-equivalent to the
history's previous-operation order.

### Proof

The history's previous-operation order respects `>R`, because every `R` edge
points from a later operation to an earlier one.

First suppose the history stops. Any two linear orders that respect the same
finite strict partial order can be connected by exchanges of adjacent
incomparable operations. To see this, take the first operation in the desired
order, move it left across the operations that currently precede it, and repeat
with the remaining operations. Every crossed operation must be incomparable with
it; otherwise one of the two orders would violate the partial order.

Operations incomparable under `>R` have pairwise unrelated operated positions.
If they had related positions, whichever operation is later under `<` would form
an `R` pair with the earlier one, so they would be comparable.

Starting from the defined previous-operation order, apply the commutation lemma
to each adjacent exchange. An exchange preserves the observations of the
exchanged operations and the state received by all later operations. Induction
over the sequence of exchanges proves that the desired schedule is defined,
gives every operation the same occupancy observation, and leaves the same final
occupancy.

Now suppose the history is unbounded. Fix any finite prefix `P` of the desired
schedule. Let `k` be greater than the previous-operation index of every
operation in `P`, and let `L` be the finite list of history operations whose
indices are less than `k`. Thus `P` is a duplicate-free subcollection of `L`.

Remove the operations of `P` from `L` without changing the order of the
remaining operations, obtaining `T`. Then `P` followed by `T` contains exactly
the operations of `L`. It also respects `>R`. The prefix `P` respects `>R` by
hypothesis, and `T` respects `>R` because it retains the relative order from
`L`. For the remaining cross case, suppose an operation `p` in `P` were required
to follow an operation `t` in `T`. The complete desired schedule contains `t`
and respects `>R`, so it places `t` before `p`. Because `p` occurs in the fixed
prefix `P`, `t` would then also occur in `P`, contradicting its membership in
`T`.

The finite case applied to `L` and `P` followed by `T` proves that this
completed finite schedule is defined with the history's observations. Its prefix
`P` is therefore defined with those observations. Since the choice of finite
prefix was arbitrary, every operation in the desired schedule is defined and
observes the same occupancy as it does in the previous-operation order. An
unbounded history has no final occupancy claim. ∎

## Theorem: Every Cover Ordering Is Necessary

For every cover pair `A` before `O`, there is a `>R`-consistent execution order
in which `A` is immediately before `O`. Reversing that adjacent pair makes the
execution undefined.

### Proof

First, `(O, A)` must itself be in `R`. If every `R` path from `O` to `A` had at
least two edges, any intermediate operation on such a path would lie strictly
between `A` and `O`, contrary to the definition of a cover pair.

Next, a cover pair can be adjacent in a schedule that respects `>R`. Let `L` be
the finite history prefix ending with `O`. Every predecessor of `O` belongs to
`L`, because reachability always moves to a smaller previous-operation index.
From `L`, take the other predecessors of `O` in their history order, then place
`A` and `O`, and finally place the other members of `L` in their history order.

This permutation of `L` respects `>R`. The other predecessors retain their
relative history order. None is required to follow `A`, because together with
its path from `O` that would put it strictly between the cover pair. Nothing
placed before `O` is required to follow `O`, because reachability moves to a
smaller index. Finally, if an operation moved after `O` were required before any
operation in the new prefix, transitivity would make it a predecessor of `O`, so
it would already have been placed before `A`.

If the history continues after `O`, append its later operations in history
order. No earlier operation is required to follow one of those later operations,
again because reachability moves to a smaller index. The resulting complete
schedule therefore respects `>R`, and the preceding theorem makes it a defined
execution with `A` immediately before `O`.

Because `(O, A)` is in `R`, choose an operated position `p` of `A` and an
operated position `q` of `O` such that `p <= q` or `q <= p`. Every operated
position is one of two kinds for its operation:

- its _Empty Position_, which must be occupied before the operation; or
- its _Fill Position_, which must be available and empty before the operation.

A Move's source is its Empty Position and its target is its Fill Position. A
Create has only a Fill Position, and a Destroy has only an Empty Position.

After an enabled operation, its Fill Position is occupied. Its Empty Position
and every child position of that Empty Position are empty. The latter statement
also holds for a Move. The Move precondition says that its source is not a
parent position of its target. Its target cannot be a parent position of its
source either: prefix closure and the occupied source would then make the target
occupied, contrary to the Move precondition. The source and target are therefore
unrelated, so moving particles to target-based names cannot restore an old
source-based name.

The history's initial occupancy is prefix-closed. The proof of
[valid-history Lemma 1](valid-history.md#lemma-1-valid-operations-preserve-prefix-closure)
shows that each enabled Create, Destroy, or Move preserves prefix closure.
Applying that lemma successively to the finite schedule prefix before `A` proves
that the occupancy immediately before the adjacent pair is prefix-closed. We can
now consider the four possible roles of `p` and `q`.

1. Suppose both are Empty Positions. If `p <= q`, executing `A` empties `q`, so
   `O` cannot be enabled next. The original order is defined, so this direction
   is impossible. We must have `q <= p`; executing `O` first then empties `p`,
   so `A` is not enabled.
2. Suppose `p` is an Empty Position and `q` is a Fill Position. If `q <= p`,
   prefix closure makes `q` occupied before `A`, whereas executing `O` first
   requires `q` to be empty. Otherwise, relatedness makes `p` a strict parent
   position of `q`. Then `O` requires `p` to be occupied after `A` so that `q`
   is available, but `A` empties `p`. Thus either the reversed order is
   undefined or the assumed original order was already undefined.
3. Suppose `p` is a Fill Position and `q` is an Empty Position. If `p <= q`,
   executing `O` first requires `q` to be occupied, so prefix closure makes `p`
   occupied, whereas `A` requires `p` to be empty. Otherwise, relatedness makes
   `q` a strict parent position of `p`. Executing `O` first then empties `q`, so
   `p` is unavailable when `A` attempts to fill it.
4. Suppose both are Fill Positions. If `p = q`, executing `A` fills the position
   that `O` requires to be empty, contradicting the assumed original execution.
   If `p` is a strict parent position of `q`, executing `O` first requires `p`
   to be occupied, whereas `A` requires it to be empty. If `q` is a strict
   parent position of `p`, `A` requires `q` to be occupied so that `p` is
   available, whereas executing `O` first requires `q` to be empty.

The four cases exhaust the possible roles of the selected operated positions. In
every case, `A` followed by `O` and `O` followed by `A` cannot both be defined
from the same occupancy. Because the original adjacent order is defined, the
exchanged order is undefined. ∎

### Consequence: no program-oriented constraint can be removed

Let `P` be the precedence relation represented by `>R`, and let `Q` be a strict
partial order that is a proper subrelation of `P`. Choose `(O,A)` in `P` but not
in `Q`. Every operation strictly between `A` and `O` in `P` has a natural-number
index strictly between their indices, so there are only finitely many.
Repeatedly inserting an intermediate operation therefore produces a finite chain
of cover pairs from `A` to `O`. If `Q` contained every pair in that chain,
transitivity would put `(O,A)` in `Q`. Thus `Q` omits at least one cover pair.

Take the `P`-consistent order in which that pair is adjacent and exchange the
pair. The exchanged order violates no relation of `P` except the omitted cover
pair, so it respects `Q`; the theorem above says that it is undefined. Thus no
proper subrelation of `P` guarantees a defined execution for all of its linear
orders.

This is the necessity result used by the “maximum safe concurrency” claim.

## Why the Result Is Not a Global Maximum

Occupancy-equivalence can treat two complete Create-and-Destroy pairs as
interchangeable. Let one position `p` be initially empty, with program order

```text
C1 = Create p
D1 = Destroy p
C2 = Create p
D2 = Destroy p
```

Because all four operations use `p`, `>R` requires

```text
C1 before D1 before C2 before D2.
```

But this order is also defined:

```text
C2 before D2 before C1 before D1.
```

In both orders, each Create observes `p` empty, each Destroy observes `p`
occupied, and the final state has `p` empty. The orders are therefore equivalent
under this document's occupancy-only definition even though the second order
reverses constraints in `>R`.

The equivalence cannot be exposed by removing only the constraint between `D1`
and `C2`. That would also allow interleavings with two consecutive Creates or
two consecutive Destroys, which are undefined. A precedence graph cannot express
the choice “run either complete pair first, but do not interleave the pairs”
without choosing one pair order. Occupancy alone gives no reason to prefer the
program's pair order over the reverse order.

Thus `>R` is inclusion-minimal among safe subrelations of the program-oriented
relation, but it is not the intersection of all occupancy-equivalent total
orders and is not a unique global optimum over differently oriented precedence
relations.

## The Unique Transitively Reduced Graph for This Reachability

Among graphs on `V` whose reachability is exactly `>R`, the transitive reduction
is the unique inclusion-minimal graph. When `V` is finite, it is consequently
also the unique graph with the fewest edges.

### Proof

Every cover pair must be a direct edge in any graph with reachability `>R`.
Without that edge, a path between the pair would have an intermediate operation,
contrary to the definition of a cover pair.

Conversely, the graph consisting of the cover-pair edges has reachability `>R`.
For any `(O,A)` in `>R`, only finitely many natural-number indices lie strictly
between the indices of `A` and `O`. As above, this refines `(O,A)` into a finite
chain of cover pairs. No cover edge is redundant, because an alternate path
would put an intermediate operation between its endpoints.

The transitive reduction therefore consists of exactly the cover-pair edges.
Every graph with the same reachability contains those edges; any different such
graph also has at least one additional edge. The cover graph is therefore the
unique inclusion-minimal graph with that reachability. If `V` is finite, adding
an edge strictly increases the number of edges, giving the stated unique
fewest-edge result. ∎

By
[Particle Operation Dependency Graph Characterization](characterization-proof.md),
the Fill, Empty, and Move Rules produce this transitive reduction. The graph
therefore allows every reordering obtained by commuting operations on unrelated
positions, and no constraint in its reachability can be removed while keeping
every allowed order occupancy-safe.

## Scope

This proof concerns occupancy for one resolved Particle Operation history, which
may stop or continue without end. It assumes the history's previous-operation
order is defined and uses only the specified occupancy effects of Create, Move,
and Destroy. An unbounded history has observations and states at every finite
index but no final occupancy state.

It does not prove correctness of the runtime's concurrent execution, Action
Requirement inference, or any behavior other than occupancy. In particular, it
does not compare particle identity, qualities, Action triggering, destructor
effects, or the ordering of other effects. Those observations may require
additional constraints, and they may distinguish the two orders in the
Create-and-Destroy counterexample.
