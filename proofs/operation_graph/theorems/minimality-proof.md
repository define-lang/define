# Particle Operation Dependency Graph Minimality

## Claim

For every valid resolved Particle Operation history, the graph calculated by the
Fill, Empty, and Move Rules is a directed acyclic graph and is transitively
minimal: removing any direct dependency changes reachability.

This proof does not assume or prove completeness. In particular, it never
assumes that every related previous operation is reachable. Completeness is a
separate theorem.

## Inputs from the preceding proof components

The shared definitions represent an occurrence by its kind, operated positions,
Action Parent position, and natural-number occurrence index. Write `B > A` when
`B` reaches `A` through one or more dependency edges.

For one operation `O`, the calculation supplies:

- a Collection containing source-side entries and at most one Fill Dependency;
- the simultaneous Comparison result;
- the Move Correction result; and
- for a Move, the result after the possible Fill Dependency removal.

[Particle Operation Dependency Graph Calculation Correctness](calculation-correctness-proof.md)
proves the following facts for every valid resolved history:

1. every candidate is a previous Particle Operation;
2. an entry selected at position `p` operates on `p` or a parent position of
   `p`;
3. a non-Move entry selected at `p` operates on `p` itself;
4. a name operated on by a previous operation remains queryable, and the entry
   at that name is that operation or a more recent one;
5. every direct dependency is exactly a candidate retained by the applicable
   rule stages; and
6. Create, Destroy, and Move have their exact occupancy transitions.

None of those facts assumes acyclicity, transitive minimality, completeness, or
the desired reachability relation.

## Backward edges and acyclicity

Every direct dependency of `O` is a member of `O`'s Collection. Every Collection
member is a previous occurrence, so every edge points from a greater occurrence
index to a smaller one.

A dependency path therefore has strictly decreasing occurrence indices. It
cannot return to its source, so the calculated graph is acyclic. This argument
does not require the complete occurrence set to be finite.

## The antichain criterion

The direct dependencies of `O` form a _reachability antichain_ when no distinct
direct dependencies `X` and `Y` satisfy `X > Y`.

If every operation's direct dependencies form a reachability antichain, the
whole graph is transitively minimal.

### Proof

Suppose the direct edge `O -> Y` could be removed without changing reachability.
A replacement path from `O` to `Y` cannot use that edge. Its first edge is
therefore `O -> X` for a distinct direct dependency `X`, and the rest of the
path shows `X > Y`. This contradicts the antichain property. ∎

The remainder of the proof establishes this antichain property for the exact
dependency set produced by each operation kind.

## Candidate geometry

### Direct-dependency position lemma

If `O -> D` is a direct dependency, some position operated on by `O` is related
to some position operated on by `D`.

#### Proof

A Fill candidate has an operated position that is a parent position of the
filled position. A source candidate selected at `p` has an operated position
that is a parent position of `p`, and `p` is related to the emptied position.
The parent position remains related to the emptied position. A Move combines
those two candidate sets. Later rule stages only remove candidates. ∎

### Later-related-operation exclusion lemma

Let `O` empty `s`. Suppose a Create or Destroy candidate `Y`, selected at name
`y`, remains after the Comparison. There cannot be an operation `Z` satisfying
all of the following:

- `Y` is previous to `Z`, and `Z` is previous to `O`;
- `Z` operates on `z`;
- `z` is related to `y`; and
- `z` is related to `s`.

#### Proof

Calculation correctness supplies the entry `B` at `z`. It is `Z` or is more
recent than `Z`, so it is more recent than `Y`. The Empty Collection contains
`B` because `z` is related to `s`.

The position operated on by `B` is `z` or a parent position of `z`, and is
therefore related to `y`. Because `Y` is not a Move, it operates on `y` itself.
Thus `B` and `Y` participate in the Comparison, and the more recent `B` excludes
`Y`. This contradicts the premise that `Y` remains. The argument uses the
simultaneous Comparison, so it is unaffected if another candidate also excludes
`B`. ∎

### Occupied-source bridge lemma

Let `O` empty the occupied position `s`. Suppose a Create or Destroy candidate
`Y`, selected at `y`, remains after the Comparison, with `y` a strict parent
position of `s`. Then there is an intervening operation `K` such that:

- `Y` is previous to `K`, and `K` is previous to `O`;
- `K` operates on a position related to `s`; and
- that operated position is also related to `y`.

#### Proof

Because `Y` is a Create or Destroy on the strict parent position `y`, the exact
non-Move occupancy transition leaves `s` empty immediately after `Y`. The source
`s` is occupied immediately before `O`. Among the finitely many transitions
between those two occurrence indices, choose the first at which `s` becomes
occupied. The valid-history transition theorem supplies an operation `K` at that
transition whose operated position is related to `s`. Since `y` is a parent
position of `s`, that operated position is also related to `y`. ∎

This lemma is only an occupancy statement. It does not assert any dependency
path to or from `K`.

## Non-Move source candidates are irredundant

Let `O` empty `s`. Suppose distinct candidates `X` and `Y` remain after the
Comparison, `Y` is a source-side Create or Destroy candidate selected at `y`,
and `X > Y`. This is impossible.

### Proof

The selected name `y` is related to `s`, so there are two cases.

First suppose `s ≼ y`. Take the final edge `Z -> Y` of a path from `X` to `Y`.
The direct-dependency position lemma gives related positions operated on by `Z`
and `Y`. Because `Y` is not a Move, its only operated position is `y`; call the
related position operated on by `Z` `z`. The positions `z` and `s` are both
comparable with `y`, and `s ≼ y`; expanding the two possible directions of
`z ~ y` shows that `z ~ s`. Every edge points backward, so `Y` is previous to
`Z`; and because `X` is a candidate of `O`, the entire path occurs before `O`.
The later-related-operation exclusion lemma contradicts the survival of `Y`.

Now suppose `y` is a strict parent position of `s`.

- If `X` is source-side, its operated-position provenance and its selected
  name's relationship with `s` make its operated position and `y` prefixes of
  one common position, so they are related. Since `X > Y`, backward edges make
  `X` more recent than `Y`. The simultaneous Comparison would therefore exclude
  `Y`.
- If `X` is only the Fill Dependency of a Move, the occupied-source bridge lemma
  supplies an intervening operation `K` related to both `y` and `s`. The
  later-related-operation exclusion lemma again contradicts the survival of `Y`.

Every case is contradictory. ∎

Notice that this proof uses only candidate provenance, backward edges, exact
occupancy transitions, and the Comparison. It does not use the completeness
claim that every related previous pair is reachable.

## Each operation kind produces an antichain

Fix distinct final dependencies `X` and `Y` of one operation and suppose
`X > Y`.

### Create

A Create has at most one dependency: its Fill Dependency. It cannot have two
distinct final dependencies.

### Destroy

A Destroy has no Fill Dependency, so both final dependencies are source-side
candidates that survived the Comparison and Move Correction.

If `Y` is a Move, the Move Correction would remove it because the other
remaining candidate `X` reaches it. If `Y` is a Create or Destroy, the non-Move
source-candidate theorem gives a contradiction. Thus a Destroy's dependencies
form an antichain.

### Move

A Move applies the Comparison and Move Correction once to the combined source
Collection and optional Fill Dependency.

If `Y` is a Move, the Move Correction removes it. Suppose instead that `Y` is a
Create or Destroy.

- If `Y` is source-side, the non-Move source-candidate theorem gives a
  contradiction.
- If `Y` is the Fill Dependency and `X` is source-side, the Move Rule's final
  removal removes `Y` because the distinct remaining source candidate `X`
  reaches it.
- If both `X` and `Y` are the Fill Dependency, uniqueness of that dependency
  gives `X = Y`, contradicting distinctness.

These cases are exhaustive, so a Move's dependencies also form an antichain.

## Coverage of resolved operation forms

The valid resolved history contains every concrete Particle Operation
occurrence. An automatic Destroy Particle Statement and a Destroy Particle
Statement contributed by a destructor or Destruction Contract are therefore
ordinary Destroy occurrences and use the Destroy case above.

An entry for a moved particle's transitive child name may be the Move on a
parent position of that name. The operated-position provenance used throughout
the proof permits exactly this case, and the Move Correction handles a surviving
Move candidate. No step assumes that an entry operates directly on its selected
name unless calculation correctness also establishes that the entry is not a
Move.

Action Requirements, Action Guarantees, and requirements or guarantees on
implied positions contribute resolved names and concrete occurrences before this
theorem begins; they are not graph vertices. Their resulting Create, Destroy,
and Move occurrences are covered by the same three cases. The Action Parent
position constrains which resolved names an occurrence may operate on, but the
antichain proof needs only the resulting position relationships.

## Minimality theorem

For every valid resolved history, calculation correctness constructs its exact
resolved dependency graph. The backward-edge argument proves that graph acyclic.
The three operation-kind cases prove that every direct dependency set is a
reachability antichain. The antichain criterion therefore proves that the graph
is transitively minimal. ∎

For an unbounded history, the same proof applies. Every edge and every proposed
replacement path belongs to a finite prefix, and all dependency paths are finite
by definition. No final occurrence or finite complete vertex set is required.

## Scope

This theorem begins with a valid resolved history. The separate
source-to-history proof must still establish that resolving valid Define source
produces that history. Compiler conformance must separately establish that the
implemented operation graph equals the calculated graph, including modular
Action Parent resolution. Neither obligation is assumed by the antichain
argument above.
