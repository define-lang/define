# Shared Definitions for the Operation Graph Proofs

## Purpose

The conceptual definitions apply throughout the operation graph proofs. The
[requirement construction](../theorems/requirement-construction.md) preserves
identified positions, relative occupancy, and particle existence.

The relevant specification sections are:

- [Position References](../../../define/spec/spec.md#position-references);
- [Moving Particles](../../../define/spec/spec.md#moving-particles);
- [Destroying Particles](../../../define/spec/spec.md#destroying-particles);
- [Action Contracts](../../../define/spec/spec.md#action-contracts); and
- [Deterministic Automatic Concurrency](../../../define/spec/spec.md#deterministic-automatic-concurrency).

## Conceptual meaning of particles, positions, and operations

The mathematical representations below must preserve the following conceptual
meaning, as specified by Identifying Particles and Positions and the Particle
Operation effects. It is not an additional set of dependency rules.

A particle is a concrete thing that exists in the program's universe. It has
qualities, which can include defining positions and actions.

A position is a location in space that may be empty or occupied by one particle.
A particle can define other positions relative to itself, and those positions
may be occupied by other particles.

A position's identity includes the particle defining it. A replacement particle
has its own defined positions, even when references to them have the same
spelling and spatial location as references to the originals. Unfinished
destruction work continues to act on the original particles and positions, not
on replacements. A model must distinguish occupancy available to subsequent
operations from occupancy preserved for unfinished destruction work.

The Particle Operations have these conceptual effects:

- **Create:** bring a new particle into existence in an empty position,
  assigning the required qualities.
- **Move:** move an existing particle from an occupied source to an empty
  destination, leaving the source empty. The particle retains its identity and
  qualities. The positions it defines move with it, along with the particles
  occupying those positions, transitively. Their spatial relationships to the
  moved particle remain unchanged; their spatial relationships to the rest of
  the universe change. Empty positions defined by the particle move too.
- **Vacate:** represent the selected particle vacating its position, not the end
  of its existence or completion of its destructors. The vacancies in a
  simultaneous destruction are selected from one common preceding state. A
  later-executing Vacate does not select a replacement particle. The original
  particles remain available to destructors as though in their positions
  immediately before destruction, including movements performed by those
  destructors. Occupancy preservation ends after both the Vacate and the last
  direct Move requiring that occupancy. This is distinct from Vanishment:
  operations on the particle's own defined positions can require its existence
  after its incoming occupancy ends.
- **Vanish:** end the selected particle's existence after its Vacate and after
  the interactions that still require it. Vanish is separate from making its
  former position available for reuse. Its dependencies are not supplied by the
  Create, Move, and Vacate construction.

Position names and references describe these spatial relationships; they are not
the relationships themselves. When a particle moves from `a` to `b`, the change
from a child reference `a::c` to `b::c` represents movement, not merely a
different spelling for an unchanged location. The serial interpretation resolves
each written reference to the particular position on which the operation acts.
Execution does not retraverse the written names. Consequently an operation
written at `b::c` can act on the identified child position before its defining
particle moves to `b`, provided the operation's actual requirements and the
relationship conditions hold. This applies to written operations as well as
implicit transitive Vacates; the latter have no written reference to resolve.

### Correspondence required of every proof model

The [operation-requirement derivation](operation-requirements.md) distinguishes
serial reference resolution from runtime occupancy and existence requirements.
Using an identified position does not require preserving its defining particle's
spatial location in the serial interpretation, whether the written reference was
local, implied, interface, or chained.

These checks apply to existing English arguments and Lean formalizations as well
as new ones:

- Distinguish a particle's identity, its position, positions it defines, and the
  names used to describe those positions. State which of these each mathematical
  object represents.
- Represent a Move's transitive spatial effect, not just its source and
  destination occupancy or a renaming of an otherwise unchanged state. A model
  that records only occupied positions may omit empty positions only where that
  omission does not affect the property being proved.
- A reordered execution must execute the same Particle Operations with their
  identified positions and required occupancy. Derive the identities from the
  serial interpretation and Action Contracts; do not retarget an operation to
  whichever particle or position happens to be reachable at execution time. For
  pending destruction work, preserve the originals and their shared changes; do
  not look up replacements through their reused names.
- Distinguish a completed simultaneous destruction from each individual
  destruction. A result about permuting only the selected Vacates does not
  establish that those Vacates may also be reordered across Creates or Moves.
- Distinguish a Vacate's vacancy from the end of the original particle's
  existence. Distinguish a last use of incoming occupancy from a last use of the
  particle's defined positions. Destructors that interact with the same original
  particle share its changing state, not independent copies of the state before
  destruction.
- Separate graph facts from execution facts. Acyclicity, transitive minimality,
  and reachability characterization do not by themselves establish that the
  allowed executions preserve these concepts or provide maximum safe
  concurrency.

A representation is an abstraction of these concepts, not a replacement for
them. Its correspondence must be established for the claimed result before a
theorem about that representation is described as a theorem about Define.

## Occurrences, traces, and ranks

An occurrence is one Create, Move, Vacate, or Vanish, not an entire action.
Repeated executions of a statement give distinct occurrences. The serial
execution in Particle Operation Recency supplies the reference trace and the
particles selected by each reference and destruction.

The graph construction processes Create, Move, and Vacate occurrences in recency
order. An arbitrary enumeration of equal-recency Vacates is used only as a
natural-number rank for induction; it adds no dependency between them. The
[construction proof](../theorems/requirement-construction.md) shows why
processing one such Vacate cannot change another's candidates.

A Position Reference identifies its final position using the serial state.
Positions declared in an Action Statements Block distinguish their declaration
and Action Execution; interface positions instead persist on the assigned
action. Positions defined by a particle distinguish that particle and quality.
These mathematical identifiers describe positions, not a naming mechanism that
replaces spatial movement.

## Mathematical terminology

A dependency graph is a directed graph on operation occurrences. Its edge
`O -> D` means that `O` depends on `D`, so `D` must execute first. `Reaches` is
the positive transitive closure of that edge relation. Acyclicity means that no
vertex reaches itself.

A graph is transitively minimal if removing any edge changes reachability.
Direct dependencies form an antichain when no distinct pair of them is related
by reachability. A cover pair in a strict partial order has no intermediate
element. The proofs use these standard mathematical meanings, independently of
any claim that the relation captures all Define requirements.

A schedule lists distinct occurrences in execution order. It must extend the
ordinary precedence relation and satisfy the relationship conditions. Different
permitted schedules need not be connected by adjacent exchanges through
permitted schedules. The finite linear-extension lemmas apply to the ordinary
precedence relation, not by themselves to the additional relationship
conditions. Unbounded execution is checked through finite prefixes; no theorem
asserts termination or fairness.

The state models are products of occupancy and existence observations. An effect
is a partial state transformation: its requirements determine when it is
defined, and its changes determine the resulting state. The
[effect definitions](operation-effects.md) and
[standard mathematical correspondences](../theorems/external-results.md) give
the precise constructions and the library results reused.

## Verification boundary

The English proofs derive the state observations and lifetime requirements from
Define source. Lean checks the stated mathematical models and graph
calculations. A valid Lean term is not itself proof that the compiler implements
the spec, or that the translation from source to that model is fully formalized.
