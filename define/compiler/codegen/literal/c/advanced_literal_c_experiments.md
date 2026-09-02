# Advanced Literal C Experiments

This document records experiments that extend the scheduler, Join, and
pointer-free studies to generated-program shapes. It covers:

- combining several Join arrivals in one atomic operation and deriving
  satisfaction from the returned value;
- eliminating separate readiness publication after Join satisfaction;
- static, dynamic, and hybrid scheduling regions;
- large generated-code behavior; and
- multiple overlapping Action Executions.

The retained programs are experiments and codegen patterns, not a commitment to
one universal runtime. Each selected representation has a static eligibility
condition. Codegen should emit the least general eligible representation.

## Retained tools

- [`join_fusion_benchmark.c`](join_fusion_benchmark.c) compares flat Join
  counters with byte-lane counters packed into one atomic word, direct use of
  the returned satisfaction state with a ready-word round trip, and immediate
  with locally batched continuations.
- [`region_scheduler_benchmark.c`](region_scheduler_benchmark.c) compares
  one-worker Action Executions, static branch regions, dynamic branch regions,
  and mixed static/dynamic regions across simultaneous Action Execution counts.
- `//define/compiler/codegen/literal/c:generate_large_literal_c` emits
  semantically identical pointer-free programs as compact data, straight-line
  operations, bounded direct-call regions, a generated switch, or a function
  table.

All benchmarks verify every expected Particle Operation after the timed region.
The C sources compile as C23 with both GCC and Clang. Defining
`LITERAL_C_GEM5_ROI` adds gem5 work-begin and work-end markers and omits host
affinity calls that gem5 syscall emulation does not implement. It does not alter
native builds. Generated AArch64 binaries are static musl programs so QEMU and
gem5 do not depend on a target dynamic linker.

## Measurement environment

Native results were measured on 2026-09-01 on:

- Fedora kernel `7.1.8-200.fc44.x86_64`;
- AMD Ryzen 9 9950X, 16 physical cores and 32 hardware threads;
- two 32 MiB L3 topology groups, cores 0--7 and 8--15 respectively;
- 48 KiB L1 data, 32 KiB L1 instruction, and 1 MiB L2 per physical core;
- GCC 16.2.1 and Clang 22.1.8;
- all 32 CPU policies fixed to 4.300 GHz with the `performance` governor and
  energy-performance preference, and boost disabled; and
- benchmark workers pinned to distinct physical processors before SMT siblings
  are considered.

Unless a table says otherwise, native values are medians of nine independent
processes built with C23, `-O3`, and `-march=native`. The large-code programs
run on processor 0. LTO and profile-guided optimization are intentionally
excluded.

The AArch64 toolchain is Zig 0.16.0 targeting static `aarch64-linux-musl` with
`-mcpu=neoverse_v2`. QEMU 10.2.2 is used only for functional checking. gem5 is
v25.1.0.1 at commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`, configured for
AArch64, Ruby CHI, private 64 KiB L1 instruction and data caches, private 2 MiB
L2 caches, DDR4-2400 memory, a 3 GHz clock, and the gem5 Neoverse V2 O3 model.
gem5 reports modeled cycles; it does not predict the exact time of any
particular physical AArch64 processor.

## Fused Join arrivals and readiness

### Representation

When one completed Particle Operation contributes arrivals to several
small-count Joins, codegen can pack the independent counters into unsigned lanes
of one atomic word. One acquire-release fetch-subtract applies every arrival. In
every selected lane, a returned value of one means that this Particle Operation
satisfied that Join. A direct continuation therefore needs no separate readiness
publication.

The benchmark uses eight predecessor Particle Operations and up to eight Joins.
Every Join has four distinct predecessors, and each predecessor contributes to
up to four Joins. It compares:

1. compact independent counters;
2. cache-line-isolated independent counters;
3. a cache-line-isolated packed word; and
4. a compact packed word.

It can also publish newly satisfied identities to one ready word and reclaim
them with an acquire-release exchange. This is the smallest correct scheduler
round trip for the control experiment. It intentionally gives the readiness form
every opportunity to win; a real queue search can add more work.

Unsigned lane subtraction is valid only while no selected lane can reach zero
before its final statically known arrival. This prevents borrow from one lane to
another. The lane width must represent the exact initial count. Every arrival
must have statically known lane membership and multiplicity.

### Packing result

These values use 500,000 Action Executions, eight physical workers, and workless
continuations. Times are nanoseconds per Action Execution.

| Joins | GCC flat | GCC packed | Change | Clang flat | Clang packed | Change |
| ----: | -------: | ---------: | -----: | ---------: | -----------: | -----: |
|     1 |    8.052 |      6.224 | -22.7% |      6.372 |        7.514 | +17.9% |
|     2 |   11.206 |      8.112 | -27.6% |     15.343 |        8.277 | -46.1% |
|     4 |   19.693 |      8.032 | -59.2% |     19.965 |        8.551 | -57.2% |
|     8 |   31.091 |     13.805 | -55.6% |     35.273 |       14.473 | -59.0% |

The single-Join control does not justify the transformation: its result is
compiler-dependent because it changes only the atomic width. Two or more updated
Joins produce a robust fine-work win. At one million Action Executions, the
compact eight-Join packed form remained 54.7% faster under GCC and 51.2% faster
under Clang.

The isolated packed form enlarged every Action Execution from 72 to 128 bytes.
At large working sets that extra traffic erased much of the atomic saving. The
compact packed form is valid when the generated schedule prevents unrelated
worker groups from concurrently modifying adjacent words. Otherwise codegen must
isolate packed words whose writable lifetimes overlap, or retain flat counters.
This layout choice is part of scheduling, not a target-independent constant.

Packing is only material for fine continuations. This eight-Join matrix varies
the xorshift work performed by each satisfied continuation.

| Work |  GCC flat | GCC packed | Change | Clang flat | Clang packed | Change |
| ---: | --------: | ---------: | -----: | ---------: | -----------: | -----: |
|    0 |    31.248 |     13.790 | -55.9% |     30.418 |       13.674 | -55.0% |
|   64 |   469.414 |    475.063 |  +1.2% |    462.119 |      465.628 |  +0.8% |
| 4096 | 34173.449 |  34173.869 |  +0.0% |  34155.788 |    34153.719 |  -0.0% |

At 64 iterations the atomic saving is already amortized and can perturb which
worker executes independent continuations. Packing should therefore be selected
from the expected continuation cost, not merely from the number of counters it
can combine.

### Readiness and continuation result

For workless continuations, using the returned Join state directly consistently
beat publishing and reclaiming readiness. Each row uses the fastest measured
immediate or local-batch direct form for that compiler and representation.

| Joins and representation | GCC direct | GCC ready word |  Change | Clang direct | Clang ready word |  Change |
| ------------------------ | ---------: | -------------: | ------: | -----------: | ---------------: | ------: |
| One, flat                |      5.753 |         14.240 | +147.5% |        6.861 |           14.246 | +107.6% |
| Eight, flat              |     26.814 |         36.498 |  +36.1% |       25.804 |           34.811 |  +34.9% |
| Eight, packed            |     11.895 |         17.603 |  +48.0% |       14.003 |           23.495 |  +67.8% |

At 64 work iterations, readiness publication was usually neutral because
continuation work dominated. Direct use remains strictly less scheduler state
when the continuation is statically known and placement does not require
submission. The ready word remains necessary when the continuation must stay
individually claimable or move to another worker or topology group.

One completed Particle Operation can satisfy several Joins. Deferring those
continuations into a local mask before dispatching them changed the workless
eight-Join result as follows:

| Representation | GCC immediate | GCC local batch | Change | Clang immediate | Clang local batch | Change |
| -------------- | ------------: | --------------: | -----: | --------------: | ----------------: | -----: |
| Flat           |        33.633 |          26.814 | -20.3% |          31.128 |            25.804 | -17.1% |
| Packed         |        13.186 |          11.895 |  -9.8% |          14.003 |            16.832 | +20.2% |

This is a target-and-compiler code-shape decision. The harness retains
`JOIN_FUSION_BATCH_SATISFIED`; codegen should not infer it from Define
semantics.

### Information required from the compiler

Codegen needs:

- each Join's exact distinct completing predecessors and each predecessor's
  arrival multiplicity;
- which completed Particle Operations contribute to more than one Join;
- the maximum simultaneously live count in every candidate lane;
- whether every selected Join has the same lifetime and reset point;
- whether satisfaction may invoke a direct continuation, or must publish work
  for another worker;
- which simultaneously satisfied continuations may execute in either order;
- the estimated continuation costs and their uncertainty;
- which Action Executions and packed words can be concurrently writable; and
- target-calibrated costs for atomic widths, cache-line sharing, local batching,
  and the added lane-test instructions.

Packing must not combine semantically distinct Joins merely because they have
equal counts. It combines their arithmetic updates while preserving each Join's
independent satisfaction event.

## Hybrid static and dynamic regions

### Generated situation

The retained region benchmark has a direct serial prefix, a wide family of
independent branch regions, and a terminal Join enabling a direct serial suffix.
Each branch represents eight Particle Operations. Runtime-variable branches can
take either a fixed-cost or a more expensive path from a runtime seed; other
branches have fixed cost.

The compared schedules are:

- one worker executes a whole Action Execution directly;
- workers receive static contiguous branch regions and contribute one grouped
  arrival each;
- every branch is claimed dynamically and contributes one arrival; and
- runtime-variable branches are claimed dynamically while fixed branches use
  static regions, reducing the terminal Join to one arrival per static worker
  region plus one per dynamic branch.

A generated Define source established that this is not an artificially tiny
topology. It was produced with:

```sh
uv run python -m tools.generators.generate_operation_graph_source \
  --output /tmp/define_literal_hybrid.dfn \
  --repetitions 8 --move-chain-length 32 --tree-depth 32 \
  --wide-children 64 --pods 8 --retriggers 4 \
  --independent-move-branches 1024 \
  --independent-move-chain-length 64 \
  --fqun-prefix mv:define-lang.org:literal_c_hybrid
```

The 22,917-line source compiled without diagnostics into four actions, 13,777
Particle Operations, and 17,462 dependency arrivals. Its maximum fan-in and
fanout are both 1,024; 1,657 Particle Operations have multiple dependency
arrivals and 3,506 have fanout. The C benchmark isolates the wide-region shape
so schedule variants execute identical work.

### Fine uniform work

With 4,096 workless branches and eight workers, static scheduling won when one
Action Execution was live: 49.0 us under both GCC and Clang. With eight live
Action Executions, direct whole-execution sharding and static branch regions
were both about 10--11 us per Action Execution. At 32, static regions measured
6.49 us under GCC and 6.40 us under Clang. Fully dynamic claims cost much more
than the Particle Operations they distributed.

For overlapping fine work, branch-major dynamic identities reduced contention
and interleaved Action Executions better than execution-major identities. At 32
Action Executions, GCC's 16-unit claim took 52.7 us per Action Execution in
branch-major order versus 131.3 us execution-major; the corresponding hybrid
values were 10.5 and 21.9 us. Both remained slower than the 6.5 us static form.
Identity order is therefore a secondary generated choice, not a reason to use a
dynamic schedule.

### Sparse uncertainty

This case uses 4,096 branches, only every 64th branch runtime-variable, fixed
work of 64 iterations, and variable work of 16,384 iterations. Times are
microseconds per Action Execution.

| Compiler and executions | Whole execution | Static regions | Dynamic all |  Hybrid |
| ----------------------- | --------------: | -------------: | ----------: | ------: |
| GCC, 1                  |        1661.747 |        268.275 |     271.534 | 242.534 |
| GCC, 8                  |         223.235 |        223.456 |     227.300 | 212.511 |
| Clang, 1                |        1657.626 |        268.895 |     274.615 | 243.654 |
| Clang, 8                |         223.964 |        225.479 |     229.799 | 212.514 |

The one-execution hybrid is 9--11% faster than the best static or fully dynamic
alternative under both compilers. At eight executions it retains about a 5--7%
advantage. It keeps the 4,032 fixed branches out of the shared claim cursor
while allowing all workers to balance the 64 uncertain branches.

When variable work rose to 65,536 iterations, GCC's one-execution hybrid took
652.9 us, versus 698.6 us for the best fully dynamic form and 790.2 us for
static regions. At low variable cost, scheduling overhead dominates and static
regions can match hybrid. At very high cost, dynamic and hybrid converge because
claim overhead is amortized.

### Millisecond-scale work and overlapping Action Executions

This case uses 256 branches, every eighth branch runtime-variable, and 500,000
xorshift iterations on the selected path. Each selected path is approximately
millisecond-scale on the native machine. GCC and Clang agreed within about 0.5%.
Representative GCC times are milliseconds per Action Execution.

| Executions | Whole execution | Static regions | Dynamic all | Hybrid |
| ---------: | --------------: | -------------: | ----------: | -----: |
|          1 |          21.989 |          4.209 |       3.172 |  3.174 |
|          8 |           2.755 |          2.488 |       2.094 |  2.095 |
|         32 |           2.385 |          2.517 |       2.092 |  2.093 |

One Action Execution cannot use all workers under whole-execution sharding. With
eight or more, it uses all workers but still preserves cost variance within each
private Action Execution. Individual claims balance that variance across
executions and remain about 12--17% faster. Dynamic and hybrid converge because
the expensive uncertain branches dominate; dynamically claiming fixed branches
is then measurable only in the fine and moderate ranges.

Large claims are unsafe for heterogeneous costs. For one execution, a 16-branch
dynamic claim took about 4.21 ms versus 3.17 ms for claims of one or four. In
the hybrid schedule, a 16-unit claim over uncertain branches took 11.51 ms
because it concealed expensive work. The compiler needs a bound on cost variance
before it can group claims.

### Information required from the compiler

Codegen needs:

- the exact statically independent Particle Operation regions and their
  predecessor and successor relationships;
- which region costs and runtime paths are proven fixed, bounded, profiled, or
  unknown;
- cost bounds and variance, not only mean cost;
- exact terminal Join arrivals contributed by a complete static region and by
  each dynamic region;
- the number of Action Executions expected to be live simultaneously;
- whether source identity order correlates with cost;
- each region's Particle access set and working-set size;
- whether completing one Action Execution earlier has value beyond total
  throughput; and
- target-calibrated claim, atomic-arrival, and cache-locality costs.

These facts let codegen emit whole-execution sharding, static regions, a hybrid,
or full dynamic claiming specifically for the compiled program. Unknown cost
must stay claimable. Proven fixed work need not enter a general scheduler merely
because uncertain work exists elsewhere in the action.

## Large generated code

### Compilation behavior

The generator emits the same observable updates to 64 Particle values in five
forms. Every completed binary produced the same checksum. These are cold compile
times in seconds; `regions` uses 64 Particle Operations per no-inline function.
A dash means the compile was stopped or omitted after an established compiler
cliff.

| Compiler | Operations | Compact | Direct | Functions | Regions | Switch |
| -------- | ---------: | ------: | -----: | --------: | ------: | -----: |
| GCC      |        256 |    0.03 |   0.13 |      0.25 |    0.10 |   0.22 |
| GCC      |      4,096 |    0.04 |   1.53 |      3.51 |    1.10 |   1.29 |
| GCC      |     16,384 |    0.06 |   9.40 |     14.47 |    4.35 |  13.64 |
| GCC      |     65,536 |    0.14 |  65.43 |     58.62 |   17.61 |  80.37 |
| Clang    |        256 |    0.04 |   0.10 |      0.09 |    0.07 |   0.10 |
| Clang    |      4,096 |    0.04 |   2.61 |      0.80 |    0.56 |  20.40 |
| Clang    |     16,384 |    0.05 |  33.85 |      3.67 |    2.29 |  >60.0 |
| Clang    |     65,536 |    0.08 |  >60.0 |     15.92 |    9.51 |      - |

At 65,536 operations, GCC's direct compile peaked at about 1.43 GiB and emitted
2.26 MiB of text. Its function form peaked at 1.63 GiB and emitted 5.25 MiB; the
generated switch peaked at 1.75 GiB and emitted 3.13 MiB. Sixty-four-unit
regions used about 604 MiB and emitted 2.30 MiB. GCC and Clang compact forms
compiled in at most 0.14 seconds and emitted about 528 KiB, mostly the constant
table. Clang's 65,536-operation region form used about 438 MiB and emitted 1.73
MiB.

Bounded functions control compiler memory and compile time but do not by
themselves make the instruction working set compact. Region sizes from 16 to
1,024 left GCC's 65,536-operation text between 2.28 and 2.40 MiB and Clang's
between 1.73 and 2.12 MiB.

### Native runtime

These values are nanoseconds per generated Particle Operation. `Regions` again
uses 64 operations per function.

| Compiler | Operations | Compact | Direct | Functions | Regions | Switch |
| -------- | ---------: | ------: | -----: | --------: | ------: | -----: |
| GCC      |        256 |   0.545 |  0.265 |     1.398 |   0.272 |  0.929 |
| GCC      |      1,024 |   0.531 |  0.530 |     5.406 |   0.881 |  1.477 |
| GCC      |      4,096 |   0.527 |  0.496 |    11.071 |   0.491 |  7.826 |
| GCC      |     16,384 |   0.526 |  0.526 |    12.451 |   0.531 | 12.909 |
| GCC      |     65,536 |   0.527 |  1.165 |    15.877 |   1.158 | 22.995 |
| Clang    |        256 |   0.418 |  0.161 |     1.396 |   0.462 |  1.341 |
| Clang    |      1,024 |   0.403 |  0.259 |     5.317 |   0.463 |  0.871 |
| Clang    |      4,096 |   0.399 |  0.395 |    11.008 |   0.463 |  0.896 |
| Clang    |     16,384 |   0.400 |  0.416 |    12.440 |   0.463 |      - |
| Clang    |     65,536 |   0.399 |      - |    15.600 |   0.554 |      - |

Straight-line code is best for small generated bodies and remains competitive
through 4,096--16,384 operations, depending on compiler. The compact loop has a
nearly constant cost across all tested sizes. At 65,536 operations it is 55%
faster than GCC direct code and 26% faster than Clang's best measured region
size.

The region-size sweep shows that there is no portable boundary. GCC's fastest
sizes were 64 at 4,096 operations, 16 at 16,384, and 1,024 at 65,536. Clang's
fastest were 256 at 4,096 and 16,384 operations, then 64 at 65,536. Clang's
256-operation regions reached 0.334 and 0.308 ns per operation at 4,096 and
16,384, faster than its compact and monolithic direct forms. At 65,536, every
tested direct-region size lost to compact data.

### Hardware counters

Representative `perf stat` values used longer runs and five repetitions.

| Compiler and shape | Operations | Cycles (millions) | Instructions (millions) | L1 instruction misses |
| ------------------ | ---------: | ----------------: | ----------------------: | --------------------: |
| GCC compact        |     65,536 |             152.4 |                   867.9 |                 6,142 |
| GCC direct         |     65,536 |             337.5 |                   378.6 |               927,848 |
| GCC regions, 1,024 |     65,536 |             327.7 |                   375.8 |               467,791 |
| Clang compact      |     16,384 |             115.5 |                   634.8 |                 5,991 |
| Clang regions, 256 |     16,384 |              85.8 |                   206.1 |               593,866 |
| Clang compact      |     65,536 |             115.4 |                   633.9 |                 6,109 |
| Clang regions, 64  |     65,536 |             156.3 |                   186.2 |               702,485 |

At medium size, direct regions can retire far fewer instructions and repay
instruction fetches. At large size, front-end traffic dominates and the compact
loop wins despite retiring more instructions. Source operation count alone
cannot locate the crossover because compiler instruction selection and region
formation change it.

### Information required from the compiler

Codegen needs:

- the number of emitted Particle Operations after semantic specialization;
- the expected generated instruction count and constant-data size, or a target
  calibration that estimates them;
- hot execution frequency for each generated region;
- whether a repeated operation family can use compact operands and one direct
  interpreter-like loop without losing required specialization;
- natural direct-call region boundaries from dependency and scheduling facts;
- estimated compile-time and compiler-memory budgets;
- the selected compiler, version, target ISA, and optimization level; and
- whether the program is closed to optional LTO or profile-guided optimization.

The final item is recorded for future investigation; this experiment does not
use LTO or profile-guided optimization. Codegen should calibrate a small set of
representation thresholds per supported target/compiler pair. It should not emit
a function per Particle Operation or a giant switch as a general literal
representation.

## AArch64 validation

All selected AArch64 binaries run successfully under QEMU, including flat and
packed Joins, static and hybrid region schedules, compact generated code, and
direct regions. QEMU values are not timing results. Zig emits the Neoverse-V2
LSE acquire-release `ldaddal` instruction for the packed fetch-subtract rather
than an LL/SC loop.

The first gem5 binary was built with unsupported host GCC 16 and crashed in the
O3 model before useful execution; no result from it is retained. A separate
host-Clang 22 build completes the model. Startup uses a Timing core, then an
in-program work-begin marker switches to the Neoverse V2 O3 model and resets
statistics.

For 256 generated Particle Operations repeated 1,000 times, gem5 modeled:

| Representation |       Ticks | 3 GHz cycles | Cycles per Particle Operation |
| -------------- | ----------: | -----------: | ----------------------------: |
| Compact data   | 343,183,806 |    1,029,551 |                         4.022 |
| Direct code    | 218,828,286 |      656,485 |                         2.564 |

Direct code used 36.2% fewer modeled cycles, agreeing with the native small-code
direction without claiming that the Ryzen ratio transfers to AArch64.

gem5 syscall-emulation mode did not produce an accepted concurrent result. After
affinity was correctly omitted for simulated cores, its pthread barrier made
hundreds of thousands of consecutive AArch64 store-conditional failures before
the work marker. The run was stopped before measurement. Concurrent Join and
hybrid-region timing therefore remains native evidence; AArch64 concurrency
needs a gem5 full-system Linux image or physical hardware. No simulator failure
is reported as a result about Define scheduling.

The optional `pydot` package was absent, so gem5 did not draw a topology graph.
That does not affect configuration or modeled statistics. Capstone, HDF5, and
PNG support are likewise not on the timing path.

## Resulting selection rules

The experiments support a generated portfolio:

1. Use the subtract result to invoke a statically known, locally placed
   continuation directly. Do not publish readiness merely to reclaim it.
2. Pack two or more Joins only when one completion contributes to several
   counters, lane arithmetic is proven valid, writable layout is safe, and
   continuations are fine enough to repay the extra lane tests.
3. Keep proven fixed work in static regions. Dynamically claim only uncertain
   regions when sparse uncertainty can cause meaningful imbalance.
4. Prefer whole-Action-Execution sharding when enough similarly costly Action
   Executions are live. Preserve finer claimability when cost variance remains
   material across those executions.
5. Use small direct code for hot bounded regions. Use target-calibrated direct
   region sizes at medium scale and a compact representation before generated
   instruction text exceeds the target's useful front-end working set.
6. Keep compiler-dependent batching, claim size, identity order, and region size
   as calibrated codegen decisions. None changes Define semantics.
