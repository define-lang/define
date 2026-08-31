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

Keep unrelated concurrently active Join counters on separate cache lines to
avoid false sharing. Do not pad every Particle or every scheduler task.

### Worker activation

Processor count is a runtime policy. Start with one worker per physical core for
fine, coherence-heavy work. Activate SMT siblings only when runnable breadth
exceeds the physical-worker count and the estimated working set is unlikely to
saturate shared caches or memory bandwidth. Long Action Fragments alone are not
sufficient evidence: SMT improved dependency-heavy computation with abundant
runnable work, but hurt sparse computation and large per-worker memory regions.
The generated Operation Graph is unchanged by this choice.

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
- Join dependency counts;
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
  runnable Action Fragments.

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
ThreadSanitizer checks.

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

The principal workloads can then be reproduced by substituting either binary in
these commands:

```sh
/tmp/define-scheduler-benchmark-gcc serial 2000000 compute 0 0 0 uniform 0 2 15
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
corresponding physical workers.

Timed samples include scheduler initialization and destruction but exclude task
allocation, memory first-touch, and result validation. The current target
configuration uses processor 0 for a serial chain, processors 0–7 as one
topology group for same-group stealing, and processors 0 and 8 as separate
topology groups for the wide and skewed cases. Their SMT siblings are processors
16–23 and processors 16 and 24, respectively. Those assignments must be changed
to match another machine before its results are compared.

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
- removal of the owner deque's capacity-check load when the compiler proves that
  its capacity cannot be exceeded for every reachable execution;
- C23 fixed-underlying-type enums and `_BitInt` representations after codegen
  has real identity domains, cardinality bounds, and external-ABI requirements
  to measure;
- function multiversioning and runtime target selection when one binary must run
  efficiently on materially different processors;
- scheduler behavior at generated-program scale, including large live task and
  Join populations and Action Fragment target diversity; and
- the release-decrement plus final-acquire-fence Join on weaker-memory-order
  targets with suitable race detection and hardware measurements.

Link-time optimization, profile-guided optimization, and designs involving
multiple C translation units were deliberately outside this study rather than
deferred recommendations.

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

## Consequences and boundaries

- The common serial path performs no queue operation.
- The scheduler preserves every concurrency opportunity represented by the
  Action Plan; topology preference changes placement, not dependencies.
- Flat Join state is small, but a concurrently active Join normally consumes a
  cache line when isolated from unrelated active counters.
- Generated Action Fragment functions need a common scheduler-call signature so
  queued tasks can use one indirect dispatch path.
- The fixed-capacity queues and fixed cross-group poll threshold in the
  [C example](scheduler_and_join_example.c) are benchmark mechanisms, not final
  production policies. Production queues need a proven capacity strategy, and
  cross-group policy needs workload feedback.
- The synthetic measurements choose an initial architecture. Benchmarks of
  generated Define programs remain necessary before fixing constants or
  specializing Particle layout.
