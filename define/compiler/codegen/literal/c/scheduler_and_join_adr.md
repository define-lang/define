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

When cost and cardinality facts justify it, a thief may claim several tasks with
a bounded sequence of ordinary single-task Chase-Lev compare-exchanges without
restarting victim selection. It republishes all but its directly executed task
to its own deque with one release. A range claim using one compare-exchange is
not correct for a Chase-Lev deque because its owner can pop into the proposed
range without changing `top`. A proven single-producer, multiple-consumer
injection queue whose total lifetime enqueue count cannot exceed its capacity
may safely reserve a range with one compare-exchange. Unknown or strongly
heterogeneous costs use single-task claims. Claimed tasks remain visible for
redistribution; private batches are not selected.

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

When one Particle Operation contributes to two or more independent Joins,
codegen may instead pack their small counters into unsigned lanes of one
lock-free atomic word. One acquire-release subtraction updates every selected
lane, and the returned lane values identify every newly satisfied Join. This is
valid only with exact arrival membership, sufficient lane widths, no subtraction
from a lane after it reaches zero, and compatible counter lifetimes. Compact
packing cut the workless eight-Join case by approximately 55% under both GCC and
Clang, but was neutral once each continuation performed 64 synthetic work
iterations. Cache-line-isolating the packed word enlarged Action Execution state
enough to erase part of the gain at a large working set.

Use the returned satisfaction state directly when the continuation is statically
known and can remain on that worker. Even the smallest ready-word publish and
reclaim control added approximately 35--68% in the workless eight-Join cases.
Local batching of several simultaneously satisfied continuations is separately
target- and compiler-dependent. The complete eligibility rules and measurements
are in [the advanced experiments](advanced_literal_c_experiments.md).

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

### Worker lifetime, publication, and waiting

Do not force every generated Operation Graph through one worker-lifecycle or
scheduling policy. Codegen selects the least general eligible member of this
portfolio:

1. direct serial control flow when parallel coordination cannot repay its cost;
2. fresh operating-system threads with direct static assignment for substantial
   one-shot parallel work;
3. persistent workers with generated static publication and completion when the
   runnable identities and worker assignments are bounded; and
4. the claimable deque and injection-queue scheduler when work identity, cost,
   or cardinality remains uncertain.

One action may combine these forms. Proven fixed-cost Particle Operation regions
can use generated static worker ranges while only sparse runtime-variable
regions enter a shared claim cursor. In the measured 4,096-branch case with 64
uncertain branches, this hybrid was 9--11% faster than both fully static and
fully dynamic alternatives for one Action Execution under GCC and Clang. When
several uniformly cheap Action Executions were live, whole-execution sharding or
static regions remained faster. Codegen selects regions from exact dependency,
cost-variance, simultaneous-Action-Execution, and locality facts.

On Linux, create a persistent pool with pthreads. The pthread workers use no
pthread synchronization operation during Action Execution. Their generated hot
path is ordinary memory, lock-free C atomics, processor relax instructions, and
direct futex system calls when parking is selected. Pool creation and
destruction remain outside Action Execution.

Spinning and parking are separate generated policies, not two implementations of
an otherwise fixed scheduler. Use independent thresholds for:

- a worker awaiting its next publication, whose arrival may depend on later or
  externally initiated Action Executions; and
- the caller awaiting known predecessors in its current Action Execution, whose
  remaining critical-path cost can be estimated from the Operation Graph.

Parking has two correct generated protocols. A hybrid spin-then-park policy can
atomically OR a waiter bit into the generation word. Publication atomically
replaces that complete word; the returned previous value proves whether a wake
is mandatory. The completion counter can likewise reserve its high bit for the
caller: the caller atomically ORs the bit before waiting, and the final
completing worker's atomic increment proves whether it must wake the caller.

A generated pure-parking policy can remove those waiter-bit read-modify-write
operations. A worker waits on the exact old generation while the publisher
performs a release store and an unconditional futex wake. If publication wins
the race before the worker enters the kernel, the futex value comparison fails
instead of sleeping. The caller can similarly wait on the observed completion
count while the final completing worker always wakes. This trades potentially
unnecessary futex wake system calls for fewer atomic instructions. Neither form
uses a mutex or explicit atomic fence. A separately published Boolean is not a
correct conditional-wake protocol.

The final x86-64 disassembly makes the distinction precise. The direct and
fresh-thread benchmark executables contain no generated lock-prefixed or
memory-operand `xchg` instruction. Targeted spinning with completion generations
contains one locked increment for pool-startup readiness and none during Action
Execution. Dense broadcast pure parking contains that startup increment plus the
shared completion counter's locked addition; generation publication and caller
waiting use ordinary atomic stores and loads around futex calls. The waiter-bit
form necessarily adds atomic exchanges and compare-exchange loops. Neither GCC
nor Clang emits `mfence`, `lfence`, or `sfence` for these paths.

Generated static publication uses a cache-line handoff per selected worker when
workers are spinning. A worker polls its own generation, writes its completion
generation to the same handoff line, and the caller reads only the workers
assigned to that Action Execution. This was faster than one broadcast generation
word even when every tested worker was active: the broadcast writer repeatedly
invalidated a line cached by every polling processor. With two to sixteen
workers, targeted publication reduced the effect-free phase by approximately
17--60% under both GCC and Clang.

Parking changes the publication choice. With two active workers in an
eight-worker pool, targeted waiter-bit publication took approximately 2.24--2.33
us in the stable GCC and Clang runs, while broadcasting to all eight workers
took approximately 2.83--3.30 us and consumed far more processor time. When
every worker was active, one broadcast word plus unconditional wakes beat
per-worker publication: approximately 2.63--2.79 us at eight workers, 7.44--7.66
us at sixteen, and 12.0--12.1 us at thirty-two. The generated active subset,
park policy, and target measurements therefore select publication together.
Topology-group publication remains a later candidate between one global word and
one word per worker.

When the caller will spin until statically assigned workers finish, use
per-worker completion generations. They are release stores and acquire loads, so
they contain no atomic read-modify-write operation on x86-64. With targeted
publication they beat the shared completion counter at every tested width from
two through sixteen workers. Retain the shared counter when the caller may park,
when the final completing worker is not statically identified, or when the
general scheduler must represent a true multi-arrival Join.

The following GCC and Clang `-O2` medians show why selection requires the whole
scheduler/runtime pair. The synthetic work amounts are xorshift rounds; 800,000
rounds were approximately one millisecond on the measured processor.

| Action Execution shape                                     | Direct serial | Fresh pthreads | Selected persistent scheduler |
| ---------------------------------------------------------- | ------------: | -------------: | ----------------------------: |
| Two effect-free assigned workers                           |       2--4 ns |    about 10 us |                     35--48 ns |
| Eight effect-free assigned workers                         |      7--15 ns |      47--48 us |                    83--107 ns |
| Eight workers, two approximately 13 us Particle Operations |       31.9 us |        49.6 us |               12.69--12.72 us |
| Eight approximately 1 ms Particle Operations               |       7.85 ms |  1.03--1.05 ms |                 about 1.01 ms |
| Eight workers, two approximately 1 ms Particle Operations  |       1.97 ms |        1.03 ms |                 about 1.01 ms |

In the last row, continuous spinning consumed approximately 8.07 ms of total
processor time per Action Execution. Parking the early workers and caller with
the waiter-bit completion counter preserved the approximately 1.01 ms wall time
while reducing processor time to approximately 2.03 ms. With a one-millisecond
gap and only two active workers in an eight-worker pool, targeted spinning
responded in approximately 0.11--0.13 us but consumed approximately 7.3 ms of
processor time. Targeted parking responded in approximately 2.6--2.7 us and
consumed approximately 4.2 us.

The worker-creation experiment rejected raw `clone3`; its retained variants are
benchmark controls, not codegen options. The measurements and rationale are
recorded under Rejected alternatives.

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

Generated instruction size is also a representation input. In the retained
large-code study, direct and bounded-region code remained competitive through
approximately 4,096--16,384 synthetic Particle Operations, depending on compiler
and region size. At 65,536, a compact operand loop was 55% faster than GCC
direct code and 26% faster than Clang's best measured direct-region size while
also reducing compile time from seconds or minutes to less than 0.15 seconds.
The hardware counters attribute the reversal to instruction-fetch pressure.
Region size and the direct-to-compact threshold require calibration for the
selected compiler and target; a function per Particle Operation and a generated
giant switch are not general fallbacks.

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
- which one Particle Operation completions contribute to several Joins and which
  simultaneously satisfied continuations may execute in either order;
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
- cost bounds and variance for independently schedulable regions;
- the expected number of simultaneously live Action Executions;
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
- instruction-cache and front-end capacity relevant to generated code size; and
- the selected compiler and version, plus capabilities such as guaranteed tail
  calls, link-time optimization, and function multiversioning.

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
| Pack several Join counters into one subtraction               | One completion contributes to every selected Join, exact lane counts and lifetimes prevent borrow or reset overlap, the target atomic width is lock-free, and continuation cost plus writable layout justify packing                                         |
| Invoke a Join continuation from the subtract result           | The continuation identity is static, it may run on the final-arriving worker, and no placement or claimability requirement forces readiness publication                                                                                                      |
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
| Activate physical workers or their SMT siblings               | Runnable breadth over time, Action Fragment cost and variance, estimated per-worker working sets and memory traffic, target sibling topology and shared-cache capacity, and target measurements of activation and contention                                 |
| Group repeated Chase-Lev steals                               | A runnable-count bound, cost and variance estimates, maximum deque occupancy including republished tasks, and target measurements select the cap; every task still receives an individual compare-exchange and every additional claim is republished         |
| Use shared victim lists or a generated victim scan            | Exact active-worker and topology-group membership, group cardinality, and target measurements; this changes only how workers search and never weakens claimability                                                                                           |
| Select direct serial, fresh threads, or a persistent pool     | Runnable breadth, estimated path costs and variance, expected invocation count, pool lifetime, and calibrated creation and coordination costs                                                                                                                |
| Combine static and dynamically claimed regions                | Exact independent regions, proven fixed costs, sparse uncertain costs, terminal arrival grouping, simultaneous Action Execution count, and target claim overhead justify the boundary                                                                        |
| Select direct regions or compact operand data                 | Emitted instruction and constant-data estimates, hot frequency, natural region boundaries, compiler and target calibration, instruction-front-end capacity, and compile-resource budgets                                                                     |
| Publish directly to selected persistent workers               | The worker assignment and exact active subset are known, no unassigned worker must claim the work, and target measurements prefer handoff lines for spinning or a sparse parked subset                                                                       |
| Publish one broadcast generation                              | Every retained worker is selected or waking additional workers is cheaper than publishing and waking individual words, as established by target measurements for the parked dense case                                                                       |
| Use per-worker completion generations                         | Each selected worker completes exactly once, the caller will spin rather than park, and no runtime-selected worker can contribute an arrival                                                                                                                 |
| Use the shared completion counter                             | More than one selected worker can complete last and estimated remaining time justifies allowing the caller to park                                                                                                                                           |
| Use conditional waiter-bit wakes                              | The generated policy may finish during its spin interval, so avoiding unnecessary futex wake calls repays the additional lock-free atomic read-modify-write operations on the target                                                                         |
| Use unconditional futex wakes                                 | The generated policy expects pure parking, and target measurements show that removing waiter-bit read-modify-write operations repays any wake call that finds no waiter                                                                                      |
| Choose separate worker and caller spin limits                 | Estimated time to current dependency satisfaction, expected time to the next publication, target pause and futex costs, and whether the later invocation time is unknown                                                                                     |

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

### Measured system

| Component                | Recorded value                                                                                                                                                                                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Host and firmware        | System76 Thelio Mira r4; American Megatrends 4.10.SP01 BIOS dated February 23, 2026                                                                                                                                                                          |
| Processor                | AMD Ryzen 9 9950X, x86-64 family `0x1a`, model `0x44`, stepping `0`, microcode `0xb404035`; one socket, 16 physical cores, 32 logical processors; SMT enabled; no hypervisor                                                                                 |
| Cache                    | 64-byte coherence lines; 32 KiB L1 instruction, 48 KiB L1 data, and 1 MiB L2 per physical core; two 32 MiB L3 groups                                                                                                                                         |
| Processor topology       | NUMA/cache group 0: processors `0-7,16-23`; group 1: processors `8-15,24-31`; processor `n + 16` is the SMT sibling of processor `n`                                                                                                                         |
| Initial frequency policy | `amd-pstate-epp` driver, `powersave` governor, `balance_performance` energy preference, and frequency boost enabled; reported policy limits 624.1940--5756.4521 MHz; frequency was not fixed during the initial measurements                                 |
| Controlled rerun policy  | System76 `Performance` profile, `performance` governor and energy preference, frequency boost disabled, and every processor policy constrained to a 4300.000 MHz minimum and maximum; all other system services and idle-state policy remained active        |
| Idle policy              | `acpi_idle` driver with the `menu` governor; enabled POLL, C1, C2, and C3 states reporting 0, 1, 18, and 350 us exit latency respectively; actual state residency was not controlled or recorded                                                             |
| Memory                   | Linux `MemTotal` 63,422,700 KiB, approximately 60.5 GiB usable                                                                                                                                                                                               |
| Operating system         | Fedora Linux 44 (COSMIC), glibc 2.43, 4 KiB base pages, transparent huge pages in `madvise` mode, automatic NUMA balancing enabled, and TSC clock source                                                                                                     |
| Kernel                   | `Linux 7.1.8-200.fc44.x86_64 #1 SMP PREEMPT_DYNAMIC Mon Aug 10 03:35:23 UTC 2026 GNU/Linux`; default Fedora vulnerability mitigations, with no mitigation-disabling or processor-isolation kernel arguments                                                  |
| Compiler toolchains      | GCC `16.2.1 20260819 (Red Hat 16.2.1-2)` and Clang `22.1.8 (Fedora 22.1.8-4.fc44)`, targeting `x86_64-redhat-linux-gnu`; the initial scheduler comparison used `-O3 -march=native -mtune=native`, and later studies state their differing options explicitly |
| Measurement tools        | Linux `perf 7.1.10-200.fc44.x86_64` and AMD uProf 5.3.521.0                                                                                                                                                                                                  |

The harness used bounded multi-producer, multi-consumer queues, C-race-free
Chase-Lev deques, worker affinity, direct-successor bypass, flat and two-level
Joins, and synthetic serial, wide fanout, and balanced binary fork-Join graphs.
Benchmark candidates ran one at a time with the caller and workers pinned as
described by each workload. The initial comparisons used no deliberate competing
compute workload, real-time scheduling, fixed-frequency mode, CPU isolation, or
shutdown of normal operating-system and user-session services. The controlled
rerun changed only the frequency policy described in the table. Each study below
records its warmup and sampling policy; reported comparisons use medians rather
than best-case samples.

DIMM count, channel population, transfer rate, timings, ambient temperature,
processor temperature, package power limits, idle-state residency, and the
runtime selection of the kernel's dynamic preemption mode were not captured
during the measurements and cannot be reconstructed reliably afterward. Results
involving dynamic boost, parking, or memory traffic should therefore be treated
as measurements of this ordinary interactive configuration, not as
frequency-locked laboratory results.

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

The initial benchmark harness passed AddressSanitizer,
UndefinedBehaviorSanitizer, and ThreadSanitizer checks. The corrected grouped
deque form described below passed Clang AddressSanitizer,
UndefinedBehaviorSanitizer, and ThreadSanitizer, GCC `-fanalyzer`, `cppcheck`,
and Clang's analyzer. The installed GCC sanitizer libraries were unavailable for
the corrected rerun. The later exact-execution builds also passed Clang
AddressSanitizer, UndefinedBehaviorSanitizer, and ThreadSanitizer across the
physical-worker, SMT, and exact two-worker specializations. Analyzer diagnostics
for intentional cache-line padding, including the reference implementation
directly in the benchmark translation unit, standard `void *` allocation
conversions, and bounded standard-library calls remain classified as design
constraints or false positives rather than source changes.

### Controlled-frequency confirmation

The decision-sensitive scheduler cases were rerun on September 1, 2026 with all
32 processor policies constrained to the nominal 4.30 GHz frequency described
above. A 9.38-second, eight-worker confirmation measured 323,048,451,435 core
cycles, 321,397,636,649 reference cycles, and 74.875 seconds of aggregate task
clock. These correspond to approximately 4.314 GHz of core cycles and 4.292 GHz
of reference cycles per busy processor. The immediately subsequent processor
control temperature was 46.875 degrees Celsius. This does not capture a peak
temperature, but the counter ratio and stable sample times provide no evidence
of frequency throttling during the confirmation.

Fixed frequency preserved the scheduler's architectural decisions. The SMT and
physical-worker tables below replace the earlier dynamic-frequency SMT tables.
The corrected same-group 4 MiB private-memory workload made SMT approximately
2.04--2.27 times slower across both compilers and optimization levels. Parking
measurements remain subject to the ordinary `menu` idle governor and C-state
wake latency; frequency control does not normalize those effects.

The thread-runtime choices also survived the controlled rerun. On the dense
short-work mixture, spin-only workers improved wall time by approximately 0.5%
and consumed similar process CPU because all workers remained active. On the
imbalanced millisecond mixture, that same wall-time difference cost about 10.385
ms of process CPU instead of 2.615 ms with targeted parking. After a 1 ms idle
interval with only two of eight workers active, spin-only wakeup was
approximately 0.1--0.18 microseconds rather than 4.5--4.9 microseconds, but used
about 7.33 ms of process CPU instead of approximately 3.3 microseconds. Targeted
parking therefore remains the generated default; spin-only waiting is a latency
policy that explicitly accepts orders of magnitude more idle CPU.

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

The strongest result was exact queue sizing. In the controlled-frequency rerun,
reducing a 65,536-entry queue to a proven 128-entry capacity reduced
complete-runtime time by approximately 82--84% for 128 fine tasks: about 0.60 ms
became 0.09--0.10 ms with eight workers, and about 1.21--1.22 ms became
0.21--0.22 ms with 16 logical workers. It improved a mixed approximately
one-millisecond case by approximately 4% with physical workers and 15% with SMT.
The gain comes principally from avoiding allocation and initialization of queue
state that the generated program cannot use. Codegen should therefore emit the
smallest safe power-of-two capacity from a proven simultaneously queued-task
bound. When no such bound exists, it must retain a runtime capacity policy.

Removing the owner-deque capacity checks after proving them unreachable became
more important with safe grouped stealing. In fine workloads it improved
complete-runtime time by approximately 20--72%, depending on compiler, topology,
and Action Fragment cost, because every stolen group is republished through that
path. It remained neutral for approximately one-millisecond and private-memory
Action Fragments. These checks must be omitted only from a deque whose bound
includes republished stolen tasks. Removing the index mask as well remains
rejected: it helped some physical-worker cases but regressed GCC with SMT by
6--8% and Clang by as much as 3%.

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

The original batch experiment was invalid. It read a proposed range from a
Chase-Lev deque and advanced `top` over the whole range with one
compare-exchange. A concurrent owner can pop from the opposite end into that
range without changing `top`; the thief's compare-exchange can then succeed and
execute some tasks twice. Longer controlled-frequency runs exposed this as
nondeterministic checksums in both the checked and proven-capacity forms. Zero
rounds could not expose the error because executing a task zero or multiple
times left its value unchanged.

The corrected thief selects a victim once, then claims each task with the
ordinary single-task Chase-Lev compare-exchange before republishing the group to
its deque with one release. This preserves lock-free deque semantics while
amortizing victim selection and publication. Caps from 2 through 32,768 were
screened. Fine-work performance plateaued at approximately 4,096 tasks; larger
caps did not improve robustly and required larger temporary worker stacks. A
compiler may emit a smaller cap when its proven runnable bound is smaller. A
proven-bound SPMC injection queue still reserves a range with one
compare-exchange because its monotonic dequeue reservation prevents the owner
overlap that invalidates a Chase-Lev range claim.

A final controlled-frequency confirmation compiled the corrected retained source
with both compilers and ran three reversed-order outer repetitions; each
repetition was the median of 15 samples after three warmups. The following
complete-runtime medians are in milliseconds. The selected one-group form
republishes a safely claimed group of at most 4,096 tasks. The 16-worker form
uses the measured random victim scan, and the exact two-worker form uses a
proven-bound SPMC injection queue with a 256-task reservation cap.

| Topology and work                         | GCC single claim | GCC selected | Clang single claim | Clang selected |
| ----------------------------------------- | ---------------: | -----------: | -----------------: | -------------: |
| One group, 60,000 workless tasks          |             6.52 |         1.54 |               6.35 |           1.52 |
| One group, 60,000 64-round tasks          |             5.90 |         1.75 |               5.57 |           1.72 |
| One group, 128 mixed approximately 1 ms   |            11.77 |        11.76 |              11.76 |          11.78 |
| One group, 64 mixed 256 KiB memory tasks  |             5.16 |         5.14 |               5.16 |           5.12 |
| 16 logical workers, 60,000 workless tasks |             7.42 |         2.06 |               7.12 |           2.04 |
| 16 logical workers, 60,000 64-round tasks |             7.79 |         2.05 |               7.05 |           2.05 |
| Two one-worker groups, 60,000 workless    |             1.68 |         1.39 |               1.53 |           1.38 |
| Two one-worker groups, 60,000 64-round    |             5.87 |         5.41 |               6.55 |           5.96 |
| Two one-worker groups, mixed about 1 ms   |            45.00 |        44.96 |              44.95 |          44.97 |
| Two one-worker groups, 256 KiB memory     |            19.78 |        19.77 |              19.82 |          19.81 |

All paired task-and-memory checksums matched. The selected 4,096-task deque form
additionally completed 400 independent stress processes and 12,400 measured
64-round samples across both compilers and both one-group worker topologies
without a checksum failure. Separate exact-execution builds counted every task
atomically and required a count of exactly one after each sample. GCC and Clang
each passed the physical-worker, SMT, and exact two-worker configurations with
both workless and 64-round tasks: 540 independent processes and 5,940 checked
samples including warmups. The performance binaries omit this instrumentation
and were byte-for-byte identical before and after exact checking was added.

Keeping safely claimed tasks in a private non-atomic batch is rejected. It was
approximately three times slower for workless fine tasks, neutral at best for
64-round physical-worker work, more than twice as slow with SMT, and three to
six times slower for heterogeneous millisecond and memory work. Republish
claimed tasks so that other workers can redistribute them. A conservative
unknown-cost case uses single-task claims rather than a large group.

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

The corrected scheduler was compiled at `-O2` and `-O3` with GCC and Clang and
rerun at fixed frequency. Each result is the median of three reversed-order
outer runs; each outer run took the median of nine samples after two warmups.
The following GCC `-O2` complete-runtime medians show the effect of adding the
eight SMT siblings to eight physical workers in one topology group:

| Uniform Action Fragment work | Tasks | 8 physical workers | 16 logical workers | SMT speedup |
| ---------------------------- | ----: | -----------------: | -----------------: | ----------: |
| Approximately 1 us compute   | 8,192 |           2.049 ms |           2.175 ms |       0.94x |
| Approximately 100 us compute |   512 |           9.582 ms |           6.102 ms |       1.57x |
| Approximately 1 ms compute   |   128 |          23.056 ms |          12.827 ms |       1.80x |
| Approximately 10 ms compute  |    32 |          56.322 ms |          29.543 ms |       1.91x |
| 256 KiB private memory       |    64 |           9.981 ms |           7.253 ms |       1.38x |
| 4 MiB private memory         |    32 |          12.732 ms |          27.797 ms |       0.46x |

The other compiler and optimization combinations reproduced the
workload-dependent pattern. Their SMT speedups ranged from 0.94--1.03x at
approximately 1 us, 1.57--1.64x at 100 us, 1.75--1.80x at 1 ms, 1.83--1.91x at
10 ms, and 1.17--1.38x for 256 KiB. For 4 MiB they ranged from 0.44--0.49x: SMT
was approximately 2.04--2.27 times slower. SMT therefore helped abundant
dependency-heavy computation once work dominated scheduler startup, provided a
smaller and compiler-sensitive benefit for 256 KiB regions, and lost decisively
when the private working sets saturated the shared cache and memory path.

Runnable breadth changed the SMT decision even at millisecond scale. These
fixed-frequency GCC `-O2` random-distribution medians compare the same eight
physical workers with their SMT siblings:

| Mixed-cost work             | Total tasks | Slow tasks | 8 physical workers | 16 logical workers | SMT speedup |
| --------------------------- | ----------: | ---------: | -----------------: | -----------------: | ----------: |
| Approximately 1 ms          |         128 |         64 |          11.863 ms |           7.124 ms |       1.67x |
| Approximately 10 ms         |         800 |          8 |          14.583 ms |          16.343 ms |       0.89x |
| Approximately 1 ms, 256 KiB |          64 |         32 |           5.140 ms |           3.819 ms |       1.35x |
| Approximately 1 ms, 256 KiB |         400 |          4 |           4.460 ms |           6.371 ms |       0.70x |

Across all four compiler settings, the respective speedup ranges were
1.64--1.67x, 0.88--0.90x, 1.16--1.35x, and 0.66--0.70x. When the number of
expensive tasks already matched the physical-worker count, SMT added contention
without exposing additional useful parallelism.

The corrected fixed-frequency comparison also measured eight physical workers
against two physical workers. Eight workers were 3.92--3.96 times as fast for
the 256 KiB workload but only 1.34--1.39 times as fast for the 4 MiB workload
across GCC, Clang, `-O2`, and `-O3`. This saturation is invisible to a scheduler
decision based only on runnable Action Fragment count.

Interleaved, deterministic-random, early-clustered, and late-clustered slow
tasks were rerun with the corrected grouped-steal scheduler. Each result was the
median of three outer runs with at least five samples after warmup. Across dense
and sparse one- and ten-millisecond compute mixtures, distribution changed the
median by at most 3% for every compiler setting. For the eight-of-eighty 256 KiB
memory mixture, the spread was 7--10%; interleaving was consistently slowest.
Publication order therefore still has a measurable memory-locality effect.
Codegen should provide cost and locality estimates so a future generated
publication policy can exploit those program facts.

At one- and ten-millisecond compute costs, GCC and Clang and `-O2` and `-O3`
were generally within measurement noise for the uniform cases. The generated
compute loop was effectively unchanged between optimization levels within each
compiler at those costs. This reinforces `-O2` as a reasonable provisional
default but does not predict the optimizer behavior of real generated Action
Fragments.

### Retained thread-runtime benchmark

The [thread-runtime benchmark](thread_runtime_benchmark.c) retains the complete
serial, fresh-pthread, persistent-pthread, spin, futex, publication, and
completion variants used above, plus the rejected raw-clone comparison controls.
It deliberately assigns known work directly to workers; the existing scheduler
benchmark remains the evidence for runtime claiming and work stealing.

For example, build the selected targeted spinning pthread form, a sparse
targeted waiter-bit parking form, and a dense broadcast unconditional-wake form
with:

```sh
gcc -std=c23 -O2 -march=native -mtune=native -fno-stack-protector -DDEFINE_THREAD_RUNTIME=2 -DDEFINE_COMPLETION=2 -DDEFINE_PUBLICATION=2 -pthread define/compiler/codegen/literal/c/thread_runtime_benchmark.c -o /tmp/define-thread-spin
gcc -std=c23 -O2 -march=native -mtune=native -fno-stack-protector -DDEFINE_THREAD_RUNTIME=3 -DDEFINE_COMPLETION=1 -DDEFINE_PUBLICATION=2 -pthread define/compiler/codegen/literal/c/thread_runtime_benchmark.c -o /tmp/define-thread-sparse-park
gcc -std=c23 -O2 -march=native -mtune=native -fno-stack-protector -DDEFINE_THREAD_RUNTIME=3 -DDEFINE_COMPLETION=1 -DDEFINE_PUBLICATION=1 -DDEFINE_GENERATION_WAKE=2 -DDEFINE_COMPLETION_WAKE=2 -pthread define/compiler/codegen/literal/c/thread_runtime_benchmark.c -o /tmp/define-thread-dense-park
```

Clang accepts the same commands. `DEFINE_THREAD_RUNTIME=1` selects fresh
pthreads and `DEFINE_THREAD_RUNTIME=6` selects direct serial execution.
Completion value `1` is the shared counter and value `2` is per-worker
completion generations. Publication value `1` is broadcast and value `2` is
targeted. Generation-wake and completion-wake value `1` uses the waiter-bit
conditional-wake protocol; value `2` uses unconditional wake. Raw-stack values
`1`, `2`, and `3` select guarded mapped, unguarded mapped, and static generated
stacks respectively when reproducing the rejected raw-clone comparison.

The command format is:

```text
benchmark workers active-workers executions fast-work slow-work slow-workers idle-microseconds worker-spin caller-spin warmups samples
```

For example, these reproduce the dense short mixture, the imbalanced millisecond
mixture, and the sparse one-millisecond idle interval:

```sh
/tmp/define-thread-spin 8 8 10000 1000 10000 2 0 1000 1000 10000 9
/tmp/define-thread-dense-park 8 8 100 1000 800000 2 0 0 0 50 9
/tmp/define-thread-sparse-park 8 2 200 0 0 0 1000 0 0 10 9
```

Every sample verifies that each active worker executes exactly once per Action
Execution, that inactive workers execute zero times, and that checksums match
across samples. It reports median cold-pool startup, wall time and total process
CPU time per Action Execution, shutdown, and startup/shutdown-amortized wall
time. Because glibc caches pthread stacks within a process, cold-process
lifecycle comparisons require repeated one-sample process invocations rather
than relying on later samples in one invocation.

### Retained benchmark

The [retained benchmark](scheduler_and_join_benchmark.c) includes the reference
implementation directly so that it measures the exact scheduler and Join code in
this ADR. The measured physical-worker, SMT, and exact two-worker configurations
are distinct generated specializations. From the workspace root, build them
with:

```sh
gcc -std=c23 -O2 -march=native -mtune=native -pthread -Wall -Wextra -Wpedantic -Werror -DLITERAL_MAXIMUM_WORKERS=8 -DLITERAL_SINGLE_TOPOLOGY_GROUP=1 -DLITERAL_PROVEN_DEQUE_CAPACITY=1 -DLITERAL_SHARED_VICTIM_LISTS=1 -DLITERAL_STEAL_BATCH_SIZE=4096 define/compiler/codegen/literal/c/scheduler_and_join_benchmark.c -o /tmp/define-scheduler-physical
gcc -std=c23 -O2 -march=native -mtune=native -pthread -Wall -Wextra -Wpedantic -Werror -DLITERAL_MAXIMUM_WORKERS=16 -DLITERAL_SINGLE_TOPOLOGY_GROUP=1 -DLITERAL_PROVEN_DEQUE_CAPACITY=1 -DLITERAL_SHARED_VICTIM_LISTS=0 -DLITERAL_STEAL_BATCH_SIZE=4096 define/compiler/codegen/literal/c/scheduler_and_join_benchmark.c -o /tmp/define-scheduler-smt
gcc -std=c23 -O2 -march=native -mtune=native -pthread -Wall -Wextra -Wpedantic -Werror -DLITERAL_MAXIMUM_WORKERS=2 -DLITERAL_TWO_SINGLE_WORKER_GROUPS=1 -DLITERAL_PROVEN_DEQUE_CAPACITY=1 -DLITERAL_PROVEN_BOUNDED_SPMC_INJECTION=1 -DLITERAL_STEAL_BATCH_SIZE=4096 -DLITERAL_INJECTION_BATCH_SIZE=256 define/compiler/codegen/literal/c/scheduler_and_join_benchmark.c -o /tmp/define-scheduler-two
```

Clang accepts the same commands. These flags combine generated proof facts with
measured policy choices; they are not universal settings. In particular, the
proven-bound SPMC flag asserts a single producer and a total lifetime enqueue
bound, while the deque-capacity fact must include tasks republished after a
grouped steal. Shared prefiltered victim lists won for eight physical workers;
the measured random scan won for the larger same-group SMT topology.

The principal workloads map to the compatible generated binaries as follows:

```sh
/tmp/define-scheduler-physical serial 2000000 compute 0 0 0 uniform 0 2 15
/tmp/define-scheduler-physical idle 2000000 compute 0 0 0 uniform 0 2 15
/tmp/define-scheduler-two wide 60000 compute 64 64 0 uniform 0 3 15
/tmp/define-scheduler-physical steal 128 compute 64 1000000 64 random 0 3 15
/tmp/define-scheduler-smt steal-smt 128 compute 64 1000000 64 random 0 3 15
/tmp/define-scheduler-physical steal 64 memory 1 160 32 random 262144 3 15
/tmp/define-scheduler-smt steal-smt 64 memory 1 160 32 random 262144 3 15
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
allocation, memory first-touch, and result validation. The ordinary performance
build checks that the complete task-and-memory checksum remains stable across
samples. For correctness and stress runs, add
`-DLITERAL_BENCHMARK_EXACT_EXECUTION_CHECKS=1`; this instruments every task with
an atomic execution count and requires exactly one execution. Do not time that
build because the instrumentation intentionally adds shared state and an atomic
operation to every task. The current target configuration uses processor 0 for a
serial chain, processors 0–7 as one topology group for same-group stealing, and
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

- selective Action Fragment inlining and direct-call expansion with real value
  behavior; the retained synthetic generated-code study establishes the
  instruction-front-end crossover but not value-specific optimization;
- optimization-level and code-alignment selection against realistic mixtures of
  Action Fragment cost, fanout, Join fan-in, and topology preference rather than
  adopting one synthetic-workload winner;
- `restrict`, scalar replacement, and compiler assumptions derived from proven
  Particle aliasing, address-identity, lifetime, and queue-capacity facts;
- function multiversioning and runtime target selection when one binary must run
  efficiently on materially different processors;
- scheduler behavior at generated-program scale with value-bearing Action
  Fragments, large live task and Join populations, and target diversity;
- topology-group generation publication between the measured per-worker and
  global forms for dense parked pools above eight workers;
- the release-decrement plus final-acquire-fence Join on weaker-memory-order
  targets with suitable race detection and hardware measurements;
- concurrent Join and hybrid-region measurements on physical AArch64 or gem5
  full-system Linux; gem5 syscall-emulation pthread barriers did not reach the
  measured region reliably.

Broader link-time-optimization performance, profile-guided optimization, and
scheduler designs involving multiple C translation units were deliberately
outside this study rather than deferred recommendations. The narrow
multi-translation-unit check recorded above establishes only that full link-time
optimization can recover cross-action elimination for a closed, serialized,
effect-free model. It does not establish that a fully scheduled parallel fixture
can erase.

## Rejected alternatives

### Bypass pthreads with raw clone

Raw `clone3` did not change steady-state scheduling performance. In the
stabilized short mixed-cost case, pthread and raw-clone workers both took
approximately 12.74--12.75 us under GCC and Clang. Across independent cold
processes with seven background workers, persistent pthread lifecycle cost
approximately 116 us before useful work. Proof-gated unguarded mapped or static
raw stacks sometimes reduced that to approximately 80--98 us, but the winning
stack representation changed between GCC and Clang, and guarded raw stacks did
not improve the cost consistently.

The small, inconsistent cold-start improvement does not justify owning the Linux
thread ABI. Correct raw workers require generated stacks, blocked asynchronous
signals, custom termination and waiting, and the exclusion or implementation of
libc access, foreign behavior, thread-local storage, sanitizers, and stack
protection. Use pthreads for worker lifecycle. The raw variants remain in the
benchmark only to reproduce this decision; codegen does not select them.

### Queue every runnable task

Queueing serial continuations cost two to three orders of magnitude more than
direct execution. Queueing is reserved for work that must become available to
another worker.

### One global ready queue

A global queue made its enqueue and dequeue positions coherence bottlenecks and
discarded the useful locality already present in fork-Join graphs.

### Publish a separate futex waiter flag

A separate Boolean can remain observably false after a worker has decided to
park, allowing a concurrent publisher to omit the wake and leave completed work
sleeping indefinitely. Generation and completion protocols instead encode the
waiter bit in the atomic word whose transition publishes work or completion, so
the returned previous value proves whether a wake is required.

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
activation is therefore a generated target-and-program policy selected from
runnable breadth, cost, and working-set evidence.

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
- Pthreads are a selected Linux worker-lifecycle boundary, not a required Action
  Execution synchronization mechanism; persistent workers execute the generated
  hot path without pthread calls.
- Raw-clone workers are retained only as a benchmark control for a rejected
  alternative; codegen does not select them.
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
- Grouped steals preserve runnable tasks but can change when and where they run.
  Their caps are generated policy choices driven by proven bounds, estimated
  cost, locality, and uncertainty. Each Chase-Lev task is still claimed with its
  own compare-exchange, and all additional claimed tasks are republished. Only a
  proven bounded SPMC injection queue may reserve a range with one
  compare-exchange.
- The synthetic measurements choose an initial architecture. Benchmarks of
  generated Define programs remain necessary before fixing constants or
  specializing Particle layout.
