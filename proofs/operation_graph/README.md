# Operation Graph Proofs

These proofs investigate whether Define's
[Particle Operation Dependency Graph](../../define/spec/spec.md#the-particle-operation-dependency-graph)
preserves particle-operation requirements and provides a transitively minimal
graph for safe concurrency.

## Current proof

The English argument derives position and particle requirements from the
specification, distinguishes vacancy from retained destructor state, and proves
schedule safety and necessity of the remaining dependencies. It does not impose
whole-action barriers or keep every ancestor alive for a descendant operation.

Lean checks the exact-effect collection, incremental Comparison calculation, and
graph and scheduling results used by that argument. The rules themselves produce
transitive minimality; no later minimization algorithm is applied. Lean also
checks the structured-reference and occupancy transitions in
[`particle_requirements.lean`](definitions/particle_requirements.lean), the
shared-state components in
[`retained_requirements.lean`](definitions/retained_requirements.lean), and
their execution correspondence in
[`particle_scheduling.lean`](theorems/particle_scheduling.lean).

The [Vanish extension](theorems/vanishment-proof.md) derives lifetime candidates
from actual references and directly moved particles, with no new ordering among
Creates, Moves, or Vacates. Its lifetime components are checked in
`vanishment_requirements.lean`. `vanishment_graph.lean` checks that adding the
Vanishes preserves existing reachability, acyclicity, and transitive minimality.

The derivation of those representations from valid source, geometric
accessibility, and completion of destruction is an English argument. This is not
a Lean-checked compiler or a fully formalized source-language semantics.

Maximum safe concurrency here means that removing a remaining dependency would
admit an invalid execution within the chosen dependency orientation. It does not
mean that one graph admits every possible safe serial ordering of destructors.

## Reading order

1. [Conceptual definitions](definitions/definitions.md#conceptual-meaning-of-particles-positions-and-operations)
   and [operation requirements](definitions/operation-requirements.md): what
   particles, positions, references, and operations mean.
2. [Reference shape](theorems/reference-shape-proof.md) and
   [ordinary correspondence](theorems/ordinary-requirements-proof.md): how
   actual references and relative occupancy preserve Create and Move semantics.
3. [Vacancy and retained state](theorems/retained-state-proof.md): how
   simultaneous selection, replacements, and shared destructor operations
   interact without imposing a destruction-group barrier.
4. [Graph construction](theorems/requirement-construction.md): collection, local
   removal of redundant candidates, and completion of destruction.
5. [Scheduling proof](theorems/requirement-scheduling-proof.md): safety, edge
   necessity, and unbounded execution.
6. [Vanish extension](theorems/vanishment-proof.md): lifetime collection, source
   correspondence, graph safety and necessity, and concurrency-preserving
   fusion.

[Ordering derivation](theorems/ordering-derivation.md) explains why a serial
destructor-order choice is needed, and why a direct implied reference can allow
more concurrency than a written reference through the caller's position.
[Exact effects](definitions/operation-effects.md) presents the mathematical
exchange and graph results reused in the scheduling proof.
[Established mathematical results](theorems/external-results.md) gives the exact
correspondences, external citations, and limits of the library results reused
here.

## Directory guide

- `definitions/` contains conceptual definitions and mathematical models.
- `theorems/` contains English arguments and Lean proofs.
- `witnesses/` contains the checked destructor-order counterexample. Examples
  support the general arguments; they do not replace them.

See [Building proofs](../README.md#building-proofs) for the Lean build command.
