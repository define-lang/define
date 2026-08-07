---
name: profile-compiler
description: >-
  Profile and investigate Define compiler CPU performance with py-spy, including
  complementary generated stress shapes, phase and hotspot tables, a view
  excluding bundled lark, and sampled caller drill-downs. Use for compiler
  profiling, benchmarks, bottlenecks, flame graphs, optimization targets, or
  questions about where compilation time goes in define/compiler.
---

# Profile the Define compiler

Measure and explain; do not optimize unless asked.

Use fresh inputs from `tools/generators/`:

| Generator                          | Stress                       |
| ---------------------------------- | ---------------------------- |
| `generate_large_define_source`     | parsing                      |
| `generate_action_graph_source`     | reference-graph validation   |
| `generate_operation_graph_source`  | operation-graph construction |
| `generate_reference_graph_project` | cross-file references        |
| `generate_deep_pipeline_source`    | requirement propagation      |

For a general profile, run every generator at its default. For focused work,
inspect the relevant generator's `--help` and choose the options that exercise
the requested code. Regenerate inputs and require no compiler diagnostics and
zero py-spy sampling errors.

Keep artifacts under `tmp/profile/`. Inspect the runner, then record each
profile:

```text
uv run tools/run_profile.py --help
uv run tools/run_profile.py --source <absolute source> --out <absolute profile.json>
uv run tools/run_profile.py --project <absolute directory> --out <absolute profile.json>
```

Run `run_profile` outside the Codex sandbox. It builds the compiler, then
invokes py-spy on that executable and records the complete process, including
imports. Reject a run that reports diagnostics.

Analyze each retained capture through:

```text
bazelisk run //tools:analyze_profile -- --profile <absolute profile.json>
```

For each shape, report:

- cumulative sampled time and percent for imports/startup, parse (including
  lexing), AST transform, reference-graph validation, requirement inference and
  destruction contracts, guarantee propagation, operation-graph construction,
  and code generation; locate current entry points in source;
- top overall functions by self sampled time, with cumulative sampled time and
  self sample count;
- the analyzer's Lark/non-Lark split and the same hotspot table after removing
  `lark_standalone.py` stacks.

Use self sampled time for project coordinator bookkeeping because coordinator
and worker stacks overlap. State that samples estimate CPU distribution, sample
hits are not calls, and absolute wall time requires an unprofiled run. Contrast
the shapes and rank observations without implementing changes.

For follow-ups, reuse the speedscope JSON. Attribute direct callers and callees
with adjacent stack frames and weights, and cumulative callers with stack
prefixes. Use cProfile only when exact call counts themselves are needed, not to
rank CPU hotspots.
