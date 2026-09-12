# Remove DLP 44 from the compiler

## Goal and scope

Remove parallel Particle Operation execution and dependency-graph construction
from the compiler. Keep a working literal Python compiler, static validation,
and operation tracing. Tracing will report a serial list of operations actually
performed, checked against explicit expectations from real Define programs.

Prefer deletion-only review changes before modifications. When active consumers
prevent deletion, replace those consumers first and submit the resulting bulk
deletion separately. Each numbered change must leave the compiler working. These
are review boundaries, not instructions to commit: do not commit or push without
approval. Writing this plan and preserving the C experiments do not authorize
executing the removal.

After completing and validating each numbered step, stop and summarize the
changes and validation results for the user's review. Wait for explicit approval
before starting the next step. Approval to continue does not authorize
committing or pushing unless the user also requests it.

Do not implement symbolic operations, optimize away the serial program, retain a
speculative future scheduler, or replace graph execution with a topological sort
of the same graph. Leave the spec, DLP 44, and proofs untouched unless
separately authorized. Preserve unrelated working-tree changes.

## Model assignments and handoffs

Use Sol for steps 1–2, 4, and 6–8. Use Astra for steps 3 and 5. Have Astra
independently review the destruction-contract and validator changes after step
7, and perform the final independent review after step 8.

At each review pause, identify the model assigned to the next step or review. If
a switch is needed, explicitly remind the user to switch before continuing. Wait
for confirmation of the switch or an explicit override. Do not silently continue
under the current model or spawn an agent to bypass the handoff.

- After step 2: switch to Astra for step 3.
- After step 3: switch to Sol for step 4.
- After step 4: switch to Astra for step 5.
- After step 5: switch to Sol for steps 6–7, retaining the separate review pause
  after each step.
- After step 7: switch to Astra for an independent review of the
  destruction-contract and validator changes before step 8. Fix issues found and
  report the results for approval, then remind the user to switch to Sol for
  step 8.
- After step 8: switch to Astra for the final independent review. Fix issues
  found and report the results for approval.

## Preparation

- Inventory production consumers, build targets, test fixtures, and graph-only
  interfaces before deleting them. A graph-related name does not prove that a
  file serves only concurrency.
- Record the current build/test baseline and existing xfails. Do not mask new
  failures with broad xfails.
- Preserve the literal C directory, including current nonignored untracked files
  and working-tree edits, in `~/projects/research/literal-c/`. Verify file names
  and bytes before deleting anything from this repository. Keep the existing
  compiler archive unchanged. Treat the separate C copy as an archive, not a
  working backend that must build in the research repository.
- Identify conflicts between existing graph-execution design instructions and
  the replacement. Update implementation design documents with the relevant
  implementation change. If serial execution requires a language decision not
  already settled, explain the concrete case to the user before proceeding.

## 1. Delete standalone research artifacts

Remove the experimental algorithms and research documents under
`define/compiler/validator/reference_graph/operation_graph/design/`, the
preserved literal C experiments, and their dedicated build targets, after
confirming that production does not consume them. Check references before
deleting documentation or fixtures shared with other features.

This change does not alter production execution or validation.

## 2. Delete exclusively concurrency-related tests

Remove tests whose only purpose is checking dependency edges, parallel
schedules, or transitive minimality, including abandoned experimental graph
expectations. Retain execution and tracing coverage until its replacement is
ready; deleting obsolete graph tests is not permission to remove all tests of
the code being replaced.

Graph integration fixtures are also used by code generation and execution tests.
Preserve these shared sources. Where a case also checks meaningful validation,
triggering, or destruction behavior, retain or migrate that coverage before
deleting its only test. Keep fixture migrations separate from bulk deletion
where practical, using `git mv` for moves.

## 3. Separate semantic information from graph information

The [former Step 3 sub-plan](dlp44_step3_subplan.md) is superseded. Codegen will
walk the full AST; do not introduce a separate Particle Operation recording
representation. Design destruction-contract handling separately when needed.

Inspect `operation_graph_model.py`, `particle_tracker.py`,
`definition_postorder_validator.py`, and `action_contract.py`. Separate facts
needed for validation and execution from dependency/scheduling bookkeeping.

Preserve requirements, guarantees, action executions, particle identities, and
verified destruction-contract information actually required by consumers. Do not
just rename the operation graph or retain its dependency fields in a new
representation. Design the semantic representation around the serial codegen and
validator's actual needs.

The existing backend should still work after this change, with no intentional
execution change. Avoid introducing an alternate general-purpose framework.

## 4. Replace dependency tracing with operation tracing

Change `define/runtime/tracing.py` and the generated-program test interface to
record an ordered list of successfully performed operations. Retain sufficient
action-execution and operation identity to distinguish repeated invocations and
repeated operations. Keep tracing optional.

Remove dependency reconstruction, dependency JSON plumbing, and assertions that
compare runtime edges with compiler edges. Expected traces must be written from
the Define source's intended behavior, not generated from the compiler's own
plan or copied blindly from observed execution.

While the old concurrent backend remains active, its observed order may vary. Do
not assert a deterministic serial order prematurely or sort the trace to make it
pass. Preserve applicable execution checks in this intermediate change; add
exact serial trace assertions with change 5. If this separation cannot retain
useful test coverage, include the trace switch in change 5.

## 5. Design destruction contracts and switch to serial code generation

### Simplify destruction-contract passing first

Before choosing the serial Python representation, trace how verified contracts
reach the action that performs destruction today. Distinguish information needed
to identify and execute destructors from machinery needed only to schedule them
concurrently.

We may still need statically generated contract arguments passed from caller to
callee, including through intermediate actions. Do not replace that with runtime
discovery merely because the scheduler is gone. Consider direct generated
functions or methods, with explicit arguments for the required particles,
positions, and caller-supplied destruction behavior. Use small structured values
only where the actual consumers need them. Compare these representations using
readable generated Python for real cases, favoring code and interface simplicity
over preserving the existing architecture.

Work through at least these cases before choosing the representation:

- A destructor fully known to the destroying action.
- A child or destructor known only to its caller, or several callers away.
- Contributions from multiple callers, including implied/interface positions.
- A destructor that moves particles or triggers another action.
- Automatic destruction and destruction initiated by a destructor.
- Repeated executions of the same action with different contract information.
- Multiple paths identifying the same destructor, without duplicate execution.

Specify where contracts are constructed, how they are forwarded, how their
references identify the intended particles, and where destruction consumes them.
Preserve modular generated callees rather than flattening the whole program or
specializing every callee for every caller. Do not propagate whole copies of
transitive action plans or use recursive host-language calls without checking
the compiler's expected execution depth.

Use existing normal `define/testdata` cases and add missing cases through the
normal mechanisms. Demonstrate the chosen representation with expected generated
Python and actual execution traces. The representation should not need joins,
fanouts, readiness counters, runtime guarantee publications, or general
dependency connections merely to pass a contract.

### Switch execution

Replace graph-driven fragments with serial execution of operations and triggered
actions using the semantic information from change 3. Implement the chosen
contract representation as part of this switch. A single-threaded version of the
current scheduler is not the final design.

Preserve constructors, destructors, retriggering, quality assignment, particle
identity across Moves, and child-position behavior. Simultaneous Transitive
Destruction must not accidentally become a new rule that children are always
destroyed before parents. Preserve the selected particles and the access needed
by destructors, including when those destructors move particles. Distinguish the
logical destruction behavior from the serial order chosen to execute it.

Add exact ordered trace expectations and regenerate/review intentionally changed
generated-code expectations. Revisit existing execution xfails: dependency-shape
failures may disappear, but missing destructor execution must not be dismissed
as an obsolete concurrency concern.

This is the main behavioral change. Split preparatory refactors where they can
stand independently, but do not switch the production backend until all
supported execution features have a working replacement. Do not leave a
permanent old/new backend selection mechanism.

## 6. Delete unused execution machinery

After the switch, remove unused action plans, scheduling-only resolvers,
fragments, joins, fanouts, binding-hole code, runtime guarantee signals, thread
scheduling, and their dedicated templates and tests.

Use the destruction-contract consumer inventory from change 5 to determine which
old connections can be deleted. Preserve the simplified static contract
arguments and any essential invocation mechanism; do not delete contract
semantics because their previous representation was scheduling machinery. Keep
static Action Guarantees distinct from runtime completion signals.

Make this a predominantly deletion-only change, separate from the execution
switch, so that the removed machinery is easy to review.

## 7. Remove graph construction from validation and compiler results

Delete the remaining graph builders, dependency rules, graph-only models,
renderers, labelers, and dedicated tests. Remove graph bookkeeping from the
particle tracker and graph fields from validator results and driver/codegen
APIs. Serial code generation must consume the semantic information directly.

Verify that destruction-contract validation and static contract propagation
still work without graph nodes or execution dependencies standing in for
semantic facts. Remove unused fields rather than leaving empty dependency
collections or compatibility wrappers. Validate requirements, guarantees,
invalid-source diagnostics, and caller-known destruction cases again.

## 8. Final cleanup and validation

Remove stale build dependencies, scheduler flags, graph-only test helpers,
profiling references, and implementation documentation. Update instructions that
mandate the removed graph execution design. Do not delete the language's
destruction semantics or alter the spec, proposal, or proofs as cleanup.

For each review change:

- Format and check affected build dependencies and Bazel type-check targets.
- Run applicable validation, generated-code, execution, and tracing tests.
- Check that expected source diagnostics are unchanged unless an independently
  understood bug is intentionally fixed.
- Review generated-code changes, rather than accepting regenerated files without
  inspection.
- Keep a record of what was removed, what behavior changed, and checks run.

Run parser/fuzz and validator regression coverage after changing validation
plumbing. Finish significant implementation work with repository-wide coverage
and coverage analysis, fixing uncovered changed production behavior through
normal integration tests. Coverage runs the tests; do not redundantly run the
entire test suite immediately before or after it.

The work is complete when the compiler validates and executes supported Define
programs serially, traces match explicit operation lists, contracts remain
statically expressible and correctly passed across actions, and no active
Particle Operation dependency graph or scheduler remains. No future symbolic
semantics or generic concurrency infrastructure is required for completion.
