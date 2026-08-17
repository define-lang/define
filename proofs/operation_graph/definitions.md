# Shared Definitions for the Operation Graph Proofs

## Purpose

This document defines the mathematical objects shared by the operation graph
proofs. It deliberately does not define the Fill, Empty, Move, or Action Parent
Rules. Those rules must be applied to this model and proved correct; they may
not be assumptions of the model.

The relevant specification sections are:

- [Position References](../../define/spec/spec.md#position-references);
- [Moving Particles](../../define/spec/spec.md#moving-particles);
- [Destroying Particles](../../define/spec/spec.md#destroying-particles);
- [Action Contracts](../../define/spec/spec.md#action-contracts); and
- [Deterministic Automatic Concurrency](../../define/spec/spec.md#deterministic-automatic-concurrency).

## Scope

The model describes occupancy and dependencies between resolved Particle
Operation occurrences. A Particle Operation is a Create Particle Statement, a
Move Particle Statement, or a Destroy Particle Statement.

The model does not treat an action as one operation. If an Action Execution
contributes five Particle Operations, those are five distinct occurrences. Two
Action Executions of the same Action Definition also contribute distinct
occurrences, even when they execute the same written statement.

Automatic destruction behaves as though the compiler had written the
corresponding Destroy Particle Statements. Particle Operations performed by a
destructor are ordinary resolved occurrences. When a Destruction Contract causes
another destructor to be verified at the recorded destruction, its Particle
Operations are likewise resolved at that destruction. The Destruction Contract,
Destruction Fact, and Child State are not themselves graph vertices.

Action Requirements and Action Guarantees are also not graph vertices. They
determine which source programs and Action Executions are valid and how a
callee's positions and Particle Operations are related to its caller. After
resolution, the graph contains only the resulting concrete Particle Operation
occurrences.

## Resolved positions

A _resolved position_ identifies one position for one particular sequence of
Action Executions and particles. Thus, the same global position name used by two
different Action Executions denotes two different resolved positions.

For the proof, represent a resolved position by its sequence of position-name
components. Action names that occur between position names in Define syntax do
not add another position component. The occurrence identities associated with
the components distinguish separate Action Executions.

Write

```text
p ⪯ q
```

when `p` is `q` or a transitive parent position of `q`. Equivalently, the
sequence for `p` is a prefix of the sequence for `q`. Write `p ≺ q` when `p` is
a strict transitive parent position of `q`.

Write

```text
p ~ q
```

when `p ⪯ q` or `q ⪯ p`. We then say that `p` and `q` are _related_. Relatedness
is reflexive and symmetric, but not transitive: two different child positions of
one parent position need not be related to each other.

When `p ⪯ q`, write `q = p · r`, where `r` is the remaining sequence of
position-name components. A Move from `p` to `t` changes the applicable name
`p · r` to `t · r` for each transitive child position of the moved particle.

## Resolved Particle Operation occurrences

Let the occurrence indices be either a finite initial segment of the natural
numbers or all natural numbers. Write `Oᵢ` for the occurrence at index `i`, and
let `V` be the set of those occurrences. Each `Oᵢ` has exactly one of these
kinds:

```text
Create(p)
Destroy(p)
Move(s, t)
```

Define `positions(O)` as follows:

```text
positions(Create(p))  = {p}
positions(Destroy(p)) = {p}
positions(Move(s,t))  = {s,t}
```

Occurrences remain distinct even if their kinds and positions are equal.

Each occurrence also has an _Action Parent position_: the position of the
particle to which that occurrence's Action Execution is assigned. Every position
operated on by the occurrence is the Action Parent position or one of its
transitive child positions.

## The previous-operation order

The words “previous,” “most recent,” and “more recent” in the graph rules
require an order. Represent that order by listing the occurrences once, either
stopping after a finite number of occurrences or continuing without end:

```text
O₀, O₁, O₂, ...
```

Write `A < O` when `A` has the smaller index. A “previous operation” of `O` is
an `A` for which `A < O`. A most-recent member of a set is the member with the
greatest index. Every `Oᵢ` has exactly `i` previous occurrences. Therefore every
nonempty set of previous occurrences has a unique most-recent member even when
the complete history is infinite.

This is a _previous-operation order_, not a promise that a runtime executes all
operations sequentially in this order. The dependency graph exists to permit
other execution orders and concurrent execution.

The specification defines this logical order through its rules taken together:
Particle Operations in an Action Statements Block have their logical statement
order; Action Requirements are satisfied before an action triggers; Action
Guarantees become available after the callee's relevant final operation;
constructors have an assignment order; Cascading Destruction and destructors
have stated timing; Destruction Contracts record the order of destructions; and
the concurrency rules state when a caller operation may proceed after a callee
operation. The source-to-model proof must compose those existing clauses and
show that each use of “previous” by a graph rule agrees with the resulting
occurrence order. This is a lemma about the specification as written, not a new
requirement for the specification.

Nothing here says that an execution terminates. A nonterminating execution has
the infinite order `O₀, O₁, O₂, ...`. Quantifiers may likewise contribute an
unbounded number of occurrences. The proofs reason about an arbitrary occurrence
`Oᵢ` and its finite earlier prefix; they do not require a final occurrence or a
finite complete program execution.

## Occupancy states

An occupancy state `S` is the set of resolved positions that are occupied.

A position `p` is _available_ in `S` when every strict transitive parent
position needed to name `p` is occupied. A state is _prefix-closed_ when

```text
q in S and p ⪯ q imply p in S.
```

Prefix closure says that an occupied child position has every transitive parent
position required by its position reference.

The three Particle Operations have the following occupancy preconditions and
effects.

### Create

`Create(p)` requires `p` to be available and empty. Its next state is

```text
S union {p}.
```

Because `S` is prefix-closed, an empty `p` has no occupied transitive child
position.

### Destroy

`Destroy(p)` requires `p` to be occupied. Cascading Destruction empties `p` and
all its transitive child positions. Its next state is

```text
{q in S | not p ⪯ q}.
```

This is the state change specified by Cascading Destruction whether the Destroy
Particle Statement was written directly or introduced by Automatic Destruction.

### Move

`Move(s,t)` requires:

- `s` to be occupied;
- `t` to be available and empty;
- `s` and `t` to be different; and
- `s` not to be a prefix of `t`.

The last condition is the specification's prohibition against moving a particle
to a position it defines. Prefix closure and the other preconditions also rule
out `t` being a strict transitive parent position of `s`: such a `t` would have
to be occupied. Therefore the source and target positions of a valid Move are
unrelated.

For every occupied `s · r`, the next state has `t · r`. Occupied positions that
do not have `s` as a prefix are unchanged. In set notation, the next state is

```text
{t · r | s · r in S}
  union {q in S | not s ⪯ q and not t ⪯ q}.
```

This preserves the moved particle and its particles at transitive child
positions while changing their applicable resolved names. The second condition
on the unchanged set removes the old contents of the target subtree before the
renamed positions are added. A valid pre-Move state already has no occupied
position in that subtree, because the target is empty and the state is
prefix-closed.

Destination Position Constraints and particle qualities affect whether source
code is valid, but they do not change this occupancy transition.

## Resolved histories

A _resolved history_ consists of:

1. occurrences indexed by a finite initial segment of the natural numbers or by
   all natural numbers;
2. a state `Sᵢ` before every `Oᵢ` and a state `Sᵢ₊₁` after it; and
3. the Action Parent position of every occurrence.

`Sᵢ` is the state immediately before `Oᵢ`, and `Sᵢ₊₁` is the state after it. A
resolved history is _valid_ when:

- `S₀` is prefix-closed;
- every `Oᵢ` satisfies its occupancy preconditions in `Sᵢ`;
- `Sᵢ₊₁` is exactly the state produced by the operation's effect;
- every operated position is the Action Parent position or its transitive child
  position; and
- the history contains every Particle Operation occurrence contributed by its
  resolved Action Executions and destructions, exactly once.

This definition mentions no dependency edge and no graph rule.

The Lean representation pads a finite history with indices containing no
operation and requires the occupancy state to remain unchanged at those indices.
The padding does not add occurrences; it only lets finite and unbounded
histories use the same natural-number-indexed state function.

## Dependency graphs

A dependency graph has vertex set `V`. Write

```text
O -> D
```

when `O` directly depends on `D`. The edge direction means that `D` must execute
before `O`.

Write `O > D` when there is a nonempty directed path from `O` to `D`. The graph
is acyclic when no `O > O`. It is _transitively minimal_ when removing any
direct edge changes reachability. This is equivalent to saying that no direct
edge has an alternate path between the same two occurrences, even for an
infinite graph, because every graph path is finite.

Define the rule-independent relation `R` by

```text
O R A exactly when A < O and
some p in positions(O) and q in positions(A) satisfy p ~ q.
```

`R` depends only on the resolved history's previous-operation order and operated
positions. It does not depend on the Fill, Empty, Move, or Action Parent Rules.

The eventual completeness theorem must prove that every `R` pair is reachable.
The minimality theorem must independently prove that no direct edge calculated
by the rules is redundant. Only the later characterization theorem may combine
those results.

Minimality and completeness proceed by induction on the natural index of the
operation under consideration, so neither result needs the whole history to be
finite. The maximum-safe-concurrency argument likewise proves each finite prefix
by finitely many adjacent exchanges; this determines every observation in an
unbounded schedule without asserting a final state.

## Boundaries that later proofs must discharge

These shared definitions leave four separate obligations visible:

1. **Source correspondence.** Resolving valid Define source must produce a valid
   finite or infinite history whose occurrence order agrees with the
   specification's sequencing rules.
2. **Calculation correctness.** Applying the four graph rules to any valid
   history must produce exactly the calculation used by the graph proofs.
3. **Graph results.** Minimality and completeness must be proved independently
   for that calculated graph.
4. **Compiler conformance.** Observable compiler behavior must agree with the
   specification-level calculation.

The existing Lean structures begin after the first boundary: they assume
resolved occurrences, occupancy states, and candidate-selection properties. The
planned universal construction theorem must replace those manually supplied
candidate properties with results derived from a valid history and the four
rules.
