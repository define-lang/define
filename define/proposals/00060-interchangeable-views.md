# Define Language Proposal 60: Interchangeable Views

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** November 28, 2026
- **Date Finalized:**

## Problems

One of our aspirations with Define is to enforce, to whatever degree possible,
that there is only one way to write any given program.

When an operation is commutative (two or more of its input views can be swapped
without changing what the operation computes) there are multiple ways to write
the exact same execution statement.

For example, with boolean `and`, `or`, `xor`, `equal`, or numeric addition
`a + b`, swapping the arguments computes the exact same result.

If I invented some function like `three_and(a, b, c)` (that just does
`a and b and c`) there would be six ways to pass the same three views, and so on
as we increase the number of interchangeable views.

There are two additional problems to solve.

### 1: Groups of Interchangeable Views

We can imagine a function that calculates `a + b` and `c + d` and returns the
results separately:

```python
def double_add(a: int, b: int, c: int, d: int) -> (int, int):
    return (a + b, c + d)
```

In that case, `a` and `b` are interchangeable, and `c` and `d` are
interchangeable, but the two groups can't be swapped with each other in any way.

### 2: Not All Mathematically Commutative Views Should Be Swapped

It is tempting to have the compiler automatically infer which views of every
Value Operation are mathematically commutative.

Imagine you have a function like `may_edit(is_owner, is_admin)` that just
returns `is_owner and is_admin`. Even though that's _mathematically_
commutative, you don't want the bit for `is_owner` passed in as `is_admin`. What
if the logic of `may_edit` changes in the future? It would be very hard to
automatically refactor the callers to behave correctly, in that situation. They
need to be passing in the bits that make sense logically for that situation. The
same is true for something like `rectangle_area(width, height)`---the operation
is commutative, but the input parameters have an important semantic meaning that
should not be swapped in the caller.

It is also worth noting that proving `f(x, y) = f(y, x)` for arbitrary numeric
operations is not decidable in general, so we could not actually infer this
universally. (It is calculable for boolean operations, but we will certainly
have more than boolean operations.)

On the other hand, if programmers can simply declare views interchangeable
without the compiler checking the claim, the declaration can be wrong or drift
out of sync with the code.

## Solution

We introduce **View Interchangeability Statements** so an Abstract Operation
(Logical Operation or Value Operation) can explicitly declare which of its
read-only input views are interchangeable, verified by the compiler, and we
define an **Argument Order** to enforce a single canonical order for arguments
passed to any interchangeable view group.

### View Interchangeability Statements

In interface view definitions for Value Operations or Logical Operations, an
author may write a **View Interchangeability Statement**
(`it is interchangeable with view<...>.`) immediately after `it is read.`.

For example, in an Interface View definition in a Value Operation:

```define
define the operation<mv:example.com:logic:/example> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        # View Interchangeability Statement
        it is interchangeable with view<a>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # ...
    }
}
```

Just to be clear, View Interchangeability Statements cannot be specified for
local views, nor in any views of an Encoding Operation.

### Interchangeability Rules

1. **Read-only views only:** A View Interchangeability Statement may only appear
   on a read-only interface view (`it is read.`, without `it is written.`), and
   the view it names must also be a read-only interface view of the same
   operation. Output views and read/write views cannot be interchangeable.
2. **Must name the first view in the group:** The named `view<name>` must be
   defined earlier in the same operation and must not itself have a View
   Interchangeability Statement. Each view may have at most one View
   Interchangeability Statement.
   - This groups related read-only input views into disjoint **interchangeable
     view groups** of two or more views: each read-only view that is named by
     one or more View Interchangeability Statements starts a group, and every
     later view that names it joins that group.
   - For example, in `three_and(a, b, c)`, both `view<b>` and `view<c>` declare
     `it is interchangeable with view<a>.`, forming one group
     `{view<a>, view<b>, view<c>}`.
3. **Identical quality assignments:** In a Value Operation, every view in an
   interchangeable view group must have the exact same View Quality Assignment
   Block (the same value quality and any other quality assignments), so any
   particle valid for one view is valid for every view in its group.

To be clear, a read-only view that has no View Interchangeability Statement and
is not named by one is not in any interchangeable view group.

### Argument Order

Within a Value Operation's Operation Statements Block, whenever a statement
executes an Abstract Operation that has an interchangeable view group, the
arguments given to the views in that group must appear in **rank order**, sorted
as follows:

1. **Input interface views** of the enclosing Value Operation come first, in the
   order they are defined. This includes reading of read/write interface views.
2. **Literals** come next, compared first by their **fully-qualified typed
   global name** (for example, `literal<standard:/number/decimal>`), and then by
   their **literal content** (after escape decoding, compared by Unicode
   code-point order as strings rather than as parsed values).
3. **Views written by a previous statement** (a local view, or an output-only
   interface view read after it is written) come last.

Arguments given to an interchangeable view group in the wrong order are an
error. The compiler says which argument has to go to which view.

To be clear, only views in an interchangeable view group have to follow this
Argument Order. Views that are not in an interchangeable view group keep their
arguments as written.

At this time, this enforcement of argument order only applies inside Value
Operations; Argument Order inside actions is left for a future proposal.

#### Ranking Views Written by Previous Statements

What happens when more than one argument in the interchangeable view group was
written by a previous execution statement? For each such view, look at the
execution statement that wrote it, put its input arguments into a list, and
compare the lists element by element using each argument's rank (applying the
full ranking rules recursively, including the tie-breakers below). If one list
is shorter and matches the start of the other list, the shorter list comes
first.

We then sort the views according to the same order.

If two views came from execution statements with the exact same input arguments
(including two output views of the same statement), compare the
**fully-qualified typed global name** of each executed Abstract Operation by
Unicode code-point order, then which of that operation's **output views** wrote
the view (in the order those output views are defined), and finally, if two
separate statements executed the exact same operation with the exact same
arguments, the order in which those statements appear.

For example, if the enclosing Value Operation defines input interface views
`power` (1st), `door_closed` (2nd), and `alarm_active` (3rd):

- `not(power)` has input list `[power]`
- `and(power, door_closed)` has input list `[power, door_closed]`
- `three_and(power, door_closed, alarm_active)` has input list
  `[power, door_closed, alarm_active]`
- `and(power, alarm_active)` has input list `[power, alarm_active]`
- `not(and(power, door_closed))` has input list `[and(power, door_closed)]`

Comparing those lists element by element using each argument's rank (`power` <
`door_closed` < `alarm_active` < any view written by a previous statement) puts
them in that exact order.

#### Ranking Views Copied by View Setting Statements

A local view that is the target of a **View Setting Statement** has the same
primary rank as the view that is its source, so a view and its copies stay
grouped together (for example, `view<dx>` and `view<dx_copy>` both rank before
`view<dy>`).

When a source view and one or more copies of it appear in the same
interchangeable view group, the **source view comes first**, followed by its
copies in the order their View Setting Statements appear.

### Compiler Verification of Interchangeability

For Logical Operations, the compiler simply trusts the author's statements.
Commutativity is part of the inherent _definition_ of the logical operation.

For Value Operations, the compiler verifies each View Interchangeability
Statement (`view<b>` interchangeable with `view<a>`) via two checks. The
statement is valid if either of these two checks succeed. The compiler can
choose to run them in whatever sequence is most efficient.

A note on tractability and implementation: Because interchangeability is
transitive, verifying each View Interchangeability Statement once (`m - 1`
checks for a group of size `m`) guarantees that every permutation of the group
produces the exact same outputs.

#### 1. Direct Structural Check (All Value Operations)

Essentially, we check that if you swapped around all the views that claim to be
interchangeable, the value operation would still compute exactly the same thing.
This works purely structurally (we don't have to logically understand anything
about the operations being executed other than that the views are
interchangeable). We will explain what this means logically, although there are
much more efficient algorithms to actually _implement_ this than what we are
about to describe.

First write out an expression that represents how each output view gets its
value. For example, imagine you have `x, y = multiply_two(a, b, c, d)`. You
could write `x = a * b` and `y = c * d`.

Now, we can see there that `a` and `b` are interchangeable, as are `c` and `d`.
For each of those pairs, we try to swap them around and see if we still get the
same expression for each output view.

More specifically, imagine you have two views that declare they are
interchangeable, `view<a>` and `view<b>`. Everywhere they are read within the
Operation Statements Block, swap them. Then re-apply **Argument Order** to every
executed operation (putting the arguments inside each callee's interchangeable
view groups back into rank order).

Once you do this, each output view's expression should be identical to what it
was before you started.

For example, in `distance_squared(dx, dy) = (dx * dx) + (dy * dy)`:

- Original: `(dx * dx) + (dy * dy)`
- Swap `dx` and `dy`: `(dy * dy) + (dx * dx)`
- Re-apply Argument Order (`add` has interchangeable inputs):
  `(dx * dx) + (dy * dy)` — exact same expression, so `dx` and `dy` pass.

By contrast, in `(a + c) * (b + d)`:

- Original: `(a + c) * (b + d)`
- Swap `a` and `b`: `(b + c) * (a + d)`
- Re-apply Argument Order (`multiply` has interchangeable inputs):
  `(a + d) * (b + c)` — different expression, so `a` and `b` fail.

Two small details keep this exact:

- If an Abstract Operation executed inside the Operation Statements Block has
  multiple output views, the names of those output views are part of the overall
  Value Operation's output view expression. (You can't swap `operation.output1`
  for `operation.output2`.)
- For a read/write interface view, "reading" it refers to its initial input
  value, while checking it as an output view checks the expression written to
  it.

As an implementation note, the compiler does not need to literally rewrite the
statements or re-run Argument Order. It can compute the exact same result in
linear time per swap via bottom-up hash-consing: assign each distinct
`(operation, output view, sorted argument IDs)` a unique integer ID (sorting
argument IDs within each interchangeable view group of the executed operation),
and check that every output view gets the same ID before and after swapping
`view<a>` and `view<b>`.

#### 2. Exact Equation Check

For some Value Operations, you cannot verify commutativity accurately purely
through the structural check.

For example, imagine the Boolean `all_equal(a, b, c)` that just does
`(a == b) and (a == c)`. The structural check can see that `b` and `c` are
interchangeable, because swapping them produces the expression
`(a == c) and (a == b)`, which re-orders back to `(a == b) and (a == c)`.

However, the structural check cannot see that `a` is interchangeable with `b`,
because swapping `a` and `b` produces `(b == a) and (b == c)`, which re-orders
to `(a == b) and (b == c)`.

As a result, the compiler also publishes the actual logical equation that the
Value Operation represents, and checks commutativity logically against that
equation, when that computation is tractable.

For example, for a Boolean Value Operation, the compiler already knows the exact
output value (`true` or `false`) for every combination of input values, due to
the requirements of DLP 59. The check passes if swapping the values given to
`view<a>` and `view<b>` produces the exact same output value for every
combination of inputs.

Exactly how publication of the logical equation works will be specified in
future proposals.

## A Real Program

### A Logical Operation With Interchangeable Views

With this proposal, `logical_operation<standard:/boolean/and>` from DLP 56 must
declare its two input views interchangeable:

```define
define the logical_operation<standard:/boolean/and> {
    define the view<a> {
        it is read.
    }
    define the view<b> {
        it is read.
        it is interchangeable with view<a>.
    }
    define the view<result> {
        it is written.
    }
}
```

### A Multi-Input Boolean Value Operation

A three-input operation `three_and` declares all three input views in one
interchangeable view group `{view<a>, view<b>, view<c>}`:

```define
define the operation<mv:example.com:logic:/three_and> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        it is interchangeable with view<a>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<c> {
        it is read.
        it is interchangeable with view<a>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        define the view<ab> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        # `and` declares its own view<a> and view<b> interchangeable.
        # Input interface view<a> (defined 1st) ranks before view<b> (defined 2nd).
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<ab>.
        }
        # Argument Order puts view<c> before view<ab>, because view<c> is an
        # input interface view (Rule 1) and view<ab> was written by a previous
        # statement (Rule 3).
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<c>.
            with view<b> looking at view<ab>.
            with view<result> looking at view<result>.
        }
    }
}
```

### Calling It in Argument Order

A caller executing `three_and` must pass its three arguments in rank order:

```define
define the operation<mv:example.com:logic:/all_ready> {
    define the view<power> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<door_closed> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<alarm_active> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<ready> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        define the view<no_alarm> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<alarm_active>.
            with view<result> looking at view<no_alarm>.
        }
        # `three_and` declares {view<a>, view<b>, view<c>} as one
        # interchangeable view group, so these three arguments must be in rank order:
        execute the operation</three_and> {
            # 1st input interface view (Rule 1).
            with view<a> looking at view<power>.
            # 2nd input interface view (Rule 1).
            with view<b> looking at view<door_closed>.
            # View written by a previous statement (Rule 3).
            with view<c> looking at view<no_alarm>.
            with view<result> looking at view<ready>.
        }
    }
}
```

### Errors

#### False Interchangeability Claim

Declaring two views interchangeable when swapping them can change the output is
an error:

```define
define the operation<mv:example.com:logic:/bad_and_not> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        # Error: swapping view<a> and view<b> changes view<result>
        # (for example, when view<a> is true and view<b> is false).
        it is interchangeable with view<a>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        define the view<not_b> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<b>.
            with view<result> looking at view<not_b>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<not_b>.
            with view<result> looking at view<result>.
        }
    }
}
```

#### Non-Canonical Group Reference

A View Interchangeability Statement must name the first view of its group:

```define
define the operation<mv:example.com:logic:/bad_group_chain> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        it is interchangeable with view<a>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<c> {
        it is read.
        # Error: view<b> already declares interchangeability with view<a>.
        # Write "it is interchangeable with view<a>." instead.
        it is interchangeable with view<b>.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        define the view<ab> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<ab>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<c>.
            with view<b> looking at view<ab>.
            with view<result> looking at view<result>.
        }
    }
}
```

#### Wrong Argument Order

Passing arguments to an interchangeable view group out of rank order is an
error:

```define
define the operation<mv:example.com:logic:/bad_argument_order> {
    define the view<power> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<alarm_active> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<ready> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        define the view<no_alarm> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<alarm_active>.
            with view<result> looking at view<no_alarm>.
        }
        # Error: view<power> has to go to view<a>, because it's an interface
        # view, and view<no_alarm> isn't.
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<no_alarm>.
            with view<b> looking at view<power>.
            with view<result> looking at view<ready>.
        }
    }
}
```

## Why This is the Right Solution

### Why Explicit Opt-In Instead of Automatic Inference?

An earlier design inferred interchangeable views automatically on every Boolean
Value Operation: the compiler tested every pair of input views against the
boolean function the operation computes, partitioned interchangeable views into
groups, and forced every caller to pass arguments to each group in rank order.

I went with explicit opt-in declarations for three reasons:

1. **Named views carry domain meaning.** Basically, this is Problem 2 above.
   Consider this nonsensical (and likely dangerous, when you change how
   `may_edit` works) thing we would be forcing developers to write:

   ```define
   execute the operation<mv:example.com:access:/document/may_edit> {
       with view<is_owner> looking at view<author_is_admin>.
       with view<is_admin> looking at view<author_is_owner>.
       with view<allowed> looking at view<editable>.
   }
   ```

2. **Automatic commutativity inference doesn't generalize to numbers.** For
   boolean operations, checking every pair of input views is decidable. For
   arbitrary numeric Value Operations, proving `f(x, y) = f(y, x)` for all `x`
   and `y` requires symbolic algebra or SMT and is not decidable in general.
   With explicit declarations, we get a unified system for all forms of logical
   operations and value operations, regardless of what sort of logic we need or
   want to implement in the future.

3. **Simpler compilation.** It replaces `k * (k - 1) / 2` pairwise swap checks
   on every Boolean Value Operation with at most `m - 1` checks only when an
   author declares an interchangeable view group of size `m`.

### Why Opt-In Instead of Opt-Out Syntax?

I also considered inferring interchangeable views by default and adding opt-out
syntax (marking views as _not_ interchangeable).

The problem is once again Problem 2, but from a human lens. An author could
accidentally make the mistake from Problem 2, not know about it, and then have a
very bad time later. They might not even realize it if they are writing a
library that other people call and they aren't looking at the weird stuff they
are forcing on their callers.

We will opt in correctly for all the basic logical operations. That's actually
super easy to do and pretty hard to get wrong. So most code just gets all of
this for free, and gets to specify commutativity if it wants. That does mean
that we force a bit less "one way to write it" on user-specified programs than
we otherwise would, but I think in this case it's the right trade-off.

There _could_ be an analyzer that looks at user-specified code and _suggests_
that people add commutativity annotations, though.

### Why Must Every View Name the First View in Its Group?

Requiring `view<c>` to write `it is interchangeable with view<a>.` rather than
`it is interchangeable with view<b>.` guarantees that every partition of views
into interchangeable view groups has exactly one legal spelling, avoids forward
references, and means verifying a group of size `m` only takes `m - 1` swaps (by
transitivity, if swapping `a` with `b` and `a` with `c` both preserve the
output, swapping `b` with `c` automatically preserves the output too).

### Why This Rank Order?

The rank order is designed to work well for both humans reading code and the
compiler analyzing it. Let's talk about a few specific choices.

#### Arguments before operation names

I tried pretty hard to minimize depending on the alphabet wherever possible,
because it gives names semantic meaning that I don't want them to have. (It
forces people to reformat their code just because you changed a name, which
isn't great.) So we don't use operation names as the first sort key.

In our rank order, the alphabet is only our tie-breaker when two views come from
exactly the same arguments through different operations, which I expect to be
relatively uncommon.

Arguments-first also helps when the compiler checks DLP 59 using a decision
diagram (ROBDD). A decision diagram tests boolean inputs in a fixed order, which
the compiler chooses by walking statements depth-first in argument order.
Decision diagrams stay small when inputs that interact with each other appear
next to each other in that order, and can grow exponentially when those inputs
get interleaved with unrelated ones. If operation names came first, an `and`
combining late inputs `y` and `z` would sort ahead of an `or` combining early
inputs `a` and `b`, scattering related inputs apart. Comparing arguments first
keeps subexpressions that use the same early inputs grouped together, so
depth-first traversal visits related inputs next to each other.

#### Interface views before statement results

Putting interface views first puts simple gating inputs (like `enabled` in
`enabled and complex_expr`) ahead of computed subexpressions. When the compiler
builds its ROBDD decision diagram in depth-first argument order, `enabled` lands
at the top of the diagram above all of `complex_expr`:

- With `enabled` at the top, computing `enabled and complex_expr` allocates a
  **single** new node in the ROBDD (`false` → `false`, `true` → the existing
  root of `complex_expr`), reusing all `N` nodes of `complex_expr` in `O(1)`
  time.
- With `enabled` at the bottom, every `true` leaf of `complex_expr` has to be
  replaced by a test on `enabled`, which forces the compiler to rebuild every
  ancestor node along those paths. That's up to `N` new nodes and `O(N)` work
  for each gating input (doubling the diagram for one gate, and multiplying it
  by `k + 1` for `k` gates).

#### Execution statement argument structure

Why sort using that complex algorithm on the rank orders of previous statements'
arguments instead of just the order in which statements are specified?

Well, it turns out it creates an unresolvable conflict with an algorithm from a
later proposal (that I am writing simultaneously with this one) about how
_statements_ must be ordered. (The statement ordering depends on something about
arguments, so arguments can't depend on statement ordering.)

#### Why not expression height first?

We could have ranked views written by previous statements by **expression
height**. That would basically ask the question "what was the longest unbroken
chain of dependent statements that it took to produce this view's value?" Input
interface views and literals have height 0, a statement that reads them has
height 1, statements that read the output of that statement have height 2, and
so on.

To really understand why we made this decision, you would have to see a later
proposal about statement order that I am also working on. In brief, the argument
order that we specify changes the statement order. If we do expression-height
argument order, it ends up forcing a statement order that you can't reason about
unless you do a whole expression-height calculation in your mind. With the order
we have specified, you can _look_ visually at the code and know what order your
arguments and statements are supposed to be in.

On the other hand, expression height actually _would_ be better for the
compiler. Using expression height lets the compiler assign every statement an
integer rank in a single bottom-up pass (`O(S log S)` worst case, rather than
`O(S^2)` in a pathological diamond graph of `S` statements). So there's some
slight chance we will change to it in the future. In practice, though, checking
argument order stops at the first differing argument (`O(S)` on real code), so
it probably doesn't matter.

## Forward Compatibility

Every piece of this proposal can be changed deterministically in the future.

1. **Changing or replacing the `it is interchangeable with view<...>.` syntax:**
   The View Interchangeability Statement is unambiguous inside an interface
   view's definition block and uniquely encodes the partition of read-only views
   into interchangeable view groups. Because that partition is represented with
   zero ambiguity, we can refactor into any other syntax. For example, we could
   convert every value operation into having a statement like:

   ```define
   define the interchangeable views {
       the view<a>.
       the view<b>.
       the view<c>.
   }
   ```

   Even removing the syntax entirely (for example, if we ever switched to
   automatic inference or dropped interchangeability declarations) is a purely
   syntactic deletion as simple as just deleting the statements.
2. **Changing the rank order (for example, switching to expression height first
   or a different tie-breaker):** The compiler verifies that our re-sorting
   cannot change behavior. So we could change to any other deterministic sorting
   algorithm that also does not change behavior, and a refactoring tool could
   automatically re-sort the code.
3. **Weakening or extending enforcement:** Removing Argument Order only accepts
   more programs; extending Argument Order to Actions later can be refactored
   deterministically by sorting interchangeable arguments at Action call sites
   (which will preserve behavior, because interchangeability is already verified
   on the called operation); adding stronger verification for non-Boolean Value
   Operations only accepts more programs than this proposal does now (the
   structural check only over-rejects, it does not over-accept).

## Refactoring Existing Systems

Existing code written with `logical_operation<standard:/boolean/and>` or any
operation that adds a View Interchangeability Statement can be refactored
automatically with a refactoring tool that sorts the arguments within each
interchangeable view group into rank order. We have a
[proof that such a refactoring terminates](https://github.com/define-lang/research/tree/main/boolean_equality_checking/proof).
