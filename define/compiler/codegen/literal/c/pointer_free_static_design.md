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
- A presence value is emitted only when later runtime behavior can observe or
  depend on presence. If control and dependency facts prove presence, no value
  is needed.
- Storage may be reused for non-overlapping Particle identities when address
  identity is not externally observable.

The fastest form of a statically proven Particle is therefore not a memory
location containing `1`; it is no runtime presence storage at all. The generated
operations and the storage required by live qualities are sufficient evidence of
its existence. If presence is runtime-dependent, the next choices are a direct
byte or a bit in an Action Execution-local word. An address should become the
Particle identity only when generated or foreign behavior can observe that
address. Otherwise, giving the Particle an address adds an identity operation
that the semantics do not require.

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
   Joins, completion atomics, and Particle presence proven by the graph all
   disappear.
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

The retained benchmark is Linux-only because it pins pthread workers with Linux
affinity APIs. Its processor-relax operation has x86 and AArch64 forms and a
portable compiler-fence fallback. These harness choices are not requirements of
the generated representation; another target needs a small threading, affinity,
and processor-relax adapter. GCC and Clang accepting the C source does not by
itself guarantee that every target has the same operating-system facilities or
atomic costs.

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

## Facts codegen needs

Optimal selection requires facts, not details of how the compiler currently
represents them:

- the resolved, transitively minimal Particle Operation dependency graph,
  including initially runnable operations, fanout, fan-in, and every point at
  which a caller may continue;
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
- estimated cost bounds and variance for Particle Operations and complete Action
  Executions, not merely an average cost;
- the number of independent Action Executions expected at each invocation and
  whether their cost ordering is known; and
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
[`three_operation_chain`](../../../../testdata/codegen/operation_graph_single_action_integration/three_operation_chain/operation_dependencies.json)

```text
create item -> move item to dest -> destroy dest
```

The move changes the compile-time Position association. The same Particle state
is used before and after it.

### Multiway Join and fanout

Source:
[`multiway_join_and_fan_out`](../../../../testdata/codegen/operation_graph_single_action_integration/multiway_join_and_fan_out/operation_dependencies.json)

```text
                              create b -> destroy b
create box -> fanout                                      -> destroy box
                              create a -> destroy a
```

One branch runs directly. The other is published by static identity. The final
destroy uses a two-arrival Join.

### Parallel local and triggered Action Execution chains

Source:
[`local_create_and_action_execution_run_in_parallel`](../../../../testdata/codegen/operation_graph_two_actions_integration/local_create_and_action_execution_run_in_parallel/operation_dependencies.json)

```text
create local item -> destroy local item
create trigger Particle -> create other item -> destroy other item
```

Both roots are initially runnable. Benchmark completion joins the two chains so
that the harness can validate the complete Action Execution.

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

### Outer and inner parallelism

With one fan/Join Action Execution whose Particle Operations each perform one
million rounds, direct execution took about 6.4 ms while exposing the two
branches to two workers took about 4.3 ms. The parallel-chain graph measured
about 5.4 versus 3.3 ms. Whole-word and eight-bit claims lost that parallelism
by giving both expensive roots to one worker.

At eight uniformly expensive Action Executions, contiguous direct ranges already
occupied eight workers and matched the individually claimable forms. Thus the
generated decision is based on runnable breadth, not merely whether an Operation
Graph contains parallel Particle Operations.

### Integer identity versus function pointers

The function-pointer form adds a 16-byte table entry per initially runnable unit
and leaves an indirect `call` in GCC and Clang assembly. It offered no
repeatable speedup. With 64-unit claims, the workless chain took 0.45-0.56 ms
with integer identities and 0.71-0.86 ms with function pointers under GCC. The
workless parallel graph took 0.77-0.81 versus 1.23-1.44 ms. At million-round
costs the forms became indistinguishable because generated operation work
dominated both dispatch paths.

Use integer identities and generated direct dispatch. A function pointer is a
fallback for code that cannot be statically enumerated, not the fast literal
representation.

### Particle presence

The three presence variants all produce the same checksum:

- no presence storage when the Operation Graph and control flow prove it;
- one byte on each directly addressed Particle state; and
- one bit per Particle in an Action Execution-local word.

No storage was consistently fastest and always smallest. For compact direct
fan/Join state, it used 56 bytes per Action Execution and a workless run took
about 0.038 ms. Byte presence increased the state to 80 bytes and the run to
about 0.052 ms. A sequential packed word retained the 56-byte state and took
about 0.048-0.054 ms.

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
noise. Codegen should still remove presence first. If runtime presence remains,
use direct bytes unless a measured state-layout benefit justifies an ordinary
packed word, and avoid packing concurrently written presence merely to save
bits.

SIMD over presence words does not help these graphs: no bulk presence query
exists, and the best proven representation has no presence word. Ordinary bit
instructions are useful for scanning readiness. SIMD becomes a candidate only if
a future program performs a genuine bulk query over non-concurrently modified
presence state.

### Generated instructions and compiler options

The direct form's timed path contains no locked instruction, readiness access,
Join operation, indirect call, or presence access. Its tight loop is scalar;
compiler vectorization reports applied only to benchmark initialization outside
the timed interval. The integer cursor adds one atomic fetch-add per claimed
batch. The function-pointer control adds an indirect call for every unit.

`-O3` was not a universal improvement over `-O2`. It was neutral for direct
moderate and expensive work, and both faster and slower for sub-millisecond
scheduler cases depending on graph and compiler. The representation choices were
unchanged. Keep `-O2` as the benchmark baseline and retain optimization level as
a per-program item to measure. This study intentionally excludes LTO and
profile-guided optimization.

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

### Whole-program erasure of the fixtures

No macro-free fixture compilations are retained. In all three original Define
programs, no Particle Operation invokes observable quality behavior, no Particle
occupancy survives program completion, and no Particle identity escapes.
Removing those operations also removes every dependency, Join, and scheduling
decision. The maximally optimized real compilation of each program is therefore
the same empty successful `main`.

Under both GCC and Clang, that `main` consists only of clearing the integer
return register and returning on the measured x86-64 target. Keeping three
copies of it would record no additional representation or code-generation
decision.

This does not imply that every pre-value Define program can erase. Termination
is observable, so an unbounded action-trigger cycle cannot become a successful
empty program. Particle state that crosses a caller or separate-compilation
boundary must satisfy that boundary's contract, and tracing makes the traced
events observable. Future value and foreign operations will introduce ordinary
observable effects. However, a closed, terminating program whose complete
resolved graph only changes temporary Particle occupancy is a valid candidate
for whole-program erasure, regardless of how complicated that graph was before
the proof.
