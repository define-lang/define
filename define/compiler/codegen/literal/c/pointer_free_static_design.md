# Pointer-Free Static Literal C Execution

- Status: Experimental
- Date: 2026-08-31
- Scope: Literal C representation study

## Goal

Represent a resolved Define Operation Graph without storing a pointer to each
runnable operation. Positions should remain compiler concepts rather than
runtime objects. When Particle identity and Action Execution cardinality are
statically bounded, generated C should identify runnable work with statically
assigned integers or bits and derive every state address from that identity.

Runtime performance is the primary objective of this study. Memory use is
secondary unless a faster representation also uses less memory without an
additional tradeoff.

## Semantic model

Codegen assigns each distinguishable live Particle a static identity for as long
as its lifetime can overlap another Particle's lifetime. A Position is a
compile-time association from a Position reference to one of those identities.

- Creating a Particle begins the lifetime of its assigned identity.
- Moving a Particle changes the compiler's association and need not emit a C
  instruction.
- Destroying a Particle performs every statically required destruction effect
  and ends the identity's lifetime.
- The strict literal form gives every Particle an ordinary presence byte and
  emits every Create and Destroy as a write to that byte. The C optimizer may
  remove a write after proving that no behavior observes it.
- Storage may be reused for non-overlapping Particle identities when address
  identity is not externally observable.

An optimizing backend could prove that control and dependencies make a presence
value unnecessary and omit its storage. That is useful as a performance lower
bound in this study, but it performs Define-level semantic optimization beyond
the strict literal boundary. A literal backend should instead emit an ordinary,
non-volatile byte and allow C's ordinary dead-store elimination to reach the
same machine code when it can prove the complete use is unobservable.

Quality implementation state is separate from Particle presence. The benchmark
stores a value for every Particle only to give each simulated Particle Operation
an observable result that the optimizer cannot delete; that value is not a
proposal that every Particle needs a payload word.

This does not require a runtime Position object. Child names resolve through the
statically identified Particle that defines them.

When more than one Particle identity can reach the same generated operation, the
distinction cannot simply disappear. Codegen must preserve it in control flow,
duplicate identity-specific code, or use a compact runtime identity such as an
integer or one-hot bit. A pointer is one possible representation, not a semantic
requirement.

## Static runnable identity

Every concurrently distinguishable generated runnable unit receives a static
integer identity. A runnable unit may fuse a dependency chain of Particle
Operations when no intervening scheduling decision can improve execution. Its
identity determines:

- the generated code to execute;
- the Action Execution state to access;
- the preferred topology group, if any; and
- the successor and Join relationships.

No queued function pointer, context pointer, or topology value is needed. A
worker claims an integer or bit and dispatches through generated control flow.
The benchmark uses arithmetic to derive an Action Execution index because it
repeats each fixture many times. Fully generated code could instead use fixed C
symbols or constant indexes.

One bit is valid only while at most one unclaimed execution of that static work
identity can exist. Overlapping executions require distinct bounded identities,
a count, or the general dynamic scheduler.

## Candidate representations

The study compares these representations:

1. **Direct generated control flow.** One caller executes a complete graph with
   direct calls and ordinary compact state. Positions, readiness, satisfied
   Joins, and completion atomics disappear. Literal Particle presence writes
   remain in emitted C unless the C optimizer proves them unnecessary.
2. **Contiguous direct ranges.** Each worker receives a contiguous range of
   complete Action Executions and runs the same direct control flow. This pays
   one atomic completion operation per worker, not per Action Execution.
3. **Static worker assignment.** Initially runnable work is assigned directly to
   workers with no shared readiness representation. Dynamically enabled work
   uses a bitset. This is eligible only when the cost distribution is known well
   enough that loss of stealing is acceptable.
4. **Contiguous initial assignment.** Workers receive contiguous initial
   runnable ranges, but dynamically enabled units remain in a bitset.
5. **Atomic initial cursor.** Workers claim chunks of the statically known
   initial runnable set from one atomic counter. Dynamically enabled work uses a
   bitset.
6. **One atomic byte per runnable identity.** Publication stores one byte and a
   worker scans and exchanges ready bytes.
7. **Atomic bitset with single-bit claims.** Publication performs a word-level
   atomic OR. A worker claims one ready bit with compare-exchange.
8. **Atomic bitset with bounded batch claims.** A worker clears and retains up
   to a generated number of bits with one compare-exchange.
9. **Atomic bitset with whole-word claims.** A worker exchanges a ready word
   with zero and retains every bit. This minimizes atomic operations but can
   conceal heterogeneous work from other workers.
10. **Function-pointer control.** This uses the same atomic cursor as candidate
    5, but each initially runnable unit occupies a 16-byte function-and-integer
    record and executes through an indirect call. It is a control measurement
    for the integer representation.

Direct control need not be one monolithic C function. Codegen may divide a
statically ordered path into target-calibrated direct-call regions without
introducing a runtime work pointer. At larger scale it may encode a regular
family of operations as compact constant operands consumed by one generated
loop. This also remains pointer-free: the operation number determines each
Particle identity and behavior through generated arithmetic or tables rather
than a queued function or state address. The retained large-code study measures
these code-layout forms separately from scheduling.

The static and cursor forms are not substitutes for dynamic readiness. They
remove readiness work only for Particle Operations that the Operation Graph
proves are runnable at Action Execution initialization. Direct ranges are
eligible only when enough independent Action Executions already expose all
useful processor parallelism. Otherwise, they can hide useful parallel Particle
Operations in one worker's private range.

## Publication and memory ordering

A byte publication uses release ordering and its successful claim uses acquire
ordering.

Multiple processors can publish different bits in the same atomic word. A
word-level publication therefore uses an acquire-release read-modify-write so
that consecutive publishers form a synchronization chain. A worker's acquiring
claim observes the Particle writes associated with every bit it claims. A single
release OR followed by one acquire claim would not, by itself, establish that
relationship with every independent publisher represented in the combined word.

The Join remains an acquire-release subtract-and-return counter. A readiness
bitmask is not a faster general replacement: identifying the unique final
arrival requires observing the previous atomic value, and common CPUs do not
provide a cheaper fetch-and-return OR than their atomic subtraction path.

Packing unrelated, concurrently written Particle presence values into one word
is not implied by this design. It can introduce false sharing and atomic
read-modify-write operations where direct bytes or no storage would be faster.
Readiness bitsets are valuable because workers must search them; an individually
addressed Particle often has no such requirement.

SIMD loads are not used over concurrently modified C atomic objects. Local
claimed words can be traversed efficiently with trailing-zero and clear-lowest-
bit instructions. A hierarchy of atomic summary words is a possible later
optimization if scanning the primary words becomes material.

## Portability boundary

The static identities, direct control flow, and C atomic ordering are portable
C23. Their performance is not target-independent: codegen must know that the
selected atomic integer width is lock-free and must select cache-line and worker
topology facts for the target. A C implementation is allowed to implement an
atomic operation with a library call or lock.

Static AArch64 builds of the selected forms run correctly under QEMU. In gem5's
Neoverse V2 model, a 256-operation direct body used 36.2% fewer cycles than the
compact form, agreeing with the native small-code direction. gem5
syscall-emulation pthread barriers did not reach the concurrent measured region
reliably, so no modeled AArch64 concurrency value is accepted. Physical hardware
or full-system simulation is still required for target thresholds involving
Joins or hybrid regions.

The specialized generated scheduling paths demonstrated by the exact fixtures
permit only atomics that the target guarantees are lock-free. They emit no
mutex, semaphore, `atomic_flag` lock, or explicit atomic fence. On x86-64, the
word `lock` still appears in the complex fixture's disassembly because
`lock sub`, `lock or`, and `lock cmpxchg` are that ISA's atomic
read-modify-write instructions. They are not software locks, and no separate
`mfence`, `lfence`, or `sfence` is emitted. The serial and statically assigned
small fixtures have no atomic instruction in their generated machine code.

The reusable general scheduler is a different case. Its Chase-Lev deque uses
explicit C fences, including a sequentially consistent fence that GCC emits as a
locked dummy OR on the measured x86-64 target. The deque needs that ordering
while an owner and thieves race. Static codegen can remove both the deque and
its fences only when its Operation Graph and cardinality facts prove that the
generated execution does not require that concurrent claiming behavior.

Thread lifecycle is outside that guarantee. `pthread_create` and `pthread_join`
may use libc and kernel synchronization internally. Replacing pthreads requires
a target runtime that creates and waits for operating-system execution contexts;
it cannot make parallel processors execute generated code using ordinary
user-space instructions alone.

The retained [thread-runtime benchmark](thread_runtime_benchmark.c) establishes
that thread creation and hot scheduling should be selected independently. A
persistent pthread worker performs no pthread operation during Action Execution;
it can use the same targeted atomic publication, completion generations, and
direct futex parking independently of its pthread lifecycle. A sparse or hybrid
parking policy can use same-word waiter bits to avoid unnecessary wake calls; a
pure-parking policy can instead use release stores and unconditional wakes to
remove those atomic read-modify-write operations.

Use pthreads for worker lifecycle. Raw clone did not improve steady-state
execution, and its small, inconsistent cold-start improvement did not justify
owning the Linux thread ABI or excluding libc, foreign behavior, thread-local
storage, sanitizers, stack protection, and asynchronous signal handling. The raw
variants remain only as controls in the retained benchmark; codegen does not
select them.

The thread-runtime benchmark is Linux x86-64-only because it includes Linux
affinity and futex calls plus an x86-64 raw-clone trampoline. These harness
choices are not requirements of the generated representation; another target
needs threading, affinity, waiting, and processor-relax implementations for its
operating system and ISA. GCC and Clang accepting C23 does not by itself
guarantee that every target has the same facilities or atomic costs.

## General fallback

This representation is selected only for a statically bounded region. A general
dynamic scheduler remains the fallback for unbounded or overlapping Action
Executions, runtime-selected identities, and foreign behavior that makes the
reachable work set unknown. Its entries can still use integer handles into an
arena; this study does not establish that pointers are required at that
boundary.

A generated program may use both representations. Direct successor calls and a
static readiness bitset can cover most of one action, while a dynamic boundary
submits an integer-bearing runnable unit to the general scheduler.

That boundary may occur between generated regions within one action. Fixed-cost
regions can use direct static assignment while sparse runtime-variable regions
remain individually claimable. On the measured target, a 4,096-branch schedule
with only 64 uncertain branches was 9--11% faster as this hybrid than as either
a completely static or completely dynamic schedule for one Action Execution.
With uniform fine work or sufficient similarly costly Action Executions, static
regions or whole-execution ranges remained faster.

Persistent static scheduling also has generated subforms. Per-worker generation
and completion values avoid both task pointers and a broadcast cache line when
the assignment is exact. A waiter-bit completion counter replaces completion
values when the caller may need to park. Dense pure-parking schedules can use a
broadcast generation and unconditional wakes instead. The general dynamic
scheduler remains necessary when a worker must claim runtime-selected work.

## Facts codegen needs

Optimal selection requires facts, not details of how the compiler currently
represents them:

- the resolved, transitively minimal Particle Operation dependency graph,
  including initially runnable operations, fanout, fan-in, and every point at
  which a caller may continue;
- every dependency arrival's completing Particle Operation and multiplicity,
  rather than only the total arrival count of its successor;
- an upper bound on simultaneously live Action Executions and on concurrently
  distinguishable instances of each generated runnable unit;
- Particle identity and lifetime facts, including which identities can overlap,
  which storage can be reused, and whether address identity is observable;
- Position occupancy facts at every operation, including whether any runtime
  branch can observe uncertain presence;
- the runtime state size, alignment, read set, and write set of each reachable
  quality behavior;
- whether each Particle Operation can invoke foreign behavior, block, create
  further work, or otherwise has a cost that cannot be bounded;
- every terminal Particle Operation and whether all other reachable Particle
  Operations transitively precede it;
- the compilation and symbol-visibility boundary, including which Particle
  addresses or generated functions can escape ordinary C optimization;
- estimated cost bounds and variance for Particle Operations and complete Action
  Executions, not merely an average cost;
- the number of independent Action Executions expected at each invocation and
  whether their cost ordering is known;
- the number of Particle Operations and expected generated instructions in each
  hot direct region, natural dependency boundaries between regions, and whether
  a regular family can be represented by compact operands;
- compile-time and compiler-memory budgets, plus the selected compiler, version,
  optimization level, target instruction-front-end capacity, and calibrated
  direct-region and compact-data thresholds;
- the expected number and lifetime of parallel Action Executions over which a
  persistent worker pool can be amortized;
- the maximum retained worker count and exact active worker subset at each
  statically scheduled publication;
- estimated time until each selected worker completes and until it can receive
  its next publication, so caller waiting and worker waiting can use independent
  spin or park policies;
- whether each park is expected to find a waiter, and the selected fraction of
  the retained pool, so codegen can choose conditional or unconditional wakes
  and targeted or broadcast publication together;
- whether generated workers can access libc, foreign behavior, thread-local
  storage, sanitizer runtimes, stack-protector paths, or asynchronous signal
  handlers;
- a maximum generated worker stack use when unguarded mapped or static stacks
  are considered; and
- target facts that affect the decision, including available physical
  processors, cache-line size, cache and NUMA topology, and atomic-operation
  costs.

Without a strong cost or cardinality fact, codegen should select the form that
preserves individual claimability. Unknown does not mean uniform.

## Benchmark fixtures

The benchmark is derived from these existing Operation Graph fixtures rather
than from the current compiler implementation:

### Three-operation chain

Source:
[`three_operation_chain`](../../../../testdata/reference_graph/operation_graph_single_action_integration/three_operation_chain/operation_dependencies.json)

```text
create item -> move item to dest -> destroy dest
```

The move changes the compile-time Position association. The same Particle state
is used before and after it.

### Multiway Join and fanout

Source:
[`multiway_join_and_fan_out`](../../../../testdata/reference_graph/operation_graph_single_action_integration/multiway_join_and_fan_out/operation_dependencies.json)

```text
                              create b -> destroy b
create box -> fanout                                      -> destroy box
                              create a -> destroy a
```

One branch runs directly. The other is published by static identity. The final
destroy uses a two-arrival Join.

### Parallel local and triggered Action Execution chains

Source:
[`local_create_and_action_execution_run_in_parallel`](../../../../testdata/reference_graph/operation_graph_two_actions_integration/local_create_and_action_execution_run_in_parallel/operation_dependencies.json)

```text
create local item -> destroy local item
create trigger Particle -> create other item -> destroy other item
```

Both initially runnable Particle Operations begin together. Benchmark completion
joins the two chains so that the harness can validate the complete Action
Execution.

## Benchmark method

The retained C benchmark repeats bounded instances of the selected graph so that
worker creation is amortized. Runnable and Particle-state allocation,
initialization, and checksum validation are outside the timed interval. Initial
readiness publication, worker creation, execution, and worker joining are timed.

Each Particle operation performs a configurable xorshift workload. Zero-round
runs expose representation overhead; mixed-cost and longer runs expose load
balancing. The operation values and final Particle presence are incorporated
into a deterministic checksum outside the timed interval. Every sample must
match the first sample.

Both GCC and Clang are tested with C23, `-O2`, `-march=native`, and
`-mtune=native`. Candidate order is reversed across outer repetitions.

## Findings

There is no universal scheduler winner. The fastest generated representation is
selected by statically known runnable breadth and cost regularity:

1. Use direct generated control flow for one or a few inexpensive Action
   Executions. This is the only form with no scheduler work at all.
2. Use contiguous direct ranges when independent Action Executions can occupy
   the active workers and their costs are tightly bounded.
3. Preserve individual claimability when costs are unknown or heterogeneous.
   Claim one runnable unit at a time for millisecond-scale work.
4. When there are fewer Action Executions than active workers and independent
   Particle Operations are expensive, expose those Particle Operations to the
   workers instead of serializing each complete graph in a direct range.

### Direct and contiguous crossover

These are representative GCC 16.2 medians in milliseconds for 60,000 uniform
Action Executions on eight physical processors. Direct uses the calling
processor; ranges creates eight workers. `work` is the number of xorshift rounds
performed by each simulated Particle Operation.

|  work | chain direct | chain ranges | fan/Join direct | fan/Join ranges | parallel direct | parallel ranges |
| ----: | -----------: | -----------: | --------------: | --------------: | --------------: | --------------: |
|     0 |        0.025 |        0.126 |           0.038 |           0.098 |           0.044 |           0.167 |
|     1 |        0.108 |        0.101 |           0.158 |           0.163 |           0.137 |           0.161 |
|     4 |        0.388 |        0.137 |           0.708 |           0.191 |           0.606 |           0.189 |
|    16 |        2.440 |        0.408 |           4.499 |           0.660 |           3.990 |           0.584 |
|    64 |       11.495 |        1.569 |          22.331 |           2.972 |          19.059 |           2.543 |
|   256 |       48.032 |        6.270 |          95.494 |          12.494 |          79.937 |          10.384 |
| 1,000 |      188.804 |       24.491 |         377.187 |          48.776 |         314.665 |          40.687 |

Thread creation dominates at zero work. At four rounds, contiguous ranges are
already 2.8 to 3.7 times faster. At larger costs they approach the expected
eight-processor speedup. The atomic cursor converges on range performance as
work grows, but for the chain at zero work it took 0.57 ms rather than 0.13 ms
because it retained shared-claim overhead.

Clang reproduced the crossover. At zero rounds it measured 0.028 versus 0.107 ms
for the chain; at 64 rounds it measured 11.52 versus 1.56 ms. The two compilers
therefore agree on the representation decision even when their exact fine-work
timings differ.

The initial results above used the ordinary dynamic-frequency policy recorded in
the scheduler ADR. A September 1, 2026 rerun constrained every processor to 4.30
GHz. These GCC `-O2` medians use the same 60,000 Action Executions and show
direct / eight-range complete-runtime milliseconds:

| work |          chain |       fan/Join |       parallel |
| ---: | -------------: | -------------: | -------------: |
|    0 |  0.025 / 0.108 |  0.049 / 0.165 |  0.057 / 0.109 |
|    1 |  0.110 / 0.116 |  0.205 / 0.167 |  0.177 / 0.126 |
|    4 |  0.504 / 0.165 |  0.912 / 0.223 |  0.784 / 0.202 |
|   64 | 15.185 / 2.006 | 29.526 / 3.804 | 25.116 / 3.250 |

Clang reproduced the same result. At one round, its ranges were 1.14, 1.90, and
1.29 times faster for the chain, fan/Join, and parallel graphs. GCC's chain
remained 6% faster as direct control at that cost, while its other two graphs
favored ranges. Holding frequency constant therefore preserved the
representation decision but moved the fine-work crossover earlier by removing
the single-active-processor boost advantage. Codegen needs a target-calibrated
cost threshold; the number of synthetic rounds is not a portable boundary.

### Mixed costs

For 128 Action Executions with half at zero rounds and half at one million
rounds, single claims consistently beat private ranges:

| distribution | chain single / ranges | fan/Join single / ranges | parallel single / ranges |
| ------------ | --------------------: | -----------------------: | -----------------------: |
| random       |        26.1 / 32.6 ms |          52-53 / 65.2 ms |      43.5-43.8 / 54.4 ms |
| clustered    |        26.1 / 51.3 ms |          52.3 / 102.5 ms |      43.6-43.8 / 85.7 ms |

A 64-unit cursor or whole-word bit claim made the random chain take about 113
ms. Retaining a batch privately reduced atomic operations but concealed slow
work. Batching is therefore an optimization only when codegen has a strong upper
bound on cost variance.

Static round-robin assignment was also distribution-sensitive. It matched single
claims for a favorable clustered order, but took about 39 ms for the random
chain and 65 ms for the random parallel graph. Source or identity order is not a
cost proof.

The 4.30 GHz rerun preserved this decision. Across GCC and Clang, ranges were
1.11--1.25 times slower than single claims for the random distributions and
almost exactly twice as slow for the clustered distributions. Absolute
single-claim times were approximately 33.5 ms for the chain, 75.2 ms for the
fan/Join random case, and 55.8 ms for the parallel graph.

### Outer and inner parallelism

With one fan/Join Action Execution whose Particle Operations each perform one
million rounds, direct execution took about 6.4 ms while exposing the two
branches to two workers took about 4.3 ms. The parallel-chain graph measured
about 5.4 versus 3.3 ms. Whole-word and eight-bit claims lost that parallelism
by giving both expensive initially runnable Particle Operations to one worker.

At eight uniformly expensive Action Executions, contiguous direct ranges already
occupied eight workers and matched the individually claimable forms. Thus the
generated decision is based on runnable breadth, not merely whether an Operation
Graph contains parallel Particle Operations.

At fixed frequency, one fan/Join Action Execution measured 8.35 ms directly and
5.60 ms with its independent Particle Operations exposed to two workers. The
parallel-chain graph measured 6.96 and 4.23 ms. Both compilers reproduced the
respective 1.49 and 1.64--1.65 times speedups.

### Integer identity versus function pointers

The function-pointer form adds a 16-byte table entry per initially runnable unit
and leaves an indirect `call` in GCC and Clang assembly. Initial measurements
favored integer identity: with 64-unit claims, the workless chain took
0.45--0.56 ms with integer identities and 0.71--0.86 ms with function pointers
under GCC, while the workless parallel graph took 0.77--0.81 versus 1.23--1.44
ms.

The controlled-frequency rerun showed why this is not a universal dispatch
result. Integer identity was 37--39% faster for the workless chain, but the
function table was 26% faster for the workless parallel graph. That result is
consistent with avoiding an integer-identity branch while this regular call
sequence made the indirect target predictable. At 64 rounds, integer identity
was equal to 10% faster across both graphs and compilers. Generated direct
control or generated ranges avoid both costs when statically eligible. When
dynamic claimability is required, retain integer identity as the pointer-free
representation and treat function control as a target-measured alternative, not
as either a guaranteed penalty or a generally optimal form.

### Particle presence

The three presence variants all produce the same checksum:

- no presence storage when the Operation Graph and control flow prove it;
- one byte on each directly addressed Particle state; and
- one bit per Particle in an Action Execution-local word.

No storage was fastest in direct control and always smallest. For compact direct
fan/Join state, it used 56 bytes per Action Execution and a workless run took
about 0.038 ms. Byte presence increased the state to 80 bytes and the run to
about 0.052 ms. A sequential packed word retained the 56-byte state and took
about 0.048--0.054 ms. At fixed frequency, GCC measured 0.048, 0.062, and 0.061
ms for no storage, bytes, and bits; Clang measured 0.057, 0.066, and 0.070 ms.

Packed bits are not a free runtime win even when Particle Operations are
sequential. In the eight-worker direct-range fan/Join case, GCC measured about
0.101 ms for bytes and 0.160 ms for a packed word; Clang measured about 0.217
and 0.160 ms respectively. The smaller packed representation helped one compiler
but its bit manipulation hurt the other. For the concurrent fan/Join bitset
scheduler, the shared atomic presence word increased state from 320 to 384
bytes. It took about 4.50 ms under GCC, versus 3.34 ms for independently
addressed presence bytes. Those bytes did not enlarge the already
cache-line-separated concurrent state.

For million-round work, all three presence choices were within measurement
noise. The fixed-frequency workless range runs were bimodal because worker wake
time dominated their approximately 0.1--0.16 ms duration; they established no
repeatable benefit from retaining presence that the Operation Graph proves
unnecessary. The strict literal form should use direct bytes unless a measured
state-layout benefit justifies an ordinary packed word, and should avoid packing
concurrently written presence merely to save bits. The no-storage result bounds
what a future optimizing backend could achieve by proving presence unnecessary.

SIMD over presence words does not help these graphs: no bulk presence query
exists, and the fastest measured lower bound has no presence word. Ordinary bit
instructions are useful for scanning readiness. SIMD becomes a candidate only if
a future program performs a genuine bulk query over non-concurrently modified
presence state.

### Generated instructions and compiler options

The benchmark's no-storage direct form contains no locked instruction, readiness
access, Join operation, indirect call, or presence access in its timed path. Its
tight loop is scalar; compiler vectorization reports applied only to benchmark
initialization outside the timed interval. The integer cursor adds one atomic
fetch-add per claimed batch. The function-pointer control adds an indirect call
for every unit.

Pointer-free direct code also has a scale boundary. In the retained generated
study, straight-line or bounded direct-region code was fastest through
approximately 4,096--16,384 synthetic Particle Operations, depending on compiler
and region size. At 65,536, a compact constant-operand loop held nearly constant
runtime while generated instruction bodies slowed: compact data was 55% faster
than GCC direct code and 26% faster than Clang's best measured direct-region
size. GCC hardware counters recorded approximately 0.93 million L1 instruction
misses for direct code versus about 6,100 for the compact loop over the measured
work.

A function per Particle Operation and a giant generated switch both had poor
large-scale compile and runtime behavior. GCC's 65,536-operation function table
emitted 5.25 MiB of text and ran at about 15.9 ns per Particle Operation, versus
0.527 ns for compact operands. Clang did not finish the corresponding monolithic
direct compile within 60 seconds, while compact data compiled in 0.08 seconds.
The literal backend therefore remains pointer-free while changing code layout:
small hot regions use direct C operations, and sufficiently regular large
regions use integer identity and compact operands.

`-O3` was not a universal improvement over `-O2`. It was neutral for direct
moderate and expensive work, and both faster and slower for sub-millisecond
scheduler cases depending on graph and compiler. It did not change the broad
choice among direct control, ranges, and individually claimable work, but fine
thresholds remain target measurements. Keep `-O2` as the benchmark baseline and
retain optimization level as a per-program item to measure. This study
intentionally excludes LTO and profile-guided optimization.

## Reproducing the benchmark

The graph and scheduler values are named at the top of
[`pointer_free_static_benchmark.c`](pointer_free_static_benchmark.c). For
example, this builds the fan/Join graph with single-bit claims:

```sh
gcc -std=c23 -O2 -march=native -mtune=native -pthread \
  -DPOINTER_FREE_GRAPH=2 -DPOINTER_FREE_SCHEDULER=4 \
  -DPOINTER_FREE_CLAIM_LIMIT=1 \
  pointer_free_static_benchmark.c -o pointer_free_static_benchmark
```

The executable accepts:

```text
executions fast-work slow-work slow-executions distribution workers warmups samples
```

For example, `60000 0 0 0 uniform 8 2 11` measures fine uniform work, and
`128 0 1000000 64 random 8 1 5` measures the random mixed-cost case. Every
result reports the compiled representation, state sizes, median, p90, and a
checksum that must remain identical across samples.

## Preserved implementation forms

[`pointer_free_static_example.c`](pointer_free_static_example.c) is the compact,
production-shaped reference implementation. Its generated configuration block
selects:

- `DEFINE_LITERAL_STRATEGY` as direct, contiguous direct ranges, or individually
  claimable integer identities;
- Action Execution and worker cardinalities;
- initial and dynamic claim limits;
- target cache-line size;
- the operation workload used to keep this example observable; and
- `DEFINE_LITERAL_PREPARE_WORKER`, a target hook for affinity or other worker
  preparation.

The direct and range configurations contain no runtime Join or readiness state.
The claimable configuration emits one initial cursor, a generated child-branch
readiness bitset, and one two-arrival Join per Action Execution. It never stores
a per-runnable function or state pointer. Pthreads necessarily receives one
static worker-entry function when a worker is created; no Particle Operation is
dispatched through that function pointer.

GCC and Clang emit no locked instruction for the direct or range reference
configurations and no indirect call in any per-runnable path. The claimable
configuration retains only the atomics required by its cursor, readiness word,
completion count, and Join.

An actual code generator emits the configuration values and replaces the
example-specific Action Execution state and Particle Operation functions with
the program's resolved graph. All conditionals then disappear during C
preprocessing and optimization.

### Literal fixture compilations

The fixture-specific examples in [`generated_examples`](generated_examples) are
exact examples of C that literal codegen should emit for the four source
fixtures, rather than configurable templates or deliberately conservative
demonstrations. Every Particle has a statically named presence byte, each Create
and Destroy writes `1` or `0`, a Move changes only the generated Position
association, and action triggering is a direct C call or a statically enumerated
dependency. They contain no configurable preprocessor choices, unused fallback
paths, or per-runnable function or state pointer.

The
[scheduler ADR's static-justification table](scheduler_and_join_adr.md#static-justification-for-the-generated-fixtures)
records the exact compiler proof or target-cost input that selects every
specialization below. No choice depends on recognizing the fixture by name or on
knowledge that exists only in the handwritten C example.

The emitted scheduling preserves every parallel relationship in the resolved
Operation Graph:

- `three_operation_chain` uses direct successors because only one Particle
  Operation can be runnable at a time.
- `multiway_join_and_fan_out` assigns one branch directly to its only pthread
  worker and executes the other branch on the calling worker. The required
  `pthread_join` proves both branches complete, so the two-arrival Join and
  readiness word erase from this exact schedule.
- `local_create_and_action_execution_run_in_parallel` likewise assigns its one
  independent chain directly to its only pthread worker. No worker searches or
  atomically claims work whose identity is already fixed by codegen.
- The
  [`creator_reverse_child_order_is_canonical_across_three_actions`](../../../../testdata/reference_graph/operation_graph_destructor_integration/creator_reverse_child_order_is_canonical_across_three_actions/operation_dependencies.json)
  fixture contains 36 Particle Operations across eight actions, 97 dependency
  arrivals, 23 successors with multiple dependency arrivals, and a 15-arrival
  final Join. Grouping arrivals contributed by the same completed Particle
  Operation proves that only 13 successors require atomic Joins. Its maximum
  Operation Graph antichain has seven members, which is an upper bound rather
  than a mandate to create seven workers. All ready work and completion fit in
  one atomic word.

The complex compilation initializes its statically known Join counts in the C
data image. A generated switch expresses successor topology directly. A worker
keeps the first newly runnable successor on its direct path and publishes every
additional successor by integer identity. Multiple arrivals from one completed
Particle Operation use one subtract by their exact multiplicity. If that one
operation contributes every arrival, the atomic Join disappears. The generated
program emits only the 13 remaining Join counters and keeps concurrently active
counters on separate cache lines; the first two Joins share one line because the
Operation Graph proves their lifetimes cannot overlap.

One completion can make several successors runnable. Their bits are accumulated
locally and published with one acquire-release OR after successor selection,
rather than one atomic OR per successor. The unique terminal Particle Operation
stores a reserved completion bit in the readiness word, eliminating both a
scheduler-wide remaining-operation decrement and a second completion cache line.
Independent publishers use acquire-release read-modify-write operations so that
a claiming worker acquires the synchronization chain for every bit in a combined
word.

The antichain permits seven simultaneous workers, but 10,000-run worker-count
matrices with both compilers selected one pthread worker plus the calling worker
for this effect-free fixture. Two total workers were approximately 18% faster
than seven with GCC and 57% faster with Clang in the first matrix, and remained
the winner when the 2--4 worker candidates were measured in reverse order. The
single readiness word still exposes every newly satisfied Particle Operation;
worker count limits simultaneous execution without encoding additional
dependencies.

At `-O2`, GCC and Clang remove the unobserved ordinary Particle presence writes
from all four programs. Only the serial chain reduces to clearing the integer
return register and returning. The two statically assigned parallel programs
retain their pthread calls, while the complex program also retains its readiness
atomics and Join arrivals. Full link-time optimization produces the same
distinction; it does not erase the fully scheduled programs.

Direct static pthread assignment removed 8--13 retired instructions and 68 bytes
of BSS from each small parallel fixture. Reversed 2,000-run and 5,000-run
hardware-counter measurements put their user-space cycles within approximately
1% of the original forms, with the winning direction changing for only the
local-chain fixture. Whole-process timing was mixed because pthread and process
startup dominate the effect-free work. The smaller static form is retained
because it eliminates the readiness read-modify-write operations and runtime
state without a repeatable cycle regression.

The fully specialized complex fixture improved by approximately 8% with GCC and
22% with Clang relative to the original seven-worker compilation in a final
reversed-order comparison. Its ELF text-plus-data-plus-BSS size fell from 10,706
to 4,782 bytes with GCC and from 7,682 to 4,307 bytes with Clang. Process and
pthread startup also dominate this fixture, so the retained decisions require
the individual transformation results below rather than one noisy whole-process
comparison.

The complex fixture also confirmed several program-specific specializations.
Using the calling thread as a worker instead of creating an equivalent extra
worker reduced measured cycles by about 4%, instructions by 2%, cache references
by 6%, and cache misses by 4% in the matched five-worker experiment. Static Join
initialization removed about 220 startup instructions. Replacing successor
tables with a generated switch removed about 1,100 instructions per process and
was neutral in cycles. Replacing a decrement after every Particle Operation with
one store from the unique terminal Particle Operation removed the locked
decrements and was neutral at whole-process scale. The source retains all four
changes because each removes work or runtime data without a measured regression.

The subsequent exact-output study removed still more generated work. Grouping
same-predecessor arrivals reduced emitted locked decrements and improved GCC
whole-process time by about 11% while remaining neutral under Clang. Emitting
only the 13 real atomic Joins reduced initialized data by 1,532 bytes and was
neutral or faster. Publishing all additional successors from one completion with
one atomic OR improved GCC by about 15% in its direct comparison and was neutral
under Clang. Sharing the readiness and completion word improved both compilers
by about 2%. A critical-path-based direct-successor reordering was rejected: it
improved GCC by 5--9% but repeatedly slowed Clang by 3--4%. C23 `uint8_t`
underlying types for the closed operation and claim-result enums were also
rejected: they left GCC's binary size unchanged, reduced Clang's by 88 bytes,
and slowed both compilers by approximately 6--8% in both execution orders. A
6-bit unsigned `_BitInt` operation identity enlarged both binaries and added 40
instructions under GCC and 197 under Clang. In 2,000-run hardware-counter
measurements it also added approximately 0.2--0.3% cycles.

Restricting the complex process to one measured cache topology group was neutral
to slower, including a roughly 28% Clang loss in the seven-worker comparison.
Generated affinity is therefore absent from this fixture; knowing a locality
relationship does not justify paying affinity costs when effect-free work has no
Particle working set to preserve.

The emitted C remains literal even when ordinary presence writes disappear from
machine code: that erasure is C dead-store elimination rather than a
Define-level proof that the Particle Operations may be removed.

A Define code generator that emitted an empty `main` directly would need a
whole-program semantic-effect and termination proof. That is a separate
optimizing-backend feature, not a requirement or responsibility of literal C
codegen.
