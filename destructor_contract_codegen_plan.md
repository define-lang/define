# Destructor Contract Destructor Codegen Plan

## Status

Checkpoint 1 is committed. The contributed-destruction recording refactor is
implemented and validated, and is awaiting review. The resolved-execution
refactor will have its own checkpoint and commit before Stage 2 begins. Stages 2
and 3 remain planned.

Each implementation stage must produce behavior visible from a real Define
project in generated code or an operation trace. A behavior-preserving refactor
is appropriate only when it improves code used by the implementation. Stop for
review before committing each stage.

## Goal

Generate and run Destructors learned through Destruction Contracts as though the
original destroying action had known about them. Preserve the specification
rules for Destructor verification, Automatic Action Requirements, Destructor
effects, operation ordering, safe concurrency, and modular per-action
generation.

## Semantic Model

A Destruction Contract does not move destruction to the caller that verifies it.
The caller contributes newly known Destructor work to the original Destruction
Fact:

- The original destroying action owns the Destruction Fact and its cascade
  Destroy operations.
- The first caller that knows the Destructor assignment and every required Child
  State verifies and contributes that Destructor.
- The Destructor action supplies its own Operation Graph behavior.
- The original destroying Action Execution activates the contributed Destructor
  and remains its runtime trace parent.
- Intermediate actions preserve the Destruction Fact and contribution identity
  when the contribution crosses more than one call boundary.

For `/test -> /middle -> /destroyer`, a Destructor known only by `/test` must
therefore trace as `/test -> /middle -> /destroyer -> /destructor`.

Directly known Destructors remain ordinary Action Executions of the destroying
action. Caller-contributed and directly known Destructors may use different
generated control flow, but both must obey the same specification Operation
Graph dependencies. Assignment order alone does not serialize independent
Destructor bodies.

## Project Invariants

- Runtime ordering must represent the dependencies required by the
  specification's Particle Operation Dependency Graph rules. Do not add a join
  or dependency merely to simplify runtime implementation.
- Independent Destructor work and independent cascade work may execute in
  parallel or be safely reordered.
- Adding a caller, including one that contributes a Destructor, must never
  change any callee's generated code.
- Directly known Destructor generation must remain unchanged unless a separate
  source-backed correctness case requires a change.
- Code generation remains modular. No codegen pass discovers callers or builds a
  whole-program Operation Graph.
- Work and retained data must scale with the relevant Action Executions,
  Destructor contributions, requirements, and destruction positions. Avoid
  repeated whole-graph scans and fan-out-sensitive linear lookups.
- Each Destructor is verified independently and contributed exactly once.

## Stage 1: Direct-Caller, Requirement-Free Destructors

Support the smallest complete case: a direct caller knows a Destructor with no
Automatic Action Requirements or runtime Action state, and its direct callee
destroys the particle.

### Intended Behavior

- Activate the contributed Destructor at the Destroy selected by the original
  Destruction Fact and destruction position.
- Give the resulting Destructor Action Execution the original destroying Action
  Execution as its runtime trace parent.
- Preserve the Destructor action's ordinary Operation Graph behavior and the
  concurrency of independent operations.
- Support multiple caller-contributed Destructors and multiple independent
  operation chains in one contributed Destructor.
- Preserve independence when two callers reach the same destroyer and know
  Destructors in different assignment orders.
- Keep the callee's generated code byte-for-byte identical with and without a
  contributing caller.
- Keep directly known Destructor generated code unchanged.

### Usable Result

A real generated Define program runs a direct-caller Destruction Contract
Destructor at the callee's destruction moment, with the correct runtime parent
and no special test harness behavior.

### Checkpoint 1

Stop before committing. Report the semantic ownership, generated control flow,
source-backed behavior, callee independence, directly known Destructor
regression coverage, and all affected quality checks.

Commit Checkpoint 1 only after approval.

## Contributed-Destruction Recording Refactor Checkpoint

After committing Checkpoint 1, split the overly long operation-graph recording
of caller-contributed destruction into cohesive responsibilities. Preserve its
Operation Graphs, generated code, and operation traces.

Stop for review before committing the refactor. Report the resulting ownership
boundaries and all affected quality checks. Commit it only after approval, then
begin the resolved-execution refactor.

## Resolved-Execution Refactor Checkpoint

After committing the contributed-destruction recording refactor and before
beginning Stage 2, simplify the resolved operation graph. It currently retains
facts about triggered Action Executions that can be derived from their call
relationship, while its lookup from a caller and direct Action Execution to the
realized callee scales linearly with caller fan-out. Give each fact one source
of truth and keep realized-callee lookup efficient at project scale. Preserve
generated code and operation traces.

Stop for review before committing the refactor. Report the simplified ownership
model, scalability of the realized-callee lookup, unchanged generated code and
traces, and all affected quality checks. Commit it only after approval, then
begin Stage 2.

## Stage 2: Direct-Caller Destruction-Time Dependencies

Extend direct-caller contributions to Destructors whose execution depends on
runtime Action state or Automatic Action Requirements.

### Intended Behavior

- Preserve runtime Action state needed by the contributed Destructor.
- Resolve each Automatic Action Requirement against the cumulative Child State
  immediately before destruction, including caller operations, callee
  Guarantees, caller-contributed Destroys, and default-empty state.
- Support Destructors on caller-contributed child particles.
- Make only the Destroy operations required by the specification wait for
  relevant Destructor completion.
- Compose Destructor contributions with caller-contributed Destroy operations
  for the same Destruction Fact.
- Preserve trace relationships for ordinary Action Executions triggered by a
  contributed Destructor.
- Cover explicit and automatic destruction cascades.

The following source-backed cases should become ordinary passing tests:

- `auto_destruction_of_child_with_caller_known_destructor`
- `caller_contributed_child_destructor_depends_on_callee_guarantee`
- `diamond_callers_serialize_added_destructor_around_known_destructor`

### Usable Result

Generated programs run direct-caller Destructors that depend jointly on caller
state and callee Guarantees, including Destructors on contributed child
particles, with only the dependencies required by the Operation Graph.

### Checkpoint 2

Stop before committing. Report source-backed requirement delivery and Destroy
ordering, concurrency regressions, tracing behavior, and all affected quality
checks.

## Stage 3: Contributions Across Multiple Callers

Extend completed Destructor contribution semantics through intermediate callers.

### Intended Behavior

- Contribute a Destructor from the first action that can verify its assignment
  and Automatic Action Requirements.
- Preserve the original Destruction Fact, destruction position, and destroying
  Action Execution identity across every call boundary.
- Activate each contributed Destructor exactly once.
- Compose contributions made at different call depths with each other and with
  caller-contributed Destroy operations.
- Preserve modular generation and callee independence at every depth.

The following source-backed cases should become ordinary passing tests:

- `destructor_known_only_two_callers_up`
- `destructor_with_children_known_only_two_callers_up`

### Usable Result

Generated programs propagate Destruction Contract Destructor behavior across
arbitrary call depth while preserving the original destroyer's runtime identity
and specification-permitted concurrency.

### Checkpoint 3

Stop before committing. Report a source-backed multi-caller execution, trace
parentage, removal of the remaining expected failures and exclusions, callee
independence, and repository-wide validation.

## Final Acceptance

The project is complete when:

- All targeted Operation Graph and tracing expected failures and codegen
  exclusions are removed.
- Contract-learned and directly known Destructors obey the same specification
  semantics.
- Traces identify the original destroying Action Execution as the contributed
  Destructor's parent at every call depth.
- Automatic Action Requirements use cumulative pre-destruction Child State.
- Relevant Destructor completion gates only the applicable Destroy operations.
- Independent operations and Destructors retain specification-permitted
  concurrency.
- Adding or removing a caller leaves every callee's generated code unchanged.
- No superseded caller-triggered or whole-program generation path remains.
- Formatting, dependency checks, lint, type checking, codegen tests, tracing
  tests, the full build, repository-wide coverage, and coverage analysis pass.
- Every implementation stage is reviewed in the working tree before commit.
