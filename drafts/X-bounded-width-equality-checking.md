# Bounded-Width Equality Checking

A possible way for the compiler to decide whether two boolean values always
equal each other, which a rule like "don't write the same logic twice" needs.
See
[Representations of Boolean Logic](../define/proposals/background/boolean-logic-representations.md),
especially "Width Along a Fixed Order," "Checking Two Whole Circuits," and "SAT
Sweeping," for the research behind it.

## The Idea

Statements in a value operation already come in a fixed order. Between any two
statements, count the boolean values that have been computed (or are inputs) and
that a later statement still uses: the values that are _live_ there. Call the
largest such count the operation's _width_.

Measuring the width takes one pass over the statements, and it's exact. It's the
same count register allocation uses.

### Below the Limit: OBDDs

If the width is at most some limit `k`, the compiler builds a reduced OBDD for
each value, with the inputs ordered by where each is first used. Cutting the
statements just before an input's first use, everything after the cut depends
only on the at most `k` live values there and on the inputs not used yet, so the
OBDD has at most 2^k nodes at each level and at most n·2^k nodes in all. Berman
(1991) proves a bound of this kind for circuits in general.

Reduced OBDDs are canonical for their input order. So when every value being
compared uses the same input order, two values are equal exactly when they're
the same node, and finding all the equal values among many is a hash table
lookup for each one.

### Above the Limit: SAT

If the width is more than `k`, the compiler checks equality with a SAT solver
instead: Tseitin-encode `f xor g` and ask whether it can be true. If it can't,
`f` and `g` are equal. If it can, the solver's assignment is an example where
they differ.

To avoid asking the solver about every pair, the compiler first simulates the
values on random inputs and groups the values that agree on every pattern. Only
pairs in the same group go to the solver, and each assignment the solver finds
becomes a new pattern that splits its group. That's SAT sweeping.

Parts of an equation that stay within the limit can still use OBDDs, and the
equalities they prove shrink what the solver has to handle.

### Why This Combination

Run to completion, the OBDD check and the SAT check give the same answer. So the
limit `k` only changes how long checking takes, never which programs are
accepted. That's what makes it predictable for the programmer.

The alternative, replacing values past the limit with new independent inputs, is
cheaper but not predictable. It never reports a false equality, because putting
the real values back can't make two equal results differ. But it misses some
real equalities, and which ones it misses depends on where the limit happened to
cut the equation.

## Open Questions

- **What `k` is.** Each live value doubles the worst-case OBDD width, so `k` has
  to be small. Real value operations need to be measured to pick it.
- **A shared input order.** OBDD equality only works between values that use the
  same input order. Values whose inputs are first used in different orders need
  one order chosen for both, and the width bound only holds for the order it was
  measured in.
- **Programs that are easy but wide.** The width is measured for the order the
  statements are written in, not the best order, and finding the best order is
  NP-hard (it's the pathwidth problem). For example, an `and` of `n` inputs
  written as a balanced tree keeps about `log n` values live, even though its
  OBDD only has `n` nodes. Such programs would go to SAT unnecessarily.
- **Bounding SAT.** If the solver has a limit, results depend on the limit.
  Either it runs to completion, accepting rare slow compiles, or the limit
  counts something deterministic, like solver conflicts instead of seconds, so
  that the same program always gets the same answer.
- **Error messages.** A satisfying assignment shows that two values differ. A
  proof of equality points at the two values and the statements they depend on.
  How to present either one to the programmer is still open.
- **Values that aren't single bits.** This counts boolean values. Numbers and
  other values would count as more than one bit each.
