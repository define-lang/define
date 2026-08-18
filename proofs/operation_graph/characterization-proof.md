# Particle Operation Dependency Graph Characterization

## Claims

For every valid resolved Particle Operation history, let `G` be the graph
calculated by the Fill, Empty, and Move Rules, and define `R` by

```text
O R A exactly when A is previous to O and
some position operated on by O is related to
some position operated on by A.
```

Then:

1. reachability in `G` is exactly the transitive closure of `R`; and
2. among dependency relations that point backward in the same occurrence order
   and have this reachability, `G` is the unique transitively minimal relation.

These are combined results. They use both the independent completeness and
minimality theorems but are not premises of either theorem.

## Inputs

[Particle Operation Dependency Graph Minimality](minimality-proof.md) proves
that `G` points backward in the occurrence order and is transitively minimal. It
also proves that every direct dependency joins operations with related operated
positions.

[Particle Operation Dependency Graph Completeness](completeness-proof.md) proves
that every `R` pair is reachable in `G`.

The shared definitions make every dependency path finite, even when the valid
resolved history is unbounded.

## Reachability characterization

For operations from the history,

```text
O reaches A in G

if and only if

O reaches A through one or more R steps.
```

### From graph reachability to `R` reachability

Consider one direct dependency `X -> Y`. Every dependency points backward, so
`Y` is previous to `X`. The direct-dependency position lemma supplies related
positions operated on by `X` and `Y`. Hence `X R Y`.

Replace every edge of a finite dependency path by that `R` step. This turns any
path in `G` into a path in `R` with the same endpoints.

### From `R` reachability to graph reachability

The completeness theorem turns every `R` step `X R Y` into a dependency path
`X > Y` in `G`. Replace every step of a finite `R` path by its corresponding
dependency path and join those paths. This produces a path in `G` with the same
endpoints.

The two transformations prove equality of the reachability relations. Neither
direction assumes that the complete occurrence set is finite. ∎

## Uniqueness lemma

Let `D₁` and `D₂` be two dependency relations on the same occurrences. Assume:

1. every edge in either relation points to a smaller occurrence index;
2. both relations are transitively minimal; and
3. `D₁` and `D₂` have the same reachability.

Then `D₁` and `D₂` have exactly the same edges.

### Proof

Take an edge `O -> A` of `D₁`. Equal reachability supplies a path from `O` to
`A` in `D₂`. If that path is the direct edge `O -> A`, the edge belongs to `D₂`
as required.

Otherwise, write the path as

```text
O -> X -> ... -> A.
```

Equal reachability supplies a `D₁` path from `O` to `X` and a `D₁` path from `X`
to `A`. Their concatenation is a second `D₁` path from `O` to `A`. It remains to
show that this path does not use the edge `O -> A`.

The `D₂` path points backward, so

```text
index(A) < index(X) < index(O).
```

Every `D₁` path also points backward.

- The path from `O` to `X` cannot begin with `O -> A`, because it would then
  have to reach the more recent `X` from the older `A`.
- After that path leaves `O`, all its remaining sources have smaller indices
  than `O`, so none can be the source of the edge `O -> A`.
- Every source on the path from `X` to `A` likewise has a smaller index than
  `O`.

Thus the concatenated path avoids `O -> A`. This contradicts the transitive
minimality of `D₁`. The supposedly longer `D₂` path is impossible, so every edge
of `D₁` is an edge of `D₂`.

Apply the same argument with the two relations exchanged. Their edge relations
are equal. ∎

The occurrence-index premise matters for this proof. The result is not claiming
that arbitrary cyclic relations or arbitrary orders have a unique transitive
reduction.

## Characterization theorem

The calculated graph `G` points backward and is transitively minimal by the
minimality theorem. Its reachability is the transitive closure of `R` by the
reachability characterization above.

Let `D` be any other dependency relation that points backward in the same
occurrence order, is transitively minimal, and has the same reachability. Apply
the uniqueness lemma to `G` and `D`. It follows that `D` and `G` contain exactly
the same direct dependencies. ∎

## Consequence for automatic concurrency

The characterization identifies the exact ordering relation calculated by the
Fill, Empty, and Move Rules: it is the unique transitively minimal,
occurrence-order-respecting relation whose reachability is the transitive
closure of `R`.

This does not by itself prove that every schedule respecting that relation has
the same behavior. The maximum-safe-concurrency proof separately establishes the
applicable occupancy commutation and scheduling results. It also states the
limits of the claim for particle identity, qualities, Action triggering,
destructor effects, and other observations.

The separate maximum-safe-concurrency proof identifies this relation with the
cover-pair graph and proves that every relation with the same reachability
contains all of its edges. Thus the calculated relation is the unique
inclusion-minimal relation even for an unbounded history. When a valid resolved
history stops after finitely many occurrences, any different relation with the
same reachability has the finite cover-edge set plus at least one additional
edge, so the calculated relation is also the unique relation with the fewest
direct dependencies. Infinite edge counts are not compared.

## Coverage and scope

The characterization quantifies over the concrete occurrences and resolved
positions in a valid history. Automatic and contributed Destroy Particle
Statements, operations obtained through Action resolution, implied positions,
and moved transitive-child names are covered because the independent premises
already cover them. The Action Parent Rule remains modular compiler-resolution
behavior rather than another edge kind in `G`.

Source-to-history correspondence and compiler conformance remain separate
obligations. This theorem characterizes the specification-level graph calculated
from a valid resolved history; it does not assert that the current compiler
constructs that graph in every case.
