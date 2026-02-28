# Compile-Time Position Occupancy Tracking: Theoretical Design

## Context

Define needs a compile-time system to track which positions contain dimension
points at every point during program execution, so the compiler can detect
conflicts such as:

- Creating a dimension point in an already-occupied position
- Moving a dimension point to an occupied position
- Moving/destroying from an empty position
- Two concurrent actions modifying the same position (paradoxes)

This document proposes a theoretical framework. No implementation yet.

---

## 1. Why Define Makes This Tractable

Define's design constraints create what we'll call the **Closed-Form Property**
-- the compiler can almost always determine exact position occupancy:

- **No aliasing**: A dimension point exists in exactly one position. No pointers
  or references.
- **Sequential intra-action execution**: Within an action body, statements run
  in sequence, instantaneously.
- **Trigger conditions are entry invariants**: When
  `the position<x> has a dimension point` triggers an action, `position<x>` is
  guaranteed Occupied at entry.
- **Position constraints are type information**: If `position<x>` requires
  `it has the position</balance>`, then any occupied `position<x>` guarantees
  `position<x>::position</balance>` exists.
- **Deterministic destruction ordering**: Cascading follows reverse-assignment
  order -- statically knowable.
- **No conditionals or loops**: Within an action body, there are no branches or
  iterations to create uncertainty.
- **Acyclic dependency graph**: No circular dependencies between global
  definitions.

The only source of uncertainty is across `wait until` boundaries, where
concurrent actions may have modified state. But even here, the `wait until`
conditions establish new invariants, and effect summaries bound what could have
changed.

---

## 2. The Position State Domain

For each position known to the compiler at a given program point:

| State         | Meaning                                      |
| ------------- | -------------------------------------------- |
| **Undefined** | Position not yet defined in scope            |
| **Empty**     | Position exists, contains no dimension point |
| **Occupied**  | Position exists, contains a dimension point  |

Because Define lacks conditionals and loops within action bodies, there is no
need for an "Unknown" or "Maybe" state within a single execution segment. Across
`wait until` boundaries, the new trigger conditions re-establish definite
states.

---

## 3. Intra-Action Analysis (Sequential)

Within a single action body, the compiler runs forward dataflow analysis with
transfer functions for each statement:

**`define the position<x>`**: `state[x] = Empty`

**`create a dimension point in position<R>`**:

- Precondition: `state[R] == Empty` (error if Occupied)
- All intermediate chain positions must be Occupied
- Postcondition: `state[R] = Occupied`
- Compound effect: Required qualities from position constraints are assigned
  atomically (DLP 20), each quality's init block runs synchronously (DLP 32),
  potentially filling child positions

**`move the dimension point in position<R1> to position<R2>`**:

- Precondition: `state[R1] == Occupied`, `state[R2] == Empty`
- R2 must not be a descendant of R1 (DLP 25)
- Postcondition: `state[R1] = Empty`, `state[R2] = Occupied`
- Child positions transfer: `R1::child` references become `R2::child`

**`destroy the dimension point in position<R>`**:

- Precondition: `state[R] == Occupied`
- Postcondition: `state[R] = Empty`
- Cascade: Destructors run synchronously in reverse-assignment order (DLP 34),
  then child positions are emptied recursively (DLP 31)

**`assign the position<P> to dimension point in position<R>`**:

- Precondition: `state[R] == Occupied`
- Postcondition: `state[R::P] = Empty` (or post-init-block state if P has an
  init block)

**`wait until { conditions }`**:

- Splits the action body into two segments
- After the boundary, states are re-derived from the `wait until` conditions +
  effect summaries of what could have changed concurrently

**End of action block**: Locally-defined positions with dimension points are
automatically destroyed in reverse definition order (DLP 31). The tracker
simulates these implicit destructions.

---

## 4. Effect Summaries (Modular Compilation)

Each action/quality produces an **Effect Summary** that describes its observable
behavior without revealing implementation:

```
ActionEffectSummary:
  trigger_conditions:   what triggers this action
  reads:                positions observed
  creates:              positions where dim points are created
  vacates:              positions emptied (move-from, destroy)
  fills:                positions filled (move-to, create)

  segments:             split by wait-until boundaries
  cascade_plans:        precomputed destruction cascades
```

For position qualities with init blocks:

```
PositionEffectSummary:
  constraints:          required qualities
  init_effects:         what the "after it is assigned" block does
```

**Computation**: Bottom-up along the acyclic dependency graph. Qualities/actions
with no dependencies first, then those that depend on them. Each summary uses
only its direct dependencies' summaries. Terminates because the graph is
acyclic.

**Position references are relative**: An action that declares
`this dimension point must have the position</balance>` has effects relative to
`this::position</balance>`. At each use site, the compiler instantiates relative
references against the concrete position.

---

## 5. Trigger Graph, Cycle Detection, and Concurrency Sets

**Trigger Graph**: Directed graph where:

- Nodes = effect segments (portions of action bodies between `wait until`
  boundaries)
- Edge from S1 to S2 exists when S1 writes a position that appears in S2's
  trigger conditions, and the write would make S2's conditions become true

**Trigger cycles are possible** and must be detected. Unlike the
dependency/reference graph (which is acyclic by rule), the trigger graph CAN
have cycles: Action A writes `position<x>` triggering B, B writes `position<y>`
triggering A, etc. This would create infinite trigger chains at runtime.

**Cycle detection rule**: Any cycle in the trigger graph is a compile error. The
compiler must:

1. Build the trigger graph from effect summaries
2. Run standard cycle detection (e.g., Tarjan's SCC algorithm)
3. Report any cycle as an error with the full chain of actions involved

This is a conservative rule -- some cyclic trigger graphs might terminate in
practice (if the cycle conditions don't keep becoming true). But verifying
termination in cyclic trigger graphs is equivalent to the halting problem.
Forbidding cycles is clean, simple, and keeps analysis bounded.

**Concurrency Set**: Starting from a state-changing statement, the set of all
segments that could execute simultaneously. Includes:

- The remainder of the current segment (triggering action continues)
- Triggered actions' first segments
- Transitively triggered actions (following the acyclic trigger graph -- cycles
  are already errors)
- But NOT segments after a `wait until` (they start only when their condition is
  met)

**Causal ordering within concurrency sets**: Two segments in a concurrency set
may have causal ordering -- S1's effect triggers S2. This matters for conflict
detection (see Section 6).

---

## 6. Paradox Detection (Concurrent Conflicts)

A **paradox** = two concurrent segments with conflicting modifications to the
same position where no causal ordering guarantees consistency. The goal is to
prevent actual runtime race conditions, not to be overly conservative.

**Causal ordering principle**: If segment S1's write to `position<x>` is what
triggers segment S2, then S2's read of `position<x>` is NOT a conflict -- S2's
trigger condition guarantees it sees the post-write state. More generally, if
there is a causal path from S1 to S2 in the trigger graph, S2 sees all of S1's
effects.

**Conflict rules for each concurrency set**:

- **Write-write (no causal order)**: Two segments that both write the same
  position, with no causal path between them = paradox
- **Read-write (no causal order)**: A segment reads a position that another
  writes, with no causal path from the writer to the reader = paradox (race
  condition: reader may see pre- or post-write state)
- **Read-write (causally ordered)**: If the writer causally precedes the reader
  (writer's effect triggered the reader), the reader sees the post-write state.
  NOT a paradox.
- **Write-write (causally ordered)**: Even with causal ordering, two writes to
  the same position conflict. The first write fills it, the second would try to
  fill an occupied position. Still a paradox (unless the first write is a vacate
  and the second is a fill, which is sequenced correctly).

**Formal check**: For each concurrency set C, for each pair of segments (S1, S2)
in C that both access position P:

1. If both are writes with no causal path between them → paradox
2. If one reads and one writes with no causal path from writer to reader →
   paradox
3. If causally ordered (writer → reader), check that the reader's assumptions
   about P's state match the writer's postcondition → OK if consistent

This is isomorphic to **serializability checking** in databases, but tractable
because:

1. The "schedule" (set of concurrent transactions) is statically determined from
   the trigger graph
2. The trigger graph is cycle-free (cycles are already compile errors from
   Section 5)
3. Effect summaries are precomputed
4. Causal ordering provides a partial order that resolves many apparent
   conflicts

---

## 7. Destruction Cascades

Destruction is the most complex operation. The compiler precomputes a **Cascade
Plan** for each position:

```
CascadePlan:
  steps: [
    RunDestructor(action_ref, effects),      -- synchronous
    DestroyChild(position_ref, nested_plan), -- recursive
    UnassignQuality(quality_ref),
  ]
```

Key: During cascading destruction, position constraints are suspended (DLP 31)
and actions triggered by quality removal do NOT fire. This simplifies the
cascade analysis -- only explicit destructors need to be traced.

---

## 8. Interaction with Quality Constraints

Position constraints and occupancy tracking reinforce each other:

- If `position<x>` is Occupied AND has constraint
  `it has the position</balance>`, then the compiler knows
  `position<x>::position</balance>` exists
- During atomic creation (DLP 20), the compiler traces quality assignments in
  constraint-list order, updating the occupancy map for each init block
- Constraint propagation: occupancy of a parent position implies existence of
  all constrained child positions

---

## 9. Analysis Architecture (Four Phases)

**Phase 1 (per-file, parallel)**: Intra-action forward dataflow. Track occupancy
state statement-by-statement within each action body. Produce effect segments.

**Phase 2 (bottom-up along dependency DAG)**: Compute effect summaries from
Phase 1 results + dependency summaries. Handle init blocks, cascade plans.

**Phase 3 (cross-file)**: Build trigger graph from effect summaries. Compute
concurrency sets.

**Phase 4 (cross-file)**: Check each concurrency set for conflicting writes.
Report paradoxes.

This maps naturally onto the existing compiler: Phase 1 in `FileValidator`,
Phases 2-4 in `ProgramValidator`.

---

## 10. Analogy to Petri Nets

The system has a direct Petri net analogy:

- **Places** = Positions
- **Tokens** = Dimension points (at most 1 per place = 1-bounded net)
- **Transitions** = Actions
- **Marking** = Current occupancy state
- **Firing rules** = Trigger conditions

The key property we verify is **1-boundedness** (no position ever holds >1
dimension point) and **conflict-freeness** (no two transitions fire
simultaneously with conflicting effects).

General Petri net analysis is EXPSPACE-complete, but Define's acyclicity
constraints reduce this to linear/polynomial.

---

## 11. Resolved Design Decisions

- **Trigger cycles**: CAN form (independently of the dependency graph). The
  compiler must detect and report them as errors. Cycle detection via Tarjan's
  SCC on the trigger graph.
- **Read-write conflicts**: Only paradoxes when truly concurrent (no causal
  ordering). If the write triggers the read, the reader sees post-write state --
  no race condition.
- **Forms/collections**: Designed for 1-bounded case only. Will extend later
  when forms are added.

## 12. Remaining Open Questions

1. **Wait-until state reconstruction**: After a `wait until` boundary, how
   precisely should the compiler determine what changed? Option A:
   conservatively mark all concurrently-writable positions as needing
   re-derivation from the wait conditions. Option B: use effect summaries to
   precisely track only what could have changed.

2. **Trigger cycle error messages**: When a trigger cycle is detected, how much
   context should the error provide? The full chain of actions and positions? A
   minimal cycle?

3. **Cascade-triggered actions and paradoxes**: During cascading destruction,
   destructors run synchronously but actions triggered BY destructors run
   asynchronously (DLP 34). Should the paradox detector treat
   destructor-triggered async actions differently from normal trigger chains?

4. **Transitive causal ordering**: If A triggers B and B triggers C, C sees A's
   effects (transitively). But if A and C both write to position<x>, is that a
   paradox? (C is causally after A, so C would try to write to a position A
   already wrote to. This depends on whether A filled and C is trying to fill
   the same position, vs A vacated and C fills.)
