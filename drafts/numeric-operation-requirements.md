# Numeric Operation Requirements

This is a survey of what a programming language needs from numeric operations,
gathered to check the design of logical operations
([DLP 55](../define/proposals/00055-logical-operations.md)) and range
constraints ([DLP 56](../define/proposals/00056-range-constraints.md)) against.

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
  the interval arithmetic standard (directly relevant to DLP 56).
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
- **Widening:** produce a result in a wider encoding so that it always fits (64
  × 64 → 128, or just the high half of a product, which is common in hashing and
  fixed-point code).
- **Carrying and borrowing:** add-with-carry and subtract-with-borrow, which are
  how arbitrary-precision arithmetic is built from fixed-width pieces.
- **Proven not to happen:** the compiler (or the programmer, unsafely) knows the
  result always fits. LLVM's `nsw`/`nuw` and Rust's `unchecked_` exist for this.

In Define, logical operations are exact, so widening is just "the compiler picks
an encoding big enough for the range." Carrying and borrowing are how an
Encoding Operation implements exact arithmetic on a wide value, so they belong
to encodings. Wrapping and saturating are logical. Checked arithmetic needs the
runtime assertions mentioned in DLP 56.

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
  DLP 52 handles for literals but which programs also need at runtime.

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
metadata. This is what DLP 56 provides.

### O2: Algebraic Properties (Logical)

Associativity, commutativity, distributivity, identity elements (x + 0 = x), and
absorbing elements (x × 0 = 0). These are what let the backend reorder,
vectorize, combine, and simplify operations, and replace expensive operations
with cheap ones (x × 8 becomes a shift, x / 4 becomes a shift when x is known to
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

A related intent is an error bound: "this result must be within N units of the
exact answer." That lets the backend choose fast approximate instructions (like
a reciprocal square root estimate) when they're accurate enough.

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
built for. DLP 56 covers the range part of this.

### P2: Relations Between Values

Proving things like "x < y," "i < length," "start ≤ end," or "the sum of the
parts equals the total." These relate two or more values to each other, which
DLP 56's single-value range constraints can't express. Almost every real
invariant is relational.

This is also exactly where decidability gets hard. Linear relations between
values (x + 2y ≤ z) are still decidable (Presburger arithmetic, decided by tools
like `lia` and `omega`), though they cost more than intervals. Relations that
multiply values together are undecidable in general.

### P3: Invariants Over Time

Proving that something stays true across every change to a value ("the balance
is never negative," "this counter only goes up"). TLA+ is centered on this. In
Define, this is roughly a constraint that's checked at every Value Setting
Statement and every operation that writes to a position, which DLP 56 already
does for ranges. Monotonicity ("only goes up") is a relation between the old
value and the new value, so it's a P2 problem.

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
sees through all of them. The open question from DLP 55 (whether logical
operations go inside `execute the encoding operation` or directly in the
Operation Statements Block) then becomes a question about how Encoding
Operations declare which logical operations they implement, not about
optimization.

### Programmer Intent Needs Its Own Place

Fast-math permissions, error bounds, and determinism (O3, O7) aren't part of any
operation's mathematical meaning, but they decide which implementations are
allowed. They need a place to live that isn't a logical operation. They may be
properties of a logical operation's execution, of a value operation, or of an
encoding. This only matters once Define has floating point.

### Relational Constraints Are the Next Big Step

DLP 56's constraints are about one value at a time, which keeps checking linear
and decidable. P2 shows that most real invariants relate several values. The
decidable next step is linear relations between values, which is a well-studied
problem (Presburger arithmetic, and abstract domains like octagons and polyhedra
that track linear relations between pairs or groups of values). That should be a
deliberate future proposal, with its cost understood up front.

### Division Needs Constraints Ranges Can't Express

E3 and O4 both need "the divisor is never zero." A range can express that only
if the divisor is always positive or always negative. Excluding a single value
from the middle of a range needs constraints that are a list of ranges (as
described in DLP 56's section on boolean conditions).

### Open Questions

- Which division rounding rules should be logical operations: all three
  (truncated, floored, Euclidean), or just one with the others as compositions?
- Is wrapping arithmetic its own family of logical operations
  (`standard:/number/modular/add`?), or is it exact arithmetic followed by a
  remainder?
- Do we need a three-way comparison, or are the separate comparisons enough?
- Where do floating-point permissions (O3) and determinism (O7) live?
- What's the smallest set of logical operations that covers E1 through E12
  without the backend losing information (O2, O5)?
