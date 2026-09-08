# Checkpoint 2 Review and Implementation Plan

## Purpose and status

Reconstruct the completed Checkpoint 2 implementation as a reviewable series
starting from the committed pre-Checkpoint-2 implementation. Checkpoints 0 and 1
are already committed and are not work to repeat.

This is a new implementation sequence, not a statement that the existing
Checkpoint 2 implementation is incomplete. Keep
`destruction_implementation_plan.md` as the record of that implementation and
its validation. The existing changes are a reference for the intended design,
regressions, and generated examples, not patches to apply indiscriminately.

Preservation steps P0 through P3 are complete. T0 is approved for commit and
push; M1 through S5 remain pending. The user deferred the destructor-ordering
decision recorded in `checkpoint_2_specification_audit.md`; its 22 unresolved
expectations are not treated as specification decisions. Subsequent review
changes will remain uncommitted until approved.

## Review boundaries

- Every strictly mechanical transformation is its own change. Its review cost is
  near zero even when it touches many files or generated artifacts. Perform it
  at the earliest point where its prerequisites exist.
- A mechanical change must have a precise transformation rule and preserve
  behavior. Do not combine it with a bug fix, data-model redesign, new lifetime,
  changed dependency, or changed initialization order.
- Group substantial changes that redesign the same code and require the same
  reasoning. Do not introduce a temporary implementation just to divide one
  coherent redesign into more reviews.
- Establish independent regressions first in T0. Each later change includes
  removal of the expected-failure markers it resolves, any
  implementation-specific tests, documentation, and intentional generated-code
  updates. Generated artifacts are not a later omnibus change.
- Present each change for review before starting the next substantive change. Do
  not commit or land changes without the user's direction.
- If another mechanical transformation becomes apparent during implementation,
  extract it into its own change before the substantive work that needs it. Pure
  file moves use `git mv` and do not include content redesign.

## Preparation

### Preserve the current work before extracting tests

Perform this preparation only when the user authorizes starting the series,
including its preservation operations. Do not start T0 against the current
implementation and then try to separate tests from production changes afterward.

Use a named stash as the initial recovery copy and a dedicated local snapshot
branch and commit as the convenient long-lived reference. The stash also retains
the original staged/unstaged distinction, which a single snapshot commit does
not. Neither is a change intended for review or merging.

| When                                                          | What is preserved or restored                                                                                                           | Destination                        |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| P0: Before changing branches or extracting tests              | Inventory original branch, HEAD, staged/unstaged changes, untracked files, and relevant ignored files                                   | Preservation record                |
| P1: Before T0                                                 | All current Checkpoint 2 production changes, tests, fixtures, generated artifacts, and design/plan documents, including untracked files | Named recovery stash               |
| P2: Immediately after verifying P1                            | Apply the preserved task changes on a new branch from the original HEAD and commit them                                                 | Local reference snapshot branch    |
| P3: After verifying P2                                        | Return to the original baseline branch; restore only this review plan for the implementation series                                     | Working branch, documentation only |
| T0: After P3                                                  | Extract independent tests and fixtures selectively from the reference snapshot                                                          | First tests-only review change     |
| M1 through S5                                                 | Consult the snapshot and extract only material belonging to the current step                                                            | Successive review changes          |
| After S5 is approved and recovery copies are no longer needed | Offer to remove the snapshot branch and task recovery stash                                                                             | Cleanup only with user approval    |

#### P0: Inventory and confirm scope

Record the original branch and exact HEAD revision. Classify staged, unstaged,
and untracked files before any stash or commit. The task snapshot includes all
new tests and both normal and tracing generated expectations, not just compiler
and runtime source files. Include `checkpoint_2_review_plan.md`,
`destruction_implementation_plan.md`, `destruction_ordering_design.md`, and any
task-specific regression investigation documents.

Do not assume every dirty file belongs to this task. Keep unrelated user work
out of the task snapshot. If unrelated changes must be put aside to obtain a
clean baseline, preserve them in a separately named stash with their own scope
and restoration record. If task and unrelated edits overlap and cannot safely be
separated, stop for direction rather than guessing.

Ignored build products and reproducible local-development files do not belong in
the reference commit. Inspect relevant ignored files for irreplaceable work
before relying on a stash with untracked-file inclusion; it does not preserve
ignored files. Preserve any such work explicitly without capturing caches or
credentials.

#### P1: Create and verify the recovery stash

Create a clearly named task stash with untracked-file inclusion and the exact
scope identified in P0. Do not use an unrestricted repository-wide stash unless
the inventory proves all affected changes belong to this task. Do not use
`--keep-index`: the baseline must not retain staged implementation changes.

Record the stash's immutable object ID, not merely its changing `stash@{n}`
position. Inspect the saved tracked changes and untracked-file contents against
the inventory. Confirm that tests, generated artifacts, and this plan are
recoverable before proceeding. Do not drop or pop the stash.

#### P2: Create the inspectable reference snapshot

Create a new, uniquely named local reference branch from the recorded baseline,
for example `reference/checkpoint-2-completed`. Apply the task stash using its
recorded ID and `--index`, then explicitly stage the inventoried task files and
commit the snapshot when authorized. Follow normal commit hooks and trailer
requirements; do not bypass verification for the snapshot.

Verify that the snapshot contains the preserved implementation and fixtures. If
hooks change files, inspect those changes and reconcile them with the inventory;
retain the original recovery stash regardless. Record the snapshot commit ID and
confirm the reference branch has no unpreserved changes before switching away.
If snapshot creation fails, resolve it or report the blocker; do not discard the
recovery copy or clean the worktree destructively.

#### P3: Return to the baseline and retain the plan

Switch back to the original branch, whose HEAD must still equal the recorded
baseline. Do not reset it or merge/cherry-pick the snapshot. Restore only this
review-plan document from the reference snapshot, add the preservation IDs and
status, and present it as a documentation-only change for approval. Once that
documentation is committed with authorization, T0 starts from unchanged baseline
production code.

The earlier completion report, detailed design documents, final generated
artifacts, and implementation remain available on the snapshot branch. Bring
their relevant portions into later changes deliberately, not by restoring the
whole snapshot. Keep this plan available on the working branch throughout.

#### During and after the series

Do not reapply the full implementation stash after T0 or after any later step.
Use the snapshot to compare code and selectively recover fixtures; adapt each
change to its current reviewed baseline. Keep deferred tests in the snapshot
until the implementation step that can support them. Commit each approved review
change before beginning the next; no additional implementation stash is normally
needed between steps.

If interrupted with uncommitted work, preserve only that in-progress review
change in a separate named stash and record its base commit and object ID. Never
replace the original recovery stash with a partial implementation.

Keep unrelated user-work stashes separate throughout. Restore them with their
original staging where feasible when returning the workspace to the user, or
earlier at the user's direction. Inspect conflicts rather than dropping or
overwriting either version. Retain those stashes until restoration is verified.

After S5, compare the final implementation and regression coverage against the
reference snapshot to identify anything accidentally omitted; byte-for-byte
equality is not required. Retain both task recovery copies until the user
approves cleanup. Never merge the snapshot as a final step.

Preservation record to fill during execution:

- Original branch: `main`; baseline commit:
  `3a2b6a0d4f862eaf3599fe910851c23116e59001`.
- Inventory: 55 unstaged modified files, 1,282 staged modified files, 871 staged
  added files, and four untracked plan/design documents. All belonged to this
  task. Existing stashes and ignored files were left untouched; no separate
  unrelated-work stash was needed.
- Task recovery stash:
  `checkpoint-2-completed recovery before review series 2026-09-07`; object ID
  `ad37e18d041ba2417656bfcee514cb996c4a44ae`.
- Reference branch: `reference/checkpoint-2-completed`; snapshot commit:
  `42c3d18cd2b2a727f0d6bb0e88f0115ef0bc8108`.
- Verification: tracked worktree and index diff checksums matched before and
  after preservation; all four untracked document checksums matched. Snapshot
  code and testdata match the stash. Returned to unchanged `main` with only this
  plan restored before T0 extraction.
- Review-plan restoration: complete, left uncommitted for review with T0 rather
  than creating a separate documentation commit. The snapshot is the only new
  commit; the user confirmed continuing after checking its branch.

### Baseline validation

Record the baseline test results and existing expected failures. An extracted
change must not introduce new regressions or hide failures by adding broad
expected-failure markers. Reproduce each claimed independent bug against this
baseline before implementing its fix.

## Sequence

| Order | Change                                                           | Review category                   |
| ----- | ---------------------------------------------------------------- | --------------------------------- |
| T0    | Establish independent regression tests on the committed baseline | Tests-only baseline               |
| M1    | Rename the runtime `Guarantee` class to `Fanout`                 | Mechanical                        |
| M2    | Rename `Fanout.publish` to `Fanout.run`                          | Mechanical                        |
| M3    | Supply the fanout scheduler at construction                      | Mechanical API migration          |
| M4    | Make `Scheduler.continue_with` accept positional tasks           | Mechanical API migration          |
| M5    | Use `continue_with` for generated multi-continuation fanouts     | Mechanical generation rewrite     |
| M6    | Extract common Particle Operation naming logic                   | Mechanical extraction             |
| S1    | Verify Destructors separately for each particle                  | Small correctness fix             |
| S2    | Discover all callees of contributed Destructors                  | Small correctness fix             |
| S3    | Correct child-operation dependencies across callers and Moves    | Cohesive graph-correctness change |
| S4    | Unify initialization planning and Python generation              | Cohesive initialization redesign  |
| S5    | Implement dependency-based caller-contributed destruction        | Remaining Checkpoint 2 redesign   |

T0 is the first review change, before M1. M1 through M6 precede substantive
implementation. Additional mechanical changes that require structures introduced
by S4 or S5 occur as soon as those structures exist; do not introduce unused
structures merely to move a rename earlier.

### T0: Establish independent regression tests

Execution details and the per-case failure audit are recorded in
`checkpoint_2_baseline_test_audit.md`. Cases affected by baseline initialization
races retain concurrent execution with non-strict xfail markers. Remove these
markers in S4/S5 after repeated multi-worker validation. Register missing
scenarios with the existing fixture-driven tracing tests; do not duplicate their
checks or assert internal initialization order. Generate new tracing artifacts
using the baseline compiler instead of importing the snapshot's generated code.

After preserving the current implementation, extract its independent regression
tests onto the committed pre-Checkpoint-2 baseline. This tests-only change makes
the required behavior reviewable before the fixes. Do not include production
changes merely to make these tests pass.

- Include real Define-source fixtures and specification-derived Operation Graph
  assertions that can run against the existing interfaces.
- Include runtime, tracing, and callee-independence regressions where the
  existing test infrastructure can express them. Keep their intended assertions
  intact; do not weaken expectations to match baseline bugs.
- Leave tests requiring new internal APIs or the new implementation structure
  with their corresponding implementation change.
- Keep the completed implementation's generated-code expectations with the
  code-generation changes that produce them. If existing test infrastructure
  requires generated artifacts for a new baseline fixture, generate them using
  the baseline compiler and distinguish those artifacts from the specification's
  required behavior. Do not import final generated code to make a baseline
  runtime regression pass.

Run every candidate against the committed baseline, not the completed working
implementation. First run without expected-failure suppression and inspect the
failure to establish that it exposes the intended bug rather than a missing
artifact, incompatible test API, or unrelated failure.

Passing cases have no marker. For a failing case, use a narrowly scoped
`xfail(strict=True)` with a specific reason and the planned fixing step, S1
through S5. Apply markers to individual test cases or parameter instances, not
whole test modules or unrelated assertions. Maintain a mapping from each new
expected failure to its intended fix; record multiple required steps explicitly
when a case depends on more than one. Strict markers detect unexpected success
but do not prove that a failure has the intended cause, so retain the initial
failure audit as part of the review handoff.

Review exception for demonstrated intermittent concurrency failures: retain real
concurrency and use per-case `xfail(strict=False)` markers. A successful
schedule is not evidence that the race is fixed. Do not reduce worker counts to
make these tests pass.

Run the resulting test selection normally and confirm only the documented
failures are expected. Present T0 for review before the mechanical changes.
Commit or land it only with the user's direction. Each subsequent implementation
change removes the markers for cases it fixes and reruns the complete
assertions. Add further regressions with their implementation when extraction
was not possible or new behavior is discovered; T0 is not a reason to stop
adding tests.

### M1: Rename the runtime class

Rename `literal.Guarantee` to `literal.Fanout` and update all references in
runtime tests, code-generation templates, generated expectations, and examples.
Keep fields, construction, and publication behavior unchanged. Do not rename the
Define concept Guarantee or compiler data types representing Guarantees. Do not
retain an alias for the previous runtime class name.

### M2: Rename the runtime method

Rename `Fanout.publish` to `Fanout.run` and update its call sites and associated
documentation. Preserve its arguments and method body. This does not rename
language-level Guarantee publication or change when it occurs.

### M3: Move the scheduler argument to construction

Store the scheduler supplied when constructing each fanout and remove the
scheduler argument from `run`. Update generated construction and tests together.
Check every call site to confirm it uses the same scheduler for the lifetime of
that fanout; a reachable exception makes that part non-mechanical and requires
separate treatment.

Preserve per-call consumer arguments, their ordering relative to registered
consumers, and synchronous initialization before consumer release. Do not
simultaneously change consumer ownership, generated execution construction
timing, or class representation beyond what this API migration requires.

### M4: Change the scheduler calling convention

Change `continue_with(methods)` to `continue_with(*methods)` and update every
caller, override, test, and generated invocation. Keep task evaluation order,
task order, and the policy of scheduling all but the final task unchanged. This
change does not move work between scheduling and synchronous execution.

### M5: Use the scheduler helper for generated fanouts

Immediately after M4, replace generated sequences that submit every continuation
except the last and call the last directly with one `continue_with` invocation.
Use one shared rendering helper at every applicable generation site, including
Action Fragments, Binding Hole fanouts, and entry-point continuations:

- Zero continuations: emit no invocation.
- One continuation: emit a direct method call.
- Multiple continuations: pass the bound methods to `continue_with` in their
  existing order.

For example, replace:

```python
self.scheduler.submit(self.first)
self.scheduler.submit(self.second)
self.third()
```

with:

```python
self.scheduler.continue_with(self.first, self.second, self.third)
```

Keep initialization, Join checks, and other synchronous prerequisite work before
the fanout. Do not turn arbitrary sequences of synchronous calls into concurrent
work, change an all-submitted sequence into a final direct call, or bypass
`Fanout.run` where its initialization and registered consumers are required.
Confirm that every bound method is already available before the first task is
submitted: evaluating all arguments before submission must not depend on work
performed by a submitted continuation.

Remove the superseded per-method rendering helper when it has no consumers.
Update templates, examples, and generated expectations in this change. Verify
zero, one, and multiple continuations, including tracing generation, and confirm
unchanged task order, Join arrivals, and Particle Operation dependencies.

### M6: Extract common operation naming

Extract the existing Particle Operation name calculation from fragment naming
into the shared helper needed by later fanout naming. Keep allocator calls,
allocation order, collision handling, and generated identifiers unchanged. There
should be no generated-source difference for this extraction. Do not introduce
destruction fanout names yet.

### S1: Verify Destructors per particle

Index verified Destructor qualities by the particle's position relative to the
Destruction Contract's destroyed particle. Preserve this association during
propagation. Verification for a parent particle must not suppress verification
for a child particle assigned the same Destructor.

Include regressions for the same Destructor on different particles and for
propagation through additional callers. Keep contribution ordering and runtime
connections unchanged. Adapt the fix to the baseline representation rather than
importing the entire new destruction model.

### S2: Discover callees of contributed Destructors

Use the ordinary Action Execution discovery path for contributed Destructors
after the required destroying Action Execution is available. Discover their
ordinary callees and further destruction contributions as well as their own
Particle Operations.

Include a real Define-source regression where a contributed Destructor calls an
action that destroys a child with another Destructor. Preserve the existing
binding and destruction representation in this change. Check that repeated
executions remain distinct and that traversal does not repeatedly expand the
same execution unnecessarily.

### S3: Correct child-operation dependency information

Review the tracker, Guarantee propagation, and dependency correction together:

- Preserve relevant child operations independently of visible occupancy
  Guarantees, including positions whose final state is empty.
- Make this information available where later callers apply the Empty Rule,
  without broadening the visibility of interface occupancy Guarantees.
- Exclude earlier child operations superseded by a parent Move, including after
  several Moves have changed the applicable position names.
- Apply Move Correction through dependencies between guaranteed operations,
  including dependencies through intervening Action Executions.
- Include the traversal caching and pruning required to avoid expanding
  unrelated transitive call graphs. Consider both time and memory growth.

Use specification-derived complete dependency expectations and real source cases
for each behavior. Remove only the expected failures this change fixes. Keep the
destruction contribution representation and runtime connections intact.

### S4: Unify initialization planning and generation

Implement one end-to-end initialization design for existing consumers:

- Represent execution construction, Join assignments, Guarantee registrations,
  and post-initialization work through `InitPlan` instead of parallel
  special-purpose fields and structures.
- Locate initialization through arbitrary execution paths, including execution
  construction performed by Binding Holes and operation callbacks.
- Use the same location mechanism for Join assignments and Guarantee
  registrations. Preserve initialization before the first possible arrival.
- Render these plans directly in Python, removing renderer-side regrouping and
  special deferred-registration representations.
- Generate imports from the Position expressions actually emitted at retention
  sites rather than from member declarations that only use `literal.Position`.
- Keep runtime fanout initialization synchronous before releasing consumers. The
  API-only changes to that runtime are already complete in M1 through M4.
- Reproduce the independent-initialization race recorded by T0. Remove its
  non-strict expected-failure markers as soon as initialization is safe; verify
  the affected programs with repeated multi-worker execution.

Keep any change to consumer storage or lifetime in this behavioral review, not
in a mechanical migration. In particular, changing per-call consumers into
persistent consumers requires checking repeated execution and when referenced
objects exist. Preserve intrinsic successors as static where the design calls
for that distinction.

Use existing Guarantee registration and Join assignment as concrete consumers of
the new planning capabilities. Do not add destruction-specific configuration
deadlines or independent-initialization handling without an existing need;
otherwise implement those in S5. Do not remove Destruction Connections here.

Review the plan, naming, template context, and rendering changes together.
Representative examples should cover creation-time initialization, Binding Hole
initialization, and transitive Guarantee registration. Particle Operation
dependencies must remain unchanged except for an explicitly identified and
tested correctness fix required by this initialization design.

### S5: Implement caller-contributed destruction dependencies

Keep the remaining graph and runtime redesign in one review:

- Represent position state immediately before destruction explicitly and use
  shared resolution for Requirement and Action Parent bindings in both
  full-graph resolution and code generation.
- Preserve complete execution paths to callee Destroys.
- Replace ordered contribution chains and first/completion-operation bookkeeping
  with individual Particle Operations and their DLP 44 dependencies. Parent
  names do not impose ordering on simultaneous Destroys.
- Resolve contributed Destructor dependencies, including Move Rule Fill
  Dependencies already satisfied through other prerequisites. Retain metadata
  required for initialization proofs even when it causes no runtime arrival.
- Plan caller-specific additions and removals of fanout consumers and the
  corresponding Join assignments without changing a callee's generated code.
- Place configuration after all referenced Action Executions exist and before
  the relevant consumers are released. Cover independent initialization events
  in both orders, multiple configuration sites, and transitive callers.
- Preserve unrelated consumers, static intrinsic successors, and fresh mutable
  state for each repeated Action Execution.
- Remove Destruction Connections, their specialized tracing support, and all
  superseded graph, planning, and rendering machinery as part of the
  replacement.

Do not temporarily adapt the old runtime to the new destruction representation
solely to create another review boundary. The reviewer should be able to follow
the actual dependencies from graph resolution through planning to execution.

Cover caller-known children and Destructors, diamonds, repeated executions,
later contributions to previously contributed destruction, callee independence,
and initialization after local Moves as well as Guarantees and Binding Holes.
Remove the remaining relevant expected failures only when the cases pass.

## Validation and review handoff

For each mechanical change, document the exact transformation rule. Verify that
the complete diff follows it, including generated artifacts. Existing runtime
and code-generation tests still run: near-zero review cost does not mean no
validation. Scheduling dependencies and execution behavior must be unchanged.

For each substantive change, provide the invariant being changed or preserved,
the focused regression cases, and a reading order. Derive graph expectations
from the specification before inspecting implementation results. Assert complete
diagnostics and dependencies; do not filter away unexpected results.

Follow applicable `AGENTS.md` instructions at every step:

- Run the repository formatter after edits and lint affected files.
- Run the relevant Bazel type-checking and focused test targets; update and
  check direct Python dependencies when imports or targets change.
- Regenerate generated expectations only for intentional changes, review their
  diffs, and run code-generation tests. Do not run regeneration concurrently
  with formatting.
- For significant code changes, finish with repository-wide coverage and the
  required coverage analysis. Inspect changed production branches; do not run an
  additional full test suite immediately beside the coverage run.
- At S5 completion, also require callee-independence tests and repeated tracing
  runs to pass, with runtime dependencies matching the resolved Operation Graph.

Each handoff identifies representative generated examples but includes the
complete artifact changes. Report pre-existing coverage gaps accurately rather
than treating a successful coverage run as proof of complete branch coverage.

If an allegedly preparatory change requires the new destruction semantics to be
useful or correct, move that portion to S5 rather than inventing transitional
machinery. Record any revised boundary in this plan before implementing it.
