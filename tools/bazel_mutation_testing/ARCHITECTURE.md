# Bazel Mutation Testing

The problems this mutation tester solves, and the intentions behind its design.

## Goal

- Mutation-test both Rust and Python with one tool, driven by Bazel, so that a
  test in any language can kill a mutant in any language. Much of our Rust is
  tested only by Python tests through PyO3 extensions.
- Be fast enough for regular use.

## Mutants

- **Use existing mutant generators; do not write our own.** Choosing realistic
  mutations is most of a generator's value and a lot of upkeep. The tester only
  turns each generator's output into patches that a worker applies.
- **Generate Rust mutants with cargo-mutants and Python mutants with mutmut.**
  Both list mutants from source alone, without building anything. Each Python
  mutant keeps mutmut's name for it, so that its result is comparable with
  mutmut's.
- **Mutate one area at a time.** An area is a set of target patterns. A run
  mutates only the area's sources and runs only the area's tests, so a mutant
  that only a test outside the area would kill is a survivor.
- **Mutate only code that the tests are meant to check.** The tester leaves out
  test helpers, files that builds generate, and code generators. A generator's
  mutant changes only the code it generates, so a surviving one does not show
  which test is missing.
- **Test a commit, not the working tree,** so that a run's results describe code
  that someone can check out. A run resumes only from results of the same
  commit, area and settings.

## Testing a Mutant

- **Run only the tests that run the mutated line.** Each run first records which
  lines each of the area's tests runs, at the run's commit. A test that never
  runs a line cannot detect a change to it, though it may depend on the changed
  file. Bazel's cache then reruns only the chosen tests that the change reaches.
- **Choose tests only by coverage that records every run of a line.** Coverage
  builds leave code unoptimized, since an optimized crate lets other crates copy
  its small functions, and coverage never counts those copies. A line that no
  coverage records runs every test. The tests that record no coverage, such as
  type checks, always run, so that skipping a test never hides a kill.
- **Stop at the first failure.** Most mutants are killed, so most runs end
  early.
- **Any failure kills a mutant,** whether a test, a build action, the compiler
  or a lint fails, and the result names what failed first. Running out of time
  or memory is a kill, reported separately, since the mutant may only have made
  a test slower or larger. A test that fails only sometimes also counts as a
  kill.
- **Build everything in the area, not only what the tests need,** so that the
  lints run on every library, and a mutant that breaks any build action is
  killed.
- **Do not build Define programs that no test runs.** Bazel gives a build action
  no time limit, unlike a test, so a mutant that makes the compiler loop forever
  while it compiles such a program would stop its worker.
- **Give every generator a time limit, in every build.** A generator imports
  compiler code that the tester mutates, so a mutant could make a generator loop
  forever.
- **Skip the tests that look for new cases or measure cost.** They find cases
  that the other tests must then cover, or measure what compiling costs rather
  than what it does, and they are the slowest tests.
- **Give every test one generous time limit,** so that a mutant that loops
  forever is caught without failing a slow but correct test.
- **Give every action one generous memory limit,** so that a mutant that makes a
  test use memory without bound is killed alone. Otherwise the machine runs out
  of memory and kills other programs, such as the workers.
- **Format each mutant before testing it,** since formatting never makes a
  change impossible to commit. A mutant that the formatter rejects no longer
  parses, so it is killed. When the formatter fails, the tester checks that it
  still formats the unchanged file, so that a broken formatter stops the run
  rather than kill mutants.
- **Check every run with a canary,** a test that is certain to fail, added in
  the area. The run requires that test to be what fails, so that the run shows
  its tests can detect a change.

## Lints

- **Turn off only the lints that reject mutants for their shape.** Some lints,
  such as unused-variable lints, reject a mutant because of how the mutation is
  written, not because of the bug it stands for.
  - The test for each lint: could a developer write the same wrong behavior in a
    form the lint accepts? If so, its kill would claim our checks catch a bug
    they do not, so mutation runs turn it off. If not, the lint is what would
    catch that bug, and its kill is valid.
  - Lints about what deleted code leaves behind, or about how code is spelled,
    fail the test. So do lints that a turned-off lint leaves unsatisfied, such
    as unused suppression comments.
  - Compile errors, type errors and unparseable mutants are always valid kills.
    No type-correct code has the value or call that a type error reports.
  - The choice is per lint, so turning one off loses the rare real bug it would
    catch. Each new mutant generator needs the lints reviewed again.
- **Name the lint that killed each mutant,** from each tool's structured report
  rather than text meant for people. A result says when it cannot name what
  failed, so that no unreviewed failure looks like a reviewed one. A run whose
  results name only reviewed lints shows that the lint settings are complete.
- **Leave ordinary builds unchanged.** Mutation runs turn lints off through
  settings that ordinary builds do not set, so ordinary builds keep their cache,
  and nothing outside the tester depends on its lists of lints.
- **Test which mutants the lints let through,** with example mutants that each
  expect to pass or fail, so that a lint change cannot silently reject realistic
  mutants or accept ones that could never be committed.

## Running

- **Run by hand only.** There is no viable way to run it in CI.
- **Run mutants in parallel on a pool of workers,** each a worktree with its own
  Bazel server, all executing on the local remote execution service, which
  shares cached results between them.
- **Run as many workers as keep the CPUs busy without running out of memory.**
  Each worker's Bazel server takes memory, and a machine that runs out of memory
  kills other programs. Each added worker also gains less than the one before,
  because the workers share one execution service. Bazel servers stay small and
  exit when idle.
- **Rely on the execution service to stop and reuse work.** It stops the tests
  that a stopped build no longer waits for, so that a killed mutant costs no
  more than its first failure. It reuses the directories of earlier actions that
  ran the same command, which is what each mutant's reruns are.
- **Allow one run at a time per repository,** since runs share the workers.
- **A failed or interrupted worker stops the run.** Every worker reverts its
  mutant, and a stopped mutant gets no result, so a resumed run tests it again.
  Retrying a mutant on another worker would hide a broken worker.
- **Remove the workers when a run ends,** however it ends, since a fresh worker
  sets up quickly from the cache while a kept one takes a lot of disk. A worker
  with changes left in it is kept, to show what went wrong.
- **Report each run's survivors with the changes they make,** so that finding
  the missing tests needs no second run. The report also lists the mutants that
  ran out of time or memory.

## Rejected

- **A separate outcome for mutants that the compiler or a lint rejects.** A
  mutant that both a lint and a test reject would get whichever fails first,
  which varies from run to run.
- **Finding every lint that rejects each mutant** by building every mutant to
  the end. It answers more than choosing lint settings needs, at the cost of a
  second pass over every mutant.
- **One Bazel invocation that tests many mutants,** each with its own copy of
  the tests. It multiplies the build graph by the number of mutants, and is much
  harder to build than a worker pool.
- **Running mutmut itself, or extending it,** since it cannot mutate Rust, and
  Rust tools that run only a crate's own tests, since Python tests check much of
  our Rust.
- **Rust mutant generators that cannot produce patches** or that need a nightly
  toolchain.
