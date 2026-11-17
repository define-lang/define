# Bazel Mutation Testing

Decisions about the intent of this mutation tester, newest last within each
section. Started 2026-11-16.

## Goal

- Mutation-test both Rust and Python with one tool, driven by Bazel, so that a
  test in any language can kill a mutant in any language. Much of our Rust is
  tested only by Python tests through PyO3 extensions.
- Replace mutmut if this proves faster, since mutmut is too slow for regular
  use. Reusing mutmut only to generate Python mutants is acceptable.

## Decisions

- **Generate mutants per language as patches**, which a worker applies to its
  worktree.
- **Use existing mutant generators; do not write our own.** Choosing realistic
  mutations is most of a generator's value and a lot of upkeep. Our code only
  converts each generator's output into patches.
- **Generate Python mutants with mutmut's generator**, through its internal API
  with mutmut pinned.
- **Mutate the whole repository first.** A later mode will mutate only the lines
  a change touches, by filtering the mutant list to the diff.
- **Run by hand only.** There is no viable way to run it in CI yet.
- **Run every test for every mutant, and let the test cache choose.**
  `bazelisk test //... --notest_keep_going` reruns only tests whose inputs the
  patch changed, and stops at the first failure. Most mutants are killed, so
  most runs end early. No `rdeps` query or `--test_filter` is needed.
- **Tag tests with `no-mutation` to skip them**, such as slow ones like
  `resource_integration_test`, and runs pass `--test_tag_filters=-no-mutation`.
- **Classify mutants by Bazel's exit code:** 0 survived, 1 unviable (build
  failed), 3 killed. Record which test killed each mutant. Timeouts count as
  kills but are reported separately.
- **Flaky tests may count as kills.** The repository has no known flaky tests.
- **Only report mutants that could really be committed.** A mutant that the
  compiler, a type checker or a lint rejects is unviable: neither killed nor
  survived. Lints and type checks run in the same `bazelisk test` as the
  behavior tests; a mutant whose first failing test is a lint or type check
  counts as unviable.
- **Format each mutant before testing it**, since formatting never makes a
  change impossible to commit. Build the formatter once per run and run its
  binary on the one mutated file, not through `bazelisk run`.
- **Turn off only the lints that reject mutants for their shape.** Some lints,
  such as unused-variable lints, reject a mutant because of how the mutation is
  written, not because of the bug it stands for. Mutation runs turn those lints
  off. Choose them by counting which lints make mutants unviable and checking
  examples of each.
- **Test which mutants the lints let through.** A test holds example mutants,
  each expected to be viable or unviable, and runs only the lints and type
  checks on them with mutation runs' settings. It fails when a lint change
  rejects a realistic mutant, or lets through one that could never be committed.
- **Run mutants in parallel with a fixed pool of worktrees, one Bazel server
  each,** created once per run and reused across mutants. All workers execute on
  the local RBE service, which also shares cached results between them.
- **Rejected: one Bazel invocation running many mutants**, each with its own
  copies of the test targets. It multiplies the build graph by the number of
  mutants and is much harder to build than a worker pool.
- **Rejected: rules_rust_mutants**, which only runs a `rust_library`'s inline
  Rust tests, and **extending mutmut**, which cannot mutate Rust.

## Open Questions

- What test timeout to use. Measure the baseline's test durations first.
- How to generate Rust mutants. cargo-mutants fits best on paper: it lists
  mutants as patches without a Cargo build, and picks replacement values from
  each function's declared return type. mutest-rs needs nightly and Cargo and
  cannot emit patches. mewt is syntax-only and has no documented patch export.
  Not yet tried on our crates.
