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
for its output requirements and available options.

For a general profile, run every generator at its default. For focused work,
inspect the relevant generator's `--help` and choose options that exercise the
requested code. Regenerate inputs and require no compiler diagnostics or
profiling errors.

Before using the profiling tools, prepare the workspace's local Python
environment:

```text
bazelisk run --noshow_progress --ui_event_filters=-info //tools:setup_local_dev
```

Use the repository's `run_profile` tool to capture profiles and its
`analyze_profile` tool to analyze them. Read both tools' complete `--help`
output before using them and follow their current interfaces. Do not infer their
behavior from this skill. If you are Codex, always run `tools/run_profile.py`
outside the sandbox by requesting escalated execution. Keep disposable artifacts
under `tmp/profile/`.

Py-spy may report `Error: No child process (os error 10)` after successfully
writing a profile because of its upstream child-exit race. Treat that profile as
usable only when the write summary reports a positive sample count and
`Errors: 0`, the compiler emitted no diagnostics or failure output, and
`analyze_profile` reads the profile successfully. Treat every other profiling
error as a failed capture.

Make wall-time critical-path analysis the primary result and CPU-time analysis
the secondary result. For each workload, report:

- the longest pole and the functions that account for wall time;
- the principal CPU hotspots, overall and within Define compiler code;
- time attributable to imports/startup, parse including lexing, AST transform,
  reference-graph validation, requirement inference and destruction contracts,
  guarantee propagation, operation-graph construction, and code generation;
- current source entry points for the important phases and functions;
- contrasts with the other workloads and a ranked list of observations.

Use the analyzer's metric definitions and caveats as the authority when
interpreting results. Do not assume that function rows are additive, that CPU
time equals wall time, or that a sample hit represents a call.

For follow-up questions, reuse retained profile artifacts when they contain the
needed evidence. Drill into caller and callee relationships using the available
stack and timing information. Use instrumentation only when exact call counts
themselves are needed, not to rank hotspots.
