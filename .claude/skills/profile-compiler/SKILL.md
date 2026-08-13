---
name: profile-compiler
description: >-
  Profile and investigate Define compiler wall and CPU performance using the
  repository profiling tools and generated stress workloads. Use for compiler
  profiling, benchmarks, bottlenecks, critical paths, optimization targets, or
  questions about where compilation time goes in define/compiler.
---

# Profile the Define compiler

Measure and explain; do not optimize unless asked.

Use fresh inputs from `tools/generators/`:

| Generator                               | Stress                        |
| --------------------------------------- | ----------------------------- |
| `generate_large_define_source`          | parsing                       |
| `generate_action_graph_source`          | reference-graph validation    |
| `generate_operation_graph_source`       | operation-graph construction  |
| `generate_reference_graph_project`      | cross-file references         |
| `generate_deep_pipeline_source`         | requirement propagation       |
| `generate_destruction_fragments_source` | modular destruction fragments |

Invoke each generator from the workspace root through its Bazel binary:

```text
bazelisk run --noshow_progress --ui_event_filters=-info //tools/generators:<generator> -- --output <path>
```

Replace `<generator>` with a name from the table. Read that generator's `--help`
for its output requirements and available options. Relative output paths resolve
from the Bazel workspace.

For a general profile, run every generator at its default. For focused work,
inspect the relevant generator's `--help` and choose options that exercise the
requested code. Regenerate inputs and require no compiler diagnostics or
profiling errors.

Before using the profiling tools, prepare the workspace's local Python
environment:

```text
bazelisk run --noshow_progress --ui_event_filters=-info //tools:setup_local_dev
```

Read both public tools' complete help before using them:

```text
uv run -m tools.run_profile --help
uv run -m tools.analyze_profile --help
```

Run local entry points with `uv run -m`; invoking the `.py` paths directly does
not put the workspace root on Python's import path. If you are Codex, run each
`run_profile` invocation outside the sandbox. Keep artifacts under
`tmp/profile/`.

Capture requested workloads in wall mode through `run_profile`:

```text
uv run -m tools.run_profile --source <source> --out <wall-profile>
```

Do not capture a CPU profile unless the user explicitly asks for one. When they
do, use `--mode cpu` with the same source or project workflow. CPU mode requires
Linux perf access and a CPython build with perf trampoline and frame-pointer
support; it retains native `perf.data`, CPython's perf symbol map, perf's
build-ID cache, and a small Define metadata sidecar. Use a `.data` output name
for CPU captures.

For `generate_reference_graph_project`, use `--project <directory>`. Analyze
each exact artifact through the public analyzer:

```text
uv run -m tools.analyze_profile --profile <profile>
```

Use `--compiler-only` and the other analyzer filters for focused follow-up when
the complete report does not expose the needed compiler rows. Filters preserve
global lifecycle and critical-path context while narrowing attribution rows.

Treat a nonzero capture exit, compiler diagnostics, an incomplete artifact, a
discard rate above the profiler threshold, or an analyzer failure as a failed
run. Do not interpret a partial profile as successful.

Use the sampled wall critical path as the profiling result. For each workload,
report:

- the sampled completion-critical path and the dominant functions that explain
  it. Include waits, handoffs, ambiguity, off-path concurrency, and unioned
  occupancy only when materially relevant;
- contrasts with the other workloads and a ranked list of observations.

When the user requests CPU profiling, additionally report the principal CPU
hotspots overall and within Define compiler code.

Use the analyzer's metric definitions and caveats as the authority. A critical
path is not the busiest thread, summed thread time, or unioned wall occupancy.
Do not assume function rows are additive, CPU time equals wall time, or a sample
hit represents a call. CPU percentages use all sampled CPU as their denominator,
including filtered functions, Lark, and samples without a Python frame.

For follow-up questions, reuse retained profile artifacts when they contain the
needed evidence. Drill into caller and callee relationships using the available
stack and timing information. Use instrumentation only when exact call counts
themselves are needed, not to rank hotspots.
