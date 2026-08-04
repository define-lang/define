---
name: profile-compiler
description: >-
  CPU-profile the Define compiler and present the hotspots as clear tables
  (overall, and with the bundled lark parser subtree removed so the compiler's
  own work is visible), plus a phase breakdown. Profiles complementary source
  shapes that stress parsing, reference-graph validation, operation-graph
  construction, and cross-file reference resolution. Use this whenever the user
  wants to profile, benchmark, or find performance hotspots / slow spots /
  bottlenecks in the Define compiler, asks "where is time being spent" or "what
  should we optimize", wants a flame-graph-style or cProfile view of
  compilation, or wants to drill a hotspot down to the callers that drive it —
  even if they don't say the word "profile". For the Define language compiler in
  this repo (define/compiler), not generic Python profiling.
---

# Profiling the Define compiler

This skill runs CPU profiles of the Define compiler over complementary source
shapes, then presents the results as the tables the user expects: a phase
breakdown, an overall hotspot table, and a table with the bundled lark parser
removed so the compiler's own code is visible. It keeps the raw `.prof` files so
the user can ask follow-up questions.

The goal is **understanding**, not fixing. Run the profiles, present the numbers
clearly, and answer follow-ups. Do not propose or make code changes unless the
user explicitly asks.

## The source shapes

The generators live in `tools/generators/`. Each one's `--help` describes what
that shape stresses, how to scale it, and every knob with its default, so run
`--help` rather than assuming — and rather than looking for those details here.

| Source | Generator                          | Stresses                        |
| ------ | ---------------------------------- | ------------------------------- |
| A      | `generate_large_define_source`     | parsing                         |
| B      | `generate_action_graph_source`     | reference-graph validation      |
| C      | `generate_operation_graph_source`  | operation-graph construction    |
| D      | `generate_reference_graph_project` | cross-file reference resolution |
| E      | `generate_deep_pipeline_source`    | requirement propagation         |

**Asked to profile the compiler, with nothing specific in mind:** run every
generator on its defaults, which are sized for exactly this. The headline
contrast between them — parse-bound versus validation-bound, and which
validation machinery dominates — is itself a result worth presenting.

**Profiling something specific:** choose the shape and the knobs that reach the
code in question, deciding from the generators' `--help`, and say what you chose
and why. Size it so the compiler spends **at least 20 seconds** on the generated
source: a shorter run is dominated by startup and noise and rarely shows
anything worth acting on.

Generate each source fresh on every run so it is reproducible from its
parameters, and confirm each reaches **zero diagnostics**, so the profile
reflects the full pipeline rather than an early exit on error.

## Workflow

Work out of a scratch dir (default `tmp/profile/`) and keep every artifact there
— the `.prof` files especially — so follow-up questions don't require
re-running.

Run every generator and profile through its Bazel target, in the main agent and
in every subagent. Do not use `uv run`, a repository `.venv`, or the OS Python:
`uv` can select an interpreter whose performance differs enough to invalidate
comparisons. OS Python is fine for reading an existing `.prof` with `pstats`,
which measures nothing. Pass literal absolute paths rather than `$PWD`, so shell
expansion doesn't defeat the permission system's `bazelisk` approval rule and
cause an unnecessary prompt.

1. **Generate each source fresh**, overriding knobs if the user asked:
   `bazelisk run //tools/generators:generate_large_define_source -- --output <absolute path>`.
   The defaults are the intended profiling shape; pass `--help` before
   overriding anything.
2. **Profile.** `//tools:run_profile` has a mode for each kind of shape:
   - `--source <file.dfn>` profiles `driver.compile_source` in process — the
     non-filesystem compile path — which keeps interpreter startup and click
     dispatch out of the profile.
   - `--project <dir>` profiles a whole directory through `validate_program`,
     for a shape whose entry point is a position rather than a constructor
     action. It pins the work pool to one worker, which matters: cProfile is
     built on `sys.monitoring`, whose profiler tool is process-global, so one
     profiler already sees every worker thread — but two threads interleaving
     into its shared call stack would scramble the timings. Do not hand-roll
     per-thread profilers to work around this; `Profile.enable()` on a second
     thread raises `ValueError: Another profiling tool is already active`.

   Confirm each run reports `has_errors=False`; a run with diagnostics is not a
   valid full-pipeline sample, so stop and report it.

3. **Analyze** each `.prof` with `tools/analyze_profile.py` (both the with-lark
   and without-lark views come from one file). `--exclude-file` defaults to
   `lark_standalone.py`. The "without" view drops that file's functions and, for
   every other function, counts **only the calls and time that came from
   non-lark callers** — a per-edge split, not wholesale removal — so a builtin
   both sides call keeps its compiler-driven cost here instead of being charged
   entirely to lark.
4. **Present the results** in the format below, one set of tables per source
   plus the headline contrast between them.

## Output format

Lead with the caveat that cProfile inflates wall time roughly 3×; the numbers
rank costs against each other and are not absolute wall time. Then, for each
source, present the three things below as Markdown tables, rounding to 3
decimals and keeping `ncalls`. Finish with a short cross-source contrast, and a
ranked list of the optimization opportunities the numbers point to — as
observations only.

### 1. Phase breakdown (by cumulative time)

Roll up cumtime per phase. Find each phase's current entry points in the source
rather than assuming names: private helpers get renamed and moved, so a rollup
keyed to a stale name silently reports zero. The phases worth separating:

- **Parse**, with lexing as a sub-part — `parser.py` and `lark_standalone.py`
- **Transform**, parse tree to AST — `transformer.py`
- **Reference-graph validation** — `reference_graph_validator.py`, and within
  it: requirement inference and destruction-contract generation
  (`definition_postorder_validator.py`), guarantee propagation
  (`particle_tracker.py`), and operation-graph construction
  (`operation_graph.py`, its `record_*` methods)

Keep those sub-parts disjoint by checking which file actually enters which.

A `--project` run has a phase the single-file shapes don't: the coordinator's
work-pool bookkeeping (`concurrent.futures`, `threading`). Report it as tottime
rather than cumtime, because coordinator and worker frames overlap in wall time.

| Phase | cumtime | % of run |
| ----- | ------: | -------: |

### 2. Overall hotspots (with lark) — top ~10 by tottime

| tottime | cumtime | ncalls | function |
| ------: | ------: | -----: | -------- |

### 3. Compiler's own hotspots (without lark subtree) — top ~10 by tottime

Same columns. Note the headline split the analyze script prints: how much
tottime is the lark subtree versus the compiler's own code.

## Follow-up drill-downs

The `.prof` files are kept, so most follow-ups need no re-run — re-analyze with
a short throwaway `pstats` snippet written into the scratch dir rather than
adding scripts to the skill or editing the committed tools. Common ones:

- **"Who calls hotspot F?" / "what does F call?"** — load the `.prof` with
  `pstats.Stats` and use `print_callers(F)` / `print_callees(F)`, or read the
  per-edge caller dict directly: `stats.stats[func]` is
  `(cc, nc, tt, ct, callers)`, where `callers[caller_func] = (cc, nc, tt, ct)`
  is the callee's time attributable to that one caller edge.
- **"Break down file X's cost by which caller in file Y drives it"** — sum each
  function-in-X's per-edge `ct` over callers whose filename is Y, grouped by
  caller line. That per-edge `ct` already includes X's nested private helpers,
  so it attributes total cost correctly only if Y enters X through X's public
  surface; check that before trusting the numbers.
- **Re-rank by cumtime, or show more rows** — re-run `analyze_profile.py` with a
  larger `--top`.
- **Different input shape** — regenerate a source with different knobs and
  re-profile.
