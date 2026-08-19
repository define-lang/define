# Operation Graph Proofs

The main argument has one foundation, two independent principal results, and one
point where those results are deliberately combined:

```text
shared definitions
        |
valid resolved histories
        |
graph calculation
        |
calculation correctness
        |
        +-------------------+
        |                   |
   minimality          completeness
        |                   |
        +---------+---------+
                  |
          characterization
                  |
       maximum safe concurrency
```

Minimality never assumes completeness, and completeness never assumes
minimality. Characterization is the first proof allowed to depend on both.
Maximum safe concurrency is a downstream consequence of the characterized
reachability; it is not used to establish the graph results.

## Recommended reading order

1. Begin with [Shared Definitions](definitions/definitions.md), which fixes
   resolved Particle Operations, positions, occurrence order, occupancy, and
   graph notation without assuming any dependency rule. Then read
   [Valid Resolved Histories](definitions/valid-history.md), which states the
   rule-independent history properties available to every later proof. These
   documents expose the source-to-history obligations that remain outside the
   current formal model.
2. Read
   [Particle Operation Dependency Graph Calculation](definitions/calculation.md)
   for the actual Fill, Empty, and Move calculation. Its result is only a
   constructed relation; none of the desired graph properties are assumed. Then
   read [Calculation Correctness](theorems/calculation-correctness-proof.md),
   the essential bridge proving that this construction has all candidate,
   recency, occupancy, and exact-dependency facts consumed downstream.
3. Read the two principal graph proofs in either order.
   [Minimality](theorems/minimality-proof.md) proves that the calculated graph
   is an acyclic, transitively minimal graph.
   [Completeness](theorems/completeness-proof.md) separately proves that every
   previous operation on a related operated position is reachable. Auditing the
   full graph result requires both, but neither proof may borrow the other's
   conclusion.
4. Read [Characterization](theorems/characterization-proof.md) only after both
   principal proofs. It identifies reachability with the transitive closure of
   the related-and-previous relation and proves uniqueness among transitively
   minimal relations that respect the occurrence order.
5. Read [Maximum Safe Concurrency](theorems/maximum-safe-concurrency-proof.md)
   for the occupancy scheduling consequence, the finite and unbounded-history
   cases, and the counterexample to the stronger global-maximum claim.

The key graph-correctness documents are therefore Calculation Correctness,
Minimality, Completeness, and Characterization. The earlier documents are
necessary to audit their definitions and assumptions; Maximum Safe Concurrency
uses the graph result for a separate behavioral theorem.

## Lean correspondence and supporting evidence

The `definitions` package contains the rule-independent model, valid-history
properties, and the calculated dependency relation. The `theorems` package
starts with `calculation_correctness.lean`; `minimality.lean` and
`completeness.lean` independently import that foundation, and
`characterization.lean` is the first module to import both.

The maximum-safe-concurrency proof then divides into three branches.
`calculated_schedule_execution.lean` combines characterization with finite and
unbounded scheduling to prove sufficiency. `cover_order.lean` supplies generic
cover theory; `cover_schedule_order.lean` constructs adjacent calculated cover
schedules; and `cover_schedule_necessity.lean` combines that order construction
with `occupancy_noncommutation.lean` to prove finite-prefix necessity and extend
the counterexample to complete stopped and unbounded schedules. The
order-theoretic branch begins with `cover_graph.lean`;
`calculated_cover_graph.lean` then identifies the calculated relation with that
cover graph, and `stopped_dependency_edge_count.lean` derives the finite
fewest-edge result using `finite_relation_edge_count.lean`.
`maximum_safe_concurrency.lean` is the aggregate entry point for all three
branches. Every theorem-bearing Lean module has a Bazel axiom audit.

The `witnesses` package is supporting evidence rather than a link in the
universal proof chain. Its concrete histories establish non-vacuity and exercise
the calculation's name-retention, moved-child, Move Correction, and Fill
Dependency removal behavior. Its clause-specific independence modules apply the
complete calculation to valid histories while changing one clause at a time. The
aggregate witness modules collect these results, and `minimality_checker.py`
searches bounded concrete histories for counterexamples. None of this concrete
or bounded evidence substitutes for the universal English and Lean proofs above.
