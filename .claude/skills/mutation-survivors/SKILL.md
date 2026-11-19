---
name: mutation-survivors
description:
  Use this skill when the user wants to mutation-test Rust or Python code in
  this repository, inspect surviving or timed-out mutants, and add or improve
  tests to kill them. It uses the repository's Bazel mutation tester in
  tools/bazel_mutation_testing.
---

# Mutation Survivors

The mutation tester mutates the Rust and Python sources of an area, runs the
area's Bazel tests on each mutant, and reports the mutants that no test killed.
`tools/bazel_mutation_testing/ARCHITECTURE.md` explains its decisions.

## Run the Tester

```text
bazelisk run --noshow_progress --ui_event_filters=-info //tools/bazel_mutation_testing:tester -- --store .mutation_testing/<name>.jsonl <area>
```

- The area is one or more target patterns, such as `//define/... //crates/...`
  or `//define/compiler/graphs/...`. Only tests in the area can kill a mutant.
- The tester tests a commit, `HEAD` by default, not the working tree. To test
  uncommitted changes, pass `--commit` a snapshot commit (see Verify).
- A run resumes from its store, if the store was made with the same commit,
  area, test timeout and lint settings. Choose a new store name otherwise.
- Only one run at a time can use a checkout. Do not start a run while another is
  running.
- `//define/... //crates/...` has about 15,000 mutants and takes hours. Prefer a
  smaller area unless the user asks for the whole one. Run long runs in the
  background and wait for them to finish.

When the run ends, it writes `.mutation_testing/<name>.survivors.md`, which
lists each survived and timed-out mutant, grouped by file, with its patch.

## Triage the Survivors

Read each survivor's patch and the code and tests it touches. When survivors
span several files, launch parallel agents, one per file or group of files, each
given its mutants' names and patches from the survivors report.

Write `.mutation_testing/<name>.triage.md` with:

1. A header: commit, area, total mutants, kill rate, and the survived and
   timed-out counts.
2. A triage summary: how many survivors are interesting and how many are not.
3. One section per root cause, titled
   `## Root Cause N: <short description> (M mutants)`. Group survivors by why
   they survive, not by file. Each section has a 1–3 sentence explanation,
   `**Files:**` with the affected source files, and `**Mutants:**` with every
   mutant name as a bullet.
4. An uninteresting section at the end, grouped by category, listing each mutant
   name.

These survivors are uninteresting:

- Changes to `typing.cast()` type strings, which are no-ops at runtime.
- `isinstance(...)` or `is None` checks that exist only for pyright's type
  narrowing.
- Messages of exceptions for states that can never happen.
- Equivalent mutants, such as `False` to `None` in a Boolean context, or Rust
  `Default::default()` where the default is the same value.
- Unreachable match arms and wildcards.
- Timeouts caused by an infinite loop that the mutant creates, since a timeout
  still kills the mutant.

## Fix the Gaps

- Prefer adding or improving tests. Do not change production code unless the
  user asks for it.
- A test must be in the area to kill a mutant there. A mutant that only a test
  outside the area would kill is reported as a survivor.
- Tests tagged `no-coverage` do not run in mutation runs, so they kill no
  mutant.

## Verify

1. Run the targeted tests that cover the new or changed tests.
2. Make a snapshot commit of the working tree, without changing the branch or
   the user's index:

   ```text
   GIT_INDEX_FILE=<scratch file> git read-tree HEAD
   GIT_INDEX_FILE=<scratch file> git add <changed files>
   GIT_INDEX_FILE=<scratch file> git commit-tree $(GIT_INDEX_FILE=<scratch file> git write-tree) -p HEAD -m Snapshot
   ```

3. Rerun the tester with `--commit <snapshot>`, a new store, and the smallest
   area that holds the mutated files and the new tests. Check that the mutants
   you targeted are now killed.
4. Finish with `bazelisk test --noshow_progress --ui_event_filters=-info //...`.
