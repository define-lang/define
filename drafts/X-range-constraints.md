# Define Language Proposal X: Range Constraints

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 24, 2026
- **Date Finalized:**

> **Note:** This draft was written by Claude and still needs to be reviewed.

## Problems

Programs constantly need numbers that can only be within a certain range. A
percentage is 0 to 100. A TCP port is 0 to 65535. A day of the month is 1 to 31.
An index into a list of ten things is 0 to 9. Right now, there's no way to say
any of that in Define:

```define
define the potential action<mv:example.com:example:/battery/charge> {
    define the position<percent_charged> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it happens when {
        the position<percent_charged> has a particle.
    } and it does {
        # Nothing stops this, even though no battery can be 150% charged.
        set the value of position<percent_charged> to literal<standard:/number>"150".
    }
}
```

Most languages handle this with a runtime check that throws an error or panics
when the value is out of range, or (more commonly) by not handling it at all and
letting the bug happen. Define requires that we know whether a constraint holds
_while compiling_
([Constraints Must Be Statically Provable](../define/spec/requirements.md)), and
[DLP 18 (Modular Constraints)](../define/proposals/00018-modular-constraints.md)
requires that we check them modularly, without turning the whole program into
one giant equation.

[DLP 46 (Value Encodings)](../define/proposals/00046-value-encodings.md)
introduced the `constraint` name type with an early sketch of minimum and
maximum values, and [DLP 51 (Values)](../define/proposals/00051-values.md)
decided that constraints are always kept separate from values and assigned to
positions separately. But we've never actually defined how constraints work.

Ranges on naturals and integers are the simplest constraints that are actually
useful, so that's where we should start. Even something this simple has a lot of
problems, though.

### 1: Formal Verification is Hard

Proving things about values at compile time is an old problem, and a lot of very
smart people have worked on it.

The closest thing to what we want is
[refinement types](https://en.wikipedia.org/wiki/Refinement_type), which are
types with a logical condition attached, like "an integer where x >= 0." Pascal
and Ada have had simple versions of this (subrange types, like `0..100`) for
decades. Liquid Haskell and F\* have very powerful versions where the condition
can be nearly any logical statement. To check those conditions, they use an
[SMT solver](https://en.wikipedia.org/wiki/Satisfiability_modulo_theories) like
Z3: you turn your program into a big logical formula and ask the solver whether
it's always true. Dependent types (like in Lean and Rocq) go even further and
can express any proposition at all, and
[DLP 39 (Value Types)](../define/proposals/00039-value-types.md) already talks
about why we aren't going all the way there.

There's also
[abstract interpretation](https://en.wikipedia.org/wiki/Abstract_interpretation),
where an analysis runs the program on _approximations_ of values instead of real
values. The simplest version just tracks an interval (a lowest and highest
possible value) for every number. Tools like Astrée have used this to prove that
flight control software never has a runtime error. And
[SPARK](https://en.wikipedia.org/wiki/SPARK_(programming_language)), a subset of
Ada, proves that Ada's runtime range checks can never fail, so they can be
removed.

The problem is that as soon as constraints can talk about arbitrary arithmetic,
checking them is undecidable. (Deciding whether an equation with multiplication
over integers has a solution is impossible in general. That's
[Hilbert's Tenth Problem](https://en.wikipedia.org/wiki/Hilbert%27s_tenth_problem).)
SMT solvers deal with this by giving up: they say "unknown" or they time out.
When a solver times out, your program fails to compile, and small unrelated
changes to a program (or a new version of the solver) can make a proof that used
to take a second suddenly take forever. That's terrible for a programmer, who
can't predict what the compiler is going to do, and it's terrible for a compiler
that has to deterministically compile millions of lines of code. Solving a
formula for a whole function is expensive, and solving one for a whole program
is out of the question.

The powerful systems also usually make the programmer write loop invariants,
intermediate assertions, and hints to the solver. That's basically a whole
second program that you write to convince the compiler that your first program
is correct.

The simple systems (like intervals) are fast and predictable, but they lose
information. The classic example is `x - x`. The answer is always 0, but if `x`
is 0 to 10, interval arithmetic says `x - x` is -10 to 10, because it doesn't
know that both sides are the same value.

### 2: Wrapper Types vs. Composed Constraints

How do you attach a constraint to a value? There are basically two designs.

One is wrapper types, which is how refinement types usually work. You define a
new type that bundles a value with its constraints: "a `percentage` is a natural
from 0 to 100." That gives you reusable named types, which is nice and minimizes
duplication. But then you have to look into the definition of `percentage` to
find out what the actual value quality is. And every time you want a slightly
different refinement, you have to create (and name) a whole new global name,
instead of just composing a value quality and some constraints onto a position.

The other is to keep the value quality and the constraints separate, and assign
both onto a position, like every other quality in Define. That's consistent with
the rest of the language. But then constraints have to be checked differently
than every other quality.

### 3: Moving Between Differently-Constrained Positions

Today, moving a particle into a position requires the particle to already have
every quality that the destination position assigns
([DLP 19 (Guaranteeing Qualities in Positions)](../define/proposals/00019-guaranteeing-qualities-in-positions.md)).
That's a simple set comparison.

But imagine a particle in a position constrained to 0–10 moving into a position
constrained to 0–100. That should obviously be fine, since everything from 0 to
10 is also from 0 to 100. But the particle doesn't have the 0–100 constraint, it
has the 0–10 constraint, so a simple set comparison says no.

This is the subtyping problem that every refinement type system has, and wrapper
types don't actually solve it. If you have a `small` wrapper type that's 0 to 10
and a `percentage` wrapper type that's 0 to 100, either they're unrelated names
(which is strict and painful) or the compiler has to know that `small` fits
inside `percentage`, which means checking the constraints anyway.

### 4: What Do We Know About a Particle?

Logically, a particle that's been in a 0–10 position and is then moved into a
0–100 position is _still_ only ever going to be 0 to 10 (unless something writes
to it). And if it's then set to 50, we know it's exactly 50, which is narrower
than anything any position said.

Does the compiler need to track that? If it does, then every Action Guarantee
has to describe how a callee narrowed the constraints of every particle that was
passed to it. Otherwise a caller could write a value that's valid for the
position but invalid for the narrowed particle. If it doesn't, then what does it
even mean for a particle to "have" a constraint?

There's also the opposite case. Say a particle in a 0–100 position is set to 5.
Should you be able to move it into a 0–10 position? We _know_ the value is 5.
But knowing that means tracking values statement by statement through the
program (that's called "flow-sensitive" analysis), which is a lot more
complicated and expensive than just looking at what positions declared.

### 5: What Type Are the Bounds?

[Standard DLP 1](../define/standard/proposals/00001-core-numeric-value-type.md)
ran into this over and over: when I say "the minimum is 8," what kind of number
is 8? If I say "the minimum of this integer is -5," is -5 an integer? A natural
with a sign? Something else?

### 6: Which Values Support Which Constraints?

A range only makes sense for a value that has an order. "The maximum value" of a
boolean is meaningless. If constraints don't say what value quality they apply
to (and per DLP 51, they're separate from values), how does the compiler know
when a constraint is being applied to a value that it can't apply to? And where
does it report that error?

### 7: Unset Values

[DLP 53 (Unset Values)](../define/proposals/00053-unset-values.md) says that
newly created particles don't have a set value. Does a 1–10 constraint fail on
an unset value?

### 8: Conflicting Constraints

What if somebody gives a position one constraint that says "at least 50" and
another constraint that says "at most 10"? Nothing could ever be in that
position.

### 9: Values Coming Out of Operations

Most values in a program don't come from literals. They come from operations. If
the compiler doesn't know what an operation means, it can't know anything about
the range of the value it produces, and constraints would only be useful for
values that are set directly from literals.
[DLP 55 (Logical Operations)](../define/proposals/00055-logical-operations.md)
gives operations a logical meaning, but we still have to decide how constraints
and logical meanings work together.

### 10: Values From Outside the Program

Some operations (like reading from the network) produce values the compiler
can't know anything about. Those are exactly the values where constraints matter
the most, because the outside world can send you anything.

### 11: Ranges Through Many Operations

Value operations execute other value operations, which execute other value
operations, with logical operations in between. To know the range of an
operation's result where it's executed, the compiler has to know what every
operation it executes does to ranges, all the way down.

One way to do that is to work out each operation's effect on ranges once, as a
formula that says how the ranges of its results depend on the ranges of its
inputs, and use that formula everywhere the operation is executed. But for some
logical operations, those formulas get bigger with every level. Multiplying a
value by itself, and then multiplying that result by itself, and so on, gives a
formula with a higher degree at every level, and every multiplication of two
values whose ranges can include negative numbers needs a formula that picks the
smallest and largest of four products. Keeping only the formulas that stay small
(linear ones) would mean that common operations like a minimum couldn't give a
precise range where they're executed.

The other way is to go through an operation's statements again every time it's
executed, with the actual ranges. But then if one operation executes another one
twice, and that one executes a third one twice, and so on, checking one
execution means going through a number of statements that doubles with each
level.

How can the compiler know the ranges of results through many levels of
operations, precisely, without the cost getting out of hand?

### 12: Values Picked by a Condition

`standard:/choose` doesn't skip anything. Both `view<if_true>` and
`view<if_false>` are computed, and then one of them is picked. So a value can be
outside the range a program needs, as long as it's never picked when it is. For
example, to subtract 1 from a natural but stop at 0, a program can compute the
natural minus 1 as an integer, which is -1 when the natural is 0, and pick 0
instead when the natural is 0. The result is never negative. But if the compiler
computes the range of a `standard:/choose` as the range covering both of its
inputs, the result's range includes -1, and the program can't put it in a
natural.

How can the compiler know the range of a value that a condition picks?

### 13: Operands That Depend on the Same Value

The range of a logical operation's result depends on more than the ranges of its
inputs. It also depends on how the inputs are related. If `x` is 0 to 10, then
`x - x` is always 0, but two unrelated values that are each 0 to 10 can differ
by anything from -10 to 10. Interval arithmetic only looks at each input's
range, so it gives -10 to 10 for both.

This happens whenever a value is used more than once, directly or through other
values computed from it, and the two uses can be many operations apart. For
example, linear interpolation (`a + t * (b - a)`) with `a` and `b` from 0 to 10
and `t` from 0 to 1 is always between 0 and 10. But `b - a` is -10 to 10,
`t * (b - a)` is -10 to 10, and adding `a` gives -10 to 20. If one operation
computes `b - a` and passes it to another operation that multiplies it by `t`
and adds `a` back, the compiler has to see through both operations to know that
the two uses of `a` are the same value.

The compiler can't simply know every relationship exactly. Some relationships
are simple, like one value always being another value plus 1. Others aren't:
finding the exact range of a formula that only adds, subtracts, and multiplies
its inputs is NP-hard in general. And approximating relationships would make
whether a program compiles depend on how good the approximation is.

Which relationships between operands should the compiler know, and how can it
know them without the cost or unpredictability of a solver?

## Solution

### Value Qualities Declare Their Predicates

[DLP 55](../define/proposals/00055-logical-operations.md) gave value qualities a
block. That block may now also list the _predicates_ the value quality supports:
the kinds of statements that a constraint is allowed to make about values of
that value quality. `it may have the predicates` comes last in the block. The
block must contain at least one statement.

```define
define the potential value<standard:/number/natural> {
    it may have the predicates {
        it has the maximum value {
            highest allowed is infinite.
        }
        it has the minimum value {
            lowest allowed is literal<standard:/number>"0".
        }
    }
}
```

The predicates in this proposal are `it has the maximum value` and
`it has the minimum value`. Each one has a block with exactly one statement.
`it has the maximum value` contains `highest allowed is` and either a literal or
`infinite`. A constraint's maximum may not be higher than that.
`it has the minimum value` contains `lowest allowed is` and either a literal or
`infinite`. A constraint's minimum may not be lower than that.

`infinite` means there's no limit in that direction. So
`lowest allowed is infinite.` means there is no lowest allowed minimum, which is
what integers use.

The literals in these statements have the value quality that's being defined.

Predicates must be listed in alphabetical order, and each predicate may only be
listed once. `it may have the predicates` must contain at least one predicate.

The compiler defines what each predicate means.

```ebnf
value_definition_block =
    block_open,
    [ may_be_unknown_statement ],
    { logical_operation_support_statement },
    [ supported_predicates_block ],
    block_close ;
supported_predicates_block =
    "it may have the predicates",
    block_open,
    supported_predicate,
    { supported_predicate },
    block_close ;
supported_predicate = supported_maximum_predicate | supported_minimum_predicate ;
supported_maximum_predicate =
    "it has the maximum value",
    block_open,
    "highest allowed is ", predicate_limit, terminator,
    block_close ;
supported_minimum_predicate =
    "it has the minimum value",
    block_open,
    "lowest allowed is ", predicate_limit, terminator,
    block_close ;
predicate_limit = literal | "infinite" ;
```

### Defining Constraints

A constraint is defined by `define the constraint` followed by a fully-qualified
constraint name and a Constraint Definition Block. The block contains one or
more Constraint Statements, each of which uses one predicate followed by `of`
and a literal:

```define
define the constraint<mv:example.com:example:/percentage> {
    it has the maximum value of literal<standard:/number>"100".
    it has the minimum value of literal<standard:/number>"0".
}
```

Constraint Statements must be in alphabetical order by predicate, and each
predicate may only be used once in a constraint.

Bounds are inclusive. The maximum and minimum may be the same value.

A constraint doesn't say what value quality it applies to. Its literals are
interpreted with the value quality of whatever position or view the constraint
is assigned on (see [DLP 52 (Literals)](../define/proposals/00052-literals.md)).

```ebnf
fully_qualified_constraint_name = "constraint", "<", fully_qualified_global_name, ">" ;
constraint_definition =
    "define the", " ", fully_qualified_constraint_name, constraint_definition_block ;
constraint_definition_block =
    block_open,
    constraint_statement,
    { constraint_statement },
    block_close ;
constraint_statement =
    ( "it has the maximum value" | "it has the minimum value" ), " of ", literal, terminator ;
```

### Assigning Constraints

Constraints are assigned in Position Quality Assignment Blocks and View Quality
Assignment Blocks with a normal Quality Assignment Statement:

```define
define the position<percent_charged> {
    it may only contain particles where {
        it has the value<standard:/number/natural>.
        it has the constraint<mv:example.com:example:/percentage>.
    }
}
```

A constraint may only be assigned on a position or view that also assigns a
value quality, and every constraint assignment must come after the value quality
assignment. A position or view may be assigned any number of constraints.

When a constraint is assigned, the compiler checks it against the value quality
right there, and reports any errors at that Quality Assignment Statement. Every
predicate the constraint uses must be supported by the value quality. Every
literal in the constraint must be a valid literal for the value quality (so
`literal<standard:/number>"-5"` is fine as a bound on an integer, but it's an
error as a bound on a natural). And every bound must be within the value
quality's `highest allowed` and `lowest allowed` limits.

The constraints of a position or view combine: the allowed range is the overlap
of every constraint assigned there. If the overlap is empty (like a minimum of
50 and a maximum of 10, even if they come from different constraints), that's an
error on the definition of the position or view.

If a constraint assignment doesn't narrow the allowed range at all, because the
other constraints (or the value quality itself) already imply it, that's a Dead
Quality Assignment and is an error (see
[DLP 42 (Dead Code is Forbidden)](../define/proposals/00042-dead-code-is-forbidden.md)).
This doesn't depend on the order of the constraints. For example, a constraint
that only says "the minimum value is 0" is always dead on a natural, and a 0–100
constraint is dead on a position that also has a 0–10 constraint, no matter
which one is listed first.

If two constraints are tied for the tightest bound on the same side and neither
one is the tightest on its other side, then each of them is dead on its own. The
compiler reports the one that's listed later.

### Constraints Belong to Particles

Logically, constraints are qualities of a particle, like any other quality. A
particle's constraints are the narrowest constraints of every position it has
been in, and every value it's ever set to must satisfy all of them.

However, the compiler doesn't have to track that. Every check in this proposal
guarantees that a particle's constraints always fit inside the constraints of
the position it's currently in. So the compiler can check everything pairwise,
using only the constraints declared on positions and views, and it never has to
look at the history of a particle.

So narrowing is real, but for now it's only something the backend may use for
optimization. Nothing in the frontend depends on it.

### Constraints Do Not Apply to Unset Values

A constraint only applies to a set value. A particle with an unset value
satisfies every constraint.

### Range Checks

Everywhere a value can end up in a position, the compiler checks that the
value's range fits inside the position's allowed range. The range of a literal
is exactly that literal's value. The range of a position is its allowed range
(from its value quality and its constraints). The range of an output view is
computed from the view's logical meaning, as described below.

The checks are:

1. In a Value Setting Statement (`set the value of X to Y`), the range of `Y`
   must fit inside the allowed range of `X`.
2. In a Move Particle Statement, the source position's allowed range must fit
   inside the destination position's allowed range. If the compiler knows the
   particle's value is unset, this check is skipped, since constraints don't
   apply to unset values. This replaces the plain set comparison for constraints
   only. Every other quality is still checked as described in
   [DLP 19 (Guaranteeing Qualities in Positions)](../define/proposals/00019-guaranteeing-qualities-in-positions.md).
3. When an input view is looking at a position, the position's allowed range
   must fit inside the view's allowed range. A literal must be inside the view's
   allowed range. This is part of executing an operation
   ([DLP 40 (Value Operations)](../define/proposals/00040-value-operations.md)).
4. When an Operation Execution Statement writes to a position through an output
   view, the range of the value written must fit inside that position's allowed
   range.

A view that is both read and written gets both the third and fourth checks.

"Fits inside" means that the minimum of the value's range is at least the
position's minimum, and the maximum of the value's range is at most the
position's maximum. It's two comparisons per check.

### Ranges Through Logical Operations

Every numeric [DLP 55](../define/proposals/00055-logical-operations.md) logical
operation has an obvious interval version. For example, if `A` is 0 to 10 and
`B` is 0 to 5, then `standard:/number/add` of A and B is 0 to 15,
`standard:/number/negate` of B is -5 to 0, `standard:/number/multiply` of A and
B is 0 to 50, and `standard:/number/minimum` of A and B is 0 to 5. You compute
each of these from the endpoints of the operand ranges. (Multiplication needs
the most care, since negative endpoints can flip which one is the highest.)
`standard:/number/power` with an odd exponent keeps the order of the endpoints,
and with an even exponent it's never negative: a value from -3 to 5 squared is 0
to 25.

`standard:/choose` gives a range that covers the range of `view<if_true>` when
its condition is true and the range of `view<if_false>` when its condition is
false (see Narrowing by a Condition, below). A Value Setting Statement keeps the
range of whatever it sets the value from. `standard:/number/less_than` and the
equalities produce truth values, which have no order, so range constraints don't
apply to them.

When an Operation Statements Block has more than one statement, the compiler
computes the range of each statement in order, using the ranges from the earlier
statements. Each view is only written once (see
[DLP 55](../define/proposals/00055-logical-operations.md)), so each view has
exactly one range, and that's the range that's checked.

The compiler does this computation in two places.

First, when an operation is defined: if an output view has constraints, then the
range of its logical meaning, computed from the _input views'_ allowed ranges,
must fit inside the output view's allowed range. Otherwise it's an error on the
output view. An output view that has constraints and is in an Unknown Value
Statement is always an error, because an unknown value fails every constraint.

Second, when an operation is executed: the range of each output view is computed
from the ranges of whatever the _input views are looking at_ (positions and
literals), not just from the views' own constraints (see Evaluating Ranges
Through Operations, below). That's the range that gets checked against the
destination position.

The second one matters a lot. It means `standard:/number/natural/add` doesn't
need any constraints on its views at all, and you can still add a 0–10 and a 0–5
into a 0–15 position.

### Evaluating Ranges Through Operations

Where a value operation is executed, the compiler finds the ranges of its output
views by going through its Operation Statements Block in order with the ranges
of whatever its input views are looking at, using the rules above for each
logical operation. When the block executes another value operation, the compiler
does the same thing for that one, with the ranges its views are looking at at
that point.

That's practical because of how Define works:

- Define doesn't allow recursion, so the operations that an execution can lead
  to always end.
- An Operation Statements Block has no loops and no branches.
  (`standard:/choose` picks a value. It doesn't skip any statements.) So going
  through it with ranges is a single pass, from top to bottom.
- Views can't alias, so the range in one view can never change through another
  view.
- Ranges aren't carried from one statement of an action to the next (see Why the
  Compiler Doesn't Track Narrowing), so each check only involves one execution,
  with input ranges that come from declared constraints and literals.

So checking an execution takes the same number of steps as running it once, just
on ranges instead of numbers. The compiler also remembers the result for each
operation and set of inputs (their ranges, and the linear relationships between
them, below), so an operation executed with the same inputs in many places is
only gone through once.

For example, where `standard:/number/natural/minimum` is executed with a 0–100
and a 0–9, its result is 0 to 9, even though its views have no constraints.

### Linear Relationships Within an Execution

While the compiler goes through an execution with ranges, it also keeps track of
the linear relationships between values. Each value is either:

- an _independent value_, which has its own range, or
- a _linear formula_: a number, plus a number times each of some independent
  values.

At the start of a check, whatever the execution's input views look at are
independent values. Then:

- `standard:/number/add` adds the formulas.
- `standard:/number/negate` negates the formula.
- `standard:/number/multiply`, where one of its inputs is just a number (a
  literal, or a formula with no independent values in it), multiplies the
  formula by that number.
- A Value Setting Statement keeps the formula.
- Executing a value operation passes the formulas on to the views of the
  operation being executed.
- Every other logical operation (`standard:/number/multiply` of two values that
  aren't just numbers, `standard:/number/minimum`,
  `standard:/number/absolute_value`, `standard:/number/power`, and
  `standard:/choose`) isn't linear. The compiler computes the range of its
  result with the rules above, and the result is a new independent value with
  that range. (The one exception is a `standard:/choose` whose condition can
  only be true, or only false. Its result is the formula of the view it picks.)

The range of a formula is the number plus the range of each of its terms. Every
independent value can be anywhere in its own range, no matter what the others
are, so that range is exact. For example, `x - x` is the formula 0, so its range
is exactly 0 instead of -10 to 10, and `(x + 1) - x` is exactly 1.

So the rule a programmer needs to know is: within one execution, the compiler
knows every linear relationship between values, and the result of anything that
isn't linear is a new value, as far as the compiler knows. Ranges still aren't
carried from one statement of an action to the next. Each check starts over.

A formula has at most one term for each independent value. Most operations only
involve a few values, but in the worst case (like adding up many different
values), formulas get as long as the number of independent values in the
execution. So checking one execution takes time proportional to its number of
statements times the number of independent values it involves.

This is a simplified form of
[affine arithmetic](https://en.wikipedia.org/wiki/Affine_arithmetic), a
well-known way to fix the dependency problem of intervals. Full affine
arithmetic also keeps an approximate linear relationship for nonlinear results,
and it has extra terms for rounding errors. Ours keeps only the exact
relationships, so it never has to approximate anything except a nonlinear
result's range, which it computes the same way intervals do.

### Narrowing by a Condition

When `standard:/number/less_than` or `standard:/number/equality` produces a
truth value, the compiler remembers which comparison of two formulas it came
from. A Value Setting Statement and executing a value operation pass that on,
the same way they pass on formulas. A `standard:/choose` that picks the literal
false when its condition is true and the literal true when it's false (a "not")
produces the opposite comparison.

When a `standard:/choose`'s condition came from a comparison, the compiler
computes the range of `view<if_true>` knowing that the comparison is true, and
the range of `view<if_false>` knowing that it's false. The range of the result
covers those two ranges.

Every comparison is between two formulas, so it's a fact about the independent
values in them, like "x is less than y" or "x is 0." Knowing one such fact, the
range of a formula is still exact, and finding it has a fixed solution. To find
the smallest value, the compiler starts with every independent value at the end
of its range that makes the formula smallest. If the comparison isn't true
there, it moves independent values toward making it true, starting with the ones
that change the formula the least for how much they change the comparison, until
it's true. The largest value works the same way. If the comparison can't be true
anywhere, that view is never picked. This takes time proportional to the number
of independent values involved, times its logarithm. There's no search.

A few details make this work for integers:

- When both sides of `standard:/number/less_than` can only be integers, "less
  than" means "at most one less than." When either side might not be an integer,
  the compiler uses "at most" instead. That range might include the one value it
  can't be, but it's never too narrow.
- When the formula is an integer, the compiler rounds the ends of its range
  inward to integers. When every number multiplying an independent value in the
  comparison is 1 or -1, like in any comparison of two independent values, or of
  an independent value and a number, that's exactly the range.
- Knowing that two values aren't equal only narrows a range when the value it
  excludes is at one end of it. A natural that isn't 0 is at least 1, but an
  integer from -5 to 5 that isn't 0 is still -5 to 5 (see Forward
  Compatibility).

For example, this subtracts 1 from a natural, but stops at 0:

```define
define the operation<mv:example.com:example:/decrement_to_zero> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        define the view<is_zero> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/number/equality> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"0".
            with view<result> looking at view<is_zero>.
        }
        define the view<decremented> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"-1".
            with view<result> looking at view<decremented>.
        }
        execute the logical_operation<standard:/choose> {
            with view<condition> looking at view<is_zero>.
            with view<if_true> looking at literal<standard:/number>"0".
            with view<if_false> looking at view<decremented>.
            with view<result> looking at view<result>.
        }
    }
}
```

`view<decremented>` is the formula a - 1, so it can be -1, and it has to be an
integer. But `standard:/choose` only picks it when a isn't 0. A natural that
isn't 0 is at least 1, so then a - 1 is at least 0. The range of the result
covers 0 and a - 1 for an a of at least 1, which is never negative, so it fits
in a natural.

### Incrementing

Increment always works when the destination can hold the result. That's any
position without a maximum (like a count of cars that have entered a garage),
and any case where you read from a narrower position than you write to (like
reading from a 0–9 position and writing into a 0–10 position).

What _doesn't_ work is incrementing in place in a position that has a maximum.
If a position is 0–10 and holds 10, incrementing it gives you 11. The compiler
is right to reject that, because it really _could_ be 11! The program has to say
what happens at the top, and there are only a few real choices. It could
saturate (stay at the maximum), which is an operation that executes
`standard:/number/add` and then `standard:/number/minimum` with the maximum, and
that works today. It could wrap back around to the minimum, which needs
remainders, so that will come with division. Or it could fail, and the program
handles the failure. That needs a way to make assertions at runtime that the
compiler then guarantees after the assertion, which will be its own proposal.

Eventually we'll also want a way to put properties like "saturating" or
"wrapping" on logical operations themselves.

The DLP 55 version of `increment` (which is just a sum) is still the right
operation for any position that doesn't have a maximum, which is most counters.

## A Real Program

### Value Qualities

```define
define the potential value<standard:/number/natural> {
        it supports the logical_operation<standard:/number/absolute_value>.
    it supports the logical_operation<standard:/number/add>.
    it supports the logical_operation<standard:/number/equality>.
    it supports the logical_operation<standard:/number/less_than>.

    it supports the logical_operation<standard:/number/minimum>.
    it supports the logical_operation<standard:/number/multiply>.
    it supports the logical_operation<standard:/number/negate>.
    it may have the predicates {
        it has the maximum value {
            highest allowed is infinite.
        }
        it has the minimum value {
            lowest allowed is literal<standard:/number>"0".
        }
    }
}

define the potential value<standard:/number/integer> {
        it supports the logical_operation<standard:/number/absolute_value>.
    it supports the logical_operation<standard:/number/add>.
    it supports the logical_operation<standard:/number/equality>.
    it supports the logical_operation<standard:/number/less_than>.

    it supports the logical_operation<standard:/number/minimum>.
    it supports the logical_operation<standard:/number/multiply>.
    it supports the logical_operation<standard:/number/negate>.
    it may have the predicates {
        it has the maximum value {
            highest allowed is infinite.
        }
        it has the minimum value {
            lowest allowed is infinite.
        }
    }
}

define the potential value<standard:/boolean> {
    it supports the logical_operation<standard:/boolean/equality>.
}

define the potential literal<standard:/number> {
    it has the encoding<standard:/number/decimal/ascii>.
}
```

### A Battery

```define
define the constraint<mv:example.com:example:/percentage> {
    it has the maximum value of literal<standard:/number>"100".
    it has the minimum value of literal<standard:/number>"0".
}

define the constraint<mv:example.com:example:/single_digit> {
    it has the maximum value of literal<standard:/number>"9".
}

define the constraint<mv:example.com:example:/low_battery> {
    it has the maximum value of literal<standard:/number>"20".
}

define the potential action<mv:example.com:example:/battery/report> {
    define the position<percent_charged> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
            it has the constraint<mv:example.com:example:/percentage>.
        }
    }
    define the position<warning_level> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
            it has the constraint<mv:example.com:example:/low_battery>.
        }
    }

    it happens when {
        the position<percent_charged> has a particle.
    } and it does {
        define the position<charging_gain> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
                it has the constraint<mv:example.com:example:/single_digit>.
            }
        }
        define the position<projected> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        define the position<capped> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
                it has the constraint<mv:example.com:example:/percentage>.
            }
        }

        create a particle in position<charging_gain>.
        # Fine: 5 is between 0 and 9.
        set the value of position<charging_gain> to literal<standard:/number>"5".

        create a particle in position<projected>.
        # Fine: 0-100 plus 0-9 is 0-109, and position<projected> has no
        # constraints.
        execute the operation<standard:/number/natural/add> {
            with view<a> looking at position<percent_charged>.
            with view<b> looking at position<charging_gain>.
            with view<result> looking at position<projected>.
        }

        create a particle in position<capped>.
        # Error: position<projected> is any natural, which does not fit inside
        # 0-100.
        set the value of position<capped> to position<projected>.

                        # Fine: the minimum of 0-100 and 0-9 is 0-9, which fits inside 0-100.
        execute the operation<standard:/number/natural/minimum> {
            with view<a> looking at position<percent_charged>.
            with view<b> looking at position<charging_gain>.
            with view<result> looking at position<capped>.
        }

        # Fine: 0-9 fits inside 0-20.
        move the particle in position<charging_gain> to position<warning_level>.

        # Error: 0-100 does not fit inside 0-20, even though position<capped>
        # was just set from something that was 0-9.
        set the value of position<warning_level> to position<capped>.
    }
}
```

### Errors When Assigning Constraints

```define
define the constraint<mv:example.com:example:/below_zero> {
    it has the maximum value of literal<standard:/number>"-1".
}

define the constraint<mv:example.com:example:/at_least_fifty> {
    it has the minimum value of literal<standard:/number>"50".
}

define the constraint<mv:example.com:example:/at_most_ten> {
    it has the maximum value of literal<standard:/number>"10".
}

define the potential action<mv:example.com:example:/errors> {
    define the position<negative_natural> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
            # Error: "-1" is not a valid natural.
            it has the constraint<mv:example.com:example:/below_zero>.
        }
    }
    # Error: nothing is both at least 50 and at most 10.
    define the position<impossible> {
        it may only contain particles where {
            it has the value<standard:/number/integer>.
            it has the constraint<mv:example.com:example:/at_least_fifty>.
            it has the constraint<mv:example.com:example:/at_most_ten>.
        }
    }
    define the position<flag> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
            # Error: value<standard:/boolean> doesn't support the predicate
            # "it has the maximum value".
            it has the constraint<mv:example.com:example:/at_most_ten>.
        }
    }

    it happens when {
        the position<negative_natural> has a particle.
    } and it does {
        destroy the particle in position<negative_natural>.
    }
}
```

## Why This is the Right Solution

### Intervals, Not Solvers

The most important decision here is what we _don't_ do: there's no SMT solver
and no general proof search. Every check in this proposal compares two
endpoints, and every logical operation is a fixed computation on endpoints and
linear formulas. Narrowing by a condition has a fixed computation too. There are
no quantifiers, no constraint can refer to another constraint, and we never ask
"does there exist a value such that..." We only ever compute a range and compare
it. So checking is always decidable, it takes time that's linear in the number
of logical operations the program's statements perform, and it takes the same
amount of time every time. No timeouts, no "it compiled yesterday." And
programmers can predict exactly what the compiler will say: if you can add up
the endpoints, you can do what the compiler does.

What about multiplication? [The requirements](../define/spec/requirements.md)
warn about nonlinear arithmetic, because `x * y = z` is hard for a solver. But
that's hard because the solver is trying to _find_ values that satisfy the
equation. Computing the range of `x * y` when you already know the ranges of `x`
and `y` is just multiplying the endpoints. There's nothing to solve.

The trade-off is precision, like in the `x - x` case. Tracking linear
relationships within an execution fixes `x - x` and every other case where
values only meet through adding, negating, and multiplying by numbers. It
doesn't fix cases where the same value goes through a nonlinear step more than
once, like linear interpolation (`a + t * (b - a)`). I think that's an
acceptable trade-off for predictability. Where it matters, a logical operation
that takes each value once can be added (see DLP 55), and if we find real
programs where that isn't enough, there are more precise kinds of approximation
that are still fast.

### Why Evaluate Ranges Instead of Summarizing Them?

Most range analyses summarize each function, because they have to: with loops
and recursion, going through a function again at every call might never end, or
might take as long as the program runs. Summaries have a cost, though (Problem
11). Exact summaries can grow without limit, and summaries that are kept small
(like only allowing linear formulas) lose precision for common operations like
the minimum. A limit on the size of a summary would make whether a program
compiles depend on a number the programmer can't see.

Define's value operations don't need summaries. With no recursion, no loops, no
branches, and no aliasing, going through an operation's statements with ranges
is exactly as much work as running it once. Every logical operation gets its
exact interval rule, so a minimum, an absolute value, a `standard:/choose`, or a
view multiplied by itself all give precise ranges where they're executed.

The cost is that checking time is linear in how much work each statement does,
not in how long the program's text is. Those are only different for a program
whose statements do far more work than their text suggests, like an operation
that executes another one twice, which executes another one twice, and so on.
That program is just as expensive to run as it is to check, and its text says
so. Remembering results for each operation and set of input ranges means common
operations are only gone through once.

When Define has loops, a value operation that contains a loop will need some
kind of summary for that loop. That's true of every range analysis, and it
belongs in the proposal that adds loops.

### Why Track Linear Relationships?

Intervals alone lose precision whenever a value is used more than once (Problem
13). Within one execution, tracking linear relationships fixes that for
everything linear, and it's cheap: it's the same kind of bookkeeping as
intervals, just with a list of terms instead of two endpoints.

It also doesn't need views to alias, or any copy of a value to be "the same" as
the original. Two values are related because the compiler computed one from the
other, and it knows that because it just went through the statements.

This doesn't contradict Why Not Use What We Know About Values?, below. That's
about carrying knowledge from one statement of an action to the next, which
would make whether a line is valid depend on everything before it. Here,
everything the compiler learns stays within one execution, and the programmer
only ever sees whether that one execution's results fit where they're going.

We stop at linear relationships because they stay exact and simple to explain.
Following relationships through nonlinear operations means approximating them,
and then whether a program compiles would depend on how good the approximation
is.

### Why `standard:/choose` Uses Its Condition

Without it, the obvious way to guard a computation doesn't work (Problem 12). A
program that only wants a value when some condition holds has to find another
way to write it, like DLP 55's saturating subtraction, which uses
`standard:/number/minimum`. That isn't always possible. Once Define has
division, a program that divides by a value that might be 0 has to replace the 0
with something else first, and the only way to know the replacement worked is to
use the condition.

This is how compilers have handled conditions for a long time. ABCD, which
removes array bounds checks in just-in-time compilers, adds a new name for a
value after each branch that tests it, so the facts from the test belong to that
name. LLVM's ConstraintElimination pass uses the conditions that must have been
true to reach a point in the program to prove that comparisons there are always
true or always false. Define's `standard:/choose` is simpler than either,
because there's only one condition, and it applies to exactly two values.

It stays within the rules of Why Track Linear Relationships?: everything the
compiler learns stays within one execution, and the range is exact for every
comparison between two values. It's still easy to predict, too: a value that a
condition picks has the range it can have when the condition is true.

It does have a cost. Define should have only one way to do each thing, and
narrowing by a condition gives some compositions a second way. A saturating
subtraction of two naturals can now be written with `standard:/choose` and a
comparison, as well as with DLP 55's `standard:/number/minimum`. Compositions of
logical operations already allow more than one way to write many things, but
this makes a second way work where it didn't before. We still need to address
this.

### Composed Constraints, Not Wrapper Types

I thought about this a lot. Wrapper types would have given us reusable value
types, which is nice, and it fits with how Define tries to minimize duplication.
But wrapper types don't actually solve the subtyping problem (see the Problems),
so you'd still have to check that one range fits inside another, unless you made
every wrapper unrelated to every other wrapper, which would be miserable to use.
You'd also have to look inside the wrapper to know what the actual value quality
is, and every combination of value and constraints would need its own global
name.

Also, we already have reusable "types" in Define: potential positions. If you
want a reusable percentage, you define a potential position that has the value
and the constraint, and give it to particles. Wrapper types would be a second
way of doing the same thing, and there should only be one right way.

So constraints are composed onto positions, and the cost is that they're checked
with "fits inside" instead of the plain set comparison that other qualities use.
Constraints are the one quality where that makes sense, because they're the one
quality that's about what values are allowed, and sets of allowed values
naturally fit inside each other.

### Why the Compiler Doesn't Track Narrowing

At first I thought the compiler would have to track narrowing (that a particle
that's been in a 0–10 position is still 0–10 after you move it into a 0–100
position). But then a `set the value of` statement could fail on a position for
reasons that have nothing to do with that position, and the compiler would have
to carry the narrowed constraints of every particle through every Action
Guarantee. That breaks modularity: an action could narrow a particle that you
passed it, and suddenly your code doesn't compile.

Since every check guarantees that a particle's constraints fit inside its
position's constraints, we get all the safety without the history. The narrowing
is still _logically_ true, though, so the backend can use it, and there's a lot
of clever stuff the backend could do with that. For example, if you narrow a
particle from 0–100 to 0–10 and then set it to 50 from another 0–100 position,
its actual bound is 0–50, so the backend knows it fits in that range and can
pick its encoding accordingly.

(This also means that the idea in
[DLP 53 (Unset Values)](../define/proposals/00053-unset-values.md) of Action
Guarantees carrying the strictest constraints a particle was set under isn't
something the frontend needs for checking. It's backend information.)

### Why Not Use What We Know About Values?

Setting `position<warning_level>` from `position<capped>` in the example is an
error, even though we know `position<capped>` holds something from 0 to 9. To
allow that, the compiler would have to track the range of each particle,
statement by statement, through the program. That's doable, but it's a lot more
complex, and it makes errors harder to understand, because whether a line is
valid would depend on everything that happened before it, not just on what the
two positions say.

This is the strictest choice, and it's easy to relax later. The real solution
for "I know this value is small enough" will be assertions that the program
makes at runtime (with explicit behavior when they fail, like in
[DLP 18](../define/proposals/00018-modular-constraints.md)), which the compiler
then guarantees for the code after them. This is also why there's no automatic
runtime range check like in Ada: if the compiler can't prove it, it's an error,
and anything that has to happen at runtime has to be written explicitly in the
program.

### Why Value Qualities Declare Predicates

A constraint doesn't say what value quality it's for, on purpose. A constraint
like `percentage` makes sense for both naturals and integers. But then something
has to say which constraints make sense for which values. Having the value
quality declare its predicates puts that information in exactly one place, and
adding a new kind of constraint for a value is just a matter of the value
quality saying it supports it.

Most programmers will never look inside a value definition. If you _are_
defining value qualities, it's okay to have to know what a predicate is.

The `highest allowed` and `lowest allowed` statements look mostly redundant for
naturals and integers right now. (A natural can't have a literal bound below 0
anyway, because "-1" isn't a valid natural.) But they make the limits of each
predicate explicit, and they'll matter for value qualities where the set of
valid literals is bigger than the set of sensible bounds. For naturals and
integers, `infinite` is the logical truth. Any hardware limit is a property of
an encoding.

### Why Literals for Bounds?

Using literals solves the "what type is the bound" problem completely. A literal
already becomes whatever value quality the line where it's used needs
([DLP 52 (Literals)](../define/proposals/00052-literals.md)), so a bound on a
natural is a natural, and a bound on an integer is an integer. We don't need any
new numeric syntax.

### Why Errors Are Reported Where Constraints Are Assigned

Since a constraint doesn't know its value quality, it can't be fully checked
until it's assigned somewhere. The assignment is the only place where we know
both the value quality and the constraint. And since constraints have to come
after the value quality, the line that's in error always has everything it
depends on above it.

### Why Dead Constraints Are Errors

If a position is assigned both a 0–10 constraint and a 0–100 constraint, the
0–100 one does nothing. That's dead code, and
[DLP 42 (Dead Code is Forbidden)](../define/proposals/00042-dead-code-is-forbidden.md)
says we don't allow dead code. It also prevents somebody from reading the
position, seeing "0–100," and not noticing the other constraint.

Checking this is cheap, and it doesn't care what order the constraints are in.
The compiler goes through all the bounds on each side, keeping track of the
tightest bound and the second-tightest bound. A constraint is alive only if it's
strictly the tightest on at least one side. That's linear in the number of
constraints on the position. Also, positions in large programs will mostly share
the same few combinations of constraints, so the compiler can do this once per
combination instead of once per position.

### What About Boolean Conditions Later?

Eventually constraints will be able to combine conditions with "and," "or," and
"not." Then "is this constraint dead" turns into "does the combination of the
other constraints imply this one," and in general, checking whether one boolean
formula implies another is the satisfiability problem (SAT), which is not cheap.

But there's an important property that keeps us out of that trouble: a
constraint is only ever about _one_ particle's value. Any combination of "and,"
"or," and "not" over comparisons of a single ordered value against literals
always simplifies down to a sorted list of separate ranges. ("At least 1 and at
most 5, or at least 10 and at most 20.") Checking whether one sorted list of
ranges fits inside another is just one walk over both lists. It would only get
really hard if constraints could relate two _different_ values to each other,
and we should be very careful before we ever allow that.

That same property may also give us only one way to write a condition. Since
every condition on one ordered value simplifies to exactly one sorted list of
ranges, that list can be the one right way to write it, and the compiler can
reject any other way of writing the same condition and tell you exactly what to
write instead. For ranges, that means you'd never need "not" at all: "not
between 5 and 10" is just "at most 4, or at least 11." Where "not" really
matters is predicates on values that don't have an order, and we'll have to
figure that out when we get there.

### Unknown Values

Unknown values fail every constraint, which is what we want for values that come
from outside the program, like I/O. You can't put them in a constrained position
without proving something about them first. A later proposal on I/O will give us
a way to validate external values at the boundary of the program, which is where
[the concepts](../define/spec/concepts.md) say constraints matter most.

## Forward Compatibility

This is the strictest version of constraints we could have. There are only two
predicates, only declared ranges are used (with no flow-sensitive analysis),
unknown values fail every constraint, dead constraints are errors, and bounds
can only be literals. Any of those can be relaxed later without breaking any
existing program.

New predicates can be added by having value qualities declare them. Since
predicates are a fixed set of phrases defined by the compiler, they can't
conflict with any name a programmer defines.

If we later want wrapper types after all, every position that assigns a value
quality and a set of constraints maps deterministically onto a wrapper type with
that value quality and those constraints. If we want more precise analysis, any
program that compiles with interval checks will still compile, because a more
precise analysis only ever proves _more_ things.

What every future change to how ranges are computed has to keep is soundness: a
computed range must include every value the computation can really produce. It
doesn't have to be precise. A range that's wider than the true one only makes
the compiler reject a program it could have accepted, which is safe. A range
that's narrower than the true one would let a wrong value into a position, which
is never allowed. So an approximation, like a summary of a loop, or a bound the
compiler gives up on making exact, is always allowed as long as it's sound. The
other half of compatibility is that a change must not make any range wider than
it is now, or programs that compile today could stop compiling.

A range can't say that a value isn't 0 when it can be negative or positive. When
Define has division, a program will need to show that a divisor isn't 0, and for
an integer that can be negative, that needs either a predicate that excludes a
value or a range made of separate pieces. (What About Boolean Conditions Later?
shows that any condition on one value comes down to a sorted list of ranges.)
Then Narrowing by a Condition can use "isn't equal" for any value.

Some operations aren't linear, but are a linear formula plus an error that stays
within a known range, like rounding to a floating-point precision (within half
of the last place), or a quotient by a constant. Their results could keep a
linear relationship with their inputs by adding a new independent value for the
error, as full affine arithmetic does. That only ever makes ranges narrower.

Loops will need summaries of their effect on ranges. Any summary that's sound
can be added without breaking existing programs, because value operations
without loops will still be checked exactly as they are now.

## Refactoring Existing Systems

Existing Define programs don't use constraints, so nothing has to change. A
value quality that should support range constraints gains a predicate block.

Pascal and Ada subrange types map directly onto a value quality plus a
constraint, and so do refinement types that only compare against constants.
Refinement types with more complex conditions don't have an equivalent yet. Code
that relies on runtime range checks (or on overflow) would have to be
restructured so that it handles the out-of-range case explicitly, because Define
requires the range to be provable.
