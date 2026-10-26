# Libraries for Range Evaluation

This is a survey of existing Python and Rust libraries that could do parts of
the work described in
[Numeric Operation Requirements](numeric-operation-requirements.md): evaluating
exact ranges through logical operations, tracking linear relationships between
values, finding exact ranges of polynomials, and proving facts about numeric
code.

It was gathered in October 2026. This area is changing quickly, especially SMT
solvers, so the versions and comparisons here will go out of date.

## What the Work Needs

1. Exact integers and rationals of any size, for the lowest and highest values
   of ranges.
2. A rule for each logical operation that gives the exact range of its result
   from the ranges of its operands.
3. Tracking each value as a number plus a number times each of some independent
   values (a simplified form of
   [affine arithmetic](https://en.wikipedia.org/wiki/Affine_arithmetic)).
4. Finding where a polynomial turns around, exactly, for exact ranges beyond
   fixed rules.
5. Answering harder questions, like exact ranges over integers with several
   inputs, relationships between values, and proofs.
6. Rounding an exact result once, to a floating-point precision, in each
   rounding direction.

## Exact Integers and Rationals

**Python:**

- Python's built-in `int` is exact at any size, and `fractions.Fraction` is an
  exact rational built on it. (From memory.)
- [gmpy2](https://github.com/aleaxit/gmpy) wraps GMP, MPFR, and MPC. Version
  2.3.0 was released on February 8, 2026
  ([piwheels](https://www.piwheels.org/project/gmpy2)). It requires CPython 3.9
  or later and supports free-threaded builds.

**Rust:** a community benchmark,
[bigint-benchmark-rs](https://github.com/Rjected/bigint-benchmark-rs), compares
the four main libraries. Its most recent run used dashu 0.4.2, malachite 0.4.14,
rug 1.24.1, and num-bigint 0.4.6. Computing 10 million digits of e took about
2.8 seconds with rug, 3.7 with malachite, 19.9 with dashu, and 482 with
num-bigint. The differences are much smaller for numbers of ordinary size.

- [rug](https://docs.rs/rug) wraps GMP and MPFR. It's the fastest in that
  benchmark.
- [malachite](https://www.malachite.rs/) is pure Rust, with algorithms partly
  translated from GMP, FLINT, and MPFR. Version 0.10.0 is current
  ([docs.rs](https://docs.rs/crate/malachite/latest)). It has integers and
  rationals, and a rational with a small numerator and denominator doesn't need
  heap memory. Its floats are still experimental. Its author says it's often
  much faster than num-bigint and slower than GMP
  ([announcement](https://users.rust-lang.org/t/malachite-a-new-arbitrary-precision-arithmetic-library/76587),
  [benchmarks](https://malachite.rs/performance)).
- [dashu](https://users.rust-lang.org/t/dashu-is-approaching-v1-0-its-a-full-alternative-to-gmp-mpfr-mpc-and-its-now-more-optimized/141210)
  is pure Rust, with integers, rationals, binary and decimal floats, and complex
  numbers. Version 0.5.0 was announced on July 11, 2026, with faster
  multiplication and division than the 0.4 version in the benchmark above, and
  version 1.0 is planned for the end of 2026. Its transcendental functions are
  correctly rounded, but a guarantee of correct rounding in every case is still
  planned.
- [num-bigint and num-rational](https://github.com/rust-num) are pure Rust and
  the most widely used, but much slower on large numbers.

## Interval Arithmetic

- [inari](https://docs.rs/inari) is a Rust implementation of the IEEE 1788
  interval arithmetic standard. Version 1.0.0 is current. Its intervals have
  `f64` bounds, it targets x86-64 (Haswell or newer), and some operations use
  GMP and MPFR.
- [mpmath](https://mpmath.org/) (Python) has intervals with arbitrary-precision
  floating-point bounds, and
  [python-flint](https://pypi.org/project/python-flint) has Arb's ball
  arithmetic. (From memory.)

All of these are designed to bound floating-point error, so their bounds are
floating-point numbers that are rounded outward. None of them has exact integer
or rational bounds, and none has rules for operations like `quotient` with a
rounding direction.

Reference implementations of interval rules for compiler operations:

- MLIR's
  [integer range analysis](https://mlir.llvm.org/doxygen/IntegerRangeAnalysis_8h_source.html)
  infers ranges of values through any operation that implements
  `InferIntRangeInterface`. Its ranges (`ConstantIntRanges`) keep both signed
  and unsigned bounds for each value, which makes operations that mix signed and
  unsigned meanings more precise.
- LLVM's `ConstantRange` and `KnownBits` classes have rules for each LLVM
  instruction. (From memory.)
- [Nice to Meet You: Synthesizing Practical MLIR Abstract Transformers](https://arxiv.org/abs/2512.06442)
  (Peng, Kennedy, Fan, Greenman, Regehr, and D'Antoni, December 2025) generates
  these rules automatically and proves each one sound with an SMT solver. It
  builds each rule by combining several simpler sound rules. About 17% of the
  rules it generated are more precise than LLVM's hand-written ones, and it
  notes that LLVM still has no rules at all for hundreds of instructions.

## Affine Arithmetic

- [affapy](https://affapy.readthedocs.io/) is a Python library for affine
  arithmetic with arbitrary-precision bounds. Its latest version is 0.1, from
  May 2020, and it's GPL-3.0.
- [libaffa](https://www.nongnu.org/libaffa/) and YalAA are C++ libraries. (From
  memory.)
- No Rust crate for affine arithmetic turned up. Crates with "affine" in their
  names are about geometry.

The simplified form in the requirements, where only addition, negation, and
multiplication by a number are kept exact, is a map from independent value to
coefficient plus a constant. Full affine arithmetic also approximates nonlinear
operations with new error terms, which the simplified form doesn't do.

## Abstract Interpretation Libraries

These implement whole families of facts about values, including relationships
between values:

- [APRON](https://antoinemine.github.io/Apron/doc/) and ELINA are C libraries
  with intervals, octagons (facts like `x − y ≤ c`), and polyhedra (any linear
  inequality between values). The
  [octagon library](https://www-apr.lip6.fr/~mine/oct/) is now part of APRON.
- [PPLite](https://github.com/ezaffanella/PPLite) is a C++ library for convex
  polyhedra. Version 0.14 was released on August 4, 2026.
- [SPARTA](https://lib.rs/crates/sparta) is a Rust library for building
  analyzers from abstract interpretation, with sign and interval facts. Version
  0.1.4 was released in September 2026.
- [Rabbit](https://github.com/gavlegoat/rabbit) is an abstract interpretation
  library for Rust that's still in progress. Its author suggests APRON or ELINA
  in the meantime.
- No Python-native library turned up.

## Exact Turning Points of Polynomials

- [FLINT](https://flintlib.org/) is a C library for number theory and exact
  algebra. Arb, its library for real and complex numbers with guaranteed error
  bounds, was merged into it in 2023.
  [FLINT 3.6](https://groups.google.com/g/flint-devel/c/pUMOmQ3sX1w), released
  on June 29, 2026, added real root isolation and refinement for integer
  polynomials, which its announcement says is much faster than its existing
  complex root isolation. Before 3.6, Arb's documentation said its root finding
  was [not competitive](https://flintlib.org/doc/arb_fmpz_poly.html) with the
  best methods for finding real roots alone. Its root functions assume the
  polynomial has no repeated factors, so a general polynomial needs a squarefree
  factorization first.
- [python-flint](https://pypi.org/project/python-flint) wraps FLINT. Version
  0.8.0 (August 29, 2025) supports FLINT 3.0 through 3.3, so it doesn't include
  FLINT 3.6's real root isolation yet. A 0.9.0 version appears in nightly
  builds. `fmpz_poly.roots()` finds exact rational roots, and `complex_roots()`
  finds all roots with guaranteed bounds.
- [flint3-sys](https://docs.rs/crate/flint3-sys/3.6.1) is a Rust binding that
  follows FLINT's version numbers. Version 3.6.1 binds FLINT 3.6. It can build
  FLINT itself or link to the system's. The older
  [flint-sys](https://lib.rs/crates/flint-sys) crate's last release was in 2023.
- SymPy can find exact real roots too, but it's far slower. (From memory.)

The turning points of a polynomial are the real roots of its derivative, so
FLINT's real root isolation is the operation that finding exact ranges of
polynomials in one input needs.

## SMT Solvers and Integer Programming

SMT solvers answer whether a formula over integers, reals, bit-vectors, and
other theories can be true. They're how verification tools prove facts, and they
can also find exact ranges by searching for the smallest or largest value.
Linear integer arithmetic is decidable. Nonlinear integer arithmetic is
undecidable in general, so solvers use heuristics, and their running time can
change a lot from small changes to a query.

- [Z3](https://github.com/Z3Prover/z3) (MIT license). Version 5.3.2 was released
  on October 25, 2026 ([releases](https://github.com/Z3Prover/z3/releases)).
  Version 5.0.0 (July 2026) improved the nonlinear arithmetic solver, and 5.1.0
  (August 2026) improved nonlinear bounds
  ([release notes](https://github.com/Z3Prover/z3/blob/master/RELEASE_NOTES.md)).
  It has an `Optimize` mode that finds the smallest or largest value of a term.
  - Python: [z3-solver](https://pypi.org/project/z3-solver/).
  - Rust: the [z3](https://docs.rs/crate/z3/latest) crate, version 0.20.0. Its
    `vendored` feature builds and statically links Z3 from source.
- [cvc5](https://pypi.org/project/cvc5) (BSD license). Version 1.3.3 of its
  Python bindings was released on February 25, 2026. No Rust binding turned up.
  In SMT-COMP 2021, the most recent year whose winners turned up, cvc5 won the
  main track for both linear (QF_LIA) and nonlinear (QF_NIA) integer arithmetic,
  and Yices2 won the 24-second track for both
  ([QF_LIA](https://smt-comp.github.io/2021/results/qf-lia-single-query),
  [QF_NIA](https://smt-comp.github.io/2021/results/qf-nia-single-query)).
- [Bitwuzla](https://github.com/bitwuzla/bitwuzla) specializes in bit-vectors
  and floating point. On a
  [set of queries from LLVM optimizations](https://github.com/bitwuzla/bitwuzla/issues/218)
  (August 2026), it was 3 to 5 times faster than Z3 on the queries it solved,
  and much faster than cvc5. The only Rust binding found,
  [bitwuzla-sys](https://github.com/fatemender/bitwuzla-sys), hasn't changed
  since 2022.
- Projects are using several solvers together:
  [Ultimate](https://github.com/ultimate-pa/ultimate/pull/792) replaced CVC4
  with Bitwuzla and cvc5, and
  [mldsa-native](https://github.com/pq-code-package/mldsa-native/pull/1491)
  proves each fact with at least two solvers.
- New SMT solvers in Rust exist, but none is close to Z3 in speed or coverage
  yet.
  [OxiZ](https://users.rust-lang.org/t/announce-oxiz-0-1-1-a-pure-rust-smt-solver-aiming-for-z3-compatibility/137541)
  is an early alpha aiming for Z3's API.
  [rz3](https://github.com/Yatrogenesis/rz3) focuses on exact arithmetic and
  getting the same answer every run, rather than speed.
- [LLM2SMT](https://arxiv.org/abs/2603.06931) (2026) reports an SMT solver
  written entirely by a language model. On one set of benchmarks (QF_UF) it
  solved 7,468 queries, compared to 7,500 for Z3 and 7,494 for cvc5.

### Z3 as a Range Evaluator

Z3 answers whether a formula can be true. It doesn't infer relationships or
ranges by itself: to learn whether y is always at least x, a program asks
whether y < x is possible. The abstract interpretation methods in
[Numeric Operation Requirements](numeric-operation-requirements.md#prior-art-on-inferring-relationships-between-values)
find relationships without being told what to look for. Z3 does have two engines
closer to that:

- Spacer, its engine for constrained Horn clauses, infers loop invariants. It
  supports linear integer and real arithmetic fully, and nonlinear arithmetic on
  a best-effort basis
  ([HCVS 2017 slides](https://software.imdea.org/Conferences/hcvs17/slides/arie_slides.pdf)).
- Its older Datalog engine has a relation that extracts integer linear
  invariants with Karr's algorithm
  ([`karr_relation.h`](https://github.com/Z3Prover/z3/blob/master/src/muz/rel/karr_relation.h),
  from 2013).

**Which answers are exact.** Z3's arithmetic is exact, with integers and
rationals of any size, and its integers are true integers. So when it answers,
its answer is exact, and it doesn't have the problem calculus has with turning
points between integers. For linear arithmetic over integers and reals, its
procedures always answer, and `Optimize` finds the exact smallest or largest
value of a linear term. Its heuristics, like which case to try first, change how
long it takes, not the answer. For nonlinear real arithmetic, it has NLSAT,
which is based on cylindrical algebraic decomposition. (That NLSAT is complete,
but can take doubly exponential time, is from memory.) For nonlinear integer
arithmetic, which is undecidable in general, its solver is documented as
incomplete. It uses Gröbner bases, interval propagation, tangent lemmas, and
Horner forms, and it can answer "unknown"
([parameters](https://git.libre-chip.org/mirrors/z3/src/commit/b68af0c1e590c5fdd8543a5deaa99f90e4407a77/src/math/lp/nla_core.h)).
`Optimize` is described as linear optimization, MaxSMT, and their combinations
([tutorial](https://www.philipzucker.com/z3-rise4fun/optimization.html)). No
source turned up about how well it handles nonlinear objectives.

When `Optimize` can't find a bound, a program can still find one with yes-or-no
queries: "can the result be less than k?" Every "no" proves a bound, and
searching over k narrows the range. Stopping early leaves the tightest bound
proven so far, so precision degrades toward whatever bound the program started
with instead of failing.

**Matching Define's meaning.** Z3's answer is exact for the formula it's given,
so the formula has to match Define's meaning exactly. For example, SMT-LIB's
integer `div` and `mod` use Euclidean division: the remainder is never negative,
whatever the divisor's sign
([SMT-LIB Ints theory](https://smt-lib.org/theories-Ints.shtml)). It matches
neither rounding down nor rounding toward zero for every sign:

| Division | SMT-LIB `div`, `mod` | Rounding down | Rounding toward zero |
| -------- | -------------------- | ------------- | -------------------- |
| 12 ÷ −7  | −1, 5                | −2, −2        | −1, 5                |
| −12 ÷ 7  | −2, 2                | −2, 2         | −1, −5               |

So `quotient/down` and `quotient/toward_zero` each need their own encoding. Z3
also has a `rem` operator that isn't part of SMT-LIB
([mailing list](https://cs.nyu.edu/pipermail/smt-lib/2014/000822.html)).

**Performance.**

- Each query has a fixed cost to encode the formula and set up the solver.
- How long a nonlinear integer query takes can't be predicted from its size, and
  small changes to a query can change its time a lot.
- Z3 can't recover after it reaches its hard memory limit
  ([cfe-dev](https://lists.llvm.org/pipermail/cfe-dev/2020-August/066642.html)).
- A time limit doesn't give the same answers on every machine, because a query
  that finishes on a fast or idle machine can run out of time on a slow or busy
  one. Z3's `rlimit` instead counts internal steps, like conflicts and
  decisions, so a query stops at the same point on any machine with the same
  version of Z3. But steps don't track time well: Clang's static analyzer found
  queries that ran for over an hour while using very little of their `rlimit`,
  and concluded that both limits are needed
  ([Taming Z3 query times](https://discourse.llvm.org/t/analyzer-rfc-taming-z3-query-times/79520)).
  A new version of Z3 can change which queries finish under either limit.

**Where these properties matter less.** Some uses run each query once, or
rarely, so neither the cost per query nor occasional timeouts matter much:

- Proving that each logical operation's range rule is sound, and checking how
  precise it is, once, during development. The
  [Nice to Meet You](https://arxiv.org/abs/2512.06442) paper did this for its
  generated rules.
- Comparing a compiler's ranges against exact answers in tests.
- Proofs that a programmer asks for, which need a solver for facts that ranges
  and inferred relationships can't establish.

For linear integer programming, which finds the smallest or largest value of a
linear formula over integers with linear constraints:

- [HiGHS](https://highs.dev/) (MIT license). The Rust crate
  [highs](https://docs.rs/crate/highs/latest) is version 2.4.0, and
  [highs-sys](https://docs.rs/crate/highs-sys/latest) can build and statically
  link HiGHS. Its Python binding is `highspy`. (Its license is from memory.)
- [OR-Tools](https://developers.google.com/optimization) (Apache 2.0 license),
  whose CP-SAT solver handles integer constraints. Version 9.15 was released on
  January 12, 2026 ([pepy](https://pepy.tech/project/ortools)). (Its license is
  from memory.)

## Correctly Rounded Floating Point

[MPFR](https://www.mpfr.org/) computes floating-point operations at any
precision, rounded correctly in each rounding direction. It's available through
gmpy2 in Python and rug in Rust. With exact rationals, rounding to a precision
can also be done directly: find the two nearest representable values and pick
one by the rounding direction. (From memory.)

## Licenses

| Library           | License             |
| ----------------- | ------------------- |
| GMP               | LGPL-3.0 or GPL-2.0 |
| MPFR              | LGPL-3.0            |
| FLINT             | LGPL-3.0            |
| gmpy2             | LGPL-3.0            |
| rug               | LGPL-3.0            |
| malachite         | LGPL-3.0            |
| dashu, num-bigint | MIT or Apache 2.0   |
| Z3                | MIT                 |
| cvc5              | BSD 3-Clause        |
| Bitwuzla          | MIT                 |
| HiGHS             | MIT                 |
| OR-Tools          | Apache 2.0          |
| APRON             | LGPL                |
| affapy            | GPL-3.0             |

Malachite's and affapy's licenses, and dashu's and num-bigint's, were confirmed
in sources. The others are from memory. LGPL libraries have extra requirements
when they're statically linked into a program that's distributed.

## What Turned Up

- Exact integers and rationals are well covered in both languages.
- No library found has interval rules with exact bounds for operations like
  Define's logical operations. The closest are compiler analyses (MLIR, LLVM),
  which work on fixed-width integers.
- No affine arithmetic library turned up for Rust, and the Python one hasn't
  changed since 2020.
- FLINT 3.6 is new support for exactly the polynomial question, in C, with a
  current Rust binding. Python's binding doesn't support it yet.
- SMT solvers are improving quickly, especially for nonlinear arithmetic, and Z3
  has current bindings for both languages. Its answers are exact when it gives
  one, but how long a nonlinear query takes, and whether it finishes, can't be
  predicted (see [Z3 as a Range Evaluator](#z3-as-a-range-evaluator)).
