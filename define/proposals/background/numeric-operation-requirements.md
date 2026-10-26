# Numeric Operation Requirements

This is a survey of what a programming language needs from numeric operations,
gathered as input for the design of logical operations and range constraints in
Define.

It has three kinds of requirements:

1. **Expression:** things programmers need to be able to write.
2. **Optimization:** information a backend needs in order to generate the best
   possible code.
3. **Proof:** things programmers (or the compiler) need to be able to prove
   about numeric code.

At the end, there's a section on what these mean for Define.

Each requirement says which _layer_ it probably belongs to in Define:

- **Logical:** part of what an operation means, so it belongs in a logical
  operation.
- **Encoding:** part of how a value is represented, so it belongs in an encoding
  or an Encoding Operation.
- **Intent:** a freedom or restriction the programmer grants the compiler, which
  isn't part of the mathematical meaning but changes what the compiler may do.

## Sources

These are the systems this survey draws on. Between them, they cover nearly
everything real programs and real optimizers have needed.

- [MLIR](https://mlir.llvm.org/)'s
  [`arith`](https://mlir.llvm.org/docs/Dialects/ArithOps/) and
  [`math`](https://mlir.llvm.org/docs/Dialects/MathOps/) dialects. MLIR is the
  LLVM project's framework for compiler intermediate representations that keep
  high-level operations around while lowering them. `arith` is basic integer and
  floating-point arithmetic; `math` is everything else (roots, trigonometry, bit
  counting, rounding).
- [LLVM IR](https://llvm.org/docs/LangRef.html), the lower-level representation
  that most compiled languages target. Its arithmetic instructions carry flags
  that tell the optimizer what can't happen (`nsw` "no signed wrap," `nuw` "no
  unsigned wrap," `exact` "this division has no remainder"), and floating-point
  instructions carry "fast-math" flags that grant the optimizer freedoms.
- [WebAssembly](https://webassembly.github.io/spec/core/)'s numeric
  instructions. WebAssembly is notable for being almost completely deterministic
  across platforms.
- [IEEE 754-2019](https://en.wikipedia.org/wiki/IEEE_754), the floating-point
  standard, and [IEEE 1788-2015](https://en.wikipedia.org/wiki/IEEE_1788-2015),
  the interval arithmetic standard (directly relevant to range constraints).
- [Rust's integer methods](https://doc.rust-lang.org/std/primitive.i32.html),
  which are the most complete set of explicit overflow behaviors in a mainstream
  language (`checked_`, `wrapping_`, `saturating_`, `overflowing_`, `strict_`,
  `unchecked_`, `widening_`, `carrying_`).
- C23's `<stdckdint.h>` (checked arithmetic) and `_BitInt(N)` (integers of any
  width), Java's `Math.addExact` and `Math.floorDiv`, Python's unbounded
  integers and floored division, and Ada's range, modular, and fixed-point
  types.
- Verification languages: [Dafny](https://dafny.org/),
  [TLA+](https://lamport.azurewebsites.net/tla/tla.html),
  [Rocq](https://rocq-prover.org/) (formerly Coq),
  [Lean](https://lean-lang.org/), and
  [SPARK](https://en.wikipedia.org/wiki/SPARK_(programming_language)). These are
  covered in their own section below.

## Expression Requirements

### E1: Exact Integer Arithmetic (Logical)

Addition, subtraction, multiplication, negation, and absolute value, with exact
results. This is the core of nearly every program: counting, indexing, sizes,
offsets, money in the smallest unit, and so on.

Every surveyed system has these. What differs is what happens when the result
doesn't fit (see E4).

### E2: Ordering (Logical)

Comparisons (less than, less than or equal, greater than, greater than or equal,
equal, not equal), minimum, maximum, and clamping a value into a range.

Some systems also have a three-way comparison that returns less, equal, or
greater (LLVM's `scmp`/`ucmp`, C++'s `<=>`, Rust's `cmp`). It's mostly useful
for sorting.

Values can be equal without having an order (identifiers, complex numbers), so
equality and ordering are separate capabilities.

### E3: Integer Division (Logical)

Quotient and remainder, where the rounding rule is part of the meaning. The
three common rules give different answers for negative numbers:

- **Truncated** (round toward zero): C, Java, Rust's `/`, WebAssembly, and every
  common CPU's division instruction. -7 / 2 is -3, remainder -1.
- **Floored** (round toward negative infinity): Python's `//` and `%`, TLA+. -7
  / 2 is -4, remainder 1.
- **Euclidean** (the remainder is never negative): Rust's `div_euclid` and
  `rem_euclid`, Dafny's `/` and `%`. -7 / 2 is -4, remainder 1. (It differs from
  floored division only when the divisor is negative.)

Also needed:

- Ceiling division (round toward positive infinity), which is how you compute
  "how many pages of 10 do I need for 23 items." MLIR has `ceildivsi`, Rust has
  `div_ceil`.
- Exact division, where the programmer knows there's no remainder (LLVM's
  `exact` flag, Rust's `div_exact`). This is both an expression need and an
  optimization fact (see O4).
- Rounding a value to a multiple (Rust's `next_multiple_of`), which is common
  for alignment.

The divisor can't be zero. Truncated signed division also can't divide the most
negative value of a fixed-width encoding by -1, but that's an encoding problem,
not a logical one: logically, the result is just a positive number that doesn't
fit.

### E4: What Happens When the Result Doesn't Fit (Logical, Encoding, Intent)

This is where systems differ the most. Rust has every variant:

- **Wrapping:** arithmetic modulo 2ⁿ. Needed for hashing, checksums, random
  number generators, cryptography, and sequence numbers that are designed to
  wrap. This is a _different logical operation_ from exact addition: it's
  addition in the integers modulo 2ⁿ. Ada models this as a separate "modular
  type."
- **Saturating:** stay at the maximum or minimum. Needed for audio, image
  processing, and control systems. Logically, this is the exact result clamped
  into a range.
- **Checked:** produce an explicit "it didn't fit" outcome that the program
  handles (Rust's `checked_`, C23's `ckd_add`, Java's `addExact`).
- **Overflowing:** produce the wrapped result _and_ whether it wrapped.
- **Widening:** produce a result in a wider encoding so that it always fits
  (`64 * 64 → 128`, or just the high half of a product, which is common in
  hashing and fixed-point code).
- **Carrying and borrowing:** add-with-carry and subtract-with-borrow, which are
  how arbitrary-precision arithmetic is built from fixed-width pieces.
- **Proven not to happen:** the compiler (or the programmer, unsafely) knows the
  result always fits. LLVM's `nsw`/`nuw` and Rust's `unchecked_` exist for this.

In Define, logical operations are exact, so widening is just "the compiler picks
an encoding big enough for the range." Carrying and borrowing are how an
Encoding Operation implements exact arithmetic on a wide value, so they belong
to encodings. Wrapping and saturating are logical. Checked arithmetic needs
runtime assertions that the compiler relies on afterward.

### E5: Powers, Roots, and Logarithms on Integers (Logical)

Integer power (Rust's `pow`, MLIR's `ipowi`), integer square root (`isqrt`), and
integer logarithms (`ilog2`, `ilog10`, which are "how many digits/bits does this
have"). These come up constantly in sizing buffers and in numeric algorithms.

### E6: Rational and Real Arithmetic (Logical, Encoding)

Division, powers, roots, exponentials, logarithms, trigonometry, and the
hyperbolic functions (MLIR's `math` dialect has 46 operations here, including
`erf`, `expm1`, `log1p`, `atan2`, and `sincos`).

Exact rationals can be implemented (as numerator and denominator), but exact
reals cannot: equality of two computable reals is undecidable, and every real
encoding is an approximation. So in practice, "real" means floating point (or
fixed point), and the approximation is part of the meaning. See E7.

Functions like `expm1` ("e to the x, minus one") and `log1p` exist only because
of approximation: they're accurate near zero where the obvious composition
isn't. They'd be meaningless as separate logical operations in exact math, but
they matter a lot for floating point.

### E7: Floating Point (Logical, Intent)

IEEE 754 requires addition, subtraction, multiplication, division, square root,
fused multiply-add, remainder, rounding to an integral value, conversions, and
comparisons, all correctly rounded. It also defines:

- Five rounding directions (to nearest with ties to even, to nearest with ties
  away from zero, toward positive infinity, toward negative infinity, toward
  zero).
- Special values: positive and negative infinity, NaN ("not a number"), and
  positive and negative zero.
- Five exceptions: invalid, divide by zero, overflow, underflow, and inexact.
- Subnormal numbers (tiny values with reduced precision), which some hardware
  handles slowly or flushes to zero (MLIR has `flush_denormals`).
- Two kinds of minimum and maximum, because of NaN: one that propagates NaN and
  one that ignores it (MLIR's `minimumf` vs `minnumf`, IEEE 754-2019's `minimum`
  vs `minimumNumber`).

Fused multiply-add is _logically different_ from a multiply followed by an add
in floating point, because it rounds once instead of twice. Some code depends on
that (exact error terms in compensated arithmetic), and some code depends on not
fusing (reproducibility). LLVM has both `fma` (must fuse) and `fmuladd` (may
fuse or not, the backend picks).

Low-precision formats are now important for machine learning: 16-bit `half` and
`bfloat16`, 8-bit formats, and block-scaled formats where a group of values
shares an exponent (MLIR's `scaling_extf`). Some hardware also has stochastic
rounding.

### E8: Decimal and Fixed-Point Arithmetic (Logical, Encoding)

Money needs decimal arithmetic with explicit rounding rules (IEEE 754 decimal
formats, C23's `_Decimal64`, Ada's decimal fixed-point types). Embedded systems
without floating-point hardware need binary fixed point (Ada's fixed-point
types, LLVM's `smul.fix`, the Embedded C report's `_Fract` and `_Accum`).

Fixed-point and decimal values are exact rationals with a fixed denominator, so
their arithmetic is exact rational arithmetic followed by a rounding rule.

### E9: Conversions (Logical, Encoding)

- Between number kinds: natural to integer, integer to rational, integer to
  floating point (which may round), floating point to integer (which may round,
  and may not fit). WebAssembly has both trapping and saturating versions of
  float-to-integer conversion, because both are needed.
- Between widths, which in Define are encoding conversions, not logical ones.
- Rounding a real to an integer, with an explicit rule (floor, ceiling,
  truncate, round half to even, round half away from zero).
- Between numbers and their text representations (parsing and formatting), which
  [DLP 52 (Literals)](../00052-literals.md) handles for literals but which
  programs also need at runtime.

### E10: Bulk Operations (Logical, Intent)

Sums, products, minimums, maximums, and dot products over many values, and the
same operation applied to many values at once (SIMD, where one instruction
operates on a whole vector of values). LLVM has `vector.reduce.add` and friends.

For exact arithmetic, a sum over many values has one answer no matter the order.
For floating point, the order changes the result, so the programmer has to say
whether reordering is allowed (see O3).

### E11: Bit Operations (Encoding)

Shifts, rotates, population count, leading and trailing zero counts, bit
reversal, and byte swapping. Every system has these, usually on integers.

In Define, binary values are only bits, never numbers, so these belong to binary
values. Shifting a number left by 3 is logically multiplying by 8, and the
compiler can choose a shift instruction for it. Code that really means "these
bits" uses binary values and explicit conversions.

### E12: Miscellaneous Integer Operations (Logical)

Absolute difference (`abs_diff`, which can't overflow the way `abs(a - b)` can),
midpoint (`midpoint`, which famously overflows when written `(a + b) / 2`), sign
(`signum`), and copying a sign (`copysign`). Several of these exist only because
the obvious composition overflows a fixed-width encoding. With exact logical
operations, they're compositions, and the compiler picks an implementation that
doesn't overflow.

### E13: Arbitrary Precision (Encoding)

Python integers, `BigInteger` in Java, and GMP in C and Lean. Needed for
cryptography, exact rational arithmetic, and any value without a known bound. In
Define, this is an encoding for values with no maximum.

## Optimization Requirements

These are things the backend needs to know (or be allowed to do) in order to
generate the best code.

### O1: Ranges (Logical)

The exact range of every value. That's how the backend picks the narrowest
encoding, removes overflow checks, and emits facts like LLVM's `!range`
metadata. This is what range constraints provide.

### O2: Algebraic Properties (Logical)

Associativity, commutativity, distributivity, identity elements (x + 0 = x), and
absorbing elements (x * 0 = 0). These are what let the backend reorder,
vectorize, combine, and simplify operations, and replace expensive operations
with cheap ones (x * 8 becomes a shift, x / 4 becomes a shift when x is known to
be non-negative).

Exact arithmetic has all of these. Wrapping arithmetic has most of them.
Floating point and saturating arithmetic don't have associativity, which is why
O3 exists.

The backend can only use these if it can see the logical operations. An
operation whose meaning is opaque can't be reordered or combined with anything.

### O3: Permission to Change Rounding (Intent)

LLVM's fast-math flags are the most complete list of freedoms a programmer can
grant for floating point:

- `reassoc`: reorder operations as though they were associative.
- `contract`: fuse operations, like a multiply and an add into a fused
  multiply-add.
- `arcp`: replace division with multiplication by a reciprocal.
- `afn`: use approximate versions of functions like `sin` and `exp`.
- `nnan`, `ninf`: assume there are no NaNs or infinities.
- `nsz`: ignore the sign of zero.

These aren't part of the mathematical meaning. They're the programmer saying "I
accept results that are different from the strict IEEE 754 answer, within these
limits." Without them, a floating-point sum over an array can't be vectorized.

A related intent is an error bound: "this result must be within N ulps (units in
the last place) of the exact answer." That lets the backend choose fast
approximate instructions (like a reciprocal square root estimate) when they're
accurate enough.

### O4: Facts About Operands (Logical, derived from constraints)

- No overflow (LLVM `nsw`/`nuw`). In Define, this is derived from ranges.
- Exact division, no remainder (LLVM `exact`).
- Divisor is never zero, or never -1 (removes the special cases in division).
- Divisor is a constant, or a power of two (division by a constant becomes a
  multiply and a shift).
- Value is non-negative (LLVM `zext nneg`), which allows unsigned instructions.
- Two values have no bits in common (LLVM `or disjoint`), which makes an or into
  an add.
- Two compared values have the same sign (LLVM `icmp samesign`).

Most of these fall out of ranges. Some, like "has no remainder" or "is a power
of two," need constraints that ranges can't express.

### O5: Fusion and Instruction Selection (Encoding)

The backend needs to be able to combine several logical operations into one
hardware instruction (fused multiply-add, multiply-high, add-with-carry,
combined quotient and remainder, `sincos`) and split one logical operation into
several instructions (wide arithmetic on narrow hardware). This only works if
the backend sees the logical operations themselves, not only opaque calls.

For exact arithmetic, fusion never changes the meaning. For floating point, it
does, so it needs `contract` permission (O3).

### O6: Purity and Aliasing (Logical)

Logical operations have no side effects and no hidden state, and their operands
can't alias each other. Define already guarantees both.

The one exception is floating-point environment state: the current rounding mode
and exception flags are hidden global state in C and in hardware. LLVM needs
special "constrained" intrinsics to deal with it. Making the rounding direction
part of each operation's meaning (instead of global state) avoids that problem
entirely.

### O7: Determinism (Intent)

Whether results must be identical on every platform. WebAssembly guarantees this
for almost everything (except the bits inside a NaN), and has a separate
"relaxed SIMD" extension for operations that may differ between platforms in
exchange for speed. Java's `strictfp` (now the default) did the same thing for
floating point.

Exact arithmetic is deterministic by definition. Floating point is deterministic
only if fusion, reassociation, approximation, and the order of reductions are
all fixed.

### O8: Undefined and Poison Results (Logical)

LLVM represents "this operation's result is meaningless" as a _poison_ value,
which lets it optimize on the assumption that the case never happens (like
signed overflow in C). Define shouldn't need this, because everything that would
produce poison (overflow, division by zero, shifting by too much) is either
proven impossible or has an explicit meaning. But it's worth noticing that a
large part of LLVM's optimization power comes from being allowed to assume these
cases don't happen, and Define gets the same power from proof instead of from
assumption.

## Proof Requirements

These are drawn mostly from verification languages, which have spent decades on
what people need to prove about numeric code.

### How Verification Languages Handle Numbers

- **Dafny** has unbounded `int` and `nat` (a subset of `int`), exact `real`, and
  bit-vector types `bv8` through `bvN`. Its integer division is Euclidean. It
  checks everything with the Z3 SMT solver. Nonlinear arithmetic is the biggest
  source of slow or flaky proofs in Dafny, to the point that Dafny has an option
  to turn off the solver's nonlinear reasoning and make you prove those facts by
  hand.
- **TLA+** is a specification language, not a programming language: you describe
  a system (usually concurrent or distributed) as a state machine and check
  properties of it. Its numbers are unbounded mathematical naturals, integers,
  and reals. Its model checker (TLC) checks properties by exploring every
  reachable state, so numbers in a TLA+ model are kept small and bounded in
  practice. What people prove in TLA+ is mostly invariants ("the balance is
  never negative," "no two nodes think they're the leader") and that one
  specification correctly implements another (refinement).
- **Rocq** and **Lean** are proof assistants. Natural numbers are defined
  inductively (zero and successor), and arithmetic by recursion, but both have
  special efficient implementations underneath: binary integers and
  GMP-accelerated naturals, and primitive 63- or 64-bit integers and floats for
  computation. Both have automatic decision procedures for _linear_ integer
  arithmetic (Rocq's `lia`, Lean's `omega`). Linear integer arithmetic with
  constants ("Presburger arithmetic") is decidable. Nonlinear arithmetic is not,
  and their nonlinear tactics (Rocq's `nia`) are incomplete heuristics.
- **SPARK** proves that Ada programs never overflow, divide by zero, or index
  out of bounds, using mathematical integers to reason about fixed-width ones.
  It distinguishes clearly between "the mathematical value" and "the machine
  value," which is the same split Define makes between logical operations and
  encodings.

### P1: Absence of Errors

Proving that no operation ever overflows its encoding, divides by zero, or goes
out of bounds. This is the most common thing people prove, and the one SPARK is
built for. Range constraints cover the range part of this.

### P2: Relations Between Values

Proving things like "x < y," "i < length," "start ≤ end," or "the sum of the
parts equals the total." These relate two or more values to each other, which
range constraints on single values can't express. Almost every real invariant is
relational.

This is also exactly where decidability gets hard. Linear relations between
values (x + 2y ≤ z) are still decidable (Presburger arithmetic, decided by tools
like `lia` and `omega`), though they cost more than intervals. Relations that
multiply values together are undecidable in general.

### P3: Invariants Over Time

Proving that something stays true across every change to a value ("the balance
is never negative," "this counter only goes up"). TLA+ is centered on this. In
Define, this is roughly a constraint that's checked at every Value Setting
Statement and every operation that writes to a position, which is how range
constraints are checked. Monotonicity ("only goes up") is a relation between the
old value and the new value, so it's a P2 problem.

### P4: Equivalence

Proving that two computations always give the same result: an optimized version
and a simple version, or a refactored version and the original. Proof assistants
spend a lot of effort here. For a compiler, this is also what makes an
optimization correct.

### P5: Termination and Bounds on Repetition

Proving that a loop or recursion finishes, usually by showing that some number
decreases every time and can't go below zero. Dafny calls this a `decreases`
clause. This becomes relevant when Define has repetition.

### P6: Specification-Only Operations

Operations that are only used in proofs and never executed, like "the sum of
this whole collection," exponentiation over unbounded values, or "for every
element." Dafny calls these ghost code. They let you state a property in its
simplest mathematical form, even if computing it would be expensive.

### P7: Floating-Point Error Bounds

Proving that a floating-point result is within some distance of the exact
result. This is a specialized area (tools like Gappa and FPTaylor), and it's
much harder than proving integer properties. It's what would let a compiler
check an error bound from O3.

## What This Means for Define

### Logical Operations Are Exact, and Everything Else Is a Different Operation

Almost every requirement fits into a split between exact logical operations and
everything that isn't exact:

- The exact operations (E1, E2, E3, E5, E12, and exact rationals) all extend
  each other, from naturals up through rationals, so `standard:/number/add`
  means one thing.
- Wrapping, saturating, floating-point, decimal, and fixed-point operations are
  _different_ logical operations, or exact operations followed by a rounding or
  clamping rule.
- Widening, carrying, borrowing, arbitrary precision, and bit-level tricks are
  how encodings implement exact operations, so they belong to Encoding
  Operations.

### The Backend Must See Logical Meaning

O2 and O5 both depend on the backend seeing the actual logical operations,
across value operation boundaries. That suggests a requirement like: **an
Encoding Operation boundary must never hide logical meaning from the backend.**
If that holds, then it doesn't matter for optimization whether a programmer
composes value operations out of other value operations, because the backend
sees through all of them. The question of whether logical operations go inside
`execute the encoding operation` or directly in the Operation Statements Block
then becomes a question about how Encoding Operations declare which logical
operations they implement, not about optimization.

### Programmer Intent Needs Its Own Place

Fast-math permissions, error bounds, and determinism (O3, O7) aren't part of any
operation's mathematical meaning, but they decide which implementations are
allowed. They need a place to live that isn't a logical operation. They may be
properties of a logical operation's execution, of a value operation, or of an
encoding. This only matters once Define has floating point.

### Relational Constraints Are the Next Big Step

Range constraints are about one value at a time, which keeps checking linear and
decidable. P2 shows that most real invariants relate several values. The
decidable next step is linear relations between values, which is a well-studied
problem (Presburger arithmetic, and abstract domains like octagons and polyhedra
that track linear relations between pairs or groups of values; see
[Prior Art on Inferring Relationships Between Values](#prior-art-on-inferring-relationships-between-values)).
Weaker relations can still go a long way: Pentagons, which adds only facts of
the form `x < y` to ranges, proved 83% of the array accesses in .NET's core
library safe.

### Division Needs Constraints Ranges Can't Express

E3 and O4 both need "the divisor is never zero." A range can express that only
if the divisor is always positive or always negative. Excluding a single value
from the middle of a range needs constraints that are a list of ranges.

### Open Questions

- Where do the `reassoc` permission (O3) and determinism (O7) live? (The other
  floating-point permissions are covered in Floating-Point Permissions, below.)

## The Smallest Set of Logical Operations

This section works out the smallest set of logical operations that covers E1
through E12 without the backend losing information (O2, O5). It takes range
constraints with one interval per value as given. With that, the answer is 17
logical operations (24 names, if the rounding direction is part of the name).
Everything else in E1 through E12 is a composition that loses nothing.

### The Test

An operation needs to be its own logical operation only if one of these is true:

1. **It can't be composed from the others at all.** Integer square roots and
   logarithms are like this.
2. **Every composition uses an operand twice.** Range constraints track each
   view's range separately, so they can't tell that two uses are the same value.
   This is called the "dependency problem" of interval arithmetic. For an x from
   -3 to 5, `x * x` comes out as -15 to 25 instead of 0 to 25, so the compiler
   can't prove that a square is never negative. And `abs(x)` written as
   `max(x, -x)` comes out as -3 to 5 instead of 0 to 5. The other side of this
   is a known result in interval arithmetic (from Ramon Moore, who founded the
   field): when each operand appears only once, the computed range is exact.
   Those compositions cost nothing. (See The Smallest Set for Precision, below,
   for how the compiler can still know that two values are related.)
3. **Composing it changes its meaning.** This only happens with rounding: one
   rounding gives a different answer than two.

The second test is also the test for O5. LLVM used to recognize abs, min, max,
saturation, and rotates from patterns built on `select` (an instruction that
picks one of two values based on a condition). Those patterns kept breaking when
other optimizations rewrote the code, so LLVM added built-in operations for them
(`llvm.abs`, `llvm.smin`, `llvm.sadd.sat`, `llvm.fshl`). Those are exactly the
cases where the pattern uses an operand twice. Patterns that use each operand
once, like "multiply, then divide by 2⁶⁴" (multiply-high), stay easy to
recognize.

The test also argues against extra logical operations. When there are two ways
to write the same thing, the backend has to treat both forms as one, and value
qualities could declare support that makes no sense, like supporting the minimum
but not the maximum.

### The Set

These apply to any value quality:

- **`identity`:** A conversion between value qualities (E9) needs a meaning that
  says "the same value." Adding 0 only works for numbers. (Copying a value
  without changing its value quality turns out to be Define's existing Value
  Setting Statement, `set the value of`, so that part isn't a logical operation.
  Conversions between value qualities will still need something like `identity`,
  but they're their own value operations, which don't exist yet.)

- **`choose`** (a condition, `a`, and `b`): This is the only way to have a
  result that depends on a condition. It also composes every truth-value
  operation with literals: not is `choose(a, false, true)`, and is
  `choose(a, b, false)`, and or is `choose(a, true, b)`. LLVM represents `&&`
  the same way. The condition is just a truth value. Something else has to
  produce it: a value that is already a truth value, or a comparison. That's why
  the set still needs comparisons. The equalities and `less_than` are the only
  logical operations in the set that produce truth values from other values, and
  every other comparison is composed from them.

- **`equality`:** Some values have equality without having an order. Composing
  it from other logical operations uses both operands twice. There's one
  equality for each kind of value, because what it means to be the same depends
  on what the values are. For now, that's numbers and truth values
  (`standard:/number/equality` and `standard:/boolean/equality`). Comparing two
  different kinds of values needs an explicit conversion first.

These are for numbers:

- **`add`, `negate`, and `multiply`:** These are the basic operations of the
  integers. Subtraction is `add(a, negate(b))`. Having only `subtract` would be
  one logical operation fewer, but every addition would then be a double
  negation. `add` is the better standard form, because neither the order nor the
  grouping of its operands matters.
- **`less_than`:** The other comparisons swap the operands, apply a not, or
  both.
- **`minimum`:** The maximum is `negate(minimum(negate(a), negate(b)))`, which
  keeps the exact range. Composing the minimum from `choose` loses its upper
  bound.
- **`absolute_value`:** Every composition uses its operand twice.
- **`power`** (with a natural exponent): `x*x*x` for an x from -3 to 5 comes out
  as -75 to 125 instead of -27 to 125. It also lets the backend turn "multiply
  by `power(2, k)`" into a shift.
- **`divide`:** Exact division. This is for rationals (E6), and for exact
  division where the result goes into an integer view (E3).
- **`quotient/<direction>`:** a / b, rounded to an integer. The directions are
  down, toward zero, nearest with ties to even, and nearest with ties away from
  zero. Rounding up is `negate(quotient_down(negate(a), b))`, so it doesn't need
  its own direction. With b = 1, this is rounding a number to an integer (E9).
  With b as a literal step size (like 1/100 or 2⁻¹⁶), it's fixed-point or
  decimal arithmetic (E8).
- **`remainder/<direction>`:** a − b * `quotient`, for the directions down and
  toward zero. Writing it as that composition uses a and b twice, which loses
  the range 0 to b − 1, and that range is what proves an index is in bounds.
- **`nth_root` and `logarithm`:** These can't be composed from anything else
  (E5). Their results are irrational, so they can only be the input to a
  rounding. The integer square root is `quotient_down(nth_root(x, 2), 1)`.
- **`round_to_precision/<direction>`:** Floating point (E7), binary or decimal:
  round to some number of significant digits in some base, with a minimum
  exponent. It has the same four directions. Composing it from `quotient` uses x
  three times.

That's 17 logical operations, counting the two equalities. With four directions
each for `quotient` and `round_to_precision` and two for `remainder` in the
names, it's 24 names.

### How E1 Through E12 Compose

- **E1:** Subtraction is `add` and `negate`.
- **E2:** The other comparisons, the maximum, "not equal," and clamping
  (`minimum(maximum(x, low), high)`) are all compositions. A three-way
  comparison is two `choose`s, and its range is -1 to 1 either way, so it loses
  nothing. **So Define doesn't need a three-way comparison.**
- **E3:** Truncated and floored division are directions of `quotient`. Ceiling
  division is `negate(quotient_down(negate(a), b))`. Rounding up to a multiple
  is `m * quotient_up(x, m)`. Exact division is `divide` with an integer result
  view.
  - Euclidean division costs nothing. With one interval per value, the compiler
    can only prove that b ≠ 0 if b's whole range is on one side of zero. So the
    sign of every divisor is always known at compile time, and Euclidean
    division is a `choose` on b's sign that the compiler always evaluates at
    compile time.
  - **So the division rounding rules that need to be logical operations are down
    and toward zero.** If constraints later become lists of ranges, b ≠ 0 no
    longer says what b's sign is, and Define would need `remainder/euclidean`.
- **E4:** Wrapping is `remainder_down(sum, 2ⁿ)`. (Signed wrapping adds 2ⁿ⁻¹
  before and subtracts it after.) The backend handles it with a standard
  analysis of which bits of a result are actually used (LLVM calls this
  "demanded bits"). **So wrapping doesn't need its own family of logical
  operations.** Saturating arithmetic is clamping. Overflowing arithmetic is the
  wrapped result plus a comparison. Multiply-high is `quotient_down(a * b, 2ⁿ)`.
  Checked arithmetic is a runtime assertion, not a logical operation. Widening
  and carrying belong to encodings.
- **E5:** `power`, `nth_root`, and `logarithm`, followed by a rounding.
- **E6:** Rationals use `add`, `multiply`, `negate`, and `divide`. Functions
  like exp and sin are discussed under Limits, below.
- **E7:** IEEE 754 defines each operation as the exact result, rounded once. So
  a floating-point addition is `round_to_precision(add(a, b))`. A fused
  multiply-add is a * b + c with one rounding; the unfused version has two.
  `expm1`, `log1p`, and `hypot` become plain compositions, because everything
  before the final rounding is exact. The two kinds of minimum and maximum go
  away if NaN isn't allowed.
- **E8:** `quotient` with a literal step size, or `round_to_precision` in
  base 10.
- **E9:** `identity`, `quotient(x, 1)`, and `round_to_precision`. A saturating
  floating-point-to-integer conversion is clamping.
- **E10:** Exact sums are compositions that the backend may reorder (O2).
  Operations over collections wait until Define has collections.
- **E11:** These stay on binary values. Shifting a number is `multiply` or
  `quotient_down` by `power(2, k)`.
- **E12:** The absolute difference is `absolute_value(a − b)`, which uses each
  operand once. The midpoint is `quotient(a + b, 2)` in whichever direction you
  want. The sign is two `choose`s. Copying a sign is a composition.

### Proofs

When the other operand is a literal, almost every logical operation in the set
stays within Presburger arithmetic, which is decidable (P2). The exceptions are
multiplying two views, `power`, `nth_root`, `logarithm`, and `divide`,
`quotient`, or `remainder` by a view. So the compiler can tell from each
statement whether it leaves the decidable part.

### Where Logical Operations Go

This doesn't decide where logical operation executions go, but it adds a
requirement and removes a worry:

- **Requirement:** There must be a way to have exact intermediate results that
  never have to be stored. Rounding a * b + c once, multiply-high, and chains of
  wrapping arithmetic all need one.
- **The fused multiply-add worry goes away.** A value passed to a value
  operation must be a valid value of that view's value quality, so if that's a
  64-bit float, the value must have been rounded explicitly. So splitting a
  fused multiply-add around a value operation is visibly a different
  computation, not an ambiguity. Where logical operations go can be decided on
  other grounds, like readability and composition.

### Limits

- **The set depends on one interval per value.** Constraints that track
  relations between values would let `absolute_value`, `minimum`, and `power` be
  compositions, too. Range constraints use intervals on purpose, so checking
  stays predictable.
- **`choose` can't keep a division by zero from happening.** It computes both of
  its operands. If the compiler narrows ranges by a `choose`'s condition, a
  program can replace a divisor that's 0 before dividing, as in
  `choose(b = 0, 1, b)`. But for a b that can be negative, the narrowed range is
  from its minimum to -1 and from 1 to its maximum, which one interval can't
  express.
- **This model of floating point only covers values that are numbers.** NaN, the
  infinities, and negative zero aren't numbers. Either floating-point value
  qualities exclude them, and ranges prove that nothing overflows (which is
  Define getting its guarantees from proof instead of assumption), or a separate
  IEEE 754 family of logical operations comes later. Excluding them seems like
  the place to start.
- **Functions like exp and sin** are each an exact real operation that has to be
  rounded.
  - Exact rational operations followed by a rounding can always be computed
    exactly.
  - One real function followed by a rounding can be computed exactly, too.
    Libraries that do this correctly exist; CORE-MATH, a project that provides
    correctly rounded math functions, is one.
  - Several real functions before one rounding can't be computed exactly in
    general. Richardson's theorem says that deciding whether such an expression
    is exactly zero is undecidable. Those chains need the programmer to grant an
    error bound.

### Floating-Point Permissions

That last point is also where most of O3's permissions end up:

- `contract` is whether an intermediate rounding exists.
- `afn` and `arcp` are a rounding with an error bound.
- `nnan` and `ninf` become facts the compiler proves.
- `reassoc` doesn't belong to any single rounding. It's about reductions (E10),
  and it's still unsolved.

### Sources for This Section

These facts are from memory, not checked against sources:

- Moore's result that intervals are exact when each operand appears once.
- LLVM's history with built-in operations for abs, min, max, saturation, and
  rotates, and its use of `select` for `&&`.
- IEEE 754's definition of each operation as an exact result rounded once.
- CORE-MATH.
- Richardson's theorem.

The interval numbers are worked out by hand.

## The Smallest Set for Precision

The previous section asked which operations have to be logical operations so
that composing _those operations_ never loses information. This section asks the
other half of the question: what about programs whose own computation uses a
value more than once? How precise can the compiler's ranges be for those, and
what's the smallest set of logical operations that gets there?

### Two Ways a Range Gets Too Wide

1. **An operation's composition reuses an operand.** Every way of writing an
   absolute value from the other operations uses its operand twice. The previous
   section handles this by making those operations logical operations.
2. **The program reuses a value.** `x − x`, `x * x`, and `a + t * (b − a)` all
   use a value more than once because of what they compute, not because of how
   some operation is built.

### What Precision Means

A range is _precise_ when it's exactly the set of values the computation can
produce, given the ranges of its inputs. When every value appears only once in
an expression, and every operation in it has an exact interval rule, the
computed range is precise (see the
[dependency problem](https://en.wikipedia.org/wiki/Interval_arithmetic#Dependency_problem)).
When a value appears more than once, it usually isn't.

In general, finding the exact range of even a quadratic polynomial, given a
range for each of its inputs, is NP-hard in the number of inputs. That's a real
limit for analyses that follow values through whole functions or programs,
because the number of related variables grows with the code. It isn't the limit
that matters for checking one action statement at a time, using only the ranges
of that action statement's inputs. When an action statement executes a value
operation, that check covers the whole execution: the value operation's
Operation Statements Block and every operation it executes in turn. The only
independent inputs in that check are the input views of the value operation the
action statement executes (usually two or three). A cost that doubles with every
extra input is still small when there are only three inputs.

### Why Exact Ranges Are Still Expensive

Even with only a few inputs, finding an exact range is expensive, for three
reasons.

**The result's formula can get large.** To find an exact range, the compiler has
to know each output view's value as a formula in terms of the value operation's
input views. Each `multiply` or `power` raises the highest exponent in the
formula: squaring `x` gives `x²`, and squaring that gives `x⁴`. A formula with
higher exponents has more places where it can turn around between increasing and
decreasing, so there are more candidates for its smallest and largest values.
Each `minimum`, `absolute_value`, or `choose` gives a formula with two cases,
one for each side of the comparison, and the cases multiply: three of them in a
row give eight cases. So the formula grows with the number of logical operations
the value operation executes, even when it has only two input views.

**Finding a formula's smallest and largest values takes calculus.** When the
value operation has only one input view, the formula is a polynomial in that one
value, like `x⁴ − 3x²`. Its smallest and largest values are either at the ends
of that value's range or at a turning point, where the formula stops going up
and starts going down, or the reverse. The turning points are where the
derivative is zero, and the compiler can find them exactly. Checking only the
ends isn't enough: for `x²` with `x` from −2 to 3, the ends give 4 and 9, but
the smallest value is 0, at the turning point `x = 0`. With more input views,
there are more places to check. For each input, the smallest or largest value of
the formula might be where that input is at its lowest value, at its highest
value, or somewhere in between. For every combination of those choices (three
choices for each input, so 27 combinations for three inputs), the compiler has
to solve a system of polynomial equations for the inputs that are in between.
That's possible, but it costs much more than a fixed rule for each logical
operation.

**Integers make calculus inexact.** Calculus finds the smallest and largest
values over all real numbers in the input ranges, and a turning point can be
between two integers. Then the range calculus finds is sound, but it can be
wider than the true range in a way that loses a fact that matters (see
[Facts That Matter Most for Fast Code](#facts-that-matter-most-for-fast-code)).
For example, `(2x − 1)²` for an integer x from 0 to 3 has three candidates for
its smallest and largest values: the two ends of x's range and the turning
point. At the ends, x = 0 gives (−1)² = 1, and x = 3 gives 5² = 25. The
derivative is 4(2x − 1), which is zero at x = 1/2, and there the value is
0² = 0. The smallest candidate is 0 and the largest is 25, so calculus gives 0
to 25. But no integer x makes it 0: the true range is 1 to 25, so it's never 0,
and the compiler could divide by it without a check. With one input view, the
compiler can fix this by also checking the integers on each side of each turning
point. With more input views, there's no such shortcut. Finding the smallest or
largest value of a formula when its inputs must be integers in given ranges is
called integer programming, and when the formula is a polynomial, it's nonlinear
integer programming. Because every input has a range, there are only finitely
many inputs to try, so it's always solvable. But trying every combination of
inputs takes time proportional to the product of the sizes of their ranges: two
inputs from 0 to a million are a trillion combinations. The problem is NP-hard,
so solvers that do better than trying every combination still take exponential
time in the worst case.

So the compiler could find exact ranges for nonlinear formulas, one statement at
a time, but the cost depends on the formula's degree, its number of cases, and
its number of inputs. The question this section asks is which common patterns
can be made precise with fixed rules, and what each one costs.

### How the Compiler Knows Two Values Are Related

Interval arithmetic computes each logical operation's range from its operands'
ranges alone, as though the operands were unrelated. When the operands are
related, that assumption makes the range too wide. Any relationship the compiler
knows between two operands can make the range narrower. For example:

- **They depend on the same value.** If y is the `negate` of x, then the `add`
  of x and y is exactly 0.
- **One is always at least the other.** If y is never less than x, then the
  `add` of y and the `negate` of x is never negative, whatever the ranges of x
  and y are.
- **They add up to a constant.** If x and y always add up to 10, and x is from 0
  to 10, then x times y is at most 25, not 100.

The compiler can infer all three kinds, and the programmer can state them:

- **The compiler can infer them** from how the program computes its values. If y
  is computed as the `add` of x and 1, then y is always more than x. If y is
  computed as 10 plus the `negate` of x, then x and y always add up to 10. If m
  is the `minimum` of x and y, then m is never more than x or y. This works
  across action statements and value operations too, at any depth. Define's
  action graph has no cycles, so the compiler can follow every value back
  through the action statements that computed it. If every caller of a value
  operation passes a y that's at least x, the compiler can learn that by looking
  at the callers, even though nothing in the value operation shows it.
- **The programmer has to state them** only for values the program didn't
  compute, like two values read from outside the program, whose relationship
  nothing in the program shows. The programmer can also choose to state a
  relationship as part of a contract, like a value operation requiring that y is
  at least x. Then the compiler can check the value operation without looking at
  its callers, and check each caller without looking inside the value operation.
  Ranges can't express these facts (see
  [Relational Constraints Are the Next Big Step](#relational-constraints-are-the-next-big-step)).

Inferring a relationship and using it are separate problems. If y is computed as
10 plus the `negate` of x, the compiler can infer that x and y add up to 10, but
x times y is then `x * (10 − x)`, which uses x twice through a nonlinear step.
Its exact range needs either the polynomial methods above, a rewrite that uses x
once, like `25 − (x − 5)²`, or tracking nonlinear relationships
([Taylor models](#nonlinear-relationships)).

### How Define Could Infer Relationships

This section describes one way Define's compiler could infer relationships and
use them.
[Prior Art on Inferring Relationships Between Values](#prior-art-on-inferring-relationships-between-values)
surveys others.

In Define, two views of one logical operation can never look at the same view,
because views may not alias. So `multiply` can never receive x as both of its
operands. Two operands can still depend on the same value, though. For example,
a value operation could put the `negate` of x into a local view, and then `add`
x and that local view.

There are two ways the compiler could handle related operands:

- **Logical operations that take the value once.** A square is `power` with an
  exponent of 2, which has one operand, so there's no relationship to track.
- **Tracking linear relationships.** The compiler could write each value as a
  constant plus a multiple of each of some independent values. Each input view
  starts as its own independent value. `add`, `negate`, and multiplying by a
  constant produce another value of that form, exactly. Any other logical
  operation, like multiplying two values or `minimum`, produces a new
  independent value with its own range. This is a simplified form of
  [affine arithmetic](https://en.wikipedia.org/wiki/Affine_arithmetic).

For example, with an x from 0 to 10:

| Step              | Plain intervals | Tracking linear relationships |
| ----------------- | --------------- | ----------------------------- |
| y = `negate` of x | −10 to 0        | y = −x                        |
| z = `add` x and y | −10 to 10       | z = x + (−x) = 0              |
| w = `add` z and 1 | −9 to 11        | w = 1                         |

Tracking linear relationships doesn't help when a value goes through a nonlinear
step more than once. In `x * (x + 1)`, the compiler would know `x + 1` is
related to x, but `multiply` only has a rule for unrelated operands. For an x
from −2 to 3, `x + 1` is −1 to 4, and the rule gives −8 to 12, but the true
range is −1/4 to 12.

These relationships can be tracked through one action statement's execution of a
value operation, including the value operations and logical operations it
executes in turn. Because the action graph has no cycles, the same tracking can
also continue from one action statement to the next, through the whole action
graph. Then the cost grows with the number of related values, which can grow
with the size of the program instead of with one execution.

### Common Patterns

- **Squares and higher powers** (distances, `hypot`, E5, E7): `power` is exact.
  An odd power of a bigger number is always bigger, so its smallest and largest
  results come from the ends of the operand's range. An even power is never
  negative. `x³` as `multiply` of a square and x would come out as -75 to 125
  for an x from -3 to 5, instead of -27 to 125.
- **Doubling and scaling:** multiplying by a number is linear, so it's exact.
- **Quadratics:** `x² − 4x` uses x in a square and again on its own. For an x
  from 0 to 4, that comes out as -16 to 16, but the real range is -4 to 0.
  Completing the square gives `(x − 2)² − 4`, which only uses x once, and that's
  exact: x − 2 is -2 to 2, its square is 0 to 4, and minus 4 is -4 to 0. Every
  quadratic in one variable can be written this way, including products of
  related values like `x * (x + 1)`, which is `(x + 1/2)² − 1/4`.
- **Polynomials of degree 3 or more** with several terms: in general, there's no
  way to write them that uses x once. Their exact range depends on where the
  polynomial turns around, which no fixed set of logical operations captures.
- **Self-cancellation and offsets** (`x − x`, `(x + 1) − x`, `a + b − a`):
  tracking linear relationships would make these exact.
- **Clamping, absolute differences, midpoints, saturation, and wrapping** (E2,
  E4, E12): these all have forms that use each value once, so they're exact with
  the minimal set.
- **Fractional parts and remainders:** `x − floor(x)` uses x twice, but it's
  `remainder_down(x, 1)`, which is a logical operation with an exact rule.
- **Deviations from a mean:** a mean is linear, so each `x − mean` is exact. A
  variance isn't: it squares each deviation, and the squares become independent
  values even though they're related.
- **Linear interpolation:** finding a value between a and b. t says how far
  along the way from a to b the value is, as a fraction from 0 to 1, and the
  value is `a + t * (b − a)`. When t is 0 it's a, when t is 1 it's b, and when t
  is 1/2 it's halfway between them. It's common in graphics and animation, like
  for moving an object smoothly from one position to another, or blending two
  colors. Every way of writing it with addition, subtraction, multiplication,
  and division puts a or t through a multiplication of two values more than
  once. For a and b from 0 to 10, `a + t * (b − a)` comes out as -10 to 20, and
  `(1 − t) * a + t * b` comes out as 0 to 20, but the true range is 0 to 10. A
  `linear_interpolation` logical operation is exact. (It's multilinear, so it
  passes the necessary condition for a single-use form from
  [Lorkowski, Kosheleva, and Kreinovich](https://www.cs.utep.edu/vladik/2014/tr14-77a.pdf),
  below. That it has no single-use form is proved in
  [Linear Interpolation Has No Single-Use Form](https://github.com/define-lang/research/blob/main/single_use_expression_proofs/linear-interpolation-has-no-single-use-form.md),
  in Define's research repository. That proof is our own, not a published one,
  and it only covers expressions made of addition, subtraction, multiplication,
  division, and constants.)
- **Proportions** (`x / (x + y)`, like a share of a total): this uses x twice,
  once through a division. For x and y from 1 to 10, the true range is 1/11 to
  10/11, but dividing 1–10 by 2–20 gives 0.05 to 5. But when x is never 0, it's
  the same as `1 / (1 + y / x)`, which uses each value once, so it's exact:
  `y / x` is 0.1 to 10, plus 1 is 1.1 to 11, and the reciprocal is 1/11 to
  10/11.
  ([Lorkowski, Kosheleva, and Kreinovich](https://www.cs.utep.edu/vladik/2014/tr14-77a.pdf)
  use this example.) When y is never 0, `1 − 1 / (1 + x / y)` works the same
  way. The one case left is when x and y can each be 0, but never both at once.
  Ranges can't say that, so neither form works, and a proportion logical
  operation might be needed for it.

### What Makes an Exact Rule Cheap

Every logical operation above whose exact rule is cheap has the same property:
its smallest and largest results always happen at the _corners_: the
combinations of inputs where every input is at its lowest or highest value.
That's true for any function that's linear in each input separately, meaning it
changes at a steady rate as any one input changes while the others stay the same
(like `multiply` and linear interpolation), and for any function where making
one input bigger, while the others stay the same, never makes the result smaller
(or never makes it bigger), like `minimum`, odd powers, and proportions of
non-negative values. Then the exact range is just the smallest and largest of
the results at the corners. `absolute_value` and even powers are the exceptions
that are still cheap: they turn around at exactly one known place, 0.

Polynomials of degree 3 or more don't have this property, which is why no
logical operation helps them.

### The Set

The smallest set of logical operations that gives precise ranges for E1 through
E12 and the common patterns above is:

- For any kind of value: `choose`.
- For truth values: `boolean/equality`.
- For numbers: `number/equality`, `add`, `negate`, `multiply`, `less_than`,
  `minimum`, `absolute_value`, and `power`.
- With division (which also brings rational numbers): `divide`,
  `quotient/<direction>` (down, toward zero, nearest with ties to even, and
  nearest with ties away from zero), `remainder/<direction>` (down and toward
  zero), `nth_root`, `logarithm`, and `linear_interpolation`.
- With floating point: `round_to_precision/<direction>`, with the same four
  directions as `quotient`.

That's 17 logical operations, or 24 names with the rounding directions in the
names.

Compared to the previous section's set:

- `power` is needed for precision as well as for E5, since `multiply` can't take
  the same value twice.
- `linear_interpolation` is added, because it's common, and no composition of
  addition, subtraction, multiplication, and division uses each value once
  ([proof](https://github.com/define-lang/research/blob/main/single_use_expression_proofs/linear-interpolation-has-no-single-use-form.md)).
  It could be precise without its own logical operation if the compiler also
  tracked products of different independent values, like `t * a`, with no
  independent value multiplied by itself. Formulas like that are multilinear, so
  their smallest and largest values are at the corners (see
  [What Makes an Exact Rule Cheap](#what-makes-an-exact-rule-cheap)). The cost
  is evaluating the formula at every corner, which is 2ⁿ corners for n
  independent values in one product, instead of once per term.
- Proportions aren't added, because when either value is never 0, a composition
  that uses each value once is exact. A proportion logical operation might still
  be needed for values that can each be 0, but never both at once.
- There's no `identity`. Copying a value without changing its value quality is
  Define's existing Value Setting Statement (`set the value of`). A conversion
  between value qualities is a separate value operation, which needs a meaning
  like `identity`.
- There's no `subtract`, even for `x − x`. Tracking linear relationships would
  make the `add` of x and the `negate` of x exactly 0 already.

### Sources for This Section

- When each value appears only once in an expression, interval arithmetic gives
  its exact range. Practitioners rewrite expressions into this single-use form
  to get exact ranges
  ([notes from UTEP](https://www.cs.utep.edu/vladik/cs5351.21/SUE.pdf)).
- [Lorkowski, Kosheleva, and Kreinovich](https://www.cs.utep.edu/vladik/2014/tr14-77a.pdf),
  "Every Function Computable by an Arithmetic SUE Expression is a Ratio of Two
  Multi-Linear Functions," prove that a function built from addition,
  subtraction, multiplication, and division can only have a single-use form if
  it's a ratio of two multilinear functions. Not every such ratio has one.
- [Lorkowski, "From Single to Double Use Expressions"](https://www.cs.utep.edu/vladik/2010/tr10-34a.pdf)
  shows that when each value can appear twice, finding the exact range is
  NP-hard.
- The interval arithmetic standard, IEEE 1788-2015, has `sqr` and `pown` as
  functions separate from multiplication, for the same reason as `power` here:
  `mul(x, x)` treats its two operands as independent, so its range is too wide
  ([IEEE 1788 mailing list](https://grouper.ieee.org/groups/1788/email/msg08445.html),
  [standard overview](https://www.reliable-computing.org/archive/preprints/interval-standard-overview.pdf)).
  On the same list, Vincent Lefèvre wrote that the dependency problem is mainly
  a language issue, because only the language can know that two operands come
  from the same source.

These facts are from memory, not checked against sources:

- Finding the exact range of a quadratic polynomial is NP-hard in the number of
  inputs.
- A function that's linear in each input separately, or only increases or only
  decreases in each input, has its smallest and largest values at the corners.

The completing-the-square approach is described in the
[interval arithmetic article](https://en.wikipedia.org/wiki/Interval_arithmetic#Dependency_problem).
The interval numbers are worked out by hand.

## Facts That Matter Most for Fast Code

A range that's a little too wide usually doesn't change the generated code. If
the compiler thinks a value is 1 to 110 when it's really 1 to 100, it still
picks the same encoding and the same instructions. But a few facts change the
code a lot, and a range that's too wide by even a little can lose them. Most of
them are about where a value is relative to 0.

### The Facts

- **The sign is known.** When a value is never negative:
  - The backend can use unsigned instructions, and widen the value by filling
    with zeros instead of copying the sign bit (LLVM's `zext nneg`).
  - Dividing by a power of two is one shift, and the remainder is one bitwise
    and. For signed values, both need extra instructions to round toward zero
    correctly.
  - The rounding directions agree: `quotient/down` and `quotient/toward_zero`
    give the same answer when both operands are non-negative, and so do
    `remainder/down` and `remainder/toward_zero`. The backend can use whichever
    is cheaper.
  - `absolute_value` does nothing, and `minimum` with 0 is always 0.
  - Square roots and logarithms don't need a check for a negative operand.

  Knowing a value is never positive, or always negative, gives the same
  benefits, mirrored.
- **The value is never 0.**
  - Division and remainder don't need a check for division by zero, or a trap
    when it happens.
  - Logarithms and reciprocals don't need a check either.
  - Counting leading or trailing zero bits is one instruction on more hardware
    when the operand can't be 0 (LLVM's `ctlz` and `cttz` take a flag for this).
  - An encoding can use 0 to mean something else, like "no value." Rust's
    `NonZeroU32` works this way, so an optional `NonZeroU32` takes the same
    space as a plain `u32`.
- **A divisor is never -1, or a dividend is never the most negative value.**
  Signed division of the most negative value by -1 overflows, and some hardware
  traps on it (x86's `idiv`). If either fact is known, the backend doesn't need
  the special case. The same goes for `absolute_value` of the most negative
  value.
- **The value fits in fewer bits.** A narrower encoding means more values in
  each vector register, cheaper multiplies, and less memory.
- **One value is less than another.** When an index is known to be less than a
  length, the backend doesn't need a bounds check (bounds-check elimination).
  When a loop counter is known to stay below its limit, the backend can
  vectorize or unroll the loop without checking for overflow. These are
  relationships between values, which ranges can't express (see
  [Prior Art on Inferring Relationships Between Values](#prior-art-on-inferring-relationships-between-values)
  for how compilers infer them).
- **For floating point, the value is never NaN, never infinite, or never
  negative zero** (LLVM's `nnan`, `ninf`, and `nsz`). These let comparisons,
  `minimum`, and simplifications like `x * 0 = 0` and `x + 0 = x` compile to
  single instructions or disappear. In exact arithmetic these values don't
  exist, so these facts come from the encoding and from ranges together.

### Why Precision Matters for These Facts

Every fact above depends on whether a range includes 0, negative values, or one
particular value. So the imprecise ranges from earlier sections cost the most
when they cross 0:

- `x * x` for an x from -2 to 3 comes out as -6 to 9 with `multiply`, which
  includes negative values. With `power`, it's 0 to 9, which doesn't.
- Linear interpolation of a and b from 0 to 10 comes out as -10 to 20 when it's
  composed from `multiply` and `add`, which includes negative values, even
  though every result is really from 0 to 10.
- `x − x` with plain interval arithmetic gives a range around 0 instead of
  exactly 0, so the compiler can't remove the operation.

### What One Range Can't Say

A single range from a lowest to a highest value can say a value is never
negative, but it can't say a value is never 0 if the value can be both negative
and positive. For example, a divisor from -5 to 5 that's never 0 needs two
ranges (-5 to -1 and 1 to 5), or a separate fact that it's not 0. This is common
in real code, where a program checks that a divisor isn't 0 and then divides by
it. The same goes for "never -1" when a range includes values on both sides of
-1, and for "never NaN" in floating point.

### The Same Facts for Verification

The same facts are also what proving the absence of errors (P1) needs most.
Every check the backend removes is a check for an error: division by zero, a
square root or logarithm of a negative number, overflow, or dividing the most
negative value by -1. Proving the fact that removes the check also proves the
error can't happen.

These facts are also among the simplest to verify. Each one is about a single
value, so checking it doesn't need a solver or any knowledge of how values
relate. Signs and being non-zero also go exactly through multiplication and
division, even when ranges don't: if x and y are both positive, x * y is
positive, even when its computed range is too wide.

Verification and fast code differ in a few ways:

- What makes verification simple in general is linearity. Facts and
  relationships that only use addition and multiplication by a number are
  decidable (Presburger arithmetic for integers), and SMT solvers handle them
  quickly. Nonlinear integer arithmetic is undecidable in general. Linearity
  doesn't matter for fast code.
- Verification depends heavily on relationships between values (P2), like
  `i < length`. Fast code needs some of these too (see "One value is less than
  another" above), but ranges and signs can't express them.
- Fitting in fewer bits matters for fast code, but for verification it only
  matters as part of proving there's no overflow.
- Proving a result is correct (P4, and postconditions in general) isn't made
  simpler by any of these facts.

### Sources for This Section

These facts are from memory, not checked against sources:

- LLVM's `zext nneg`, `ctlz`/`cttz` with their flag for a zero operand, and
  fast-math flags `nnan`, `ninf`, and `nsz`.
- Rust's `NonZeroU32` and its optional form taking the same space as `u32`.
- x86's `idiv` trapping when it divides the most negative value by -1.

## Prior Art on Inferring Relationships Between Values

Inferring relationships between a program's values is one of the oldest topics
in static analysis. The methods differ in which relationships they can express,
and the more they can express, the more they cost.

### Equalities

- **Linear equalities.**
  [Karr (1976), "Affine Relationships Among Variables of a Program"](https://doi.org/10.1007/BF00268497)
  infers every equation of the form `a*x + b*y + … = c` that always holds at
  each point in a program. Müller-Olm and Seidl later simplified it.
- **Equal values by random interpretation.**
  [Gulwani and Necula (2004), "Global Value Numbering Using Random Interpretation"](https://people.eecs.berkeley.edu/~necula/Papers/rand_popl04.pdf)
  finds which computations always give the same value by running the program on
  random values, with a probability of a false answer that can be made as small
  as needed.
- **Affine arithmetic and zonotopes.** Affine arithmetic (Comba and Stolfi,
  1993) represents each value as a constant plus a multiple of each of some
  shared independent values, plus extra independent values for the error of
  nonlinear steps. Goubault and Putot built static analyses on it, with sets of
  these forms called zonotopes, in the Fluctuat analyzer for floating-point C
  and Ada code
  ([A Zonotopic Framework for Functional Abstractions](https://arxiv.org/abs/0910.1763)).
  The linear relationships in
  [How Define Could Infer Relationships](#how-define-could-infer-relationships)
  are a simplified form that leaves out the error values.

### Inequalities

From least to most expressive:

- **Less than.**
  [Logozzo and Fähndrich (2008), "Pentagons"](https://www.microsoft.com/en-us/research/wp-content/uploads/2009/01/pentagons.pdf)
  tracks a range for each value plus facts of the form `x < y`. It was built to
  prove array accesses are in bounds in Clousot, Microsoft's analyzer for .NET,
  where it proved 83% of the array accesses in the core .NET library safe.
  [Maalej, Paisante, Ramos, Gonnord, and Pereira (2017), "Pointer Disambiguation via Strict Inequalities"](https://hal.science/hal-01387031)
  infers `x < y` between pointers in LLVM, in time linear in the number of
  values.
- **Differences.** Difference bound matrices hold facts of the form `x − y ≤ c`.
  They come from the verification of timed systems
  ([Dill, 1989](https://www.prismmodelchecker.org/bibitem.php?key=Dil89)).
- **Octagons.**
  [Miné (2006), "The Octagon Abstract Domain"](https://arxiv.org/abs/cs/0703084)
  holds facts of the form `±x ± y ≤ c`. It needs memory proportional to the
  square of the number of values, and time proportional to the cube for each
  operation. It's part of Astrée, which proved the absence of runtime errors in
  Airbus flight control software.
- **Two variables per inequality.**
  [Simon, King, and Howe (2003)](https://openaccess.city.ac.uk/id/eprint/1709)
  allow any linear inequality between two values, like `3x − 2y ≤ 7`.
- **Template polyhedra.**
  [Sankaranarayanan, Sipma, and Manna (2005)](https://home.cs.colorado.edu/~srirams/papers/vmcai05.html)
  allow any linear inequality whose shape was chosen ahead of time, and compute
  them with linear programming.
- **Polyhedra.**
  [Cousot and Halbwachs (1978), "Automatic Discovery of Linear Restraints Among Variables of a Program"](https://cs.nyu.edu/~pmc309/COUSOTpapers/POPL78.shtml)
  allow any set of linear inequalities between any values. It's the most precise
  of these and the most expensive.
  [Singh, Püschel, and Vechev (2017), "Fast Polyhedra Abstract Domain"](https://popl17.sigplan.org/details/POPL-2017-papers/16/Fast-Polyhedra-Abstract-Domain)
  made it 100 to 100,000 times faster in practice by keeping unrelated values in
  separate polyhedra. Their library, ELINA, also has octagons and difference
  bounds.

### In Production Compilers

- **ABCD.**
  [Bodík, Gupta, and Sarkar (2000), "ABCD: Eliminating Array Bounds Checks on Demand"](https://homes.cs.washington.edu/~bodik/ucb/research/pldi00.html)
  infers facts like `i < length` from a graph of inequalities between SSA
  values, cheaply enough for a just-in-time compiler. It removed 45% of the
  bounds checks that ran, on average.
- **LLVM's ConstraintElimination pass.** It collects linear inequalities from
  the conditions that must have been true to reach each point in the program,
  and removes comparisons those inequalities prove. It solves them with
  Fourier–Motzkin elimination
  ([`ConstraintSystem.cpp`](https://llvm.org/doxygen/ConstraintSystem_8cpp_source.html)).
- **LLVM's ScalarEvolution.** It represents values that change in loops as
  chains of recurrences, like "starts at 0 and adds 4 each time," following
  Bachmann, Wang, and Zima.

### Nonlinear Relationships

- **Taylor models.** Berz and Makino represent each value as a polynomial in the
  independent values plus a range for the remainder
  ([overview](https://rec.ce.gatech.edu/rec2004/abstract/Abstract_Berz_Makino.pdf)).
  They're the nonlinear version of affine arithmetic, and they avoid most of the
  dependency problem, at the cost of handling polynomials.
- **Polynomial equalities.** Müller-Olm and Seidl (2004),
  ["Computing Polynomial Program Invariants"](https://cris-portal.uni-muenster.de/portal/en/publication/18184788),
  and Rodríguez-Carbonell and Kapur (2004),
  ["An Abstract Interpretation Approach for Automatic Generation of Polynomial Invariants"](https://cs.unm.edu/~kapur/myabstracts/sas04.html),
  infer polynomial equations between values, up to a chosen degree, using
  Gröbner bases. Finding every polynomial equation that holds is not computable
  in general.

### Loops and Branches

Most of the cost and precision lost in these methods comes from loops and
branches. At a loop, an analysis has to guess a relationship that holds on every
iteration, and widen its guess until it stops changing. Where two branches meet,
it has to find one relationship that covers both, which for polyhedra is the
smallest polyhedron that contains both (the convex hull).

One action statement's execution in Define has neither, and its Operation
Statements Blocks are SSA. So there's no widening, and linear equalities follow
directly from how each value is computed. Inequalities follow directly too: the
`minimum` of x and y is never more than x. The only place where relationships
from two cases have to be combined is `choose`. The action graph has no cycles
either, so inferring relationships across action statements, through the whole
graph, doesn't need widening.
