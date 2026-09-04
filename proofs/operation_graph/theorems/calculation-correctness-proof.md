# Particle Operation Dependency Graph Calculation Correctness

## Claim

For every valid resolved Particle Operation history, the recursive calculation
in
[Particle Operation Dependency Graph Calculation](../definitions/calculation.md)
produces a graph that satisfies all of the history, candidate, and
exact-dependency facts used by the minimality and completeness proofs.

This theorem is a bridge. It does not assume or prove that the calculated graph
is complete or transitively minimal. Instead, it replaces the manually supplied
calculation facts in those proofs with consequences of one arbitrary valid
resolved history.

## Resolved-name persistence

The graph calculation keeps a most-recent-operation entry by resolved position
name, including while that name is empty. A valid resolved history therefore has
the following invariant:

> If a previous Particle Operation operated on a resolved position name, that
> name may still be queried by the graph calculation at every later occurrence.

This does not say that the position is occupied or that Define source may use
the name at that point. It says that the compiler retains the graph identity of
the resolved name. The Empty Rule needs that identity when a later operation
empties a related position. A Move additionally writes entries under the changed
names of the moved particle's transitive child positions.

The source-to-history construction must derive this persistence from resolved
Position Definitions and Action Executions. Local positions belonging to
separate Action Executions need distinct names, but shared implied positions and
reused interface positions must retain their names across executions. An
execution may therefore collect an earlier execution's Particle Operation on one
of those shared positions. Distinct occurrence identities do not imply distinct
resolved positions.

## Entry facts

Fix a valid resolved history. Write `Eᵢ(p) = A` when `A` is the entry for
position name `p` immediately before occurrence `Oᵢ`.

### Lemma 1: direct operations write their operated positions

If `A` operates on `p`, then `A` writes the entry for `p`.

#### Proof

A Create or Destroy has one operated position, and its entry update writes that
position. A Move operates directly on its source and target, and its entry
update writes both. These are all operation kinds. ∎

### Lemma 2: every writer has operated-position provenance

If `A` writes the entry for `p`, then `A` operates on some position `a` such
that `a ≼ p`. If `A` is not a Move, then `a = p`.

#### Proof

For a Create or Destroy, the written and operated positions are identical. A
Move directly writes its source and target. Every other entry written by the
Move has the form `t · r`, where `t` is the target, so the Move operates on the
parent position `t`. Only the Move case can write a position other than one of
its direct operated positions. ∎

### Lemma 3: entries exist after an earlier direct operation

Suppose `A < Oᵢ` and `A` operates on `p`. Then `Eᵢ(p)` exists. Its operation is
`A` or is more recent than `A`.

#### Proof

By resolved-name persistence, `p` may be queried at index `i`. By Lemma 1, `A`
writes `p`, so the set of writers of `p` before `i` is nonempty. It is a subset
of the `i` previous occurrences and is therefore finite. Choose its member `B`
with greatest occurrence index. The definition of the entry gives `Eᵢ(p) = B`.
Since `A` is one of the writers, `B = A` or `B` is more recent than `A`. ∎

### Lemma 4: an entry is unique and previous

For fixed `i` and `p`, at most one operation is `Eᵢ(p)`, and that operation is a
previous occurrence of `Oᵢ`.

#### Proof

The entry definition requires its operation to precede `i`. If two operations
satisfied the definition, their distinct occurrence indices would be ordered.
The later one would contradict the earlier one's requirement that no later
writer precede `i`. Equal indices identify the same occurrence. ∎

## Candidate facts

Let `O` be an occurrence at index `i`.

### Lemma 5: Empty candidates

The source candidates calculated for `O` are exactly the entries `Eᵢ(p)` for
queryable names `p` related to the position emptied by `O`.

Every such candidate:

- is a previous Particle Operation;
- has an operated position that is `p` or a parent position of `p`; and
- operates on `p` itself when it is not a Move.

Furthermore, if a previous operation `A` operates on a position `p` related to
the emptied position, the source candidates contain an entry at `p` that is `A`
or is more recent than `A`.

#### Proof

The first statement unfolds the source-candidate definition. The three facts
follow from Lemmas 2 and 4. The final statement follows from Lemma 3 and the
assumed relationship between `p` and the emptied position. ∎

### Lemma 6: the Fill candidate

The Fill candidate, when it exists, is the unique most recent entry among the
queryable names that are the filled position or its parent positions. It is a
previous Particle Operation and has an operated position that is a parent
position of the filled position.

If a previous operation `A` operates on the filled position or one of its parent
positions, the Fill candidate exists and is `A` or is more recent than `A`.

#### Proof

The entry at each queried name is unique by Lemma 4. All entries are among the
finitely many previous occurrences, so a nonempty set of entries has one member
with greatest index. This is exactly the calculated Fill candidate.

For the final statement, let `p` be the position operated on by `A`.
Resolved-name persistence and Lemma 3 supply an entry at `p` that is at least as
recent as `A`. The selected Fill candidate is at least as recent as that entry.
Lemma 2 gives its operated-position provenance. ∎

## Prefix-graph facts

Let `Gᵢ` be the dependency relation constructed before `Oᵢ`, and let `G` be the
union of all finite-prefix relations.

### Lemma 7: every prefix edge points backward

If `X -> Y` is in `Gᵢ`, then both operations occur before index `i` and `Y < X`.

#### Proof

Proceed by induction on `i`. The statement is vacuous for `G₀`. An edge in
`Gᵢ₊₁` is either already in `Gᵢ` or was added for `Oᵢ`. The induction hypothesis
handles an old edge. Every new dependency is in the calculated Collection: for a
Create it is the Fill candidate; for a Destroy it survives the Empty stages; and
for a Move it survives the combined Move stages. Lemmas 5 and 6 say every
Collection member precedes `Oᵢ`. Thus every new edge also points backward. ∎

### Lemma 8: prefix edges are stable

If `i ≤ j`, then `Gᵢ` is a subrelation of `Gⱼ`. Moreover, an edge whose source
occurs before `i` belongs to `Gⱼ` exactly when it belongs to `Gᵢ`.

#### Proof

Each construction step retains every old edge and adds edges only from the
occurrence at that step. This proves inclusion by induction on `j - i`. For the
second statement, no step at or after `i` can add another edge from an earlier
source occurrence, because occurrence indices are unique. ∎

### Lemma 9: prefix and complete reachability agree below the prefix

If `X` occurs before `i`, then for every `Y`,

```text
X reaches Y in Gᵢ  if and only if  X reaches Y in G.
```

#### Proof

The forward implication follows from prefix inclusion. For the reverse
implication, follow a finite path from `X` in `G`. Lemma 7 makes occurrence
indices decrease along every edge, so every source on the path also occurs
before `i`. Lemma 8 places every edge of the path in `Gᵢ`. ∎

## Exact correspondence with the resolved rules

### Lemma 10: the step calculation equals the complete-graph calculation

For `Oᵢ`, calculating its dependencies against `Gᵢ` gives the same set as
calculating them against `G`.

#### Proof

Collection and Comparison do not inspect a dependency relation. Move Correction
and the Move Rule's Fill Dependency removal inspect reachability only between
members of the Collection. Lemmas 5 and 6 make every such member a previous
occurrence of `Oᵢ`. Lemma 9 therefore gives the same answer to every
reachability query in `Gᵢ` and `G`. Every stage consequently retains the same
candidates. ∎

### Lemma 11: exact dependency equation

For every occurrence `O` and candidate `A`,

```text
O -> A is in G

if and only if

the Fill, Empty, or Move calculation for O against G retains A.
```

#### Proof

Let `i` be the index of `O`. By construction, `Gᵢ₊₁` adds exactly the
dependencies calculated for `O` against `Gᵢ`. Lemma 8 says no later prefix
changes the edges from `O`. Lemma 10 replaces `Gᵢ` by `G` in the calculation. ∎

## Universal construction theorem

For every valid resolved history, take:

- its occurrence predicate as the graph vertices;
- `G` as the dependency relation;
- its occupancy trace as the exact occupancy execution;
- the calculated source-entry relation as source-candidate provenance; and
- the calculated rule inputs for every occurrence.

Then:

1. Lemma 11 gives exact correspondence between direct dependencies and the three
   resolved graph rules.
2. Lemmas 4 through 6 give every candidate-membership, previous-operation, and
   operated-position fact required by the minimality and completeness proofs.
3. The valid-history occupancy theorems give the exact Create, Destroy, and Move
   transitions used by those proofs.
4. Lemma 7 gives backward edges independently of any acyclicity or minimality
   conclusion.

Thus the calculated graph satisfies the complete shared interface consumed by
the independent minimality and completeness arguments. No field of that
interface needs to assume minimality, completeness, acyclicity, or the desired
reachability relation. ∎

## Remaining boundary

This theorem begins with a valid resolved history. A separate source-to-history
proof must still show that resolving valid Define source produces its occurrence
order, occupancy states, distinct resolved names, name-persistence trace, and
Move name changes. The theorem above then applies uniformly to every such
history, whether it stops after finitely many occurrences or continues without
end.
