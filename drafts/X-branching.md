## Bend research

match is its core branching construct. The attraction is that it handles
selection while also giving the checker useful structural information:

- It identifies the alternatives and exposes their data. Matching a list
  distinguishes an empty list from a head and tail. The compiler can check that
  every possible case is covered.

- Each alternative supplies facts. In the empty-list case, the compiler knows
  the list is empty. In the other case, it knows the list consists of that head
  and tail. Bend uses those facts to specialize the proposition being proved.

- It exposes progress for recursion. The tail is structurally smaller than the
  original list, giving the termination checker an immediately recognizable
  reason that recursion progresses.

There is one semantic distinction from a plain value-select function: a match
chooses which branch’s computation to execute. Passing f() and g() to an
ordinary eager select computes both before selection. Equivalent conditional
execution needs alternatives whose computation is deferred.

## Picking Between Values (`standard:/choose`)

> **Note:** This section was written by Claude. Most of it was moved out of the
> Range Constraints draft when `standard:/choose` was deferred from DLP 56.

`standard:/choose` was a logical operation that picked `view<if_true>` or
`view<if_false>` based on `view<condition>`. Both options are always computed,
so it doesn't skip any statements, but it makes the compiler's range reasoning
branch. It was deferred to this proposal so that it can be answered together
with real branching.

### Worst-Case Constraints

The simplest way to handle it: after a `standard:/choose`, the result gets the
worst case of both options' ranges, which is the range that covers both. That's
sound, it's linear, and it never splits the analysis. It loses precision when
the condition is what keeps an option in range.

### The Problem

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

### Narrowing by a Condition (More Precise)

When `standard:/number/less_than` or `standard:/number/equality` produces a
boolean value, the compiler remembers which comparison of two formulas it came
from. A Value Setting Statement and executing a value operation pass that on,
the same way they pass on formulas. `standard:/boolean/not` of it produces the
opposite comparison.

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
  integer from -5 to 5 that isn't 0 is still -5 to 5.

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

### Why Narrowing Might Be Worth It

Without it, the obvious way to guard a computation doesn't work. A program that
only wants a value when some condition holds has to find another way to write
it, like DLP 55's saturating subtraction, which uses `standard:/number/minimum`.
That isn't always possible. Once Define has division, a program that divides by
a value that might be 0 has to replace the 0 with something else first, and the
only way to know the replacement worked is to use the condition.

This is how compilers have handled conditions for a long time. ABCD, which
removes array bounds checks in just-in-time compilers, adds a new name for a
value after each branch that tests it, so the facts from the test belong to that
name. LLVM's ConstraintElimination pass uses the conditions that must have been
true to reach a point in the program to prove that comparisons there are always
true or always false. Define's `standard:/choose` is simpler than either,
because there's only one condition, and it applies to exactly two values.

It stays within the rules of the Range Constraints draft's Why Track Linear
Relationships?: everything the compiler learns stays within one execution, and
the range is exact for every comparison between two values. It's still easy to
predict, too: a value that a condition picks has the range it can have when the
condition is true.

It does have a cost. Define should have only one way to do each thing, and
narrowing by a condition gives some compositions a second way. A saturating
subtraction of two naturals can now be written with `standard:/choose` and a
comparison, as well as with DLP 55's `standard:/number/minimum`. Compositions of
logical operations already allow more than one way to write many things, but
this makes a second way work where it didn't before. We still need to address
this.

## Branching with Exhaustive Matches

> **Note:** This section was written by Claude, from a discussion about whether
> Define should have `standard:/choose`, structural branching, or both. The
> conditional construct being considered is a match that attempts to require
> exhaustiveness. The references in it are from memory and haven't been checked
> yet.

### What a Match Does That `choose` Can't

`standard:/choose` computes both of its options and then picks one, so each
option has to be valid even when it isn't picked. That's why `decrement_to_zero`
above computes a - 1 as an integer, and why it only works with narrowing by a
condition. In a match, a case's statements run only when that case matches. In a
case where a natural is known to be at least 1, subtracting 1 from it is simply
a natural. Anything that's only valid under a condition needs this: subtracting
naturals, dividing, and probably indexing later.

Precision is a smaller difference than it looks:

- Inside a case, the compiler knows the case's condition, and anything that
  depends only on the condition can become a literal there.
- `standard:/choose` can get the same precision for an option that's used
  nowhere else, by analyzing it as if the condition were true. That's what
  narrowing by a condition does.
- After the match, the compiler still has to assume any case could have run,
  just like after a `standard:/choose`, unless it keeps track of the condition.

So a match is more precise inside its cases, not after it.

Matches also skip work that isn't needed, and if actions can have effects that
should only happen under a condition, `standard:/choose` can't express that at
all, because it runs both sides.

### What `choose` Has Going for It

- **It's only dataflow.** Value operations stay straight-line, every view is
  written exactly once with no paths to think about, and the Single Assignment
  and View Setting Statement rules don't change.
- **It compiles without branches.** It maps to a select or conditional-move
  instruction, which runs in constant time (no timing leaks, no mispredicted
  branches) and works lane by lane in SIMD code.
- **It fits the boolean representations.** It's an if-then-else node, which is
  what a BDD node is, so it can be hash-consed with everything else.
- **It doesn't multiply paths.** n matches in a row make up to 2ⁿ combinations
  of cases, so analysis has to merge after each match, which gives back the
  precision of `standard:/choose`, or else grow exponentially.

### Cases That Produce Values

A match can stay Single Assignment from the outside if each case has its own
local views, and every case writes the same views from outside the match exactly
once. Exhaustiveness is what makes that work: if every possible value matches
some case, the match as a whole writes each of those views exactly once, with no
default values and no "maybe never written" state. The local views of a case
can't be read outside it.

Compilers already use this design: MLIR's `scf.if`, whose branches each produce
the operation's results; the gamma nodes of the RVSDG (Reissmann and others,
"RVSDG: An Intermediate Representation for Optimizing Compilers," ACM
Transactions on Embedded Computing Systems, 2020); and gated SSA, from the
Program Dependence Web (Ottenstein, Ballance, and MacCabe, PLDI 1990).

A match on a boolean value with one case for true and one for false does
everything `standard:/choose` does, so Define wouldn't need both. The compiler
can still turn a match into a select instruction when every case is cheap and
safe to run.

### Keeping Exhaustiveness Cheap

How hard it is to check that a match is exhaustive depends on what a case can
test:

- **Literals, variants, or ranges of one value:** sort the cases and look for
  gaps. That takes O(k log k) time for k cases.
- **Several values at once**, like matching two booleans against rows of cases:
  checking that the rows cover every combination is checking that a formula in
  disjunctive normal form is always true, which is coNP-complete. Exhaustiveness
  checking for ML-style patterns is NP-hard for the same reason (Maranget,
  "Warnings for Pattern Matching," Journal of Functional Programming, 2007).
  Real lists of cases are small, so this is usually fast in practice, but it
  isn't guaranteed.
- **Arbitrary conditions on a case** (guards): checking that the `or` of every
  case's condition is always true. That's the same coNP problem as everything
  else in the background research, on a formula of any size. Rust gives up here:
  a case with a guard never counts toward exhaustiveness. Haskell tries harder
  and limits how much work it does ("Lower Your Guards," Graf, Peyton Jones, and
  Scott, ICFP 2020).

So exhaustiveness can be exact and cheap if cases can only test literals,
variants, or ranges of the matched values, with anything finer done in a match
inside a case. A case with an arbitrary condition could still be allowed if it
never counts toward exhaustiveness, so a case without a condition still has to
cover the rest.

### First Match or Disjoint Cases

- **First match:** cases can overlap, and the first one that matches runs. Each
  case also knows that none of the cases before it matched.
- **Disjoint:** no value can match two cases. Then the cases split every
  possible value into separate parts, the same property that makes `or` in a
  d-DNNF deterministic. The order of the cases doesn't matter, which fits better
  with having only one way to write something. But checking that cases are
  disjoint costs the same as checking that they're exhaustive: cheap for ranges
  of one value, coNP for arbitrary conditions.

`standard:/choose` is disjoint and exhaustive by construction. Its two options
are for a true condition and a false one, and a boolean value is always exactly
one of those, so there's nothing to check. Nested `standard:/choose`s make a
decision tree, and a decision tree's leaves are disjoint for the same reason.
That's how decision-DNNF and BDDs get determinism without paying for it.

A match gets the same guarantee when each case tests the matched value for a
different literal or variant: `true` and `false` for a boolean, or ranges that
don't overlap for a number. Checking that they're different is a syntactic
comparison. The cost only appears when a case can test an arbitrary condition,
or a combination of several values.

So one option is to have no guards at all. A program that needs a complicated
condition computes it into a boolean view first, with compositions of
`standard:/boolean/and` and `standard:/boolean/not`, and then matches on that
view with a `true` case and a `false` case. Then disjointness and exhaustiveness
are free, as they are for `standard:/choose`.

That moves the hard part to what each case knows. In the `true` case, the
compiler knows the condition is true, but if the condition is an arbitrary
formula, turning that into facts about ranges is the same hard reasoning as
before. That only affects how precise the compiler's ranges are, not whether the
match is valid, so the compiler can approximate it. When the condition is a
single comparison, narrowing by a condition stays exact.

### What Each Case Knows

When a match is on a number and its cases are ranges, what each case knows is
just a narrower range for that number. That fits directly into the intervals of
the Range Constraints draft: each case's range is exact without any solver, and
it's what makes subtracting naturals inside a case safe. After the match, each
view the match writes has the range covering what every case could write to it.
