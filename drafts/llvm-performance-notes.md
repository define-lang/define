### 9: Compile-Time Optimization

For maximum LLVM optimization leverage, your encodings need to express (or let
the compiler derive):

1. Width and kind — maps directly to LLVM types. Already in your design.
2. Signedness — per-operation in LLVM, but probably per-encoding in Define
   (cleaner for the programmer). The compiler maps Define's encoding choice to
   the right LLVM operation.
3. Overflow behavior — wrap / trap / saturate / poison. Critical. Probably
   varies per operation, not per encoding (e.g.,
   operation</integer/add/wrapping> vs. operation</integer/add> where the
   default is "proven not to overflow").
4. Float math assumptions — whether NaN/Inf can occur, whether associativity is
   allowed, whether reciprocal approximation is OK. Could be encoding-level or
   operation-level.
5. Range information — if the compiler can prove a value is in [a, b], it should
   emit !range. This is verification output, not encoding input.
6. Alignment and memory layout — for dimension points that are memory-backed,
   their physical alignment matters. Probably an aspect of the encoding or
   position.
7. Aliasing — which dimension points can share memory. Likely belongs to the
   positional/ownership model, not encodings. But the compiler needs to emit
   noalias when appropriate.
8. Purity — whether an action has side effects. Define's action analysis
   probably already tracks this; map it to LLVM function attributes.
9. Atomicity — if shared mutable state exists, encodings on those dimension
   points need memory ordering semantics.

### 10: Optimizing Vectorization

1. No aliasing between pointers (critical).

The biggest vectorization-killer is uncertainty about whether `p[i]` and
`q[i+1]` might be the same memory. If the compiler can't prove they're
different, it can't reorder or parallelize. The fix is noalias attributes on
pointers (or TBAA metadata for type-based proof).

This is where Define's positional model might give you a huge natural advantage.
If two dimension points are in separate positions with no aliasing relationship,
the compiler can emit noalias automatically based on ownership analysis. This is
the kind of proof you get from C only via restrict (which programmers rarely use
correctly), or from Rust via the borrow checker (where it's enforced but still
complicated). Define could just emit it from the positional model.

2. No loop-carried dependencies.

Iteration N+1 must not depend on a value computed in iteration N (except for
specific recognizable patterns like reductions, inductions, and first-order
recurrences). Loop-carried deps force serial execution.

If Define expresses "do this action to every dimension point in this collection"
as an explicit parallel construct, you bypass much of this by declaring
parallelism up front — the compiler doesn't have to prove independence; the
programmer (or verifier) has asserted it.

3. Alignment information.

Aligned vector loads/stores are significantly faster than unaligned. align N on
load/store instructions (and on allocations) tells the compiler "trust me, this
is 16-byte aligned" and unlocks the fast path. Define's encoding system should
carry alignment, either per-encoding (most encodings have natural alignment) or
per-position (for memory-backed positions).

4. Simple control flow.

Complex branches inside the vectorizable region force masked execution (slower)
or prevent vectorization entirely. For Define, actions that have complex
conditional logic will vectorize less well than actions that are straight-line
operations.

5. Fast-math flags for FP reductions.

A sum over floats: `for (int i = 0; i < N; i++) sum += a[i];` is not
vectorizable with default FP semantics because reassociation is forbidden. With
reassoc or full fast, LLVM can vectorize the sum. Define's verification could
emit reassoc when the programmer has asserted "I accept non-bit-exact results"
(or when the operations are provably exact, like integer sums).

6. Known trip counts / bounds.

If the loop iterates a known number of times, or an SCEV-analyzable number, the
vectorizer picks a better vectorization factor and can unroll. Bounded
collections in Define would help here.

7. Uniform memory access pattern.

- Contiguous: best
- Strided with constant stride: good (uses strided loads/scatter-gather)
- Random: poor (uses gather/scatter, often slower than scalar)

The way data is laid out matters. Structs-of-arrays beat arrays-of-structs for
vectorization. If Define's positional model implies a memory layout, that layout
should favor contiguity for things likely to be processed in bulk.
