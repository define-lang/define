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

1. Begin with [Shared Definitions](definitions.md), which fixes resolved
   Particle Operations, positions, occurrence order, occupancy, and graph
   notation without assuming any dependency rule. Then read
   [Valid Resolved Histories](valid-history.md), which states the
   rule-independent history properties available to every later proof. These
   documents expose the source-to-history obligations that remain outside the
   current formal model.
2. Read [Particle Operation Dependency Graph Calculation](calculation.md) for
   the actual Fill, Empty, and Move calculation. Its result is only a
   constructed relation; none of the desired graph properties are assumed. Then
   read [Calculation Correctness](calculation-correctness-proof.md), the
   essential bridge proving that this construction has all candidate, recency,
   occupancy, and exact-dependency facts consumed downstream.
3. Read the two principal graph proofs in either order.
   [Minimality](minimality-proof.md) proves that the calculated graph is an
   acyclic, transitively minimal graph. [Completeness](completeness-proof.md)
   separately proves that every previous operation on a related operated
   position is reachable. Auditing the full graph result requires both, but
   neither proof may borrow the other's conclusion.
4. Read [Characterization](characterization-proof.md) only after both principal
   proofs. It identifies reachability with the transitive closure of the
   related-and-previous relation and proves uniqueness among transitively
   minimal relations that respect the occurrence order.
5. Read [Maximum Safe Concurrency](maximum-safe-concurrency-proof.md) for the
   occupancy scheduling consequence, the finite and unbounded-history cases, and
   the counterexample to the stronger global-maximum claim.

The key graph-correctness documents are therefore Calculation Correctness,
Minimality, Completeness, and Characterization. The earlier documents are
necessary to audit their definitions and assumptions; Maximum Safe Concurrency
uses the graph result for a separate behavioral theorem.

## Lean correspondence and supporting evidence

The Lean modules with matching names mirror the dependency diagram:
`definitions.lean` through `calculation_correctness.lean` form the foundation;
`minimality.lean` and `completeness.lean` independently import that foundation;
`characterization.lean` imports both; and `maximum_safe_concurrency.lean`
imports characterization together with the local exchange, finite-history, and
finite-schedule semantics from `occupancy_exchange.lean`,
`finite_history_schedule.lean`, `finite_schedule_order.lean`, and
`finite_scheduling.lean`. The minimality, completeness, and characterization
modules each expose a theorem stated directly for an arbitrary
`ValidResolvedHistory`, and every theorem-bearing Lean module has a Bazel axiom
audit.

The other files are supporting evidence, not links in the universal proof chain.
`create_destroy_history.lean` gives a concrete valid resolved history without
assuming a graph property; `non_vacuity_witness.lean` applies the actual
calculation to that history. `vanished_child_name_witness.lean` applies the same
path to a history retaining a queryable name after its particle vanishes, and
`moved_child_entry_witness.lean` proves the corresponding transitive-child
entries across consecutive Moves. Witness-only general lemmas flow through
`witness_support.lean`. `fill_dependency_removal_witness.lean` derives both
sides of the Move Rule's reachability check, and `minimality_witnesses.lean`
aggregates these concrete models. Clause-specific independence witness modules
apply the complete calculation to a valid history and share an executable
evaluator for variants changing one clause; `independence_witnesses.lean`
aggregates them. Their explanations live beside the executable models in those
modules. `minimality_checker.py` searches bounded concrete histories for
counterexamples. None of these witnesses or bounded searches substitutes for the
universal English and Lean proofs above.
