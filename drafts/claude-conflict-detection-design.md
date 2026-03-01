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

## 4. Two Modes of Analysis

The compiler uses two distinct modes. The sequential mode handles the common
case cheaply. The concurrent mode is only activated when async triggers are
detected.

---

## 5. Mode 1: Sequential Occupancy Tracking (the default)

This is the primary mode. It handles all programs that use only synchronous
triggering (create → wait until), which is the vast majority.

### How It Works

Walk the action body statement-by-statement, maintaining an occupancy map. When
a synchronous trigger is encountered (create followed by `wait until`), treat it
as a **function call**: step into the triggered action's body, track occupancy
through it, step out when the wait condition is satisfied, continue from the
statement after `wait until`.

This is just forward dataflow analysis extended across synchronous call
boundaries. No effect summaries, no conflict sets, no concurrency machinery.

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

**End of action block**: locally-defined positions with dimension points are
automatically destroyed in reverse definition order (DLP 31). The tracker
simulates these implicit destructions.

### Synchronous Trigger (function call semantics)

When the compiler encounters `create` followed by `wait until` that depends on
the triggered action's effects:

1. Apply the `create` transfer function (position becomes Occupied, triggering
   the sub-action)
2. Step into the triggered action's body with the current occupancy map
3. Track occupancy through the called action's body (recursively, including any
   synchronous calls it makes)
4. When the called action's effects satisfy the `wait until` condition, step out
5. Apply the `wait until` postcondition and continue in the caller

This handles arbitrarily deep synchronous call chains. The fibonacci example:
`generate` calls `next` 500 times sequentially. Each call is tracked through and
back. No concurrency analysis at any point.

### What This Mode Catches

- Create in an already-occupied position
- Move/destroy from an empty position
- Invalid intermediate references (empty intermediate in a chain)
- Occupancy errors inside synchronous calls
- Cascade effects from destruction

### Cost

O(total statements traversed across all synchronous call chains). Same order as
existing compilation. Fully parallel per-file for the top-level analysis;
synchronous calls across files follow the existing compilation order.

---

## 6. Mode 2: Concurrent Conflict Checking (on-demand)

Activated ONLY when the compiler encounters an **asynchronous trigger** -- a
`create` that is NOT followed by a `wait until` depending on the triggered
action. This is the uncommon case.

### Trigger Classification

Each trigger point in an action body is classified locally:

- **Synchronous**: `create` followed immediately by `wait until` that depends on
  the triggered action's effects → Mode 1 handles it
- **Asynchronous**: `create` without a corresponding `wait until` → Mode 2
  activates

### Effect Summaries (computed only when needed)

When Mode 2 activates, the compiler computes effect summaries for the concurrent
subtrees. Effect summaries are NOT computed for the entire program -- only for
the actions involved in the specific concurrency.

```
ActionEffectSummary:
  chain_reads:    ALL positions traversed (intermediates + endpoints)
  writes:         positions modified (creates, fills, vacates)
  cascade_plans:  precomputed destruction cascades
```

**Chain reads are critical.** A reference to
`position<a>::position</b>::position</c>` adds `position<a>` and `position</b>`
to chain_reads (intermediates) plus `position</c>` to either reads or writes
depending on the operation. Any concurrent write to an intermediate invalidates
the entire reference chain.

**Position references are relative.** An action's effects are expressed relative
to `this dimension point`. At the concurrency root, the compiler instantiates
against concrete positions.

### Concurrency via the Ownership Tree

Concurrency is always rooted at a specific node in the ownership tree -- the
node whose action body contains the async trigger(s). This is the **concurrency
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

**For all programs (Mode 1):** Sequential occupancy tracking runs as part of
existing per-file validation. Walk action bodies, track states, follow
synchronous calls. Piggybacks on existing compilation order. No new
infrastructure needed beyond the occupancy map.

**Only when async triggers are detected (Mode 2):** Compute effect summaries for
the concurrent subtrees at the concurrency root. Check for conflicts on shared
positions. Cycle detection and termination analysis for sibling actions on the
same dimension point.

No global trigger graph. No global Tarjan's. No global concurrency sets. No
global causal reachability. The ownership tree structure makes all of those
unnecessary.

Mode 2 can be implemented incrementally -- ship Mode 1 first (catching
create-in-occupied, destroy-when-empty, chain validity) and add Mode 2 when
async patterns appear in real programs.

---

## 11. Computational Complexity

**Mode 1 (all programs):**

| Work                            | Cost                        | Parallelizable?           |
| ------------------------------- | --------------------------- | ------------------------- |
| Intra-action occupancy tracking | O(S) total                  | Fully parallel per-file   |
| Synchronous call traversal      | O(call depth × callee size) | Follows compilation order |

This is the same order as existing compilation. No new bottleneck.

**Mode 2 (only at async trigger points):**

| Work                            | Cost                           | Parallelizable?      |
| ------------------------------- | ------------------------------ | -------------------- |
| Effect summary computation      | O(concurrent subtree size)     | Per concurrency root |
| Conflict checking               | O(A² × P) per concurrency root | Per concurrency root |
| Cycle detection (per dim point) | O(sibling actions)             | Per dimension point  |

Where A = number of concurrent siblings, P = number of shared positions. For
typical programs, A is small (a few async tasks at startup) and P is small (a
few shared quality requirement positions). Mode 2 is rarely invoked and cheap
when it is.

---

## 12. Resolved Design Decisions

- **Two-mode architecture**: Mode 1 (sequential occupancy tracking) handles the
  common synchronous case with no concurrency machinery. Mode 2 (concurrent
  conflict checking) activates only at async trigger points. Mode 1 can ship
  first; Mode 2 added incrementally.
- **No separate trigger graph**: trigger relationships are derived from the
  reference graph + quality requirement tree. The ownership tree is the primary
  analysis structure.
- **Sync/async classification is local**: determined by whether `wait until`
  follows a trigger point. Most triggers are synchronous.
- **Synchronous triggers are function calls**: the compiler steps into the
  callee's body, tracks occupancy through it, and steps back out. No effect
  summaries or conflict sets needed.
- **Effect summaries computed on-demand**: only for concurrent subtrees at async
  trigger points, not for the entire program.
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
