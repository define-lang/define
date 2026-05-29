---
name: profile-compiler
description: >-
  CPU-profile the Define compiler compiling a large generated source file and
  present the hotspots as clear tables (overall, and with the bundled lark
  parser subtree removed so the compiler's own work is visible), plus a phase
  breakdown. Use this whenever the user wants to profile, benchmark, or find
  performance hotspots / slow spots / bottlenecks in the Define compiler, asks
  "where is time being spent" or "what should we optimize", wants a flame-graph-
  style or cProfile view of compilation, or wants to drill a hotspot down to the
  callers that drive it — even if they don't say the word "profile". For the
  Define language compiler in this repo (define/compiler), not generic Python
  profiling.
---

# Profiling the Define compiler

This skill runs a CPU profile of the Define compiler compiling a large,
syntactically-diverse source file, then presents the results as the tables the
user expects: a phase breakdown, an overall hotspot table, and a table with the
bundled lark parser removed so the compiler's own code is visible. It keeps the
raw `.prof` so the user can ask follow-up questions.

The goal is **understanding**, not fixing. Run the profile, present the numbers
clearly, and answer follow-ups. Do not propose or make code changes unless the
user explicitly asks.

## What to profile and why this shape

- **Source**: generate it fresh on every run with
  `tools/generate_large_define_source.py` (default 50,000 lines, max chain
  length 25). It compiles to **zero diagnostics**, so the profile reflects the
  full pipeline rather than an early-exit on error. These two knobs (`--lines`,
  `--max-chain-length`) are the parameters most worth varying; longer chains
  stress reference-graph validation. Regenerate rather than reuse so each run is
  reproducible from the stated parameters.
- **Entry point**: profile `driver.compile_source(...)` in-process via
  `tools/run_profile.py` — the non-filesystem compile path, the same code
  `main compile` runs when source is piped on stdin. Profiling in-process avoids
  polluting the profile with interpreter startup and click dispatch.
- **Tool**: `cProfile`. Note for the user that **cProfile inflates wall time
  ~3×**; the numbers are for _relative ranking_, not absolute wall time.

## Workflow

Work out of a scratch dir (default `tmp/profile/`). Keep every artifact there —
the `.prof` especially — so follow-up questions don't require re-running.

1. **One-time local dev setup** (safe to repeat):
   `uv run tools/setup_local_dev.py`. This copies the Bazel-generated
   lark/protobuf modules into the source tree so `define.compiler` imports
   resolve outside Bazel.

2. **Build the CLI** so a clean-compile sanity check is possible:
   `bazelisk build --noshow_progress --ui_event_filters=-info //define/compiler:main`

3. **Generate the source** fresh (override lines/chain if the user asked):

   ```
   uv run tools/generate_large_define_source.py \
     --output tmp/profile/source.dfn --lines 50000 --max-chain-length 25
   ```

4. **(Optional) Confirm it compiles clean** via the real binary on the stdin
   path:
   `./bazel-bin/define/compiler/main compile --out /tmp/cg_check < tmp/profile/source.dfn`
   Exit 0 with no diagnostics means the profile will cover the whole pipeline.

5. **Run the profile** (needs the repo root on PYTHONPATH):

   ```
   PYTHONPATH=<repo-root> uv run python tools/run_profile.py \
     --source tmp/profile/source.dfn --out tmp/profile/compile.prof
   ```

   Confirm it prints `has_errors=False`. If it's `True`, stop and report — the
   profile is not a valid full-pipeline sample.

6. **Analyze** (both the with-lark and without-lark views, from the one
   `.prof`):

   ```
   uv run python tools/analyze_profile.py \
     --prof tmp/profile/compile.prof --top 30
   ```

   `--exclude-file` defaults to `lark_standalone.py`. The "without" view drops
   that file's functions and, for every other function, counts **only the calls
   and time that came from non-lark callers** (a per-edge split, not wholesale
   removal). So a builtin both sides call keeps its compiler-driven cost here
   instead of being charged entirely to lark.

7. **Present the results** in the format below.

## Output format

Present three things, in this order, as Markdown tables. Round to 3 decimals and
keep `ncalls`. Lead with the caveat that cProfile inflates wall time ~3×.

### 1. Phase breakdown (by cumulative time)

Assemble this from the cumtime table. The pipeline's phases show up as these
marker functions' cumtime — read them off and roll up:

- **Parse** = `parser.py:...(parse)` /
  `lark_standalone.py:...(parse_from_state)`
  - **Lexing** (a sub-part of parse) = `lex` + `next_token` + `feed_token`
- **Transform** (parse tree → AST) = `transformer.py:...(transform)`
- **Reference-graph validation** = `reference_graph_validator.py:...(validate)`
  - within it, **requirement inference** = `_maybe_infer_requirements_on_chain`

| Phase | cumtime | % of run |
| ----- | ------: | -------: |

### 2. Overall hotspots (with lark) — top ~10 by tottime

| tottime | cumtime | ncalls | function |
| ------: | ------: | -----: | -------- |

### 3. Compiler's own hotspots (without lark subtree) — top ~10 by tottime

Same columns. Note the headline split: how much tottime is the lark subtree vs
the compiler's own code (the analyze script prints both sums and percentages).

After the tables, give a short, ranked list of the optimization opportunities
the numbers point to — but only as observations. Do not change code.

## Follow-up drill-downs

The `.prof` is kept, so most follow-ups need no re-run — re-analyze it with a
short throwaway `pstats` snippet written into the scratch dir (don't add scripts
to the skill). Common ones:

- **"Who calls hotspot F?" / "what does F call?"** — load the `.prof` with
  `pstats.Stats` and use `print_callers(F)` / `print_callees(F)`, or read the
  per-edge caller dict directly: `stats.stats[func]` is
  `(cc, nc, tt, ct, callers)`, where `callers[caller_func] = (cc, nc, tt, ct)`
  is the callee's time attributable to that one caller edge.
- **"Break down file X's cost by which caller in file Y drives it"** — sum each
  function-in-X's per-edge `ct` over callers whose filename is Y, grouped by
  caller line. That per-edge `ct` already includes X's nested private helpers,
  so this attributes total cost correctly _as long as Y enters X only through
  X's public surface_ — check that before trusting the numbers.
- **Re-rank by cumtime, or show more rows** — re-run `analyze_profile.py` with a
  larger `--top`.
- **Different input shape** — regenerate the source with different `--lines` /
  `--max-chain-length` and re-profile.

## Notes

- Run all Python via `uv run`. The profile script additionally needs
  `PYTHONPATH=<repo-root>` because it imports `define.compiler` directly.
- The two scripts (`tools/run_profile.py`, `tools/analyze_profile.py`) live in
  the repo's `tools/` directory and are parameterized; prefer passing flags over
  editing them. For one-off drill-downs, write a throwaway snippet into the
  scratch dir rather than editing the committed tools.
