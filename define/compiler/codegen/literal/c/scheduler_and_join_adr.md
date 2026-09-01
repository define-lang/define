# Literal C Scheduler and Join

- Status: Accepted
- Date: 2026-08-31
- Scope: Initial literal C runtime design

## Context

The literal C backend needs to preserve the exact concurrency of the resolved
Operation Graph while representing its runtime behavior directly enough to
remain useful for debugging and education. The shared
[Operation Graph execution design](../../../operation_graph_execution_design.md)
remains authoritative for planning and code generation, and the
[language specification](../../../../spec/spec.md) remains authoritative for
Define semantics.

The runtime must support:

- direct execution of statically known Action Fragment and Binding Hole
  successors;
- parallel fanout without adding serialization;
- multi-arrival Joins;
- repeated Action Executions with distinct runtime state; and
- work sharing across processors without making a global queue the common path.

The design also needs to account for machines whose processors are divided
between cache-coherence or NUMA topology groups. On such machines, moving a Join
cache line or frequently accessed Particle data between groups can cost far more
than the instruction sequence used for the atomic decrement.

## Decision

### Scheduler structure

Use one owner-biased Chase-Lev deque per worker. A worker pushes and pops at one
end of its own deque, while other workers steal from the other end. Do not use a
global multi-producer, multi-consumer queue as the ordinary scheduling path.

Each scheduler task records a function, its execution state, and its preferred
topology group. Each topology group has an injection queue for tasks submitted
from another group. A worker searches for work in this order:

1. its current statically known successor;
2. its local deque;
3. its topology group's injection queue;
4. another worker's deque in the same topology group; and
5. another topology group's injection queue or worker deques.

Generated code runs one statically known fanout branch directly and submits the
other branches. A satisfied Join also invokes a statically known continuation
directly when its topology preference permits. Generated code should use a
direct tail call for these edges rather than returning a task merely to perform
an indirect call in the scheduler loop.

An indirect function call remains necessary for a task recovered from a deque or
injection queue. Keeping static successors on the direct path reduces the
frequency and target diversity of these indirect calls without inlining Action
Fragments.

When cost and cardinality facts justify it, a thief may claim a bounded batch
with one compare-exchange and republish all but its directly executed task to
its own deque with one release. The same policy applies to a proven
single-producer, multiple-consumer injection queue whose total lifetime enqueue
count cannot exceed its capacity. Unknown or strongly heterogeneous costs use
single-task claims. A worker keeps a claimed batch private only when codegen can
bound the batch's total cost tightly enough that preventing redistribution does
not compromise useful concurrency.

### Topology policy

Workers prefer same-group work before crossing a cache-coherence or NUMA
boundary. The exact delay before cross-group stealing is a tunable scheduler
policy, not a semantic property and not a portable constant.

The initial implementation may expose a failed-local-poll threshold. A later
runtime should use inexpensive, approximate group surplus and idle-worker
signals so that it crosses promptly when one group has materially more work.
Those signals must be updated in batches; a shared counter updated for every
task would recreate the contention this design avoids.

Continuation placement depends on the continuation's known Particle access:

- run on the final-arriving worker when the continuation is small or has no
  strong topology preference; or
- submit to its preferred topology group when it will access a substantial
  group-local Particle region.

### Join representation

Use one flat atomic counter for a multi-arrival Join. Initialize the counter to
the number of predecessors before publishing predecessor work. Each predecessor
publishes its Particle writes and acquires the preceding arrivals with an
acquire-release decrement. The predecessor that observes the previous value `1`
directly releases the continuation:

```c
bool literal_join_arrive(LiteralJoin *join) {
    unsigned int previous = atomic_fetch_sub_explicit(
        &join->remaining, 1, memory_order_acq_rel
    );
    return previous == 1;
}
```

The acquire-release operations form a synchronization chain that publishes every
predecessor's Particle writes to the continuation. A Particle with one writer,
read only after this Join, therefore does not require its own atomic storage.

On the measured x86-64 machine, this compiles to a locked decrement and branch
without a separate hardware fence. A release decrement plus a final acquire
fence may allow weaker architectures to avoid acquire ordering on non-final
arrivals. That refinement is deferred until it is benchmarked on such a machine
and the runtime's race-checking strategy accounts for fence synchronization.

Do not construct a one-arrival Join. Preserve the shared execution design's
direct call for that case.

Dependency-arrival multiplicity does not necessarily imply multiple completing
predecessors. When one completed Particle Operation contributes `count` arrivals
to the same successor, emit one acquire-release subtraction by `count` and
proceed when the previous value equals `count`. If that Particle Operation
contributes every arrival, no atomic Join is required. Codegen must therefore
retain the predecessor identity and multiplicity of every arrival rather than
reducing a dependency to its total count too early.

Keep unrelated concurrently active Join counters on separate cache lines to
avoid false sharing. Joins whose lifetimes provably cannot overlap may share a
cache line. Do not pad every Particle or every scheduler task.

When one Particle Operation completion makes several successors runnable in the
same readiness word, accumulate their bits locally and publish them with one
acquire-release read-modify-write operation. Keep one newly satisfied successor
on the direct path. Independent publishers of the same readiness word still
require an acquire-release synchronization chain.

### Worker activation

Available processor count is a target or runtime fact; active worker count is a
program-specific decision. Runnable breadth and physical cores are upper bounds,
not requirements to create that many workers. For work substantial enough to
amortize activation, start with at most one worker per physical core. The
effect-free 36-operation generated fixture was fastest with two total workers
despite an antichain width of seven.

Activate SMT siblings only when runnable breadth exceeds the physical-worker
count and the estimated working set is unlikely to saturate shared caches or
memory bandwidth. Long Action Fragments alone are not sufficient evidence: SMT
improved dependency-heavy computation with abundant runnable work, but hurt
sparse computation and large per-worker memory regions. The generated Operation
Graph is unchanged by this choice.

### Compilation policy

Use C23 with a current GCC or Clang when the target toolchain supports it. The
provisional release preset for the scheduler and generated code in one C
translation unit is `-std=c23 -O2` plus the compiler's explicit ISA and tuning
selection for the target processor. `-march=native` is appropriate only when the
binary will run on the build machine; a cross-build or distributable binary must
name its actual target or baseline instead.

`-O2` is a provisional performance default, not a semantic requirement. It was
the most balanced setting across the current complete-runtime workloads for both
compilers. `-O3` was sometimes faster but did not win consistently, and the
size-oriented modes changed scheduler behavior enough to produce large gains in
one workload and large losses in another. Do not add universal inlining, branch,
hot/cold, or code-alignment directives to the generated source on the basis of
these synthetic workloads.

Do not use `-Ofast` as a general Define build setting. It provided no stable
scheduler improvement and permits transformations that may change numerical
semantics in generated Action Fragments.

Splitting generated actions across C translation units does not inherently
prevent whole-program elimination. In a three-translation-unit, serialized model
of the literal two-action fixture, both GCC 16.2 and Clang 22 retained the call
from `main` without link-time optimization. Compiling and linking every file
with `-O2 -flto` allowed both toolchains to reduce `main` to clearing its return
register and returning, exactly as in the single-translation-unit build.

This result depends on the final link seeing every relevant definition and being
allowed to internalize it. An external ABI, symbol interposition, dynamically
linked action implementation, escaped address, `volatile` access, or foreign
behavior that can observe Particle state may require calls or state updates to
remain. Codegen should keep generated symbols hidden when the compilation
boundary permits it. Link-time optimization is therefore capable of preserving
single-translation-unit optimization across per-action C files, but is not a
substitute for declaring the compilation boundary accurately.

That narrow elimination result does not apply when emitted code preserves
parallel fanout and Join execution. Full link-time optimization removes the
unobserved Particle presence writes from the scheduled fixture compilations, but
GCC and Clang retain pthread creation and joining. They also retain readiness
atomics and Join arrivals when codegen cannot replace them with a static worker
assignment and the required pthread join, as it can for the small fixed-fanout
fixtures. Splitting scheduled actions across C translation units should not add
an optimization barrier when full link-time optimization and visibility permit
internalization, but it does not make required scheduling semantically
removable.

## Information required by C codegen

C codegen should receive facts and constraints rather than representation
decisions. It combines a fully annotated execution and storage plan with target
information and then chooses C types, numeric values, layout, direct calls, and
runtime policy. Missing information must remain explicitly unknown rather than
being interpreted as small, local, or unlikely.

### Execution relationships

The Action Plan must provide:

- every Action Fragment and Binding Hole fanout;
- exact predecessor and successor relationships;
- the identity and multiplicity of every dependency arrival, along with total
  Join dependency counts;
- which successors are statically known;
- which branches may become runnable concurrently; and
- Action Execution initialization, Guarantee publication, and destruction
  relationships kept distinct from Particle Operation dependencies.

These relationships must already express the complete resolved Operation Graph.
C codegen does not infer dependencies, repair the plan, or add serialization.

### Particle access

For every Action Fragment, the plan must identify:

- the Particles it reads, writes, moves, or destroys;
- the approximate number of bytes accessed;
- access order and expected reuse;
- whether each Particle has one writer;
- whether every read occurs after a particular Join; and
- possible aliasing and whether address identity is observable.

These facts determine when ordinary C storage is sufficient, which writes are
published by a Join, and which Action Fragments have data affinity.

### Runtime-state lifetime and cardinality

The plan must identify:

- the state belonging to each Action Execution;
- state reuse and the point at which reuse is safe;
- whether Action Executions can overlap;
- whether state escapes to another action or foreign code;
- exact or bounded fan-in and fanout;
- exact or bounded numbers of Action Executions; and
- known upper bounds on simultaneously live Action Executions, Joins, and
  runnable Action Fragments;
- exact producers and possible consumers for every generated injection queue;
  and
- bounds on both simultaneous queue occupancy and total lifetime enqueues.

Every count should be classified as exact, bounded, or unbounded. These facts
allow codegen to choose counter widths and storage representations without
assuming that a program is small.

### Identity and enum domains

For every value represented by a C enum or another numeric discriminant, codegen
must receive:

- the complete semantic domain known at the compilation boundary;
- deterministic identity across separately generated actions;
- whether the domain is closed for the compiled program;
- whether numeric values are externally observable through an ABI,
  serialization, debugging, or foreign code;
- whether later extension must preserve existing numeric values; and
- expected value frequencies, when known.

Codegen chooses widths and numeric assignments from these facts. An earlier
compiler stage supplies numeric values only when compatibility across a
compilation boundary makes the values part of an external contract.

### Abstract locality

The compiler must describe locality relationships without assigning physical
topology groups. Required facts include:

- Action Fragments that access the same Particle data;
- continuations that reuse data written by their predecessors;
- concurrently runnable Action Fragments that mostly access disjoint data;
- Join participants associated with different data regions; and
- estimated working-set size for each data region.

Concrete cache, CCD, and NUMA placement belongs to target-specific codegen or
runtime policy. The compiler-provided relationships remain valid when the same
generated program runs on a different machine.

### Cost and profile evidence

When available, codegen should receive:

- estimated Action Fragment instruction or operation cost;
- expected branch probabilities;
- expected fanout distributions;
- expected Join arrival skew;
- likely indirect-call target distributions; and
- measured execution frequency and Particle access volume.

Each value must state whether it is proven by static analysis, measured by
profile-guided optimization, estimated with a confidence level, or unknown.

### Compilation boundaries

Codegen must know:

- whether the reachable Action set is closed;
- which actions are generated separately;
- which functions and data participate in an external ABI;
- which relationships remain stable for an action regardless of its callers; and
- which optional whole-program facts are available without violating callee
  independence.

An optional whole-program optimization stage may provide additional facts, but
the reusable plan for an action cannot depend on inspecting indirect callers.

### Target description

The execution and storage plan is accompanied by target information describing:

- ISA and ABI;
- operating system, libc, and available thread facilities;
- supported atomic widths and memory-order costs;
- whether the atomic types required by the scheduler are lock-free;
- cache-line size;
- physical-core, SMT, cache, and NUMA topology, or whether those properties are
  discoverable only at runtime; and
- processor-affinity, aligned-allocation, waiting, waking, and processor-relax
  facilities; and
- compiler capabilities such as guaranteed tail calls, link-time optimization,
  and function multiversioning.

Target information is not a Define semantic property. It can vary between C
builds or at runtime without changing the Action Plan.

### Generated synchronization contract

This contract applies to the specialized generated paths demonstrated by the
exact fixtures, not to the reusable general scheduler. Those paths use no mutex,
read-write lock, semaphore, `atomic_flag` lock, or explicit C atomic fence. They
use only ordinary memory, lock-free C atomic loads and stores, and lock-free
atomic read-modify-write operations selected from the proven dependency shape. A
target on which a required C atomic type is not lock-free cannot silently use
the C library's lock-based fallback while claiming to satisfy this contract;
codegen must choose another representation or reject that target configuration.

On x86-64, the complex generated fixture's atomic subtract, OR, and
compare-exchange operations appear in disassembly as `lock decl`, `lock subl`,
`lock or`, and `lock cmpxchg`. The `lock` prefix is the processor's atomic
read-modify-write mechanism, not a generated software lock. GCC and Clang emit
no `mfence`, `lfence`, or `sfence` for these fixtures. The serial fixture and
the two statically assigned parallel fixtures emit no lock-prefixed instruction
at all.

The reusable scheduler does contain explicit release and sequentially consistent
C fences required by its current Chase-Lev work deque. On the measured x86-64
target, its sequentially consistent fence compiles to a locked dummy OR rather
than `mfence`; the release fences require no machine instruction there. Removing
these fences without changing the deque algorithm would be incorrect. A
generated path that proves it does not need concurrent deque ownership or
stealing can omit the deque and its fences, as the exact fixtures do.

This is an algorithmic contract, not a promise about library implementation. The
current examples call `pthread_create` and `pthread_join`; libc and the kernel
may use locks, futexes, barriers, or scheduler operations while creating,
waiting for, and destroying operating-system threads. A target-specific worker
runtime can move that cost outside Action Execution, but it cannot create
parallel execution contexts without using an operating-system facility at some
boundary.

Acquire, release, and acquire-release are required semantic relationships even
when the target needs no separate fence instruction. A weaker-memory-order ISA
may encode them in its atomic or load/store instructions or may require an
explicit barrier. Avoiding all target barrier instructions is therefore a
measured target property, not a portable C guarantee.

### Platform boundary

The flat Join, scheduler task representation, Chase-Lev deque, bounded
multi-producer, multi-consumer queue, and C11 memory-order relationships are
shared algorithmic logic. Their performance assumptions still require the
selected atomic types to be lock-free on the target.

The following facilities belong to target runtime support:

- thread creation, joining, and barriers;
- available-processor enumeration and thread affinity;
- cache, core, SMT, and NUMA discovery;
- aligned allocation;
- processor-relax instructions; and
- efficient waiting and waking.

GCC and Clang can generate instructions for many targets, but a cross-compiler
does not supply the target operating-system APIs, SDK, headers, libraries,
linker, or runtime objects. Supporting another platform therefore requires its
target toolchain and implementations of the required runtime facilities.

Every target property must be classified as one of:

- fixed at C build time;
- discoverable when the generated program starts; or
- unavailable on that target.

A runtime-discovered value cannot be used as a C constant expression. In
particular, a cache-line size discovered after startup cannot determine the
alignment of a statically declared C type. Such alignment comes from the target
configuration used for the C build, while runtime cache information can still
inform scheduling and dynamic allocation.

Topology groups are a scheduler interpretation of hardware relationships, not a
standard operating-system quantity. A target may derive them from shared caches,
NUMA nodes, or another documented relationship. When the necessary relationship
is unavailable, the target policy must record that fact rather than pretending
to know a topology.

Queue capacity is not a target property and cannot be discovered from the
operating system. It requires a proven program bound or an explicit runtime
capacity policy.

### Certainty

Every optimization fact must be classified as one of:

- known exactly;
- a proven upper or lower bound;
- a profile estimate with stated confidence; or
- unknown.

The existing Action Plan already provides much of the correctness topology. The
additional information needed for optimal C representation is primarily Particle
access and lifetime data, cardinality bounds, identity-domain constraints, cost
and profile evidence, abstract locality relationships, and the target
description.

### Static justification for the generated fixtures

Every specialization in the fixture-specific output follows from a compiler fact
or an explicitly identified target-cost decision:

| Generated decision                                            | Information codegen must receive or prove                                                                                                                                                                                                                    |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Direct calls for the serial chain                             | Exactly one initially runnable Particle Operation, at most one newly satisfied successor after every completion, and no foreign or runtime-selected work                                                                                                     |
| Direct pthread assignment in each small parallel fixture      | Exactly two independent chains, one invocation of each chain, one dedicated worker, and no other work that could use shared claiming                                                                                                                         |
| Use `pthread_join` as the final dependency satisfaction       | Every operation assigned to the pthread precedes the final continuation or the end of the Action Execution, the calling worker completes the other predecessor chain, and joining is already required before the Action Execution state can cease to be used |
| Omit a readiness word for statically assigned work            | The producer, only consumer, publication point, and single lifetime of the runnable identity are all exact                                                                                                                                                   |
| Group several arrivals into one subtraction                   | Dependency arrivals retain their completing predecessor identity and multiplicity, so codegen knows that one completion contributes the entire group                                                                                                         |
| Omit ten nominal multi-arrival Joins                          | After grouping, each successor has exactly one distinct completing predecessor                                                                                                                                                                               |
| Emit the remaining 13 Join counters in the C data image       | Their distinct completing-predecessor counts are exact, the compiled program creates one bounded instance of each, and initialization precedes publication of all predecessor work                                                                           |
| Share one cache line between the first two Joins              | Their exact liveness intervals cannot overlap; every other concurrently writable Join relationship remains isolated                                                                                                                                          |
| Keep one successor direct and publish the others              | Every successor identity and publication point is static, and no dependency requires the direct successor to re-enter a queue first                                                                                                                          |
| Publish several newly satisfied identities with one atomic OR | One completing worker discovers all of those identities, they occupy distinct bits of the same ready word, and one release can publish the same predecessor effects for the group                                                                            |
| Use acquire-release publication                               | More than one worker may publish into the same word, so publishers must form the synchronization chain acquired by a claimant                                                                                                                                |
| Reserve a completion bit in the readiness word                | The identity domain uses at most 63 bits, there is one terminal Particle Operation, every other Particle Operation transitively precedes it, and no ready identity can remain when it completes                                                              |
| Use two total workers although antichain width is seven       | Seven is a proven concurrency upper bound; static operation costs, absence of blocking and foreign behavior, target thread-activation costs, and benchmark evidence select the smaller active count                                                          |
| Omit generated affinity                                       | The exact Particle access sets contain no retained working set whose locality repays affinity setup on the measured target                                                                                                                                   |
| Use ordinary compact Particle presence bytes                  | Presence addresses do not escape, no foreign behavior observes them, and the closed `-O2` compilation boundary lets ordinary C dead-store elimination remove unobserved writes                                                                               |
| Use one 64-bit ready word instead of queues                   | There are only 36 static identities, at most one unclaimed instance of each exists, Action Executions do not overlap, and no operation creates unbounded or runtime-selected work                                                                            |
| Retain ordinary C enums                                       | The identity domains are closed, but target measurements rejected the smaller fixed-enum and `_BitInt` representations                                                                                                                                       |

The dependency, identity, lifetime, terminal, and escape statements in this
table are correctness proofs. Worker count, affinity, enum representation, and
similar cost choices are target-policy decisions and require measurements or a
calibrated target cost model. Codegen must not turn a cost estimate into a
semantic assumption: when a proof is unavailable it must retain claimability,
separate live state, and the required synchronization.

### Example scope

The accompanying C example is the Linux, glibc, and pthreads reference used for
the initial measurements. Its 64-byte alignment and fixed bounds reproduce the
measured target configuration; they are not cross-platform discoveries. The
example checks its lock-free atomic assumptions and rejects non-Linux builds
rather than implying portability it has not demonstrated.

The example deliberately does not introduce a shared platform interface. Such an
interface should be designed when a second target supplies concrete requirements
and can validate the shared boundary.

## Benchmark basis

The decision was tested on an AMD Ryzen 9 9950X with 16 physical cores, 32
logical processors, and two cache-coherence/NUMA groups. The harness used
bounded multi-producer, multi-consumer queues, C-race-free Chase-Lev deques,
worker affinity, direct-successor bypass, flat and two-level Joins, and
synthetic serial, wide fanout, and balanced binary fork-Join graphs. It was
compiled with GCC 16.2.1 and Clang 22.1.8 at `-O3 -march=native -mtune=native`.

The reported task cost is total elapsed wall time divided by all executed
scheduler tasks, so it measures aggregate throughput rather than individual task
latency. Representative medians were:

| Case                                                        |                        Selected design |                                          Comparison |
| ----------------------------------------------------------- | -------------------------------------: | --------------------------------------------------: |
| Serial chain, 16 workers                                    |             direct bypass: 1.7 ns/task |           local queue: 294 ns; global queue: 791 ns |
| Workless 4,096-arrival Join, 32 workers                     | topology-aware flat Join: 55.8 ns/task | global queue: 129 ns; unrestricted stealing: 196 ns |
| 4,096-arrival Join with work, 16 workers                    | topology-aware flat Join: 52.6 ns/task | global queue: 160 ns; unrestricted stealing: 200 ns |
| Balanced binary fork-Join with substantial work, 32 workers |    unrestricted stealing: 37.0 ns/task |                    topology-aware stealing: 37.6 ns |
| Topology-skewed computation                                 |   cross immediately: about 147 ns/task |                   fixed 64-poll delay: about 218 ns |
| Static per-worker SPSC distribution, 16 workers             |   local deque and stealing: 62 ns/task |                            SPSC distribution: 92 ns |

Linux `perf` counters on the wide workload showed that topology-aware scheduling
used approximately 75% fewer active cycles, 76% fewer cache references, and 68%
fewer cache misses than unrestricted stealing. AMD uProf recorded approximately
four times as many cycle samples and three times as many L1 refill and L2 access
samples for unrestricted stealing. GCC and Clang differed by approximately 0–3%
on the finalists and did not change the architectural choice.

The benchmark harness passed AddressSanitizer, UndefinedBehaviorSanitizer, and
ThreadSanitizer checks. The generic MPMC, one-group batched, one-group
private-batched, and exact two-worker SPMC generated forms also passed GCC
`-fanalyzer`, `cppcheck`, and Clang's analyzer, bugprone, performance, and
portability checks. Analyzer diagnostics for intentional cache-line padding,
including the reference implementation directly in the benchmark translation
unit, standard `void *` allocation conversions, and bounded standard-library
calls were classified as design constraints or false positives rather than
source changes.

### Single-translation-unit compiler study

A follow-up study exercised the accompanying scheduler and its actual
acquire-release `LiteralJoin` in one C translation unit. It covered a serial
direct-successor chain, two-group fanout, one-group stealing, topology-skewed
work, and both workless and 64-round synthetic Action Fragments. Serial samples
used 2,000,000 tasks; parallel samples used 60,000 tasks. Each result below is
the median of three outer runs, with each outer run taking the median of 15
measured samples after warmup. Scheduler initialization, worker creation,
execution, joining, and destruction were timed; construction of the synthetic
task array was not.

Representative results in nanoseconds per task were:

| Compiler setting | Serial | Two-group workless | Two-group work | Same-group workless | Same-group work |
| ---------------- | -----: | -----------------: | -------------: | ------------------: | --------------: |
| GCC `-O2`        |   2.66 |              45.10 |          96.88 |               97.62 |           89.16 |
| GCC `-O3`        |   2.69 |              45.52 |         103.98 |               95.80 |           89.21 |
| GCC `-Os`        |   2.56 |              82.94 |          97.73 |               64.78 |           73.84 |
| GCC `-Oz`        |   2.70 |              80.48 |          98.89 |               64.70 |           76.70 |
| Clang `-O2`      |   2.55 |              37.41 |         101.34 |              102.72 |           91.46 |
| Clang `-O3`      |   2.53 |              39.76 |         103.49 |              100.94 |           91.39 |
| Clang `-Os`      |   2.51 |              39.35 |         103.62 |              105.09 |           92.74 |
| Clang `-Oz`      |   2.75 |              40.84 |         104.60 |              102.95 |           93.75 |

The GCC size-oriented result is real but workload-specific. On the same-group
workless workload, repeated `perf stat` measurements showed GCC `-Os` executing
approximately 36% fewer cycles and 68% fewer cache references than GCC `-O3`. On
the two-group workless workload, however, `-Os` used approximately 86% more
cycles and took approximately 82% longer. A smaller scheduler binary is
therefore not a generally faster scheduler; compiler decisions can change how
submission rate interacts with stealing and cache-line movement.

The study also screened:

- C11, C17, and C23 language modes;
- generic, `-mtune=native`, `-march=native`, and combined target selection;
- default, disabled, 16-byte, 32-byte, and 64-byte function and loop alignment;
- disabled inlining, individual GCC inlining controls and thresholds, and
  additional size-mode inlining;
- `-Ofast`, loop unrolling, frame-pointer retention, PLT avoidance, semantic
  interposition control, section garbage collection, and unwind-table removal;
  and
- `restrict`, proven-invariant assumptions or check removal, hot/cold and
  always-inline/no-inline attributes, unlikely failure branches, and an unlikely
  final Join arrival.

GCC and Clang emitted byte-for-byte identical binaries for this runtime in C11,
C17, and C23 modes. For both compilers, `-march=native` also emitted the same
binary with or without an additional `-mtune=native`, and
`-fno-semantic-interposition` did not change the binary. The other compiler and
source controls produced no stable improvement across the workload set. In
particular, `restrict`, forced Join inlining, and the final-arrival hint did not
materially change generated code. No tuning directive from this study belongs in
the example source.

### Generated scheduler specialization study

A subsequent study treated the scheduler as generated program-specific code
rather than a reusable runtime library. Every candidate was compiled with both
GCC and Clang at C23 `-O2 -march=native`, tested in both execution orders, and
screened across workless, 64-round, mixed approximately one-millisecond, and
private-memory Action Fragments. Candidates with only a favorable isolated run
were rejected. The findings are recorded here so later decisions do not depend
on benchmark binaries or conversation history.

The strongest result was exact queue sizing. Reducing a 65,536-entry queue to a
proven 128-entry capacity reduced complete-runtime time by approximately 80% for
128 fine tasks: about 0.49 ms became 0.09 ms with eight workers, and about 1.0
ms became 0.18--0.20 ms with 16 logical workers. It also improved a mixed
approximately one-millisecond case by approximately 5% with physical workers and
16% with SMT. The gain comes principally from avoiding allocation and
initialization of queue state that the generated program cannot use. Codegen
should therefore emit the smallest safe power-of-two capacity from a proven
simultaneously queued-task bound. When no such bound exists, it must retain a
runtime capacity policy.

Removing the owner-deque capacity check after proving it unreachable was a
repeatable 1.5--3% improvement with eight workers and 4--6% with 16 logical
workers in queue-heavy cases, and was neutral for approximately one-millisecond
Action Fragments. This check should be omitted only from a deque whose bound is
proven. Removing the index mask as well was rejected: it helped some
physical-worker cases but regressed GCC with SMT by 6--8% and Clang by as much
as 3%.

For topology groups of at most eight physical workers, one shared, prefiltered
worker list per group was the best general victim representation. Compared with
generating a random start and scanning every worker, it reduced workless
two-group time by approximately 35--43%, topology-skewed time by approximately
62--68%, two-group SMT time by approximately 27--31%, and one-group eight-worker
time by approximately 6--13%. With 16 same-group logical workers, however, the
original random scan was 2--10% faster. The generated scheduler should select
between these representations from its exact worker topology; random-number
generation is not useful by itself.

When codegen proves that a program uses one topology group, omitting injection
queues, cross-group search, and remote-submission routing was neutral to
approximately 4% faster. It also avoids allocating semantically unreachable
state. These paths should not be emitted for such a program even where their
hot-path timing is neutral.

The startup barrier was unnecessary because the initial task is published before
thread creation. Removing it improved fine cases by approximately 5--16% and was
neutral for 100-microsecond through one-millisecond work. The generated
scheduler should not construct or wait at this barrier.

On this x86-64 target, the sequentially consistent fence between the two acquire
loads in the thief path compiled to a locked instruction. A target-specific x86
version relying on load-load ordering removed that instruction. It improved
physical-worker queue-heavy cases by approximately 2--3% and Clang's 16-worker
case by 5--7%; longer reversed GCC runs at 16 workers were neutral within 0.5%,
and realistic Action Fragment costs were neutral. This specialization is
accepted only for x86. The portable C path retains the fence until an equivalent
target-specific proof and measurement exist.

Two topology groups containing one worker each permit direct generation of the
only possible victim and the other group number. Removing the generic group
loops and victim search helped some topology-skewed fine cases, hurt some
balanced workless cases, and was neutral within approximately 1% once Action
Fragments reached millisecond or private-memory scale. Fixed cross-group delays
of 0, 1, 8, 64, and 256 polls were likewise indistinguishable for the realistic
costs; zero or one poll usually won the 64-round cases, while no value won every
workless sample. Exact topology still justifies removing impossible searches,
but a locality delay requires program locality evidence or runtime feedback
rather than a universal constant.

An apparent SPSC injection-queue win was invalid: another group was also allowed
to consume that queue. A corrected SPSC design prevented cross-group consumption
but ceased to be work-conserving and took approximately twice as long when all
expensive tasks preferred one group. It is rejected as a general queue. A
single-producer, multiple-consumer candidate with a proven total enqueue bound
retained cross-group help and removed per-cell sequence state; at 128 entries it
was approximately neutral against the full bounded MPMC queue. At 65,536 entries
it reduced workless time by approximately 35--45% and 64-round time by 6--14%,
while 1,000-round and millisecond-scale work were neutral. This representation
is accepted only when codegen proves both that the queue has one producer and
that total lifetime enqueues cannot exceed its capacity. A bound only on
simultaneous queued tasks is insufficient because the sequence-free cells cannot
be reused safely.

Batch claiming produced the largest hot-path improvement. A thief that claimed
up to 64 tasks with one compare-exchange made 60,000 fine one-group tasks
approximately three to four times faster, roughly halved the topology-skewed
64-round case, improved a large mixed-cost case by approximately 3--5%, and was
neutral for small millisecond and memory cases. Caps of 256 or 512 improved the
uniform fine cases further. Applying the same technique to the proven-bound SPMC
injection queue improved 60,000 balanced workless tasks by as much as
approximately 2.5 times and the 64-round case by about 10%.

A final post-cleanup confirmation compiled the retained source with both
compilers and ran three reversed-order outer repetitions; each repetition was
the median of 15 samples after two warmups. The following complete-runtime
medians are in milliseconds. The selected form republishes a batch of at most
256 tasks, uses the measured random victim scan for the 16-worker topology, and
uses the proven-bound SPMC injection queue for the exact two-worker topology.

| Topology and work                         | GCC single claim | GCC selected | Clang single claim | Clang selected |
| ----------------------------------------- | ---------------: | -----------: | -----------------: | -------------: |
| One group, 60,000 workless tasks          |             5.12 |         1.25 |               5.12 |           1.13 |
| One group, 60,000 64-round tasks          |             4.61 |         1.39 |               4.61 |           1.40 |
| One group, 128 mixed approximately 1 ms   |             9.23 |         9.26 |               9.22 |           9.22 |
| One group, 64 mixed 256 KiB memory tasks  |             4.18 |         4.16 |               4.20 |           4.15 |
| 16 logical workers, 60,000 workless tasks |             6.06 |         1.73 |               5.75 |           1.63 |
| 16 logical workers, 60,000 64-round tasks |             6.20 |         1.61 |               5.54 |           1.60 |
| Two one-worker groups, 60,000 workless    |             1.73 |         1.37 |               1.41 |           1.11 |
| Two one-worker groups, 60,000 64-round    |             6.60 |         6.19 |               6.06 |           5.35 |
| Two one-worker groups, mixed about 1 ms   |            37.20 |        37.22 |              35.36 |          35.20 |
| Two one-worker groups, 256 KiB memory     |            16.26 |        16.26 |              16.31 |          16.14 |

All paired task-and-memory checksums matched. The same rerun confirmed why
private batches require a cost proof: they reduced the one-group workless case
to approximately 0.86 ms, but increased the mixed one-millisecond case to
approximately 31.3 ms and the memory case to approximately 14.9 ms with both
compilers.

Claimed tasks are normally republished to the thief's deque in one release so
other workers can redistribute them. Keeping them in a private non-atomic batch
saved another 10--30% for proven uniform fine work, but was two to seven times
slower in the worst heterogeneous and memory cases. Codegen may use a private
batch only when its total estimated cost is small and sufficiently uniform.
Otherwise it must republish the batch. Task-count caps alone are not enough:
batch size and private retention must account for estimated cost, order,
locality, runnable breadth, and uncertainty. A conservative unknown-cost case
uses single-task claims.

Writing a whole statically known fanout and publishing its positions only once
improved some large workless cases by 3--9% but regressed some 64-round cases by
5--7% because the other workers could not begin promptly. Intermediate publish
sizes had no stable cross-compiler winner. Per-task publication remains the
reference; codegen may batch publication when its cost model predicts that
position traffic dominates delayed visibility.

Having the calling thread act as worker zero removed one thread creation and
join and improved fine one-group fanout by 20--30%. It also delayed useful work
until the other threads had been created, regressing heterogeneous
millisecond-scale computation by approximately 30% and private-memory work by
approximately 25%. It is rejected as the universal startup design. If the
Operation Graph proves no runnable parallelism, codegen should omit the
scheduler entirely. Choosing the first worker-activation point in a program with
a serial prefix remains a generated-program investigation.

The following candidates produced no stable gain and are not selected:

- embedding deque storage in the scheduler or reducing only the statically
  allocated maximum-worker count;
- removing the task topology-group value or execution-state pointer while
  retaining a 64-byte task stride to prevent false sharing;
- replacing the owner pop's store-plus-fence with an atomic exchange;
- moving the completion load later in the search;
- adding a local-deque empty precheck, which regressed SMT cases by 12--18%;
- replacing atomic deque slots with ordinary pointers;
- replacing indirect recovery dispatch with the best-case homogeneous direct
  dispatch, or replacing generic submission with statically selected submission
  calls, neither of which changed performance robustly after inlining;
- removing the runtime lock-free check, which the compilers already reduce to
  negligible startup code; and
- embedding a statically known initial-worker choice without changing the larger
  startup sequence.

### Action Fragment cost and distribution study

The retained benchmark was extended to vary compute work, private-memory work,
cost distribution, topology preference, and SMT activation. Compute costs ranged
from approximately one microsecond through ten milliseconds per Action Fragment.
Memory cases used either a 256 KiB region for approximately one millisecond or a
4 MiB region for approximately one millisecond per Action Fragment. Memory was
first-touched by a thread pinned to the task's preferred topology group before
the timed interval.

The following GCC `-O2` medians show the effect of adding the eight SMT siblings
to eight physical workers in one topology group. The task counts supplied enough
runnable work to keep every logical worker busy:

| Uniform Action Fragment work | 8 physical workers | 16 logical workers | SMT speedup |
| ---------------------------- | -----------------: | -----------------: | ----------: |
| Approximately 1 us compute   |            2.11 ms |            1.94 ms |       1.09x |
| Approximately 100 us compute |            9.47 ms |            4.61 ms |       2.05x |
| Approximately 1 ms compute   |           18.14 ms |           10.14 ms |       1.79x |
| Approximately 10 ms compute  |           44.13 ms |           23.88 ms |       1.85x |
| 256 KiB private memory       |            8.15 ms |            6.09 ms |       1.34x |
| 4 MiB private memory         |           12.55 ms |           27.67 ms |       0.45x |

Clang and `-O3` produced the same architectural pattern. SMT approximately
doubled throughput for the dependency-heavy compute loop once work was large
enough to dominate scheduler overhead. It provided a smaller benefit for the 256
KiB regions and made the same-group 4 MiB case more than twice as slow due to
shared-cache and memory pressure.

Runnable breadth changed the SMT decision even at millisecond scale. These GCC
`-O2` random-distribution medians compare the same eight physical workers with
their SMT siblings:

| Mixed-cost case                      | 8 physical workers | 16 logical workers | SMT speedup |
| ------------------------------------ | -----------------: | -----------------: | ----------: |
| 64 approximately 1 ms compute tasks  |           11.75 ms |            5.61 ms |       2.09x |
| 8 approximately 10 ms compute tasks  |           11.89 ms |           13.04 ms |       0.91x |
| 32 approximately 1 ms, 256 KiB tasks |            4.21 ms |            3.19 ms |       1.32x |
| 4 approximately 1 ms, 256 KiB tasks  |            5.15 ms |            6.30 ms |       0.82x |

When the number of expensive tasks already matched the physical-worker count,
SMT added contention without exposing additional useful parallelism. Across GCC,
Clang, `-O2`, and `-O3`, the sparse compute case lost 9–16% and the sparse
memory case lost 18–33% in the one-group scheduler.

With SMT disabled, eight physical workers were approximately 3.8 times as fast
as two physical workers for the 256 KiB memory case, but only about 1.2 times as
fast for the 4 MiB case. This is real-world saturation that a scheduler decision
based only on the number of runnable Action Fragments would miss.

Interleaved, deterministic-random, early-clustered, late-clustered, and
topology-correlated slow tasks were also compared. With enough expensive tasks,
work stealing usually kept compute distributions within a few percent of one
another. Sparse mixtures showed 5–16% spreads, with one repeated GCC case
reaching 28%, because publication order and deque direction affected when the
few expensive tasks began. In the memory study, clustering the expensive tasks
at the stealing end of the deque made an eight-of-eighty mixture 20–35% slower
than the other placements. This does not establish one universally optimal deque
order; it establishes that codegen should provide cost estimates and that the
scheduler may eventually use them when publishing a strongly heterogeneous
fanout.

At one- and ten-millisecond compute costs, GCC and Clang and `-O2` and `-O3`
were generally within measurement noise for the uniform cases. The generated
compute loop was effectively unchanged between optimization levels within each
compiler at those costs. This reinforces `-O2` as a reasonable provisional
default but does not predict the optimizer behavior of real generated Action
Fragments.

### Retained benchmark

The [retained benchmark](scheduler_and_join_benchmark.c) includes the reference
implementation directly so that it measures the exact scheduler and Join code in
this ADR. From the workspace root, build the two provisional configurations
with:

```sh
gcc -std=c23 -O2 -march=native -mtune=native -pthread define/compiler/codegen/literal/c/scheduler_and_join_benchmark.c -o /tmp/define-scheduler-benchmark-gcc
clang -std=c23 -O2 -march=native -mtune=native -pthread define/compiler/codegen/literal/c/scheduler_and_join_benchmark.c -o /tmp/define-scheduler-benchmark-clang
```

For example, the measured one-group generated finalist with republished batch
claims is built by adding:

```text
-DLITERAL_MAXIMUM_WORKERS=8 -DLITERAL_SINGLE_TOPOLOGY_GROUP=1 -DLITERAL_PROVEN_DEQUE_CAPACITY=1 -DLITERAL_STEAL_BATCH_SIZE=256
```

The two one-worker-group finalist additionally replaces the single-group fact
with `-DLITERAL_TWO_SINGLE_WORKER_GROUPS=1` and adds
`-DLITERAL_PROVEN_BOUNDED_SPMC_INJECTION=1` and
`-DLITERAL_INJECTION_BATCH_SIZE=256`. These are example facts and measured
policy choices, not universal flags. In particular, the proven-bound SPMC flag
asserts a single producer and a total lifetime enqueue bound, while the deque
capacity flag must include tasks republished after a batch claim.
`LITERAL_SHARED_VICTIM_LISTS=0` selects the measured random scan for a large
same-group SMT topology; shared prefiltered lists are the default.

The principal workloads can then be reproduced by substituting either binary in
these commands:

```sh
/tmp/define-scheduler-benchmark-gcc serial 2000000 compute 0 0 0 uniform 0 2 15
/tmp/define-scheduler-benchmark-gcc idle 2000000 compute 0 0 0 uniform 0 2 15
/tmp/define-scheduler-benchmark-gcc wide 60000 compute 64 64 0 uniform 0 3 15
/tmp/define-scheduler-benchmark-gcc steal 128 compute 64 1000000 64 random 0 3 15
/tmp/define-scheduler-benchmark-gcc steal-smt 128 compute 64 1000000 64 random 0 3 15
/tmp/define-scheduler-benchmark-gcc steal 64 memory 1 160 32 random 262144 3 15
/tmp/define-scheduler-benchmark-gcc steal-smt 64 memory 1 160 32 random 262144 3 15
```

The command format is:

```text
benchmark workload tasks work-kind fast-work slow-work slow-tasks distribution memory-bytes warmups samples
```

`work-kind` is `compute` or `memory`. Compute work amounts are xorshift rounds;
memory work amounts are passes over each task's private `memory-bytes` region.
The distribution is `uniform`, `interleaved`, `random`, `clustered`, `late`,
`group0`, or `group1`. A uniform run requires zero slow tasks. The `wide-smt`,
`steal-smt`, and `skew-smt` workloads activate the SMT siblings of their
corresponding physical workers. The `idle` workload runs a direct serial chain
with seven additional workers polling, exposing interference from workers that
have no useful task.

Timed samples include scheduler initialization and destruction but exclude task
allocation, memory first-touch, and result validation. Every sample checks that
its complete task-and-memory checksum matches the first sample, so a scheduler
variant that loses, duplicates, or races work does not silently produce a
favorable time. The current target configuration uses processor 0 for a serial
chain, processors 0–7 as one topology group for same-group stealing, and
processors 0 and 8 as separate topology groups for the wide and skewed cases.
Their SMT siblings are processors 16–23 and processors 16 and 24, respectively.
Those assignments must be changed to match another machine before its results
are compared.

A later layout analysis moved each worker's aligned deque before its remaining
state. This reduced a worker from 320 to 256 bytes and the 32-worker scheduler
from 10,880 to 8,832 bytes without placing the deque's contended atomics on the
same cache line. Reordering the scheduler-wide fields as suggested by a padding
analyzer reduced the scheduler by another 128 bytes but did not improve the
two-group task-heavy benchmark. In a steal-heavy benchmark it was approximately
1.5% slower by median-of-medians. Two reversed-order `perf` runs also measured
approximately 3.6–4.1% more cache references, 4.8–5.7% more cache misses, and
0.4–0.6% more cycles. The scheduler-wide field order therefore remains
unchanged.

## Deferred investigations

Revisit the following areas when literal C codegen can emit representative
Define programs:

- selective Action Fragment inlining and direct-call expansion, measured across
  generated programs large enough to expose L1 instruction-cache and instruction
  translation-lookaside-buffer pressure;
- optimization-level and code-alignment selection against realistic mixtures of
  Action Fragment cost, fanout, Join fan-in, and topology preference rather than
  adopting one synthetic-workload winner;
- `restrict`, scalar replacement, and compiler assumptions derived from proven
  Particle aliasing, address-identity, lifetime, and queue-capacity facts;
- function multiversioning and runtime target selection when one binary must run
  efficiently on materially different processors;
- scheduler behavior at generated-program scale, including large live task and
  Join populations and Action Fragment target diversity; and
- the release-decrement plus final-acquire-fence Join on weaker-memory-order
  targets with suitable race detection and hardware measurements.

Broader link-time-optimization performance, profile-guided optimization, and
scheduler designs involving multiple C translation units were deliberately
outside this study rather than deferred recommendations. The narrow
multi-translation-unit check recorded above establishes only that full link-time
optimization can recover cross-action elimination for a closed, serialized,
effect-free model. It does not establish that a fully scheduled parallel fixture
can erase.

## Rejected alternatives

### Queue every runnable task

Queueing serial continuations cost two to three orders of magnitude more than
direct execution. Queueing is reserved for work that must become available to
another worker.

### One global ready queue

A global queue made its enqueue and dequeue positions coherence bottlenecks and
discarded the useful locality already present in fork-Join graphs.

### Unrestricted cross-group stealing

Unrestricted stealing moved roughly half the wide workload across topology
groups and substantially increased cache traffic. It remains useful when a group
has a genuine work deficit, so it is delayed or signaled rather than forbidden.

### Statically distribute every fanout branch to a worker inbox

Both multi-producer, multi-consumer and SPSC per-worker inbox variants lost to
local deque submission plus stealing. Static distribution touched many
producer-side queue cache lines and imposed queue synchronization on every task.

### Two-level Join by default

A per-group counter followed by a global counter reduced some cross-group
counter traffic but made group-final arrivals perform another atomic operation.
It occasionally tied the flat Join but did not win robustly in complete-runtime
tests. It may be reconsidered for exceptionally large, statically partitioned,
simultaneous fan-in.

### Always activate SMT siblings

SMT helped computation-heavy balanced trees but hurt fine wide Joins. Worker
activation therefore remains adaptive runtime policy.

### Use the smallest fixed underlying enum type

The complex generated fixture has a closed 36-value operation identity domain,
so C23 `uint8_t` underlying types were tested for its operation and claim-result
enums. GCC's binary size was unchanged and Clang's fell by 88 bytes, but both
compilers were approximately 6--8% slower in both execution orders. Keep the
implementation-selected enum representation unless a future generated workload
demonstrates a runtime benefit or an external representation requires a fixed
width.

The same fixture also rejected a 6-bit unsigned `_BitInt` operation identity. It
enlarged both binaries, added 40 instructions under GCC and 197 under Clang, and
added approximately 0.2--0.3% cycles in 2,000-run hardware-counter measurements.

## Consequences and boundaries

- The common serial path performs no queue operation.
- The scheduler preserves every concurrency opportunity represented by the
  Action Plan; topology preference changes placement, not dependencies.
- Flat Join state is small, but a concurrently active Join normally consumes a
  cache line when isolated from unrelated active counters.
- Generated Action Fragment functions need a common scheduler-call signature so
  queued tasks can use one indirect dispatch path.
- The fallback queue capacity and fixed cross-group poll threshold in the
  [C example](scheduler_and_join_example.c) are reference policies. Generated
  queues need either a proven capacity or an explicit runtime capacity policy,
  and cross-group policy ultimately needs workload feedback.
- Batch claims preserve runnable tasks but can change when and where they run.
  Their caps and private-versus-republished representation are codegen decisions
  driven by proven bounds, estimated cost, locality, and uncertainty.
- The synthetic measurements choose an initial architecture. Benchmarks of
  generated Define programs remain necessary before fixing constants or
  specializing Particle layout.
