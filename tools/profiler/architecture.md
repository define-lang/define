# Compiler Profiler Architecture Decision and Requirements

- Status: Accepted for implementation
- Date: 2026-08-09
- Scope: `tools/profiler/`, `tools/run_profile.py`, `tools/analyze_profile.py`,
  and the `profile-compiler` skill

## Decision

Replace py-spy as the primary compiler profiling backend with a statistical
profiler that we control.

For Python 3.14t, the profiler will take externally scheduled, blocking stack
snapshots through CPython's `_remote_debugging.RemoteUnwinder`. It will suspend
the complete compiler process, capture every live Python thread, collect the
corresponding external timing data, and resume the process. Profiling work must
not run on every Python call, return, line, or opcode.

While the process is already stopped, the profiler may enrich a generated
dataclass constructor frame with the constructed object's type name through
CPython's remote debug-offset table. This work is part of the same randomized
snapshot and does not execute code in the compiler or create an additional
observation point.

Wall attribution is the primary result. CPU attribution is secondary. The raw
profile will consist of independent timestamped samples, not synthesized open
and close events. The analyzer will derive self attribution, cumulative
attribution, caller and callee relationships, and sampled continuous spans from
those samples.

`run_profile` is an orchestration tool, not part of the profiler implementation.
Its job is to build the compiler, prepare the requested source or project
invocation, run a selected profiling tool, and propagate success or failure. It
must not know how a profiler samples stacks, stops processes, measures CPU time,
or serializes its native profile. The new profiler will have its own binary or
library entry point under `tools/profiler/`. Its capture mechanism and raw
format belong behind that entry point.

Time spent suspending and inspecting the compiler will not be charged to the
sampled function. The sampling schedule will be independent of the functions
being executed and will use randomized intervals to avoid synchronization with
periodic compiler behavior.

The profiler will not use compiler phase markers or any other compiler
instrumentation. Like a normal profiler, it will capture complete stacks. The
analyzer will calculate ordinary self and cumulative attribution from those
stacks. Compiler phases can be understood from their functions, callers,
callees, filenames, and source entry points.

The first CPU implementation will evaluate external per-thread scheduler runtime
paired with sampled Python stacks. If that mechanism cannot pass the CPU
accuracy requirements, CPU capture will use Linux perf with CPython's Python
frame support. For CPU profiling, accurate attribution takes precedence over the
smaller call-correlated cost introduced by CPython's perf stack trampolines. The
wall profiler must remain free of call-correlated target-side work.

When Define moves to Python 3.15t, evaluate replacing the custom collector with
the standard-library `profiling.sampling` profiler, also known as Tachyon. It
uses the same runtime-owned external-inspection approach and already provides
wall, CPU, all-thread, blocking, and structured-profile modes. The custom raw
format and analyzer should therefore avoid unnecessary coupling to Python 3.14
internals. See the [Python 3.15 sampling profiler documentation][tachyon].

## Context

The compiler profiler must explain where elapsed compilation time is attributed,
not merely measure total compilation duration. It must work on large generated
sources, free-threaded Python, and compiler phases that create and retire worker
threads.

The `profile-compiler` workflow requires:

- wall critical-path analysis as the primary report;
- CPU hotspot analysis as a secondary report;
- complete Python caller and callee stacks;
- all-thread attribution under free-threaded execution;
- source filenames, line numbers, and function names;
- imports and startup, parse and lexing, AST transformation, reference-graph
  validation, requirement inference and destruction contracts, guarantee
  propagation, operation-graph construction, and code generation;
- focused workloads from every generator under `tools/generators/`; and
- retained machine-readable evidence that can answer later questions without
  rerunning a workload.

Overall duration variation is not itself a problem. Attribution bias is a
problem. In particular, a profiler must not make a frequently called function
look expensive merely because the profiler performs work on every call.

## Why py-spy Is Being Replaced

The current wall profile path records py-spy Chrome trace events with idle
threads included. The trace writer keeps a previous stack for each observed
thread. When a thread disappears, it does not necessarily emit close events for
that thread. At process completion, unfinished stacks are closed at the final
process timestamp.

This gives the final sampled leaf of a retired thread all remaining process
time. Hash seeding and CPU affinity changed which leaf received the time but did
not remove the false attribution.

Correcting the profiles by ending a thread at its last observation produced
these examples:

| Function                                   | Reported wall self | Corrected wall self | False tail |
| ------------------------------------------ | -----------------: | ------------------: | ---------: |
| `_apply_empty_rule_reduction_newest_first` |            1.140 s |             0.062 s |    1.078 s |
| `find_shortest_prefix_where`               |            1.265 s |             0.173 s |    1.092 s |
| `_get_chain_element_definition`            |            1.076 s |             0.083 s |    0.993 s |
| `_analyze_statements`                      |            1.034 s |             0.054 s |    0.980 s |
| `_validate_action`                         |            0.931 s |             0.000 s |    0.931 s |
| `get_occupancy_info`                       |            0.972 s |             0.007 s |    0.965 s |
| `_auto_destruct_locals`                    |            0.940 s |             0.000 s |    0.940 s |

Matching raw CPU profiles did not contain the approximately one-second spikes.
The wall failure was therefore attribution corruption, not ordinary run-to-run
timing variation.

The project also currently pins an unreleased py-spy commit for minimal Python
3.14t support. That makes correctness depend on both an upstream development
branch and local interpretation of a format whose lifecycle semantics are not
suitable for this workflow.

## Prototype Evidence

The proposed CPython inspection primitive was tested against one 25,788,623-byte
generated source with four compiler worker threads.

### Non-blocking capture

A non-blocking `RemoteUnwinder` probe was rejected. It produced 10,557 usable
observations and 1,626 failed observations, a failure rate of approximately
13.3%. Failures included inconsistent addresses, invalid strings, and changing
frame data. Discarding that many samples could systematically underrepresent
functions whose stacks change rapidly.

### Blocking capture

The process was then stopped before every snapshot and resumed immediately
afterward. Three captures produced:

| Run | Process elapsed | Usable observations | Discarded observations | Python threads |
| --- | --------------: | ------------------: | ---------------------: | -------------: |
| 1   |        24.812 s |               2,452 |                      0 |              5 |
| 2   |        24.582 s |               2,429 |                      1 |              5 |
| 3   |        24.238 s |               2,395 |                      1 |              5 |

No malformed stack was retained. A discarded observation was never replaced with
an older stack.

The four worker stacks disappeared 10–20 ms before the main Python stack. All
Python stacks disappeared approximately 0.9 seconds before the process exited,
during native interpreter shutdown. A lifecycle-safe sampler leaves that final
interval unattributed to Python. The py-spy trace behavior instead assigned it
to whichever Python leaf had most recently been observed.

The prototype used provisional duration weighting that still included some
profiler pause time. Its values are not acceptance measurements. They do,
however, show that consistent snapshots produce repeatable attribution:

| Frame metric                             |  Run 1 |  Run 2 |  Run 3 | Range / mean |
| ---------------------------------------- | -----: | -----: | -----: | -----------: |
| `_Parser.parse` cumulative               | 10.117 | 10.166 | 10.018 |         1.5% |
| `ContextualLexer.lex` cumulative         |  5.312 |  5.410 |  5.615 |         5.6% |
| `Driver.run` cumulative                  |  5.165 |  5.152 |  4.921 |         4.8% |
| `Scanner.match` self at the sampled line |  2.073 |  2.006 |  2.184 |         8.5% |

The production collector must improve on the prototype by measuring and
excluding the complete stop/read/resume interval before assigning sample
weights.

## Alternatives Considered

### Deterministic Python profilers

This group includes `cProfile`, Yappi, VizTracer, and custom collectors based on
`sys.setprofile`, `threading.setprofile_all_threads`, or `sys.monitoring` call
and return events.

They were rejected as the primary profiler. Their work is correlated with
function-call frequency. A path composed of many short calls can receive more
profiler overhead than a path with the same unprofiled cost and fewer calls.
That can change the ranking the profiler is supposed to measure. VizTracer also
records every function entry and exit, which creates unnecessary trace volume
for generated stress workloads. See the [VizTracer concurrency and tracing
documentation][viztracer].

Deterministic instrumentation remains appropriate when exact call counts are the
question. It must not be used to rank normal compiler hotspots.

### Pyinstrument

Pyinstrument reports wall time, but it samples through `PyEval_SetProfile` and
records at call boundaries. Long periods are recorded when calls return. This
mechanism does not meet the requirement that target-side work be independent of
call frequency. See [Pyinstrument's description of its mechanism][pyinstrument].

### Linux perf with CPython frame trampolines

Linux perf recorded the compiler without lost kernel samples, and direct use of
the generated Python environment with `-X perf` exposed Python frame names.
CPython's perf support makes Python frames visible through stack trampolines
interposed on Python calls. That cost is much smaller than `cProfile`, but it is
still correlated with call frequency.

Perf is accepted as the CPU fallback because an inaccurate CPU profile is worse
than the smaller, measurable trampoline bias. If external scheduler-runtime
correlation cannot pass the CPU accuracy fixtures, the profiler entry point will
run perf against the generated Python environment with `-X perf`, and the
analyzer will derive Python self and cumulative CPU attribution from its sampled
call chains. Perf will not replace the blocking wall sampler. See the [CPython
perf documentation][perf].

### Austin

Austin is an external sampler and is architecturally closer to the desired
profiler. It can collect wall and CPU-related sample data without Python call
hooks. Python 3.14t support, however, is currently present only on its
development branch and is awaiting a release. The upstream validation history
also shows that earlier free-threaded captures had very high error rates. Moving
from one pinned development profiler to another would not provide the desired
reliability improvement. See Austin's [free-threaded support
issue][austin-issue] and [implementation pull request][austin-pr].

Austin can be reconsidered after a release and a repository-specific lifecycle,
bias, and repeatability evaluation.

### eBPF and continuous profilers

Kernel profilers can measure on-CPU and off-CPU scheduling accurately. The
remaining problem is mapping a free-threaded CPython process back to complete
Python stacks without target-side call instrumentation. A system profiler would
therefore still require a runtime-specific Python unwinder or CPython stack
trampolines. Building only the narrow runtime-specific component needed by this
repository is simpler than adopting a continuous-profiling service.

### CPython 3.15 `profiling.sampling`

Tachyon is the preferred long-term backend. It is runtime-owned, version-aware,
external, all-thread capable, and explicitly supports blocking stack capture,
wall mode, CPU mode, native frames, raw data, and timeline formats. It cannot
profile the current Python 3.14t compiler because the profiler and target must
use matching Python minor versions.

The current implementation therefore mirrors Tachyon's sampling model while
remaining limited to what the repository needs. CPython's external inspection
work is based on its safer remote-debugging interface; see [PEP 768][pep-768].

## Architecture

### Profile orchestration

`run_profile` builds the compiler, resolves its source or project invocation,
prepares stdin and the code-generation destination, invokes one selected
profiling tool, and checks the compiler and profiling-tool results. It may pass
generic capture inputs such as the destination profile path, requested wall or
CPU mode, working directory, environment, stdin, and target command.

`run_profile` does not import the new profiler's collector, inspect PIDs, send
signals, interpret stacks, calculate sample weights, select a native profile
format, or understand CPython internals. Supporting a profiling tool means
running that tool through its public command-line or library entry point, not
embedding that tool's implementation into `run_profile`.

### Profiler entry point

The new profiler has a separate entry point under `tools/profiler/`. It owns
process launch and attachment, stack sampling, timing collection, its native raw
format, and capture diagnostics. The analyzer owns interpretation of the native
profile.

The profiler entry point does not need to calculate self or cumulative values.
It must preserve complete stacks, sample weights or the observations needed to
derive them, thread identity, lifecycle information, and the synchronized
thread-state and handoff evidence needed for critical-path analysis. The
analyzer alone turns that evidence into self, cumulative, and critical-path
reports.

The Bazel compiler executable begins as a shell launcher and later executes the
real Python interpreter. The profiler must not initialize an unwinder merely
because the launcher PID exists. It must verify the executable mapped by that
PID and obtain at least one valid Python stack before declaring attachment
successful.

The profiler owns cleanup and must resume the compiler in a `finally` path after
every successful stop, including collector failures and user interruption.
Launcher execution, sampling deadlines, target stops, and target exit are
observed through Linux process and timer events rather than fixed-duration
polling. The profiler exposes newline-delimited coordination events through an
optional caller-provided file descriptor so integration tests and orchestration
can synchronize with actual profiler state.

### Sampling controller

The controller chooses sample intervals independently of compiler state. It uses
a Poisson schedule whose exponentially distributed intervals have the configured
mean. This avoids repeatedly sampling the same point in periodic work and gives
observations the Poisson-arrivals-see-time-averages property when the compiler
cannot anticipate the sampling schedule.[PASTA][pasta]

For each sample, the controller will:

1. Record the start of the profiler-induced pause.
2. Stop the complete compiler thread group and confirm it is stopped.
3. Read only the raw thread identity, timing, and stack data that requires a
   stopped target.
4. Resume the complete thread group.
5. Record the end of the profiler-induced pause.
6. Validate and normalize the copied snapshot after the target resumes.
7. Persist the sample or persist a failure record on an ordered background
   worker.

The raw sample's attribution weight excludes steps 2 through 5. A deeper stack,
larger live-thread set, slower filesystem, or slower serializer must not add
attributed time to the sampled function. The next sampling deadline is armed
before the completed snapshot enters the background pipeline, so post-resume
processing does not add another full sampling interval.

### Wall attribution

Wall mode samples every live Python thread, including a thread waiting on I/O, a
lock, a condition, or work. It measures where the compiler's permitted running
time passes, excluding profiler-induced suspension.

Each sample is independent. A thread that is absent from a later sample has no
stack after its last valid observation. The analyzer may interpolate a boundary
within one sampling interval, but it may never extend the thread to process
exit.

### CPU attribution

CPU mode must remain statistical. The initial implementation will pair each
thread's sampled Python stack with cumulative kernel scheduler runtime from
`/proc/<pid>/task/<tid>/schedstat`. CPU deltas between samples provide the
weight available for attribution to the endpoint stacks.

Because a thread can change stacks between endpoints, this is an estimate. The
collector will use short randomized intervals, retain both endpoint stacks, and
record enough raw data to change the attribution policy without recapturing the
profile. Intervals with missing endpoints or retired short-lived threads must be
reported, not silently assigned to another stack.

The CPU design is accepted only after passing the transition, short-function,
waiting-thread, and call-frequency bias tests below. If it cannot pass them, the
CPU backend will invoke Linux perf with CPython Python-frame support. Perf's
sampled Python call chains must give the analyzer the same self, cumulative,
caller, and callee information as the external-counter design. The selected CPU
backend and whether CPython stack trampolines were enabled must be recorded in
the profile and displayed in the report.

CPU backend selection must not weaken wall profiling. Wall capture continues to
use blocking external snapshots even if CPU capture uses perf.

### Raw profile format

The raw format is the source of truth. Human-readable tables and visualizations
are derived products.

The format must contain:

- a schema version;
- the exact command and working directory;
- target Python version, free-threaded status, and executable identity;
- workload path and a content digest;
- sampling-mode and schedule configuration;
- configured and observed interval statistics;
- host monotonic timestamps and target-running logical timestamps;
- profiler pause duration for every observation;
- process and OS thread identifiers;
- per-thread execution states and observable wait, wake, and handoff evidence
  needed to relate work across threads;
- complete ordered Python stacks with filename, function name, and line number;
- per-thread cumulative CPU runtime when collected;
- CPU backend identity and perf configuration when applicable;
- explicit failed-observation records and reasons;
- thread first-seen and last-seen observations;
- compiler exit status and diagnostics status; and
- counts of attempted, successful, discarded, and missed observations.

Under PRF-024, machine-readable observation and capture failure kinds are
closed, versioned string enums. Exception class names and messages are evidence
in the human-readable failure reason, not ad hoc failure codes.

The collector must write incrementally so an interrupted or failed compiler can
still leave diagnosable evidence. A partial file must be explicitly marked
incomplete.

### Analyzer

The analyzer will operate only on the raw sample records. It will not infer
thread lifetime from unclosed trace events.

Wall reports will provide:

- self wall occupancy for leaf frames;
- cumulative wall occupancy for every frame in a sampled stack;
- the longest sampled continuous span for a frame and stack path;
- caller and callee breakdowns;
- per-thread and union-across-thread views; and
- compiler-only and complete-Python views.

Overlapping wall intervals for the same function on several threads are unioned
for process wall occupancy. Function rows can overlap and do not sum to total
wall time.

The completed wall analyzer will also provide a sampled critical-path view for
the entire compiler invocation. It will reconstruct the time-ordered chain of
work and waits that constrained completion, including observable handoffs
between threads, and attribute every resolved segment to its Python stack and
functions. It must distinguish this chain from the busiest thread, the sum of
thread time, and unioned function occupancy. A transition that the recorded
evidence cannot resolve must appear as an uncertain gap rather than as an
invented dependency.

CPU reports will provide self and cumulative attributed CPU estimates. CPU time
can exceed wall time when several workers execute concurrently. Reports must
show how much CPU runtime could not be attributed because of missing or
ambiguous samples.

Every report will include sample counts, sampling intervals, discarded-sample
rate, profiler-pause totals, thread counts, and confidence or resolution
caveats. A sample hit must never be described as a function call.

### Code and test design

Implementation expresses the current profiler design directly. It does not
retain py-spy formats, command flags, adapters, aliases, transitional schemas,
or analyzer paths merely to preserve previous behavior. When a checkpoint
supersedes a path in `run_profile`, `analyze_profile`, or the profiling
dependencies, that path is removed in the same checkpoint.

Defensive code is limited to failures that can occur in the deployed workflow,
such as permission failures, target exit during sampling, interruption while
writing a profile, malformed data read from an actual partial profile, and
failure to resume a real target. The implementation does not add fallback
values, optional states, exception handlers, or branches for situations that
cannot occur under the established invariants.

Tests use real processes, real threads, real files, real signals, real `/proc`
data, the actual profiler entry point, and the actual analyzer wherever the
platform provides them. Mocks are exceptional. A mock must represent an event
that occurs in the real workflow, must be the smallest practical replacement for
the unavailable boundary, and must not replace an available end-to-end test.
Synthetic test programs are acceptable when they execute the same OS and CPython
mechanisms as the compiler and isolate a measurable attribution property.

Every implementation checkpoint is a vertical slice. It produces a real profile
artifact and has an analyzer that consumes that exact artifact through its
public entry point. A collector without a consuming analyzer is not a working
checkpoint.

## Requirements

### Attribution correctness

1. **PRF-001: No call-correlated wall profiling work.** The wall profiler must
   not install call, return, line, instruction, or opcode hooks. It must not use
   a mechanism whose target-side cost is proportional to Python call count. CPU
   profiling may use CPython perf stack trampolines only after the external CPU
   design fails its accuracy requirements.
2. **PRF-002: Independent sampling schedule.** Sample timing must be chosen
   without inspecting the current function. The default schedule must include
   jitter.
3. **PRF-003: Pause exclusion.** All time during which the profiler has stopped
   the compiler must be excluded from function attribution weights.
4. **PRF-004: No stale-stack reuse.** A failed observation contributes no stack.
   The collector must not repeat the previous stack as a fallback.
5. **PRF-005: Lifecycle-bounded attribution.** A thread's attribution ends no
   later than one sampling interval after its final valid observation. Process
   shutdown must never extend a retired thread's last stack.
6. **PRF-006: Complete-process stop.** A blocking snapshot must stop every
   compiler thread before any stack is inspected.
7. **PRF-007: Consistent stack.** A retained sample must represent one coherent
   stack snapshot. Partial or internally inconsistent stacks are discarded and
   counted.
8. **PRF-008: Depth independence.** Stack collection cost must not be included
   in attribution. A deeper stack may cost more to inspect but must not receive
   more profile weight for that reason.
9. **PRF-009: Thread-count independence.** Additional live threads may make a
   snapshot slower, but that additional profiler time must not be attributed to
   any compiler function.
10. **PRF-010: Raw-data preservation.** Weighting and interpolation decisions
    belong to analysis. The raw capture must retain sufficient observations to
    reanalyze with a different policy.

### Functional behavior

1. **PRF-011: Complete invocation.** Capture records the launcher transition in
   lifecycle metadata. Python stack attribution begins when the launcher
   executes the Python target and covers imports, compilation, code generation,
   Python shutdown, and the compiler exit status.
2. **PRF-012: Orchestration boundary.** `run_profile` preserves the existing
   `--source`, `--project`, `--entry`, `--max-threads`, and code-generation
   destination behavior while invoking profilers only through their public entry
   points. It must not contain profiler implementation logic.
3. **PRF-013: Wall mode.** Wall mode captures active and waiting Python stacks
   across all compiler threads.
4. **PRF-014: CPU mode.** CPU mode first attempts externally measured per-thread
   CPU attribution. If that design fails the CPU accuracy fixtures, it uses
   Linux perf with CPython Python-frame support. Reports identify the selected
   backend, show self and cumulative CPU attribution, and report unattributed
   runtime when applicable.
5. **PRF-015: Full stacks.** Every retained thread sample contains the complete
   available Python caller-to-leaf stack.
6. **PRF-016: Source identity.** Frames include full filename, function name,
   and current source line.
7. **PRF-017: No compiler instrumentation.** Profiling requires no compiler
   phase markers, decorators, context managers, callbacks, or other source
   instrumentation. Self and cumulative attribution come from sampled stacks.
8. **PRF-018: Focused analysis.** The analyzer supports caller, callee, thread,
   file, function, and compiler-only filtering without discarding those
   dimensions during capture.
9. **PRF-019: Concurrency semantics.** Wall occupancy unions overlaps across
   threads, while CPU attribution retains concurrent CPU work and may exceed
   wall time.
10. **PRF-020: Machine and human interfaces.** Capture is machine-readable and
    the analyzer emits stable human-readable summaries suitable for the
    `profile-compiler` skill.

### Reliability and diagnostics

1. **PRF-021: Version match.** The profiler verifies the target executable,
   Python minor version, and free-threaded status before accepting samples.
2. **PRF-022: Launcher safety.** The unwinder is not retained if it was created
   before the launcher executed the Python target.
3. **PRF-023: Guaranteed resume.** Every stop has a corresponding resume in a
   `finally` path. Profiler failure must not leave the compiler stopped.
4. **PRF-024: Explicit failures.** Permission errors, malformed stacks, missed
   intervals, process-exit races, and serializer failures are recorded
   separately.
5. **PRF-025: Failure threshold.** Excluding the observation that races with a
   confirmed process exit, at least 99.9% of attempted blocking observations
   must be retained on the repository stress workloads.
6. **PRF-026: No silent partial success.** A capture with compiler diagnostics,
   a nonzero compiler exit, an incomplete raw profile, or a failure rate above
   the threshold is not a successful profile.
7. **PRF-027: Incremental persistence.** A crash or interruption preserves all
   complete preceding records and clearly marks the profile incomplete.
8. **PRF-028: Bounded storage.** The collector interns or otherwise deduplicates
   repeated frame data. Storage growth must be feasible for the largest
   generated workloads.
9. **PRF-049: Event-driven coordination.** Launcher execution, sampling
   deadlines, target stops, and target exit use explicit kernel events rather
   than fixed-duration polling. A caller can observe launcher recording, Python
   attachment, target stop, and successful-observation-persisted events without
   guessing a delay.
10. **PRF-050: Minimal stopped section.** While the target is stopped, the
    sampler performs only kernel stop confirmation and raw reads whose
    consistency requires the stop. Validation, frame conversion, allocation of
    profile-domain objects, serialization, and persistence happen after resume.
11. **PRF-051: Schedule-isolated persistence.** An ordered background worker
    validates, normalizes, interns, serializes, and persists copied
    observations. The sampler arms the next deadline before handing off the
    previous snapshot. An unbounded in-memory queue makes observation handoff
    independent of worker progress, and worker failure propagates through an
    explicit event without polling.

### Bias and lifecycle acceptance tests

1. **PRF-029: Call-frequency fixture.** Two paths with equal unprofiled work but
   substantially different Python call counts must receive attribution
   consistent with their known work ratio and sampling confidence bounds. The
   test applies to wall capture and to whichever CPU backend is selected. A perf
   CPU report must disclose any measured trampoline bias.
2. **PRF-030: Stack-depth fixture.** Equal work performed at different stack
   depths must not systematically favor the deeper or shallower path.
3. **PRF-031: Retired-thread fixture.** A worker exits while the main thread
   continues for at least one second. No worker frame may receive the remaining
   main-thread or shutdown interval.
4. **PRF-032: Real read-race fixture.** A real target exits or retires a thread
   while the profiler attempts a snapshot. The resulting failed or incomplete
   observation must create a gap and a diagnostic, not a copied stack or an
   extended span.
5. **PRF-033: Waiting-thread fixture.** Wall mode attributes a deliberate wait
   to the waiting stack. CPU mode does not turn the same wait into CPU work.
6. **PRF-034: Parallel-CPU fixture.** Two CPU-bound workers produce CPU
   attribution that can approach twice wall time without collapsing both workers
   into one timeline.
7. **PRF-035: Short-function fixture.** Repeated short-lived leaf functions are
   not systematically reassigned to a long-lived caller by the CPU endpoint
   policy. If the configured interval cannot resolve them, the report exposes
   that resolution limit.
8. **PRF-036: Rate convergence.** Attribution distributions from at least three
   meaningfully different mean sampling rates converge within their statistical
   confidence bounds on deterministic fixtures.
9. **PRF-037: Repeated compiler captures.** Five captures of one retained
   generated source preserve the same major-function self and cumulative
   ranking. Any change beyond statistical confidence must be explained by
   recorded diagnostics or demonstrated compiler nondeterminism.
10. **PRF-038: Generator coverage.** Acceptance runs every workload named by the
    `profile-compiler` skill and produces successful wall and CPU reports for
    each.

### Implementation discipline

1. **PRF-039: Current design only.** Do not add or retain compatibility shims,
   legacy profile readers, aliases, translated flags, version fallbacks, or
   transitional APIs unless a current consumer requires them at that checkpoint.
2. **PRF-040: No speculative defensive code.** Every optional state, fallback,
   exception handler, and defensive branch must correspond to a demonstrated
   situation reachable in the real profiler workflow.
3. **PRF-041: Realistic tests.** Tests exercise real binaries or libraries,
   subprocesses, Python threads, process lifecycle, signals, files, `/proc`, raw
   profiles, and analyzer entry points whenever those mechanisms are under test.
4. **PRF-042: Minimal mocking.** A test may mock only a boundary that cannot be
   exercised safely and practically with the real mechanism. The mocked event
   must be reachable in production, and an available integration test must not
   be replaced by a mock.
5. **PRF-043: Analyzer at every checkpoint.** Every checkpoint generates at
   least one profile through the public profiler entry point and analyzes that
   artifact through the public analyzer entry point. The checkpoint is not
   complete merely because its unit tests pass.
6. **PRF-044: Coverage gate.** At the end of every checkpoint, after all
   checkpoint changes are complete, run repository-wide coverage:

   ```text
   bazelisk coverage --noshow_progress --ui_event_filters=-info --combined_report=lcov //...
   ```

   Then analyze every uncovered branch:

   ```text
   bazelisk run --noshow_progress --ui_event_filters=-info //tools:analyze_coverage
   ```

7. **PRF-045: Resolve every uncovered branch.** Add a realistic test for every
   uncovered branch reachable in the real workflow. Delete every branch that
   cannot be reached by a real-world situation. Do not retain an unreachable
   branch as defensive code or suppress it from coverage.
8. **PRF-046: Remove superseded paths immediately.** When working code replaces
   an old py-spy, runner, analyzer, schema, or dependency path, remove the old
   path before the checkpoint review and commit.

### End-state critical-path analysis

1. **PRF-047: Multi-threaded critical path.** By the end of the redesign, the
   analyzer must report the sampled wall critical path of a multi-threaded
   compile: the ordered Python work and wait segments that constrained process
   completion, including cross-thread handoffs. It must identify each resolved
   segment by thread and complete Python stack, derive function self and
   cumulative attribution for the path, distinguish parallel off-path work, and
   report ambiguous or unobserved transitions explicitly. It must not substitute
   the busiest thread, total CPU time, or unioned wall occupancy for the
   critical path. An unresolved producer does not make an observed downstream
   wait uncertain. When the main thread is a producer candidate at a worker's
   first observation, keep the handoff ambiguous but preserve the earlier
   main-thread path before any competing producer candidate was observed.
2. **PRF-048: Critical-path fixture.** A real multithreaded target uses normal
   synchronization and work queues to create a known completion-critical chain
   with at least two cross-thread handoffs, blocking waits, and concurrent
   non-critical work. Without profiler-specific target instrumentation, the
   analyzer must recover the ordered critical chain and its Python functions
   within the configured sampling resolution, exclude the non-critical work, and
   expose any transition it cannot resolve.

## Consequences

### Benefits

- Wall profiling cost is independent of Python call frequency. The preferred CPU
  backend has the same property.
- Worker lifecycle is explicit in each sample rather than inferred from open
  trace events.
- The profiler can favor attribution correctness over elapsed-runtime fidelity.
- Raw samples support later caller, callee, function, and thread investigations.
- The architecture follows CPython's supported direction and has a clear Python
  3.15 migration path.

### Costs and limitations

- Python 3.14 uses a private CPython module. The profiler must be tightly
  version-checked and covered by integration tests.
- Stopping the process perturbs total elapsed time and may affect scheduling and
  caches. Multiple randomized rates and repeated captures are required to detect
  material profile-shape changes.
- Statistical sampling cannot provide exact call counts or exact function
  boundaries shorter than the sampling interval.
- CPU attribution from scheduler-runtime deltas needs stronger validation than
  wall attribution. If it cannot meet the accuracy requirements, maintaining a
  separate perf CPU backend adds implementation and analysis complexity.
- The initial implementation is Linux-specific because it depends on process
  signals, `/proc`, and Linux thread identifiers.

## Non-goals

- Preserving unprofiled wall-clock duration.
- Exact call counts.
- Exact entry and exit timestamps for every function.
- Per-line tracing of every executed line.
- Allocation or memory-leak profiling.
- General-purpose production continuous profiling.
- Supporting arbitrary Python implementations or unmatched CPython versions.

## Implementation and Migration Plan

Implementation stops at every checkpoint below. Each increment is a vertical
slice: it captures a real profile and the public analyzer consumes that exact
artifact. Collector code without a working analyzer is not a checkpoint.

Before asking for review at every checkpoint:

1. Add a short adjacent comment containing the requirement ID and name wherever
   implementation logic or a test implements a numbered requirement. Maintain
   these traceability comments as later increments replace or extend the code.
   Tag only code that positively realizes a requirement; absence constraints and
   checkpoint review rules are verified by review evidence, not asserted on
   individual implementation branches.
2. Exercise the new behavior through the public profiler entry point against a
   real process, then analyze the generated artifact through the public
   analyzer.
3. Use real processes, threads, files, signals, `/proc` observations, compiler
   workloads, and command-line entry points in tests. Use a mock only when the
   real boundary cannot practically be exercised, and mock only that boundary.
4. Run formatting, linting, the relevant tests, and any required dependency
   checks.
5. Run repository-wide coverage:

   ```shell
   bazelisk coverage --noshow_progress --ui_event_filters=-info --combined_report=lcov //...
   ```

6. Analyze the coverage report:

   ```shell
   bazelisk run --noshow_progress --ui_event_filters=-info //tools:analyze_coverage
   ```

7. Add a realistic test for every reachable uncovered branch. Delete every
   branch that cannot occur in the real workflow, including speculative error
   handling and defensive defaults.
8. Remove code, flags, formats, adapters, and tests superseded by the increment.
   Do not add a compatibility shim or maintain a parallel legacy path.
9. Demonstrate the captured profile and analyzer report to the user. The user
   reviews and commits the working increment before implementation continues.

### Increment 1: One-snapshot wall vertical slice

1. Add the profiler's own Bazel binary or library entry point under
   `tools/profiler/`.
2. Define only the versioned raw data needed for one all-thread stack snapshot
   and its capture diagnostics.
3. Implement launcher-to-Python detection, whole-process stop/resume, one
   consistent `RemoteUnwinder` snapshot, and resume behavior for the real ways
   capture can end.
4. Implement the first analyzer entry point. It reads the captured artifact and
   reports its processes, threads, Python stacks, files, and functions.
5. Test the vertical slice with a real launcher transition, a real multithreaded
   Python target, normal process exit, user interruption, and the actual
   profiler and analyzer binaries.
6. Replace any existing analyzer interface needed by this slice instead of
   retaining py-spy input support or a transitional schema.

**Checkpoint 1:** Capture one valid all-thread Python snapshot from a real test
target and inspect it with the public analyzer. Complete the checkpoint
protocol, then the user reviews and commits.

### Increment 2: Continuous wall vertical slice

1. Add randomized repeated sampling, target-running logical time, pause-time
   exclusion, incremental persistence, and lifecycle and failure records for
   events that the real capture workflow can produce.
2. Preserve synchronized thread states and observable wait, wake, and handoff
   evidence needed for later critical-path reconstruction.
3. Extend the analyzer to calculate wall self and cumulative attribution,
   longest sampled spans, callers, callees, per-thread views, overlap unions,
   filters, and confidence diagnostics from those samples.
4. Exercise retired threads, real read races, rapidly changing stacks, blocking
   waits, different stack depths, and different call frequencies with real
   target programs.
5. Capture and analyze a complete wall profile of one generated compiler source.
6. Remove the one-snapshot-only interfaces and any temporary schema or analysis
   paths that continuous capture supersedes.

**Checkpoint 2:** Review a useful analyzer report for the generated compiler
source and compare repeated captures for attribution stability. Complete the
checkpoint protocol, then the user reviews and commits.

### Increment 3: `run_profile` wall workflow

1. Give `run_profile` only the generic orchestration needed to invoke a selected
   profiling command with a target command, stdin, working directory,
   environment, and destination.
2. Keep profiler imports, CPython inspection, signal handling, sample weighting,
   schema knowledge, and analysis logic out of `run_profile`.
3. Capture real generated source and project workloads through `run_profile`,
   then consume both artifacts with the public analyzer.
4. Remove the py-spy wall path and every old `run_profile` or `analyze_profile`
   flag, format reader, error path, and test that the current wall workflow does
   not need. CPU profiling may remain unavailable until Increment 4 rather than
   being preserved through a compatibility path.

**Checkpoint 3:** Demonstrate both source and project wall profiles captured
through `run_profile` and inspected by the analyzer. Complete the checkpoint
protocol, then the user reviews and commits.

### Increment 4: Accurate CPU vertical slice

1. Evaluate per-thread scheduler-runtime deltas paired with externally captured
   stacks using the real CPU accuracy workloads and the public analyzer.
2. If the external design passes every accuracy requirement, make it the CPU
   implementation. If it does not, delete the attempted production code and make
   the profiler entry point run the generated Python environment under Linux
   perf with `-X perf`.
3. Do not retain both implementations as a runtime fallback. The checkpoint has
   one CPU capture design that passed the requirements and no rejected or
   unreachable alternative.
4. Extend the analyzer to consume the selected CPU artifact and calculate Python
   self, cumulative, caller, and callee attribution.
5. Exercise short leaf work, high call frequency, blocking waits, parallel CPU
   work, concurrency, multiple randomized rates, and repeated captures using
   real target processes.
6. Capture and analyze a CPU profile of one generated compiler source through
   the public workflow.

**Checkpoint 4:** Review the selected backend's accuracy evidence and a useful
compiler CPU report. Complete the checkpoint protocol, then the user reviews and
commits.

### Increment 5: Complete workflow redesign

1. Capture wall and CPU profiles for every generated source and project workload
   through `run_profile`, and consume every generated artifact with the public
   analyzer.
2. Implement the end-state critical-path analysis, pass the real multithreaded
   handoff fixture, and produce an actionable critical-path report for a
   generated multi-threaded compiler workload.
3. Retain only command-line options, report views, formats, and code paths used
   by the redesigned workflow.
4. Update the `profile-compiler` skill to describe and exercise the working
   profiler, `run_profile`, and analyzer interfaces.
5. Remove all remaining py-spy dependencies, unreleased dependency overrides,
   py-spy-specific code, obsolete schemas, unused flags, and tests for removed
   behavior. Do not compare against or preserve py-spy behavior as a
   compatibility requirement.

**Checkpoint 5:** Review complete end-to-end reports for every workload and the
multi-threaded critical-path report, along with removal of all superseded
profiling code. Complete the checkpoint protocol, then the user reviews and
commits.

### Later Python 3.15 migration

When the repository adopts Python 3.15t, evaluate Tachyon against the same
realistic workloads and attribution requirements. The public analyzer must
consume real Tachyon artifacts during the evaluation. If Tachyon satisfies the
requirements, replace the custom collector in the same increment; do not keep a
dual-backend compatibility layer. Complete the full checkpoint protocol,
including repository-wide coverage analysis and deletion of unreachable
branches.

**Checkpoint 6:** Review Tachyon comparison evidence and analyzer reports before
committing any backend replacement.

[austin-issue]: https://github.com/P403n1x87/austin/issues/421
[austin-pr]: https://github.com/P403n1x87/austin/pull/409
[pep-768]: https://peps.python.org/pep-0768/
[perf]: https://docs.python.org/3.14/howto/perf_profiling.html
[pasta]: https://doi.org/10.1287/opre.30.2.223
[pyinstrument]: https://pyinstrument.readthedocs.io/en/latest/how-it-works.html
[tachyon]: https://docs.python.org/3.15/library/profiling.sampling.html
[viztracer]: https://viztracer.readthedocs.io/en/latest/concurrency.html
