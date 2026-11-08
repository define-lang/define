---
name: profile-compiler
description: >-
  Run and report Define compiler wall or CPU profiles using the repository
  profiling tools and generated stress workloads. Use only when the user
  explicitly instructs the agent to run or capture a compiler profile, including
  a bare invocation of this skill.
---

# Profile the Define compiler

Measure and explain; do not optimize unless asked.

Without other instructions, immediately run a general wall profile and report
it; do not ask what to profile. Explicit user instructions override this.

Generate inputs with `tools/generators/`; read
[its README](../../../tools/generators/README.md). Run each generator from the
workspace root with the Bazel options `run_profile` builds with, so that Bazel
keeps its analysis cache:

```text
bazelisk run --config=profiling --build_runfile_links --noshow_progress --ui_event_filters=-info //tools/generators:<generator> -- --output <path>
```

For a general profile, run each generator except `generate_diagnostics_source`
once at its defaults. If a compile runs under about a second, by the wall time
`run_profile` prints, raise its size options until it runs for one to a few
seconds, and report the settings. For focused work, choose options from the
generator's `--help` that exercise the requested code.

Read the complete `--help` of `uv run -m tools.run_profile` and
`uv run -m tools.analyze_profile` before using them, and run both with
`uv run -m` from the workspace root. If you are Codex, run `run_profile` outside
the sandbox. Keep artifacts under `tmp/profile/`, and delete a generated
reference project after profiling it.

Capture wall profiles. Choose `--max-threads` for what the profile must show: 1,
the default, gives each phase one worker and the clearest critical path; more
show parallel behavior. Say which you used and why. Capture a CPU profile only
when the user asks for one.

Start each wall analysis from `--view critical-path`, then use the other views
for detail; raise `--depth` when a phase's label doesn't explain its time. Treat
a nonzero capture exit or an analyzer failure as a failed run, unless the
workload is meant to produce diagnostics; it then exits 1 and still writes a
profile.

When asked to make the compiler faster, also:

- profile with `--max-threads` at the machine's core count, where garbage
  collection, coordination, and file-system contention show. Sampling slows the
  compiler, more with more threads, so take real times from `compare_compilers`,
  never from a profile;
- profile a workload at two or three sizes and compare its phases, to find costs
  that grow faster than the input;
- capture CPU profiles without being asked when a wall profile can't name a
  cost, such as a function whose self time rises with the thread count; native
  frames show contention between threads. Past the physical core count, every
  function slows about evenly from SMT and clock speed, which isn't contention;
- weigh a phase's threads by selecting that phase with `--start-seconds` and
  `--end-seconds`, not by their share of the whole run;
- measure each change with `uv run -m tools.compare_compilers`, which also
  checks that the output is unchanged, and profile a worktree by running
  `run_profile` from it. Nothing else may run Bazel in either checkout
  meanwhile. Each checkout runs its own Bazel server; run
  `bazelisk clean --expunge` in a worktree before leaving it.

For each workload, report:

- the critical path, phase by phase, and the functions that explain each phase,
  including waits, handoffs, idle workers, and work off the path when they
  matter;
- the failed-sample rate of a wall profile, or the share of stacks not unwound
  of a CPU profile;
- contrasts with the other workloads and a ranked list of observations.

For a CPU profile, also report the main hotspots overall and in compiler code,
and a section titled `The dominant cumulative chain is:`: the most important
caller-to-callee path as an indented tree, each row with its cumulative CPU time
and share of all sampled CPU, followed down to the functions that consume the
work rather than delegate it. Build it from the busiest thread's tree
(`--view tree --thread <id> --focus WorkerContext.run --minimum-percent 2`),
then focus on each function where it branches, lowering `--minimum-percent`. For
a hot function, `--view callers --focus <function>` shows what calls it. To tell
many cheap calls from a few expensive ones, divide a function's time by its
count from `run_profile --mode calls` of the same input. Compare CPU and wall
profiles by shares, not seconds: perf support slows the compiler.

A critical path is not the busiest thread or summed thread time. Cumulative rows
are not additive, and a sample is not a call. For follow-up questions, reuse
retained profiles.
