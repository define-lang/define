# Compile-Time Position Occupancy Tracking: Revised Theoretical Design

## Context

Define needs a compile-time system to track which positions contain dimension
points at every point during program execution, so the compiler can detect:

- Creating a dimension point in an already-occupied position
- Moving a dimension point to an occupied position
- Moving/destroying from an empty position
- Referencing through an empty intermediate position in a chain
- Two concurrent actions modifying the same position (paradoxes)

This document proposes a theoretical framework. No implementation yet.

---

## 1. Three Dependency Structures

The compiler maintains three distinct graphs. Understanding their roles is
essential to the design.

**Global Name Reference Graph** (acyclic, already implemented):

- Edges: which global names reference which other global names
- Determines file loading order and compilation order
- Bounds what each definition can "see" and name

**Quality Requirement Tree** (acyclic):

- Edges: `this dimension point must have the position<...>` / `action<...>`
- Makes names accessible in the current scope
- Determines quality assignment order and dimension point structure
- Multiple actions on the same dimension point share positions through this tree

**Trigger relationships** (can cycle, derived from the other two):

- NOT an independent graph -- structurally derived from the reference graph +
  quality requirement tree
- Trigger edges either follow reference edges (caller triggers callee through
  position chain), go between quality requirement siblings (actions on the same
  dimension point sharing a position), or go in reverse along reference edges
  (callee satisfies caller's `wait until`)
- Cycles can only form between sibling actions on the same dimension point via
  shared quality requirement positions. Cross-dimension-point cycles would
  require reference graph cycles, which are forbidden.

---

## 2. The Position Ownership Tree

Positions form a dynamic tree. Each level alternates between positions and
dimension points:

```
root position
└── dimension point (occupies the position)
    ├── quality position A (assigned to the dimension point)
    │   └── dimension point
    │       └── ...
    └── quality position B
        └── dimension point
            └── ...
```

**The tree is dynamic.** A branch only exists when every intermediate position
is occupied. For the chained reference `position<a>::position</b>::position</c>`
to be valid:

1. `position<a>` must be Occupied
2. The dim point at `position<a>` must have `position</b>` assigned
3. `position</b>` must be Occupied
4. The dim point at `position</b>` must have `position</c>` assigned

If any intermediate is empty, the entire subtree below it is unreachable.
Creating a dimension point _activates_ a branch. Destroying one _deactivates_
everything below (cascading destruction).

**Concurrency is always rooted in this tree.** If two actions execute
concurrently, there is a position in the ownership tree that transitively owns
both of them. This common ancestor bounds the scope of potential conflicts.

---

## 3. The Position State Domain

For each position known to the compiler at a given program point:

| State         | Meaning                                      |
| ------------- | -------------------------------------------- |
| **Undefined** | Position not yet defined in scope            |
| **Empty**     | Position exists, contains no dimension point |
| **Occupied**  | Position exists, contains a dimension point  |

Because Define lacks conditionals and loops within action bodies, there is no
need for an "Unknown" state within a single execution segment. Across
`wait until` boundaries, the new trigger conditions re-establish definite
states.

---

## 4. Intra-Action Analysis (Sequential)

Within a single action body, the compiler runs forward dataflow analysis with
transfer functions for each statement.

### Chain Validity

Every chained position reference generates occupancy checks on ALL intermediate
positions, not just the endpoint. Referencing
`position<a>::position</b>::position</c>` is an implicit read of `position<a>`
and `position</b>` (both must be Occupied) plus whatever operation applies to
`position</c>`.

### Transfer Functions

**`define the position<x>`**: `state[x] = Empty`

**`create a dimension point in position<R>`**:

- Precondition: `state[R] == Empty`, all intermediates Occupied
- Postcondition: `state[R] = Occupied`
- Compound: constraints assigned atomically (DLP 20), init blocks run
  synchronously (DLP 32), potentially filling child positions

**`move the dimension point in position<R1> to position<R2>`**:

- Precondition: `state[R1] == Occupied`, `state[R2] == Empty`, all intermediates
  Occupied, R2 not a descendant of R1 (DLP 25)
- Postcondition: `state[R1] = Empty`, `state[R2] = Occupied`
- Child positions transfer with the dimension point

**`destroy the dimension point in position<R>`**:

- Precondition: `state[R] == Occupied`, all intermediates Occupied
- Postcondition: `state[R] = Empty`
- Cascade: destructors run synchronously in reverse-assignment order (DLP 34),
  child positions emptied recursively (DLP 31)

**`assign the position<P> to dimension point in position<R>`**:

- Precondition: `state[R] == Occupied`
- Postcondition: `state[R::P] = Empty` (or post-init state if P has init block)

**`wait until { conditions }`**:

- Splits the action body into two segments
- After the boundary, states re-derived from `wait until` conditions + effect
  summaries of what could have changed concurrently

**End of action block**: locally-defined positions with dimension points are
automatically destroyed in reverse definition order (DLP 31). The tracker
simulates these implicit destructions.

### Synchronous vs Asynchronous Trigger Classification

Each trigger point in an action body is classified locally:

- **Synchronous**: `create` (triggering a sub-action) followed immediately by
  `wait until` that depends on the triggered action's effects. This is the
  common case (see fibonacci example). No concurrency analysis needed.
- **Asynchronous**: `create` without a corresponding `wait until`. The triggered
  action runs concurrently with the remainder of the current action body.

---

## 5. Effect Summaries

Each action produces an effect summary computed bottom-up along the reference
graph (piggybacking on existing compilation order -- no new bottleneck).

```
ActionEffectSummary:
  trigger_conditions:   what triggers this action
  chain_reads:          ALL positions traversed (intermediates + endpoints)
  writes:               positions modified (creates, fills, vacates)
  segments:             split by wait-until boundaries
  cascade_plans:        precomputed destruction cascades
  sync_triggers:        trigger points classified as synchronous
  async_triggers:       trigger points classified as asynchronous
```

**Chain reads are critical.** A reference to
`position<a>::position</b>::position</c>` adds `position<a>` and `position</b>`
to chain_reads (intermediates) plus `position</c>` to either reads or writes
depending on the operation. Any concurrent write to an intermediate invalidates
the entire reference chain.

**Position references are relative.** An action's effects are expressed relative
to `this dimension point`. At each use site, the compiler instantiates against
the concrete position.

---

## 6. Concurrency Analysis via the Ownership Tree

Instead of building a separate trigger graph with global analysis, we use the
ownership tree directly. Concurrency is always rooted at a specific node in the
tree.

### Where Concurrency Arises

Concurrency occurs when an action body triggers multiple sub-actions
asynchronously, or triggers a sub-action and continues doing work without
waiting. The node in the ownership tree where this happens is the **concurrency
root**.

### Conflict Scope

Two concurrent actions can only conflict on positions they can both name:

- **Local positions**: each concurrent subtree's local positions are private. No
  conflict possible.
- **Shared quality requirement positions**: positions accessible to multiple
  concurrent siblings because they're on the same dimension point. This is where
  conflicts happen.
- **Intermediate positions**: one concurrent action traverses through a position
  that another concurrent action writes to (chain invalidation).

### Conflict Rules

For each concurrency root, check the concurrent children's effect summaries:

1. **Write-write on shared position**: two concurrent siblings both write to the
   same quality requirement position → paradox
2. **Read-write on shared position**: one sibling reads (including chain
   traversal) a position that another writes, with no causal ordering → paradox
3. **Chain invalidation**: one sibling writes to (destroys/vacates) a position
   that is an intermediate in another sibling's reference chain → paradox
4. **Causally ordered access**: if the writer's effect triggers the reader, the
   reader sees the post-write state → NOT a paradox

### The Common Case Is Free

Most triggering is synchronous (create → wait until). The fibonacci example
demonstrates this pattern: `generate` creates a dimension point in `next`'s
`position<run>`, then immediately `wait until` it's destroyed. This is a
sequential call. No concurrency analysis needed.

Only the asynchronous case (create without waiting, or multiple creates before a
wait) requires conflict checking, and even then the scope is bounded by the
ownership tree's common ancestor.

---

## 7. Cycle Detection and Termination

### Where Cycles Can Form

Trigger cycles can only form between sibling actions on the same dimension
point, connected through shared quality requirement positions.
Cross-dimension-point cycles are prevented by reference graph acyclicity.

This means cycle detection is **local per dimension point**, not global. For
each dimension point with multiple actions, check whether the sibling actions
can trigger each other in a cycle through shared positions.

### Termination Analysis

Since the state space is finite (2^|P| position states), termination is always
decidable. A layered checker:

**Layer 1 -- DAG check**: If no cycles among this dimension point's sibling
actions → done.

**Layer 2 -- T-invariant analysis**: For each cycle, compute the Petri net
incidence matrix. If no non-negative solution to Ax=0 exists → cycle provably
terminates.

**Layer 3 -- Single-pass state comparison**: For cycles with T-invariants,
simulate one traversal. If the system returns to the same state → infinite.

**Layer 4 -- Conservative rejection**: Cannot prove termination → reject.

### Intentionally Infinite Loops

Programmers may mark a cycle with a sentinel indicating it intentionally runs
forever. The compiler then skips termination checking and instead verifies the
**loop invariant**: each pass is internally consistent and paradox-free.

---

## 8. Destruction Cascades

The compiler precomputes a **Cascade Plan** for each position:

```
CascadePlan:
  steps: [
    RunDestructor(action_ref, effects),      -- synchronous
    DestroyChild(position_ref, nested_plan), -- recursive
    UnassignQuality(quality_ref),
  ]
```

During cascading destruction, position constraints are suspended (DLP 31) and
actions triggered by quality removal do NOT fire. Only explicit destructors need
to be traced.

**Chain invalidation during cascades**: destroying a dimension point deactivates
its entire subtree. Any concurrent action traversing through that subtree's
positions is in conflict.

---

## 9. Interaction with Quality Constraints

Position constraints and occupancy tracking reinforce each other:

- Occupied `position<x>` with constraint `it has the position</balance>` →
  compiler knows `position<x>::position</balance>` exists
- Atomic creation (DLP 20) traces quality assignments in constraint-list order,
  updating the occupancy map for each init block
- Constraint propagation: occupancy of a parent implies existence of all
  constrained child positions

---

## 10. Analysis Architecture

**Phase 1 (per-file, fully parallel)**: Intra-action forward dataflow. Track
occupancy state statement-by-statement. Classify triggers as sync/async. Produce
effect summaries including full chain reads. Piggybacks on existing per-file
validation.

**Phase 2 (bottom-up, piggybacks on compilation order)**: Compose effect
summaries from Phase 1 + dependency summaries. Handle init blocks, cascade
plans. No new bottleneck -- this is additional O(file size) work per file along
the existing compilation critical path.

**Phase 3 (per dimension point, fully parallel)**: For each dimension point with
multiple actions: check sibling actions for cycles (layered termination checker)
and write conflicts on shared quality requirement positions.

No global trigger graph. No global Tarjan's. No global concurrency sets. No
global causal reachability. The ownership tree structure makes all of those
unnecessary.

---

## 11. Computational Complexity

| Phase                        | Work                                    | Parallelizable?      |
| ---------------------------- | --------------------------------------- | -------------------- |
| Phase 1 (intra-action)       | O(S) total, O(file) per file            | Fully parallel       |
| Phase 2 (effect summaries)   | O(S) additional on existing compilation | Existing parallelism |
| Phase 3 (conflict detection) | O(per dimension point)                  | Fully parallel       |

The only new single-threaded work is bounded by the size of individual dimension
points (their sibling action count and shared position count), not by the total
program size.

Worst case for a single dimension point: O(A² × P) where A = number of sibling
actions and P = number of shared positions. For typical dimension points with a
handful of actions, this is constant.

---

## 12. Resolved Design Decisions

- **No separate trigger graph**: trigger relationships are derived from the
  reference graph + quality requirement tree. The ownership tree is the primary
  analysis structure.
- **Sync/async classification is local**: determined by whether `wait until`
  follows a trigger point. Most triggers are synchronous.
- **Cycles are local**: can only form between sibling actions on the same
  dimension point. Detected per dimension point, not globally.
- **Chain reads are tracked**: every intermediate position in a chain is an
  implicit read. Chain invalidation is a conflict type.
- **Read-write conflicts**: only paradoxes when truly concurrent with no causal
  ordering.
- **Forms/collections**: designed for 1-bounded case only. Extend later.

---

## 13. Remaining Open Questions

1. **Wait-until state reconstruction**: after a `wait until` boundary, use
   effect summaries of concurrent actions to determine precisely what changed,
   or conservatively re-derive from the wait conditions?

2. **Cascade-triggered async actions**: during cascading destruction,
   destructors run synchronously but actions triggered BY destructors run
   asynchronously (DLP 34). How does this interact with the ownership tree
   approach?

3. **Access controls and fan-out**: future access controls will restrict which
   actions can watch which positions. This helps programmers avoid pathological
   fan-out but doesn't change worst-case complexity.
