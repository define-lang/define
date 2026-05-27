# Define Language Proposal X: Looping Constructs

- **Author:** Max Kanat-Alexander
- **Status:** Draft (WRITTEN BY CLAUDE AND REQUIRES EXTENSIVE WORK)
- **Date Proposed:** March 21, 2026
- **Date Finalized:**

## Problems

### Programs Need Repetition

Define currently has no way to execute a sequence of operations more than once.
Actions trigger when their conditions become true, but circular global name
references are forbidden
([DLP 9](../define/proposals/00009-global-name-circular-dependencies-are-forbidden.md)),
so actions cannot form cycles. This means every chain of action triggers is a
DAG and always terminates after a bounded number of steps.

Without repetition, Define cannot express many practical programs: batch
processing, numerical algorithms, iterating over collections, event loops, retry
logic, etc.

### Programs Need Unbounded Collections

Define currently has no way to store an unbounded number of particles. All
positions are declared in source code, each holding at most one particle. The
total amount of state in a program is bounded at compile time. This makes Define
equivalent to a finite state machine, which cannot express many real-world
programs.

### Turing-Completeness Requires Unbounded Memory and Repetition

To express general computation, a language needs three things:

1. Conditional branching (Define has this via action trigger conditions)
2. Unbounded repetition
3. Unbounded memory

Define has (1) but lacks (2) and (3).

### Static Analyzability Must Be Preserved

Define's core value proposition is near-perfect static analysis via modular
reasoning. Any repetition mechanism must preserve this. Specifically:

- The compiler must be able to analyze loop correctness without unrolling or
  whole-program analysis.
- Constraints must remain statically provable.
- Modular analysis (Action Requirements and Action Guarantees) must continue to
  work.

The one guarantee we must give up is termination: Turing-completeness makes the
halting problem unavoidable. However, all other static guarantees (no
uninitialized access, constraint satisfaction, memory safety, concurrency
conflict detection) can be preserved.

## Solution

We introduce three constructs:

1. **Bags** --- unbounded, unordered collections of particles with uniform
   constraints.
2. **`for each` over bags** --- iterating over a bag's contents.
3. **`repeat` with explicit termination** --- general-purpose looping via
   repeated action invocation.

Both looping constructs invoke actions rather than containing inline statement
blocks. This is the key design decision: **actions are the only unit of
computation in Define.** Loop bodies are action calls, and the action's contract
(its Requirements and Guarantees) serves as the loop invariant.

### Bags

A bag is an unordered collection of particles that all have exactly the same
qualities --- no more, no less. Unlike positions, which hold at most one
particle, a bag can hold any number (including zero).

Bags may only be defined as local names inside Action Statements Blocks (and
Position Initialization Blocks, which share the same syntax). Bags are not
qualities and cannot be assigned to particles.

#### Syntax

A bag is defined using a constraint block identical to the one used by
positions:

```
define the bag<name>.

define the bag<name> {
    it may only contain particles where {
        it has the position<mv:example.com:example:/foo>.
        it has the action<mv:example.com:example:/bar>.
    }
}
```

A bag with no constraint block contains unconstrained particles.

#### Creating Particles in Bags

The existing `create a particle` syntax extends to bags:

```
create a particle in bag<name>.
```

As with positions, if the bag has a constraint block, atomic creation
automatically assigns all required qualities to the new particle.

#### Moving Particles In and Out of Bags

Particles can be moved between bags and positions:

```
move the particle in position<x> to bag<name>.
move a particle in bag<name> to position<x>.
```

When moving out of a bag, the bag is unordered, so the specific particle moved
is unspecified. It is an error to move a particle out of an empty bag.

When moving into a bag, the particle must satisfy the bag's constraints.

#### Bag Emptiness

The emptiness of a bag is the only condition that can be tested on a bag. This
is sufficient for all conditional branching needed by looping constructs (see
"Why This is the Right Solution").

### `for each` --- Collection Iteration

The `for each` construct iterates over the particles in a bag, calling an action
for each one. The construct creates a position reference for each item that
refers to the particle's location _inside_ the bag. The particle is not moved
out of the bag unless the action explicitly does so.

#### Syntax

```
for each position<item> in bag<work> call action</process>.
```

The loop visits each particle in the bag exactly once (order is unspecified).
`position<item>` is created by the loop construct itself and refers to the
current particle's location inside the bag. The called action receives this
position via one of its interface positions.

If the action moves or destroys the particle at `position<item>`, it is removed
from the bag. If the action does not, the particle remains in the bag after that
iteration.

#### New Items Added During Iteration

If the action adds new particles to the bag being iterated during an iteration,
those new particles will be visited by subsequent iterations. This enables the
"self-feeding" pattern, which is the mechanism for unbounded computation. The
loop terminates when there are no unvisited particles remaining in the bag.

### `repeat` --- General-Purpose Looping

The `repeat` construct repeatedly invokes an action. It requires an explicit
termination condition somewhere in the action's body.

#### Syntax

```
repeat action</step>.
```

The action is called repeatedly. The action's body must contain a termination
statement. Without one, the program will not compile.

#### Termination Conditions

A `stop` statement inside an Action Statements Block causes the enclosing
`repeat` to terminate. There are two forms:

**Counted termination** (provably bounded):

```
stop after 500 times.
```

**Conditional termination** (potentially unbounded):

```
stop when the bag<fuel> is empty.
stop when the bag<results> is not empty.
```

The conditional form tests bag emptiness. The `stop` statement may appear
anywhere in the action body --- at the beginning (like a `while` loop), at the
end (like a `do-while`), or in the middle (loop-and-a-half). The compiler
analyzes the code path up to the `stop` point to determine what is true when the
loop exits.

A `stop after N times` termination allows the compiler to prove the loop
terminates. A `stop when` termination does not --- this is the unavoidable cost
of Turing-completeness.

### Static Analysis of Loops

Because loop bodies are action calls, the compiler's existing Action
Requirements and Action Guarantees system handles loop verification:

1. The compiler analyzes the action once to determine its Requirements and
   Guarantees.
2. For `repeat`: the compiler verifies that the action's Guarantees satisfy its
   own Requirements for the next iteration. This check is O(1) regardless of
   iteration count.
3. For `for each`: the compiler verifies that the bag's constraints satisfy the
   action's Requirements for each item, and that any items added to the bag
   during the action satisfy the bag's constraints.

**A loop body with no conditionals (other than the termination condition) is
trivially analyzable.** The action is a straight-line sequence of deterministic
operations. The compiler traces through once, determines the exact state of
every interface position, and verifies it satisfies the requirements for the
next iteration. This covers the vast majority of practical loops.

Loop bodies that contain bag emptiness conditionals require the compiler to
consider multiple code paths, but the analysis is still modular and per-action
--- no whole-program reasoning is needed.

### Detecting Misuse

The compiler can statically detect when a programmer uses the wrong construct:

- **`for each` over a bag where the loop body never reads the item**: The bag is
  being used as a loop counter. The compiler should suggest `repeat` with
  `stop after N times` instead.
- **Self-feeding bag with exactly one item**: The bag is being used as a
  `repeat while` loop. The compiler should suggest `repeat` with `stop when`
  instead.

This supports Define's principle that there should be one right way to do
things.

## A Real Program

### Fibonacci Sequence

This program computes 500 Fibonacci numbers using `repeat` with a counted
termination:

```
define the potential position<define-lang.org:fibonacci:/sequence/current> {
    it may only contain particles where {
        it has a value that is an integer.
        it has the constraint</non_negative>.
    }
    after it is assigned {
        create a particle in position</sequence/current>.
        set the value in position</sequence/current> to 1.
    }
}

define the potential position<define-lang.org:fibonacci:/sequence/previous> {
    it may only contain particles where {
        it has a value that is an integer.
        it has the constraint</non_negative>.
    }
    after it is assigned {
        create a particle in position</sequence/previous>.
        set the value in position</sequence/previous> to 0.
    }
}

define the potential action<define-lang.org:fibonacci:/sequence/next> {
    it also assigns the position</sequence/current>.
    it also assigns the position</sequence/previous>.

    define the position<run>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<temp> {
            it may only contain particles where {
                it has a value that is an integer.
                it has the constraint</non_negative>.
            }
        }
        create a particle in position<temp>.
        set the value in position<temp> to position</sequence/current>.

        set the value in position</sequence/current> to position</sequence/current> plus position</sequence/previous>.

        set the value in position</sequence/previous> to position<temp>.

        destroy the particle in position<temp>.
    }
}

define the potential action<define-lang.org:fibonacci:/generate> {
    define the position<run>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<sequence> {
            it may only contain particles where {
                it has the position</sequence/current>.
                it has the position</sequence/previous>.
                it has the action</sequence/next>.
            }
        }
        create a particle in position<sequence>.

        repeat action</sequence/next> {
            stop after 500 times.
        }
    }
}
```

The `repeat` calls `action</sequence/next>` repeatedly. The compiler verifies
the action's Guarantees (both `position</sequence/current>` and
`position</sequence/previous>` remain occupied with non-negative integers)
satisfy its Requirements (both positions must be occupied). This is checked once
and holds for all 500 iterations.

### Batch Processing

This program processes a collection of work items using `for each`:

```
define the potential position<mv:example.com:batch:/result>.

define the potential position<mv:example.com:batch:/item> {
    it may only contain particles where {
        it has the position</result>.
    }
}

define the potential action<mv:example.com:batch:/process_one> {
    define the position<item> {
        it may only contain particles where {
            it has the position<mv:example.com:batch:/item>.
        }
    }
    define the position<done>.

    it happens when {
        the position<item> has a particle.
    } and it does {
        create a particle in position<item>::position</result>.
        move the particle in position<item> to bag<completed>.
        create a particle in position<done>.
    }
}

define the potential action<mv:example.com:batch:/run> {
    define the position<go>.
    define the position<had_work>.

    it happens when {
        the position<go> has a particle.
    } and it does {
        define the bag<pending> {
            it may only contain particles where {
                it has the position<mv:example.com:batch:/item>.
            }
        }
        define the bag<completed> {
            it may only contain particles where {
                it has the position<mv:example.com:batch:/item>.
            }
        }

        create a particle in bag<pending>.
        create a particle in bag<pending>.
        create a particle in bag<pending>.

        for each position<current> in bag<pending> call action</process_one>.

        if the bag<completed> is not empty {
            create a particle in position<had_work>.
        }
    }
}
```

### Self-Feeding Work Queue (Unbounded Computation)

This demonstrates Turing-complete computation. Processing a work item may
generate sub-items, which are added to the bag being iterated. The loop
continues until no items remain:

```
define the potential action<mv:example.com:work:/handle> {
    define the position<item> {
        it may only contain particles where {
            it has the position<mv:example.com:work:/task>.
        }
    }

    it happens when {
        the position<item> has a particle.
    } and it does {
        # Process the item. Processing may add sub-tasks
        # to bag<queue>, which the enclosing for-each
        # will visit in subsequent iterations.
        create a particle in position<item>::position</done>.
    }
}

define the potential action<mv:example.com:work:/run> {
    define the position<go>.

    it happens when {
        the position<go> has a particle.
    } and it does {
        define the bag<queue> {
            it may only contain particles where {
                it has the position<mv:example.com:work:/task>.
            }
        }

        create a particle in bag<queue>.
        create a particle in bag<queue>.

        for each position<current> in bag<queue> call action</handle>.
    }
}
```

## Why This is the Right Solution

### Actions as the Only Unit of Computation

By making loop bodies action calls rather than inline statement blocks, we
maintain a single computational primitive. This keeps the language simpler and
makes the compiler's analysis uniform: every piece of computation has explicit
Requirements and Guarantees.

### Action Contracts Are Loop Invariants

The most significant benefit of this design is that the compiler's existing
Requirements/Guarantees system automatically provides loop invariant
verification. To verify a loop, the compiler checks once that an action's
Guarantees satisfy its own Requirements. This is O(1) analysis that holds for
any number of iterations --- no unrolling, no fixed-point computation, no
programmer-supplied annotations.

This is in contrast to most languages, where loop invariants are either manually
annotated (Dafny, SPARK Ada), inferred via expensive analysis, or not verified
at all.

### Bags Are the Minimal Unbounded Data Structure

A bag is the simplest possible collection: unordered, with uniform constraints.
This avoids the complexity of ordered sequences (which require indexing and
ordering semantics) while providing unbounded memory. The uniform constraint
requirement (all items have exactly the same qualities, no type narrowing) keeps
the compiler's reasoning tractable.

### Bag Emptiness Is Sufficient for Branching

Bag emptiness is a binary condition (empty or not empty), which is sufficient
for all conditional branching needed by loops. A bag with 0 or 1 items is
functionally equivalent to a boolean flag. This can be proven by showing that
bags + bag iteration + bag emptiness conditionals can simulate a Minsky machine
(2-counter machine), which is known to be Turing-complete:

- Two bags serve as counters (counter value = number of items in the bag).
- Increment: add a particle to the bag.
- Decrement: move a particle out of the bag.
- Branch on zero: test if the bag is empty.

### Two Constructs With Clean Separation

`for each` and `repeat` serve distinct purposes:

- `for each` is for processing a collection of meaningful data. Each item
  matters.
- `repeat` is for executing an action a certain number of times or until a
  condition is met. The action operates on external state.

The compiler can detect when a programmer uses the wrong one and suggest the
correct alternative.

### Alternatives Considered

**Inline loop bodies (not action calls):** This would create a second form of
computation alongside actions. It would require the compiler to analyze loop
bodies differently from action bodies, and loop invariants would need a separate
verification mechanism. Using action calls keeps the system uniform.

**`repeat while condition` as a separate construct:** A `while`-style loop with
the condition in the header. This was rejected in favor of `repeat` with an
internal `stop` statement, which handles while-loops, do-while-loops, and
loop-and-a-half patterns with a single construct. The `stop` can appear anywhere
in the action body, and the compiler analyzes accordingly.

**Position occupancy conditionals (in addition to bag emptiness):**
Theoretically unnecessary for Turing-completeness, since a bag with 0-1 items
can serve as a boolean. However, this may prove to be ergonomically desirable
for per-item branching in practice and could be introduced in a future proposal.

**Non-destructive bag iteration with implicit move-back:** Each item would be
temporarily moved out of the bag and automatically returned after the iteration.
This was rejected because it requires hidden "already visited" tracking (which
is conceptually alien to an unordered collection) and creates ambiguity about
whether the programmer intended the item to remain.

## A Description of Forward Compatibility

### Zero Ambiguity

The `for each` and `repeat` constructs use distinct keywords that cannot be
confused with each other or with existing Define syntax. The `stop` statement is
only valid inside an action called by `repeat`, making its meaning unambiguous.

Bag definitions use `define the bag<name>`, which follows the existing pattern
for `define the position<name>` and `define the potential position<name>`. The
`bag` type keyword is new and cannot conflict with existing type keywords.

### Infinite Possibility

The `stop` statement can be extended with new termination conditions in the
future without breaking existing programs. For example, `stop when` could be
extended to support conditions beyond bag emptiness.

The `for each` construct could be extended to iterate over future collection
types (ordered sequences, maps, etc.) without changing its fundamental syntax.

Bag operations (create, move) follow the same syntax patterns as position
operations, so future bag operations can follow the same patterns.

## Refactoring Existing Systems

This proposal introduces entirely new syntax. No existing Define programs use
looping constructs, so no refactoring is needed.

The `repeat 500 times` syntax used in the
[fibonacci example](../define/examples/fibonacci/fibonacci/generate.dfn) would
be refactored to:

```
# Before:
repeat 500 times {
    create a particle in position<sequence>::action</sequence/next>::position<run>.
    wait until {
        NOT position<sequence>::action</sequence/next>::position<run> has a particle.
    }
}

# After:
repeat action</sequence/next> {
    stop after 500 times.
}
```

This is a deterministic transformation: any
`repeat N times { trigger action; wait until done; }` becomes
`repeat action { stop after N times. }`.
