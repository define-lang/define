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
- **Build everything in the area, not only what the tests need.** A mutant that
  breaks any build action in the area is killed. The ruff and ast-grep lint
  aspects apply only to the targets a command names, so `--build_tests_only`
  would skip them on every library. On a sample of `crates/source_scanning`
  mutants, building everything added about 0.1 seconds per mutant.
- **Skip the tests tagged `no-coverage`.** They are the tests that find cases
  the other tests must then cover, and the resource tests, which measure what
  compiling costs rather than what it does. They were also the slowest tests,
  and running them with the others overloaded the machine. A separate
  `no-mutation` tag is not needed.
- **Flaky tests may count as kills.** The repository has no known flaky tests.
- **Any failure kills a mutant**, whether a test, a build action, the compiler
  or a lint fails. Exit 0 is a survivor. Otherwise record the test or action
  that failed first, from the build events. Timeouts count as kills but are
  reported separately.
- **Rejected: a separate outcome for mutants that the compiler or a lint
  rejects.** Since the run stops at the first failure, a mutant that both a lint
  and a test reject got whichever outcome failed first, which varied from run to
  run. A lint that rejects mutants only for their shape is a lint setting to
  change, below.
- **Use a 60-second test timeout** for every test size. Without the
  `no-coverage` tests, the slowest test takes under 8 seconds even when every
  test runs at once.
- **Format each mutant before testing it**, since formatting never makes a
  change impossible to commit. Build the formatter once per run and run its
  binary on the one mutated file, not through `bazelisk run`. A mutant that the
  formatter rejects no longer parses, such as `||` in a `let` chain, so it is
  killed, with the formatter as its culprit. The formatter's errors have no
  structured form, so when it fails, it formats the unchanged file too: if that
  fails as well, the formatter itself is broken, and the run stops rather than
  record a kill that a broken tool caused.
- **Turn off only the lints that reject mutants for their shape.** Some lints,
  such as unused-variable lints, reject a mutant because of how the mutation is
  written, not because of the bug it stands for. Mutation runs turn those lints
  off. Choose them by counting which lints kill mutants and checking examples of
  each. `bzl/lint_settings.bzl` lists the lints turned off.
  - The test for each lint: could a developer write the same wrong behavior in a
    form the lint accepts? If so, its kill would claim our checks catch a bug
    they do not, and mutation runs turn it off. If not, the lint is what would
    catch that bug, and its kill is valid.
  - Turned off: lints about what deleted code leaves behind, such as unused
    variables, imports and helpers, or a function that could now be `const`.
    Also lints about how code is spelled, and the repository's ban on `/`, which
    `checked_div` gets around.
  - So far, no lint passes the test, so every reviewed lint is turned off. Even
    a lint that finds a comparison that always holds rejects only one spelling:
    `value >= 0` on an unsigned value is rejected, but `true`, which behaves the
    same, is not. Compile errors and unparseable mutants are always valid kills.
  - The choice is per lint, so turning one off loses the rare real bug it would
    catch. It holds for the mutants that cargo-mutants makes, whose
    unused-variable kills all come from replacing a body. Review the lints again
    for a new generator, such as mutmut's.
- **Name the lints that kill each mutant in its culprit,** read from the failed
  action's own standard error. With
  `--experimental_build_event_upload_strategy=local`, the action's build event
  names it as a local file, rather than a blob in the remote cache, so nothing
  reads Bazel's console. Mutation runs set rules_rust's `error_format` and
  `clippy_error_format` to `json`, and `//tools/bzl:lint_json`, which makes the
  ast-grep and Ruff aspects report JSON lines. Each tool then names each error's
  lint, rule or code in a field, rather than in text meant for people. A culprit
  says `unidentified error` when it cannot name what failed, so that no
  unreviewed failure looks like a reviewed one. A lint matters only when it
  fails first: if a test fails first, the lint changed nothing. A run whose
  culprits name only reviewed lints shows the lint settings are complete.
- **Rejected: a separate tally that builds every mutant with `--keep_going`** to
  find every lint that rejects it. It answers more than the review needs, for a
  second pass over every mutant. One partial tally, over 1,435 mutants, chose
  the lint settings.
- **Turn lints off through every Rust target's lint config.** `lint_config()`
  names a lint config in `//tools/bzl` that wraps the one from `Cargo.toml`, and
  appends an `--allow` flag for each lint that
  `--//tools/bzl:allowed_rust_lints` names. The flags then come after every
  other lint flag, for rustc and clippy alike. A run passes its turned-off
  lints, sorted, as that flag, and the results store records them. The flag is
  generic, so that mutation testing's lists stay in this package, and nothing
  outside it depends on this package. Without the flag the lint config is
  unchanged, so ordinary builds keep their cache.
- **Rejected: building the lint config only from rules_rust's public rules,**
  with `extract_cargo_lints` on a copy of `Cargo.toml` that allows the
  turned-off lints. It replaces rules_rs's generated lint config, rebuilds every
  Rust action once, and needs a TOML rewriter, to avoid loading `LintsInfo` from
  rules_rust's private providers, which rules_rs loads too.
- **Rejected: rules_rust's `extra_rustc_flag` setting** to turn lints off. It
  comes before a target's lint config, so it cannot turn off a lint that
  `Cargo.toml` names, such as `unused_crate_dependencies`.
- **Test which mutants the lints let through.** A test holds example mutants,
  each expected to pass or fail them, and runs only the lints and type checks on
  them with mutation runs' settings. It fails when a lint change rejects a
  realistic mutant, or lets through one that could never be committed. It runs
  the toolchain's rustc and clippy-driver directly, with the lint config's flags
  in the order rules_rust passes them, so that it runs in ordinary test runs.
- **Run mutants in parallel with a fixed pool of worktrees, one Bazel server
  each,** created once per run and reused across mutants. All workers execute on
  the local RBE service, which also shares cached results between them.
- **Rely on the RBE service to reuse action directories between mutants.**
  Staging each test's inputs from scratch, and deleting them afterwards, was a
  quarter of a test run's time. The service reuses the directory of an earlier
  action that ran the same command, which is what each mutant's reruns are. Its
  limit on idle directories must cover the commands one mutant reruns, once for
  each worker.
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
- **Test a commit, by default `HEAD`**, checked out in each worker's worktree,
  rather than the working tree. The results store records the commit, the area
  and the test timeout, and a run resumes only from a store with the same ones.
- **Check every run with a canary**: a failing test appended to a crate root
  that a `rust_test` the run tests with compiles. The canary passes the
  repository's lints, and the run requires that test to be what fails, since a
  lint or compile failure would not show that the tests detect a change.
- **Find an area's crates with `bazel query`, including targets tagged
  `manual`.** Each PyO3 extension's crate is compiled only by a manual
  `rust_cdylib_library`. Tests still follow `bazel test`'s patterns, which skip
  manual tests unless named.
- **Allow one run at a time per repository.** Runs share the workers' worktrees,
  so a second run would revert the first run's mutants mid-test. Each run holds
  a lock in `.mutation_testing` until it ends.
