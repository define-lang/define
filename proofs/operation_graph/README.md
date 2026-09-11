# Operation Graph Proofs

This directory contains graph proofs and unfinished investigations of ordinary
occupancy dependencies, particle lifetime, and changing parent relationships.

## Work status — September 11, 2026

This is an incomplete research checkpoint, not a completed proof of the current
[Particle Operation Dependency Graph](../../define/spec/spec.md#the-particle-operation-dependency-graph).

- The English arguments were being revised for execution using resolved particle
  and position identities, including child operations independent of parent
  Moves and alternative orders for changing parent relationships. The proposed
  spec edits were subsequently reverted. Several arguments and correspondence
  tables still call those proposed rules "the specification" or name sections
  that are not in the current spec. Those claims have not been reconciled and
  must not be treated as established current-spec correspondence.
- The Lean formalizations have not been updated to match that English redesign.
  Their checked mathematical results do not establish the revised source
  correspondence, relationship constraints, or complete scheduling claims.
- The finite relationship-completion search is a research characterization and
  small-case oracle, not an accepted compiler or runtime algorithm. An efficient
  incremental construction without general ordering search remains unfinished.
  Minimality of the combined occupancy, lifetime, and relationship constraints
  also remains unproved.
- The action-boundary argument describes composition over a finite resolved
  expansion. It does not establish a compact independently compiled interface
  preserving all the information needed by callers and caller-known destructors.
- Work most recently shifted to whether runtime particle rearrangement is needed
  at all when symbolic reads and writes address already-resolved particles.
  Research-repo experiments support symbolic-access and lifetime dependencies
  without whole-action barriers under explicit assumptions. That conditional
  result is not formalized here and does not yet prove erasure correct for the
  whole language. Symbolic effects during destruction, including temporary
  changes restored before a destructor finishes, still need semantic decisions
  and verification.

Before resuming the scheduling redesign, determine which runtime semantics need
to be proved: observable particle rearrangements, symbolic execution with those
rearrangements erased, or both. Then reconcile the English arguments with the
chosen authoritative rules before completing the Lean correspondence. No change
to the spec is implied by this checkpoint.

## Reading order

Start with [source correspondence](theorems/source-correspondence.md), which
connects the specification's phases to the arguments and states their scope.

1. [Conceptual definitions](definitions/definitions.md#conceptual-meaning-of-particles-positions-and-operations)
   and [operation requirements](definitions/operation-requirements.md)
   distinguish particles, relative positions, serial name resolution, and
   runtime effects.
2. [Ordinary correspondence](theorems/ordinary-requirements-proof.md) explains
   endpoint occupancy and why a child-position operation need not wait for a
   parent Move. [Reference shape](theorems/reference-shape-proof.md) separates
   these requirements from circular parent relationships.
3. [Vacancy and retained state](theorems/retained-state-proof.md) covers
   simultaneous selection, shared destructor operations, replacement, and the
   end of occupancy preservation.
4. [Action boundaries](theorems/action-boundary-correspondence.md) distinguishes
   supplied particle identities from interface occupancy and identifies what
   composition must preserve.
5. [Graph construction](theorems/requirement-construction.md) proves the setter
   and Comparison invariants, ordinary reachability, and ordinary transitive
   minimality.
6. [Particle lifetime](theorems/vanishment-proof.md) derives Vanish candidates
   and proves independent insertion of Vanishes.
7. [Relationship conditions](theorems/relationship-ordering.md) characterizes
   legal arrangements using intervals and gives an exact finite completion
   search, including safe ways to divide that search into independent parts.
8. [Scheduling](theorems/requirement-scheduling-proof.md) combines occupancy,
   lifetime, and relationship legality without assuming that every safe order
   can be reached from another by legal adjacent exchanges.

[Ordering derivation](theorems/ordering-derivation.md) explains the permitted
destructor-order choice and why an ordinary precedence graph cannot represent
every alternative ordering. [Exact effects](definitions/operation-effects.md)
gives the generic component exchange lemmas.
[Established mathematical results](theorems/external-results.md) records exact
library correspondences and their hypotheses.

## Distinctions between the results

Ordinary dependency acyclicity and acyclicity of particle relationships are
different properties. Likewise, ordinary transitive minimality does not prove
that an edge or condition is necessary in the combined representation.
Relationship conditions can jointly imply additional precedence.

Maximum concurrency concerns all permitted complete orders of the same
identified occurrences, after fixing the destructor ordering allowed by the
specification. It is not merely the inability to remove an edge from one DAG.
The finite completion theorem does not imply termination of unbounded execution
or a runtime fairness guarantee.

The generic Lean Comparison and graph theorems verify their mathematical
calculations. Their application to source requires the stated correspondence. In
particular, a structured-reference model that checks written intermediate
occupancy at execution time has different requirements from the specification's
identified-endpoint execution. Verification of that model cannot substitute for
formalizing the latter and its relationship conditions.

## Directory guide

- `definitions/` contains conceptual definitions and mathematical models.
- `theorems/` contains English arguments and Lean proofs.
- `witnesses/` contains the checked destructor-order counterexample. Examples
  support the arguments; they do not replace them.

See [Building proofs](../README.md#building-proofs) for the Lean build command.
