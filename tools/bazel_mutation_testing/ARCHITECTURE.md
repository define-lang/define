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
- **Mutate one area at a time.** A run names an area as one or more target
  patterns, such as `//define/compiler/... //crates/...`. It mutates only the
  files in the area and runs only the tests in it. A mutant that only a test
  outside the area would kill is reported as a survivor. The area can be the
  whole repository. A later mode will mutate only the lines a change touches, by
  filtering the mutant list to the diff.
- **Run by hand only.** There is no viable way to run it in CI yet.
- **Run every test in the area for every mutant, and let the test cache
  choose.** `bazelisk test <area> --notest_keep_going` reruns only tests whose
  inputs the patch changed, and stops at the first failure. Most mutants are
  killed, so most runs end early. No `rdeps` query or `--test_filter` is needed.
  A mutant tested before costs about 2 seconds, since every action it needs is
  cached.
- **Build only what the tests need**, with `--build_tests_only`. Otherwise a
  mutant that breaks a build action no test depends on, such as compiling a
  Define example program, would count as a kill.
- **Skip the tests tagged `no-coverage`.** They are the tests that find cases
  the other tests must then cover, and the resource tests, which measure what
  compiling costs rather than what it does. They were also the slowest tests,
  and running them with the others overloaded the machine. A separate
  `no-mutation` tag is not needed.
- **Flaky tests may count as kills.** The repository has no known flaky tests.
- **Only report mutants that could really be committed.** A mutant that the
  compiler, a type checker or a lint rejects is unviable: neither killed nor
  survived.
- **Classify each mutant from the build events of its one test run.** Exit 0 is
  a survivor. Otherwise the first failure decides: compiling or linting the
  target that owns the mutated file, or the lint or type-check tests of that
  file's package, makes the mutant unviable, and any other failing action or
  test kills it. Record the test or action that killed each mutant. Timeouts
  count as kills but are reported separately. Since the run stops at the first
  failure, a mutant that both a lint and a behavior test reject may be counted
  either way. That never makes a false survivor.
- **Rejected: classifying by exit code alone.** Exit 1 does not mean unviable:
  code generators, such as the one that writes the parser's `ast.rs` from
  `define/compiler/ast.py`, run as build actions, so a mutant that breaks one
  fails the build, and that is a kill.
- **Rejected: a separate viability check before each test run**, building the
  owning targets and running their lint and type-check tests first. The build
  events of the one test run tell the same thing, apart from the
  killed-or-unviable mutants above.
- **Use a 60-second test timeout** for every test size. Without the
  `no-coverage` tests, the slowest test takes under 8 seconds even when every
  test runs at once.
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
- **Generate Rust mutants with cargo-mutants**, through
  `cargo mutants --list --json --diff` on a scratch Cargo manifest for each
  Bazel crate. The manifest needs only the crate root, not the crate's
  dependencies, since listing reads syntax alone. Every patch it listed for our
  crates applied. It lists mutants without a Cargo build, and picks replacement
  values from each function's declared return type. It comes from multitool,
  like the repository's other tools, and runs the Rust toolchain's cargo, which
  `CARGO` names.
- **Rejected for Rust: mutest-rs**, which needs nightly and Cargo and cannot
  emit patches, and **mewt**, which is syntax-only and has no documented patch
  export.
- **Mutate only files Git tracks.** Builds write some generated Rust files, such
  as the parser's `ast.rs`, into the source tree, where a crate's module tree
  reaches them. Their generators are mutated instead.
