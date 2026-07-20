---
name: profile-compiler
description: >-
  CPU-profile the Define compiler and present the hotspots as clear tables
  (overall, and with the bundled lark parser subtree removed so the compiler's
  own work is visible), plus a phase breakdown. Runs three complementary shapes:
  a single huge action (parse-heavy), a dense action call graph (reference-graph
  / requirement / guarantee / destruction-contract heavy), and a move-heavy body
  (operation-graph construction heavy). Use this whenever the user wants to
  profile, benchmark, or find performance hotspots / slow spots / bottlenecks in
  the Define compiler, asks "where is time being spent" or "what should we
  optimize", wants a flame-graph-style or cProfile view of compilation, or wants
  to drill a hotspot down to the callers that drive it — even if they don't say
  the word "profile". For the Define language compiler in this repo
  (define/compiler), not generic Python profiling.
---

# Profiling the Define compiler

This skill runs CPU profiles of the Define compiler over three complementary
source shapes, then presents the results as the tables the user expects: a phase
breakdown, an overall hotspot table, and a table with the bundled lark parser
removed so the compiler's own code is visible. It keeps the raw `.prof` files so
the user can ask follow-up questions.

The goal is **understanding**, not fixing. Run the profiles, present the numbers
clearly, and answer follow-ups. Do not propose or make code changes unless the
user explicitly asks.

## What to profile and why three shapes

The three sources stress different parts of the compiler. Profile **all three**
unless the user asks for a subset — the headline comparison (parse-bound vs
validation-bound, and which validation machinery dominates) is itself a result
worth presenting. Generate each fresh on every run so it's reproducible from the
stated parameters, and so each compiles to **zero diagnostics** (the profile
then reflects the full pipeline rather than an early-exit on error).

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

### Source C — move-heavy bodies (operation-graph heavy)

`tools/generate_operation_graph_source.py` (default
`--repetitions 150 --move-chain-length 24 --tree-depth 32 --wide-children 48 --pods 4 --retriggers 2`,
~45,000 lines). Sources A and B leave the operation dependency graph (DLP 44,
`operation_graph.py`) almost cold: A is create/destroy dominated with ~1,200
trivial moves, and B contains **no move statements at all**, so `record_move`,
the move dependency-minimization rules, and child-operation snapshots never run
in either. Source C's main action body repeats statement families each aimed at
a specific dependency rule: a move ladder (each move depending on the previous),
a deep position chain moved in one move and destroyed child-by-child
(stale-chain reduction), a wide particle whose many operated-on child positions
must be filtered into the move's child-operation snapshot, a sibling move ladder
under one parent particle (the move dependency-deduplication rule),
per-repetition contracted positions whose destruction needs the
caller-contribution bookkeeping for a required particle's children, and
worker/sink pods whose Action Guarantees the body consumes and which are
re-triggered and destroyed.

At the default size it profiles in ~20s under cProfile (~6s real): parse ~69% /
reference-graph validation ~31% of cumtime, lark subtree ~47% of tottime vs ~53%
compiler's own code. Within the validation phase, `operation_graph.py` is a
clearly drillable chunk (~15%, on par with `particle_tracker.py`), led by
`from_preceding_operations` and `_operation_dependencies` — with ~12,000
`record_move` calls vs zero in Source B. Knobs: `--repetitions` (body length),
`--move-chain-length`, `--tree-depth` (deeper chains make the ancestor-chain
walk quadratically more expensive), `--wide-children` (bigger child-operation
snapshots), `--pods` / `--retriggers` (trigger/guarantee-consumption volume).

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
Create it before invoking any Bazel target: `mkdir -p tmp/profile`.

> **Python environment requirement:** Run every source generator, compiler
> profile, and performance benchmark through its Bazel target. This applies to
> the main agent and every subagent. Do not use `uv run`, a repository `.venv`,
> or the OS Python for profiling: `uv` can select the OS interpreter, whose
> performance differs enough to invalidate comparisons. A subagent must build or
> run the relevant `py_binary` with Bazel instead of creating its own uv
> environment. OS Python is acceptable only for reading an existing `.prof` file
> with standard-library `pstats`, because that does not measure compiler
> performance. The commands below use `$PWD` for human readability. All agents
> must resolve it first and pass literal absolute paths in the command: shell
> variable expansion prevents the permission system from matching the existing
> `bazelisk` approval rule and causes an unnecessary approval prompt.

1. **Build the CLI** so a clean-compile sanity check is possible:
   `bazelisk build --noshow_progress --ui_event_filters=-info //define/compiler:main`

2. **Generate the sources** fresh (override knobs if the user asked):

   ```
   bazelisk run //tools:generate_large_define_source -- \
     --output "$PWD/tmp/profile/source.dfn" --lines 50000 --max-chain-length 25
   bazelisk run //tools:generate_action_graph_source -- \
     --output "$PWD/tmp/profile/graph.dfn" --layers 18 --width 64 --fan-out 32 \
     --destructor-fraction 0.5
   bazelisk run //tools:generate_operation_graph_source -- \
     --output "$PWD/tmp/profile/opgraph.dfn"
   ```

3. **(Optional) Confirm each compiles clean** via the real binary on the stdin
   path:
   `./bazel-bin/define/compiler/main compile --out /tmp/cg_check < tmp/profile/source.dfn`
   Exit 0 with no diagnostics means the profile will cover the whole pipeline.

4. **Run the profiles** through the Bazel Python toolchain:

   ```
   bazelisk run //tools:run_profile -- \
     --source "$PWD/tmp/profile/source.dfn" \
     --out "$PWD/tmp/profile/compile.prof"
   bazelisk run //tools:run_profile -- \
     --source "$PWD/tmp/profile/graph.dfn" --out "$PWD/tmp/profile/graph.prof"
   bazelisk run //tools:run_profile -- \
     --source "$PWD/tmp/profile/opgraph.dfn" \
     --out "$PWD/tmp/profile/opgraph.prof"
   ```

   Confirm each prints `has_errors=False`. If either is `True`, stop and report
   that run — its profile is not a valid full-pipeline sample.

5. **Analyze** each `.prof` (both the with-lark and without-lark views come from
   one file):

   ```
   bazelisk run //tools:analyze_profile -- \
     --prof "$PWD/tmp/profile/compile.prof" --top 30
   bazelisk run //tools:analyze_profile -- \
     --prof "$PWD/tmp/profile/graph.prof" --top 30
   bazelisk run //tools:analyze_profile -- \
     --prof "$PWD/tmp/profile/opgraph.prof" --top 30
   ```

   `--exclude-file` defaults to `lark_standalone.py`. The "without" view drops
   that file's functions and, for every other function, counts **only the calls
   and time that came from non-lark callers** (a per-edge split, not wholesale
   removal). So a builtin both sides call keeps its compiler-driven cost here
   instead of being charged entirely to lark.

6. **Present the results** in the format below — one set of tables per source,
   plus the headline contrast between them.

## Output format

Lead with the caveat that cProfile inflates wall time ~3×. Then, **for each
source** (label them "Source A — single large action", "Source B — action call
graph", and "Source C — move-heavy bodies"), present the three things below as
Markdown tables. Round to 3 decimals and keep `ncalls`. Finish with a short
cross-source contrast.

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
  - **operation-graph construction** = `operation_graph.py:...(record_create)` +
    `...(record_move)` + `...(record_destroy)` + `...(record_action_trigger)` +
    `...(record_guarantees)`

Source A is parse-dominated; Source B is reference-graph-dominated (the
guarantee/requirement/contract rollup is the bulk of its run); Source C is the
one where the operation-graph rollup and its helpers
(`from_preceding_operations`, `_operation_dependencies`) are meaningfully warm.

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
  standard-library `pstats.Stats` and use `print_callers(F)` /
  `print_callees(F)`, or read the per-edge caller dict directly:
  `stats.stats[func]` is `(cc, nc, tt, ct, callers)`, where
  `callers[caller_func] = (cc, nc, tt, ct)` is the callee's time attributable to
  that one caller edge.
- **"Break down file X's cost by which caller in file Y drives it"** — sum each
  function-in-X's per-edge `ct` over callers whose filename is Y, grouped by
  caller line. That per-edge `ct` already includes X's nested private helpers,
  so this attributes total cost correctly _as long as Y enters X only through
  X's public surface_ — check that before trusting the numbers.
- **Re-rank by cumtime, or show more rows** — re-run `analyze_profile.py` with a
  larger `--top`.
- **Different input shape** — regenerate Source A with different `--lines` /
  `--max-chain-length`, Source B with different `--layers` / `--width` /
  `--fan-out` / `--destructor-fraction`, or Source C with different
  `--repetitions` / `--move-chain-length` / `--tree-depth` / `--wide-children` /
  `--pods` / `--retriggers`, and re-profile.

## Notes

- Run all compiler-performance Python through Bazel targets. Never create a uv
  environment for a profiling run, including in a subagent worktree.
- The scripts (`tools/run_profile.py`, `tools/analyze_profile.py`,
  `tools/generate_large_define_source.py`,
  `tools/generate_action_graph_source.py`,
  `tools/generate_operation_graph_source.py`) live in the repo's `tools/`
  directory and are parameterized; prefer passing flags over editing them. For
  one-off drill-downs, write a throwaway snippet into the scratch dir rather
  than editing the committed tools.
