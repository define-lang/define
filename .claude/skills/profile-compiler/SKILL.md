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

Each source stresses a different part of the compiler. Profile **all of them**
unless the user asks for a subset — the headline comparison (parse-bound vs
validation-bound, and which validation machinery dominates) is itself a result
worth presenting. Generate each fresh on every run so it is reproducible from
the stated parameters, and confirm each reaches **zero diagnostics**, so the
profile reflects the full pipeline rather than an early exit on error.

### Source A — single large action (parse-heavy)

`tools/generate_large_define_source.py`. One enormous Action Statements Block
plus a pool of positions and actions, so a large share of the run is the bundled
lark lexer and parser. Knobs: `--lines`, `--max-chain-length` (longer chains
stress reference-graph validation).

### Source B — dense action call graph (validation-heavy)

`tools/generate_action_graph_source.py`. A layered directed acyclic graph of
potential actions reachable from the entry-point constructor action `/test`,
where each action references next-layer actions through its `out` interface
position's constraint, so every action is validated. Every action destroys the
particle in its `src` interface position, which infers an Action Requirement and
records a Destruction Contract; `--destructor-fraction` of actions also carry a
real destructor, exercising the destruction cascade. This is the
reference-graph-dominated counterpart to Source A: guarantee propagation across
triggers, requirement inference, and destruction-contract generation.

Scale it with `--layers`, `--width`, and `--fan-out` — a wider, deeper, or
denser graph — rather than by chasing a line count, because its cost is in
cross-action validation rather than in text.

### Source C — move-heavy bodies (operation-graph heavy)

`tools/generate_operation_graph_source.py`. Sources A and B leave the operation
dependency graph (DLP 44, `operation_graph.py`) nearly cold — B contains no move
statements at all — so Source C exists to warm it. Its action body repeats
statement families each aimed at a specific dependency rule: a move ladder, a
deep position chain moved at once and destroyed child by child, a wide particle
whose operated-on child positions must be filtered into a move's child-operation
snapshot, a sibling move ladder under one parent particle, and worker pods whose
Action Guarantees the body consumes. Knobs: `--repetitions`,
`--move-chain-length`, `--tree-depth` (deeper chains make the ancestor-chain
walk quadratically more expensive), `--wide-children`, `--pods`, `--retriggers`.

### Source D — wide multi-file project (reference-graph heavy)

`tools/generate_reference_graph_project.py`. The other sources are each a single
file, so Source D is the only one that exercises per-file parallel validation,
cross-file global reference resolution, and the reference graph. It generates a
project holding one potential position per file, whose Position Constraint Block
references positions in deeper layers; `--utility-fraction` of those references
aim at a small set of deepest-layer definitions, giving the graph the high
fan-in real dependency graphs have. Profile it through `validate_program` on the
generated project root. Knobs: `--modules` (files), `--layers` (reference
depth), `--fan-out` (references per definition), `--utility-fraction` (fan-in
concentration), `--seed` (shape).

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
   `bazelisk run //tools:generate_large_define_source -- --output <absolute path> …`.
   Pass `--help` to a generator for its knobs and defaults rather than assuming
   them.
2. **Profile.** `tools/run_profile.py` profiles `driver.compile_source` in
   process — the non-filesystem compile path — which keeps interpreter startup
   and click dispatch out of the profile. It takes a single source file, so
   profile a multi-file project through `validate_program` on its root instead.
   Confirm each run reports no errors; a run with diagnostics is not a valid
   full-pipeline sample, so stop and report it.
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
