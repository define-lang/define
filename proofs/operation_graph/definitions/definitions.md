# Shared Definitions for the Operation Graph Proofs

## Purpose

The conceptual definitions apply throughout the operation graph proofs. The
[requirement construction](../theorems/requirement-construction.md) preserves
actual references, relative occupancy, and particle existence.

The relevant specification sections are:

- [Position References](../../../define/spec/spec.md#position-references);
- [Moving Particles](../../../define/spec/spec.md#moving-particles);
- [Destroying Particles](../../../define/spec/spec.md#destroying-particles);
- [Action Contracts](../../../define/spec/spec.md#action-contracts); and
- [Deterministic Automatic Concurrency](../../../define/spec/spec.md#deterministic-automatic-concurrency).

## Conceptual meaning of particles, positions, and operations

The mathematical representations below must preserve the following conceptual
meaning. This is the interpretation of the specification used by these proofs,
not an additional set of dependency rules.

A particle is a concrete thing that exists in the program's universe. It has
qualities, which can include defining positions and actions.

A position is a location in space that may be empty or occupied by one particle.
A particle can define other positions relative to itself, and those positions
may be occupied by other particles.

Replacing a particle does not by itself make its positions different spatial
locations. If a particle at `p` defines the position quality `/c`, and a
replacement particle at `p` defines that same quality, its `p::/c` is the same
spatial position. However, the specification's Simultaneous Transitive
Destruction rules distinguish the original particles from replacements. Once the
original parent's Vacate empties `p`, its old child no longer occupies the
replacement's `p::/c`. Unfinished destruction work continues to act on the
original particles and positions, not on replacements. A model must therefore
distinguish occupancy available to subsequent operations from particles and
positions retained for unfinished destruction work.

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
  destructors. Actual destruction must respect the last interactions specified
  by Destructors and Destruction Ordering; it is not another interpretation of
  the vacancy vertex.
- **Vanish:** end the selected particle's existence after its Vacate and after
  the interactions that still require it. Vanish is separate from making its
  former position available for reuse. Its dependencies are not supplied by the
  Create, Move, and Vacate construction.

Position names and references describe these spatial relationships; they are not
the relationships themselves. When a particle moves from `a` to `b`, the change
from a child reference `a::c` to `b::c` represents movement, not merely a
different spelling for an unchanged location. Preserving a particle's identity
does not make it independently addressable at any position. In particular, a
written Destroy Particle Statement at `b::c` cannot execute while `b` is empty.
An additional child Vacate selected by simultaneous destruction has no newly
written `b::c` reference: it selects the original position defined by its parent
particle, which can itself move. These two kinds of occurrence must not be
identified merely because a displayed graph gives them the same full name.

### Correspondence required of every proof model

The [operation-requirement derivation](operation-requirements.md) distinguishes
the requirements of actual position references from particle identity and
existence requirements. In particular, preserving a direct implied-position
reference does not require preserving the defining particle's spatial location
in the serial reference execution.

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
  required positions and occupancy. Do not silently retarget an operation or add
  an independent binding to a particle's identity to make a schedule work. For
  pending destruction work, use the specification's explicit preservation of the
  original particles and positions; do not look up replacements through their
  reused names. This exception does not waive a written reference's requirements
  at a Move destination. An implicit child selection, like a direct implied
  reference, does not acquire that written reference from its displayed name.
- Distinguish a completed simultaneous destruction from each individual
  destruction. A result about permuting only the selected Vacates does not
  establish that those Vacates may also be reordered across Creates or Moves.
- Distinguish a Vacate's vacancy from the end of the original particle's
  existence. A destructor's last-use requirement constrains the latter; it does
  not by itself impose an edge to or from the vacancy vertex. Destructors that
  interact with the same original particle share its changing state, not
  independent copies of the state before destruction.
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

A Position Reference preserves the particle supplying each quality it accesses.
Local positions are distinguished by their declaration and Action Execution;
positions defined by a particle are distinguished by that particle and quality.
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

A schedule is a linear extension of the required precedence relation. The
finite-schedule lemmas represent it as a list of distinct occurrences and use
adjacent exchanges of incomparable elements. Unbounded execution is checked
through finite prefixes; no theorem asserts termination or fairness.

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
