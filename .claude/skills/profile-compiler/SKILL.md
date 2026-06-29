---
name: profile-compiler
description: >-
  CPU-profile the Define compiler and present the hotspots as clear tables
  (overall, and with the bundled lark parser subtree removed so the compiler's
  own work is visible), plus a phase breakdown. Runs two complementary shapes: a
  single huge action (parse-heavy) and a dense action call graph
  (reference-graph / requirement / guarantee / destruction-contract heavy). Use
  this whenever the user wants to profile, benchmark, or find performance
  hotspots / slow spots / bottlenecks in the Define compiler, asks "where is
  time being spent" or "what should we optimize", wants a flame-graph-style or
  cProfile view of compilation, or wants to drill a hotspot down to the callers
  that drive it — even if they don't say the word "profile". For the Define
  language compiler in this repo (define/compiler), not generic Python
  profiling.
---

# Profiling the Define compiler

This skill runs CPU profiles of the Define compiler over two complementary
source shapes, then presents the results as the tables the user expects: a phase
breakdown, an overall hotspot table, and a table with the bundled lark parser
removed so the compiler's own code is visible. It keeps the raw `.prof` files so
the user can ask follow-up questions.

The goal is **understanding**, not fixing. Run the profiles, present the numbers
clearly, and answer follow-ups. Do not propose or make code changes unless the
user explicitly asks.

## What to profile and why two shapes

The two sources stress different halves of the compiler. Profile **both** unless
the user asks for just one — the headline comparison (parse-bound vs
validation-bound) is itself a result worth presenting. Generate each fresh on
every run so it's reproducible from the stated parameters, and so each compiles
to **zero diagnostics** (the profile then reflects the full pipeline rather than
an early-exit on error).

### Source A — single large action (parse-heavy)

`tools/generate_large_define_source.py` (default 50,000 lines, max chain length
25). One enormous Action Statements Block plus a pool of positions/actions.
Roughly half its time is the bundled lark lexer/parser; the rest is transform
and long-chain reference validation. The two knobs most worth varying are
`--lines` and `--max-chain-length` (longer chains stress reference-graph
validation).

### Source B — dense action call graph (validation-heavy)

`tools/generate_action_graph_source.py` (default
`--layers 18 --width 64 --fan-out 32 --destructor-fraction 0.5`, ~124,000 lines,
~1,150 actions). A layered directed acyclic graph of potential actions rooted at
the entry-point constructor action `/test`; the root triggers every layer-0
action, and each action wires up the next layer, so **every action is reachable
from the root constructor** and gets validated. Each non-leaf action references
`fan_out` next-layer actions through its `out` interface position's constraint
(`it has the action</...>`) — a circulant target set, so every node has both
fan-in and fan-out of exactly `fan_out`. Every action destroys the particle in
its `src` interface position, which both infers an Action Requirement and
records a Destruction Contract; `--destructor-fraction` of actions additionally
carry a real destructor, exercising the destruction cascade.

This profile is reference-graph-dominated: at the default size, validation
(`reference_graph_validator.validate`) is ~70% of the run and parse only ~25%,
with the compiler's own code ~82% of tottime and the bundled lark subtree only
~18%. The dominant work is the reference-graph post-order traversal, the
particle tracker, guarantee propagation across triggers (`_check_trigger`),
requirement inference/checking, and destruction-contract generation. Knobs:
`--layers` (depth), `--width` (actions per layer), `--fan-out` (per-node fan-in
**and** fan-out), `--destructor-fraction`.

> **Important:** scale Source B via `--layers` / `--width` / `--fan-out` (a
> wider/deeper/denser graph), not by chasing a line count — its cost is in
> cross-action validation. The ~124,000-line default profiles in ~60s under
> cProfile (~20s real) and is the validation-bound counterpart to Source A. Cost
> scales roughly linearly in graph size (the earlier exponential blowup in
> guarantee propagation was fixed), so larger sizes are tractable but
> proportionally slower — only go bigger if the user explicitly asks.

### Common notes

- **Entry point**: profile `driver.compile_source(...)` in-process via
  `tools/run_profile.py` — the non-filesystem compile path, the same code
  `main compile` runs when source is piped on stdin. Profiling in-process avoids
  polluting the profile with interpreter startup and click dispatch.
- **Tool**: `cProfile`. Note for the user that **cProfile inflates wall time
  ~3×**; the numbers are for _relative ranking_, not absolute wall time.

## Workflow

Work out of a scratch dir (default `tmp/profile/`). Keep every artifact there —
the `.prof` files especially — so follow-up questions don't require re-running.

1. **One-time local dev setup** (safe to repeat):
   `uv run tools/setup_local_dev.py`. This copies the Bazel-generated
   lark/protobuf modules into the source tree so `define.compiler` imports
   resolve outside Bazel.

2. **Build the CLI** so a clean-compile sanity check is possible:
   `bazelisk build --noshow_progress --ui_event_filters=-info //define/compiler:main`

3. **Generate both sources** fresh (override knobs if the user asked):

   ```
   uv run tools/generate_large_define_source.py \
     --output tmp/profile/source.dfn --lines 50000 --max-chain-length 25
   uv run tools/generate_action_graph_source.py \
     --output tmp/profile/graph.dfn --layers 18 --width 64 --fan-out 32 \
     --destructor-fraction 0.5
   ```

4. **(Optional) Confirm each compiles clean** via the real binary on the stdin
   path:
   `./bazel-bin/define/compiler/main compile --out /tmp/cg_check < tmp/profile/source.dfn`
   Exit 0 with no diagnostics means the profile will cover the whole pipeline.

5. **Run the profiles** (needs the repo root on PYTHONPATH):

   ```
   PYTHONPATH=<repo-root> uv run python tools/run_profile.py \
     --source tmp/profile/source.dfn --out tmp/profile/compile.prof
   PYTHONPATH=<repo-root> uv run python tools/run_profile.py \
     --source tmp/profile/graph.dfn --out tmp/profile/graph.prof
   ```

   Confirm each prints `has_errors=False`. If either is `True`, stop and report
   that run — its profile is not a valid full-pipeline sample.

6. **Analyze** each `.prof` (both the with-lark and without-lark views come from
   one file):

   ```
   uv run python tools/analyze_profile.py --prof tmp/profile/compile.prof --top 30
   uv run python tools/analyze_profile.py --prof tmp/profile/graph.prof --top 30
   ```

   `--exclude-file` defaults to `lark_standalone.py`. The "without" view drops
   that file's functions and, for every other function, counts **only the calls
   and time that came from non-lark callers** (a per-edge split, not wholesale
   removal). So a builtin both sides call keeps its compiler-driven cost here
   instead of being charged entirely to lark.

7. **Present the results** in the format below — one set of tables per source,
   plus the headline contrast between them.

## Output format

Lead with the caveat that cProfile inflates wall time ~3×. Then, **for each
source** (label them "Source A — single large action" and "Source B — action
call graph"), present the three things below as Markdown tables. Round to 3
decimals and keep `ncalls`. Finish with a short cross-source contrast.

### 1. Phase breakdown (by cumulative time)

Assemble from the cumtime table by rolling up these marker functions' cumtime.
The two sources light up different markers — report whichever dominate.

- **Parse** = `parser.py:...(parse)` /
  `lark_standalone.py:...(parse_from_state)`
  - **Lexing** (a sub-part of parse) = `lex` + `next_token` + `feed_token`
- **Transform** (parse tree → AST) = `transformer.py:...(transform)`
- **Reference-graph validation** = `reference_graph_validator.py:...(validate)`
  - **requirement inference** = `_maybe_infer_requirements_on_chain`
  - **guarantee propagation** = `particle_tracker.py:...(apply_guarantees)` +
    `...(generate_guarantees)` (driven by `_check_trigger` as actions trigger
    one another)
  - **destruction-contract generation** =
    `definition_postorder_validator.py:...(_generate_contract)`

Source A is parse-dominated; Source B is reference-graph-dominated (the
guarantee/requirement/contract rollup is the bulk of its run).

| Phase | cumtime | % of run |
| ----- | ------: | -------: |

### 2. Overall hotspots (with lark) — top ~10 by tottime

| tottime | cumtime | ncalls | function |
| ------: | ------: | -----: | -------- |

### 3. Compiler's own hotspots (without lark subtree) — top ~10 by tottime

Same columns. Note the headline split the analyze script prints: how much
tottime is the lark subtree vs the compiler's own code. For Source A this is
roughly half-and-half; for Source B at the default size it is roughly ~82%
compiler's own code vs ~18% lark.

After the tables for both sources, give a short, ranked list of the optimization
opportunities the numbers point to — but only as observations. Do not change
code.

## Follow-up drill-downs

The `.prof` files are kept, so most follow-ups need no re-run — re-analyze with
a short throwaway `pstats` snippet written into the scratch dir (don't add
scripts to the skill). Common ones:

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
- **Different input shape** — regenerate Source A with different `--lines` /
  `--max-chain-length`, or Source B with different `--layers` / `--width` /
  `--fan-out` / `--destructor-fraction`, and re-profile.

## Notes

- Run all Python via `uv run`. The profile script additionally needs
  `PYTHONPATH=<repo-root>` because it imports `define.compiler` directly.
- The scripts (`tools/run_profile.py`, `tools/analyze_profile.py`,
  `tools/generate_large_define_source.py`,
  `tools/generate_action_graph_source.py`) live in the repo's `tools/` directory
  and are parameterized; prefer passing flags over editing them. For one-off
  drill-downs, write a throwaway snippet into the scratch dir rather than
  editing the committed tools.
