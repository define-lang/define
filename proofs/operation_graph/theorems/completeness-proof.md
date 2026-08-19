# Particle Operation Dependency Graph Completeness

## Claim

For every valid resolved Particle Operation history, let `G` be the graph
calculated by the Fill, Empty, and Move Rules. If `A` is previous to `O` and
some position operated on by `A` is related to some position operated on by `O`,
then `O` reaches `A` in `G`.

This proof does not assume or prove transitive minimality. It proves only that
the calculated graph contains a dependency path for every such related and
previous pair.

## Definitions and notation

Write `A < O` when `A` has a smaller occurrence index than `O`. Write `O > A`
when `O` reaches `A` through one or more dependency edges.

For occurrences `O` and `A`, write `O R A` when:

1. `A < O`; and
2. a position operated on by `O` is related to a position operated on by `A`.

The theorem is therefore `O R A` implies `O > A`. The relation `R` depends only
on the valid resolved history's occurrence order and operated positions. It does
not mention a graph rule.

For one operation `O`, its _Collection_ is the combined set on which its rule
stages operate: the source-side entries selected by the Empty Rule and the
optional Fill Dependency selected by the Fill Rule. A Create can have only the
Fill Dependency, a Destroy can have only source-side entries, and a Move can
have both.

## Inputs from the preceding proof components

[Particle Operation Dependency Graph Calculation Correctness](calculation-correctness-proof.md)
proves these facts for every valid resolved history:

1. Every Collection member is previous to `O` and is a concrete Particle
   Operation from the history.
2. Every dependency edge points to a previous occurrence.
3. Every candidate retained by the final applicable rule stage is exactly a
   direct dependency.
4. If a previous operation `A` operated on a name related to an emptied
   position, the source-side Collection contains an entry `C` that is `A` or is
   more recent than `A`. The entry operates on that name or one of its parent
   positions.
5. If `A` operated on a filled position or one of its parent positions, the Fill
   Dependency `C` exists, is `A` or is more recent than `A`, and operates on a
   parent position of the filled position.
6. Create, Destroy, and Move have their exact occupancy preconditions and
   transitions.

These inputs do not assume completeness, transitive minimality, or any desired
reachability relation.

## Backward paths

Every edge points from a greater occurrence index to a smaller one. Induction on
a dependency path therefore gives:

```text
X > Y implies Y < X.
```

This fact will make every rule-stage survivor chase terminate. It follows from
candidate recency, not from minimality.

## Rule-stage survivor lemma

Fix an operation `O`. Assume the completeness claim has already been proved for
every operation previous to `O`. Then `O` reaches every member of its
Collection.

### Comparison

Start with any Collection member `A`. If the simultaneous Comparison retains
`A`, stop. Otherwise, some Collection member `B` excludes it: `B` is more recent
than `A`, and `B` and `A` operate on related positions.

Both operations are previous to `O`, so the induction hypothesis applies to the
pair `B R A` and gives `B > A`. Repeat from `B` if the Comparison also excludes
`B`.

Every repetition chooses a greater occurrence index while remaining below the
index of `O`. Only finitely many natural-number indices lie in that interval, so
the process ends at a Comparison survivor `S`. Joining the paths found at each
step gives either `S = A` or `S > A`.

The Comparison is simultaneous. Therefore an excluded operation can serve as one
step of this chase even when a still more recent operation also excludes it.

### Move Correction

Start with a Comparison survivor `A`. If the Move Correction retains it, stop.
Otherwise, the correction itself supplies a distinct Comparison survivor `B`
with `B > A`. A backward path makes `B` more recent than `A`.

Repeat from `B`. The same bounded-index argument ends at a Move Correction
survivor `S`, with `S = A` or `S > A`.

### Move Rule's Fill Dependency removal

Start with a Move Correction survivor `A`. If the Move Rule retains it, stop.
Otherwise, `A` is the Fill Dependency and the removal condition supplies a
distinct retained source-side candidate `B` with `B > A`.

Repeating from `B` again increases the occurrence index without reaching the
index of `O`. The chase ends at a final Move dependency `S`, with `S = A` or
`S > A`.

### Reaching the original Collection member

For a Create, every Collection member is its Fill Dependency and is already a
direct dependency.

For a Destroy, apply the Comparison chase and then the Move Correction chase.
For a Move, apply all three chases. In either case the final survivor `S` is a
direct dependency of `O`, and it equals or reaches the original Collection
member `A`. Thus `O -> S` followed by the accumulated path proves `O > A`.

This establishes the rule-stage survivor lemma. Notice that it uses the
completeness induction hypothesis only for operations strictly previous to `O`.
It does not assume the result for `O` itself.

## Empty-position lemma

Assume the completeness claim below `O`. Let `O` empty position `s`, and let a
previous operation `A` operate on position `a` with `a ~ s`. Then `O > A`.

### Proof

The latest-source-candidate property supplies a source-side entry `C` selected
at `a`. The rule-stage survivor lemma gives `O > C`.

If `C = A`, the result follows. Otherwise, `C` is more recent than `A`. The
operated-position provenance of `C` supplies a position `c` operated on by `C`
with `c ≼ a`. Hence `c ~ a`, so `C R A`. Both `C` and `A` are previous to `O`;
the induction hypothesis gives `C > A`. Joining the two paths gives `O > A`. ∎

## Filled-position parent lemma

Assume the completeness claim below `O`. Let `O` fill position `t`, and let a
previous operation `A` operate on `a` with `a ≼ t`. Then `O > A`.

### Proof

The latest-fill-candidate property supplies a Fill Dependency `C`. The
rule-stage survivor lemma gives `O > C`.

If `C = A`, the result follows. Otherwise, `C` is more recent than `A` and
operates on some `c ≼ t`. The positions `a` and `c` are both prefixes of `t`, so
one is a prefix of the other and they are related. Thus `C R A`. The induction
hypothesis gives `C > A`, and joining the paths gives `O > A`. ∎

## Filled-position strict-child lemma

Assume the completeness claim below `O`. Let `O` fill position `t`, and let a
previous operation `A` operate on a strict child position `a` of `t`. Then
`O > A`.

### Proof

Immediately after `A`, position `t` is occupied:

- a Create or Move to `a` requires `t` in order for `a` to be available;
- a Destroy at `a` requires `a`, and therefore `t`, to be occupied and does not
  destroy its strict parent positions; and
- a Move from `a` likewise requires `a` to be occupied and does not empty its
  strict parent positions.

Immediately before `O`, position `t` is empty because `O` fills it. Among the
finitely many transitions between those occurrence indices, choose the first one
that changes `t` from occupied to empty. The exact occupancy transition supplies
an operation `K` at that transition and a position `k` operated on by `K` with
`k ≼ t`.

The filled-position parent lemma gives `O > K`. Also, `K` is more recent than
`A`, and `k ≼ t ≺ a`, so `K R A`. The induction hypothesis gives `K > A`.
Joining those paths proves `O > A`. ∎

No termination assumption is hidden here: the interval from `A` to the
particular occurrence `O` contains only finitely many indices even when the
complete history is unbounded.

## Completeness theorem

Proceed by induction on the natural-number occurrence index of `O`. The
induction hypothesis is the completeness claim for every operation with a
smaller index. Fix `A` with `O R A`, and choose related operated positions `o`
of `O` and `a` of `A`.

There are three operation-kind cases.

### Create

A Create operates only on its filled position `o`.

- If `a ≼ o`, apply the filled-position parent lemma.
- Otherwise, relatedness gives `o ≺ a`; apply the filled-position strict-child
  lemma.

### Destroy

A Destroy operates only on its emptied position `o`. Apply the empty-position
lemma.

### Move

A Move operates on its source and target positions.

- If `o` is the source, apply the empty-position lemma.
- If `o` is the target and `a ≼ o`, apply the filled-position parent lemma.
- If `o` is the target and `o ≺ a`, apply the filled-position strict-child
  lemma.

These cases exhaust the operated positions and both directions of relatedness.
Every use of the induction hypothesis concerns an operation previous to `O`, so
the induction is well founded. Therefore `O R A` implies `O > A` for every pair
in every valid resolved history. ∎

## Coverage of resolved operation forms

Automatic Destroy Particle Statements and Destroy Particle Statements
contributed by destructors or Destruction Contracts are concrete Destroy
occurrences in a valid resolved history. They use the Destroy case above; no
additional graph-vertex kind is needed.

Moved transitive-child names are covered by the source-entry provenance that
allows a Move on a parent position to be the entry selected for a child name.
The survivor lemma then treats that entry through the Move Correction like every
other Move candidate.

Action Requirements, Action Guarantees, and requirements or guarantees on
implied positions have already contributed their resolved names and concrete
Particle Operations when this theorem begins. The proof applies to the resulting
occurrences without treating those resolution mechanisms as graph vertices. The
Action Parent position restricts the positions on which those occurrences may
operate but does not add another completeness case.

## Scope

This theorem begins with a valid resolved history. The source-to-history proof
must separately show that resolving valid Define source produces that history,
including its occurrence order, concrete operations, resolved-name persistence,
and Move name changes. Compiler conformance must separately show that the
implemented graph is the graph calculated from that history.

The theorem does not say that reachability contains only paths required by `R`,
that any dependency is irredundant, or that the graph is unique. Those results
combine completeness with independent facts and belong to the later
characterization proof.
