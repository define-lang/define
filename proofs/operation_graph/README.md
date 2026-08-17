# Operation Graph Proofs

- [Shared Definitions](definitions.md) defines resolved Particle Operations,
  positions, occupancy, and graph notation without assuming any dependency rule.
- [Valid Resolved Histories](valid-history.md) proves the occupancy invariants
  used by the graph arguments and identifies the remaining source-resolution
  obligations.
- [Particle Operation Dependency Graph Minimality](minimality-proof.md) proves
  that the graph the rules produce is a transitively reduced directed acyclic
  graph, and that it is the unique such graph whose reachability is determined
  by the operation order and operated positions alone.
- [Particle Operation Maximum Safe Concurrency](maximum-safe-concurrency-proof.md)
  proves that every execution order consistent with that reachability has the
  same occupancy behavior, and that no program-oriented ordering constraint can
  be removed while keeping every permitted order valid. It also gives a
  counterexample to the stronger global-maximum claim.

Lean formalizations and witness models sit beside the documents:

- `minimality.lean` checks transitive minimality, with a non-vacuity model in
  `minimality_witnesses.lean`.
- `completeness.lean` checks completeness, the uniqueness of the graph, and that
  the Action Parent Rule determines no edge after full resolution.
- `independence_witnesses.lean` checks the required-ordering or redundant-edge
  property of concrete witness graphs for the rule clauses covered there. The
  comments derive each graph from the full and weakened rules.
- `maximum_safe_concurrency.lean` checks that the occupancy state
  transformations for operations on unrelated positions commute.
- `minimality_checker.py` searches bounded concrete operation sequences for
  counterexamples to the minimality proof.
