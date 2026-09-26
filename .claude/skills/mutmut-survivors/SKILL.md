---
name: mutmut-survivors
description:
  Use this skill when the user wants to run mutmut in this repository, inspect
  surviving or untested mutants, and add or improve tests to kill them. This
  skill is specific to the Define repo's mutmut configuration, local-dev setup,
  and verification workflow.
---

# Mutmut Survivors

Use this skill for mutation-testing work in this repo.

The repo already has one shared mutmut configuration in `pyproject.toml`. Use
that file as the source of truth for mutation scope and test exclusions.

`mutants/` is ignored by git and Bazel. Do not run multiple mutmut jobs at the
same time, because they share that state directory.

## Workflow

1. Prepare the repo:
   - `bazelisk run --noshow_progress --ui_event_filters=-info //tools:setup_local_dev`
2. Start or resume mutation testing:
   - broad run: `uv run mutmut run`
   - focused run: pass specific mutant names to `uv run mutmut run`
   - by default, prefer letting mutmut continue until there are no `not checked`
     mutants left
   - if you need a time budget for automation, wrap mutmut externally rather
     than looking for a mutmut timeout flag
3. Inspect findings:
   - `uv run mutmut results`
   - `uv run mutmut results --all true` for the full state
   - `uv run mutmut show MUTANT_NAME`
   - `uv run mutmut tests-for-mutant MUTANT_NAME`
4. **Produce a survivors report** (see Report Generation below)
5. Fix the gap:
   - prefer adding or improving tests
   - avoid changing production code unless the user explicitly asks for it
   - do not chase low-value survivors that only remove defensive built-in Python
     exceptions or code that exists only for pyright narrowing, such as
     `isinstance(...)` or `is None` checks whose purpose is type narrowing
   - use `uv run mutmut apply MUTANT_NAME` only when you need the exact mutant
     written into the working tree, because it dirties the working tree and adds
     cleanup work
6. Verify:
   - run the most targeted pytest command that covers the new or changed tests
     first
   - rerun the specific mutant or focused mutmut pattern
   - finish with `bazelisk run --noshow_progress //tools:format`
   - finish with `bazelisk test --noshow_progress //...`

## Report Generation

After a broad mutmut run completes, produce a markdown report file
(`mutmut_survivors_report.md`) with the following structure.

### Report structure

1. **Header** with run date, total mutants, kill rate, survived count, no-tests
   count, timeout count.
2. **Triage summary** showing how many are interesting vs uninteresting.
3. **Root cause sections** — group survivors by the underlying reason they
   survive (not by file or mutant name). Each section has:
   - A heading like `## Root Cause N: <short description> (M mutants)`
   - A 1–3 sentence explanation of **why** these mutants survive
   - `**Files:**` listing the affected source files
   - `**Mutants:**` listing every individual mutant name as a bullet list
4. **Uninteresting mutants** section at the end, grouped by sub-category (e.g.,
   `super().__init__()` args, `typing.cast()` strings, ValueError/KeyError guard
   text, timing/stats fields, equivalent mutants, unreachable code, type
   narrowing). Each sub-category lists its mutant names.

### Uninteresting mutant categories

These should be classified as uninteresting and listed in the uninteresting
section rather than as root causes:

- `typing.cast()` string arg mutations (runtime no-op)
- `isinstance(...)` or `is None` checks used only for pyright type narrowing
- ValueError/KeyError guard message text for states that can never happen
- Timing/stats initial values and arithmetic
- Equivalent mutants (`False` → `None` in boolean context, case-insensitive
  codec names, removing `case _: pass`, etc.)
- Unreachable match wildcards

### Parallel analysis

When analyzing survivors, **launch parallel agents** to inspect mutants from
different source files simultaneously. For example, if survivors span 5 source
files, launch up to 5 agents — one per file — each running `mutmut show` on its
set of mutants and reading the relevant source code and tests. Merge the agents'
findings into the final grouped report.

## How To Triage A Mutant

Use `mutmut show` first. It is the fastest way to see what changed without
touching tracked files.

Then use `mutmut tests-for-mutant` to find the tests mutmut considers relevant.
Treat that as the first test set to understand, but not necessarily the complete
one.

Prioritize these statuses:

- `survived`: best target for writing a stronger assertion or adding a missing
  test case
- `no tests`: usually means the mutated code path is not exercised by the
  selected tests
- `timeout` or `suspicious`: often means the mutant triggered a slow or unstable
  path and may need manual inspection

Ignore `not checked` until the run has progressed far enough to produce
completed results.
