# Step 3: Build Particle Operations alongside the Operation Graph

**Superseded:** Codegen will walk the full AST, including local position
definitions. Do not implement the separate `ParticleOperations` representation
or validator recording described below. Destruction-contract handling is
deferred for separate design. The former sub-plan is retained here for
reference.

This expands Step 3 of [the DLP 44 removal plan](dlp44_removal_plan.md). Use
Astra for these changes. Stop after each numbered change for review; wait for
explicit approval before starting the next. Commit and push only when requested.
Writing this sub-plan does not authorize implementation.

## Intended result

The validator does not need the Operation Graph to validate. It collects graph
information for codegen. Preserve that distinction with these per-action
structures:

- `ActionContract`: Position Requirements, Action Guarantees, Destruction
  Contracts, and references to callee contracts used in validation.
- `ParticleOperations`, in `particle_operations.py`: Particle Operations, the
  Action Executions they cause, and verified destruction information collected
  for codegen.
- `OperationGraph`, temporarily: dependency nodes, edges, binding holes, and
  scheduling relationships required by the existing backend.

Build the new representation alongside the existing graph, using the same
validation decisions. Populate it directly where the validator knows the facts;
do not translate graph nodes or reconstruct facts from dependency edges. Keep
the existing backend and its graph consumers working throughout this step.

New semantic records must not reference graph nodes or contain dependency
fields. Preserve distinct operation and execution occurrences and particle
identity across Moves. Share semantic facts by reference where practical, but do
not refactor the old graph's identity model merely to make both representations
use identical objects. Preserve modular callees and lazy contract propagation;
do not copy transitive callee operations or contracts into callers.

## 1. Record Particle Operations alongside graph construction

Introduce `ParticleOperations` in `particle_operations.py`, with Create, Move,
and Destroy records containing positions, source information, and distinct
occurrence identities. Populate and publish the per-action collection during
validation while continuing to build the existing graph. Include operations
already inferred by validation, such as automatic destruction. Add focused
expectations from real Define programs for this first increment.

## 2. Record Action Executions and triggering relationships

Add graph-independent Action Execution records identifying the callee and each
execution occurrence. Associate them with the operations that trigger them,
including constructors and retriggering. Reference callee information without
expanding its operations into the caller. Keep the existing graph's execution
records and consumers in place. Validate the new relationships using
source-based expectations.

## 3. Record verified destruction information

Record destruction facts, selected particles, verified destructor executions,
and requirement references needed by codegen. Preserve destruction-time state,
particle-specific verification, and caller contributions propagated through
intermediate actions. Obtain these facts from existing contract verification; do
not duplicate verification or record graph-specific first, predecessor, or
completion operations in the new structures.

Selecting particles for Simultaneous Transitive Destruction must remain distinct
from choosing their runtime execution order. Review the completeness of the
information without choosing Step 5's serial destruction order or runtime
calling convention.

## 4. Validate the complete representation and review the boundary

Review the published `ParticleOperations` against the actual needs of serial
codegen and operation tracing. Cover repeated operations and Action Executions,
Moves, constructors, automatic destruction, and caller-known destruction through
normal Define test cases. Expectations must describe the source's intended
behavior rather than reproduce the graph or copy observed execution.

Confirm that operation and execution identities support the labeler
functionality and coverage we are preserving. Leave the existing labeler and
backend consumers in place until their replacements are ready in the subsequent
main-plan steps. Audit that the new representation is independent of graph nodes
and dependency metadata. Retain graph-only `ActionContract` fields such as
`final_operations` while the old backend still needs them; remove them with the
old infrastructure rather than relocating them solely for this transition.

## Subsequent migration and deletion

After this sub-plan, continue with the main plan's review boundaries:

- Step 4 replaces dependency tracing with operation tracing, or combines that
  switch with Step 5 if needed to retain useful coverage.
- Step 5 designs static destruction-contract passing and develops the serial
  generator against `ParticleOperations`. Test it alongside the existing backend
  until supported behavior and tracing have a working replacement, then switch
  production codegen. Do not retain a permanent backend-selection mechanism.
- Steps 6 and 7 delete unused execution machinery and graph infrastructure,
  including graph-only contract fields and tracker bookkeeping. Keep bulk
  deletion separate from the backend switch.

## Validation and review

Each change includes its necessary consumer and BUILD updates, applicable design
documentation updates, formatting, dependency checks, and Bazel type checks. Run
affected validator, generated-code, execution, and tracing tests. Preserve
complete diagnostics, existing execution behavior, and generated Python; do not
regenerate expectations to conceal unintended changes.

Follow the main plan's parser/fuzz, regression coverage, and repository-wide
coverage requirements when validation plumbing or significant implementation
changes warrant them. Report the scope and validation at each review pause.

The overlap temporarily adds recording work and memory use. Keep records compact
and avoid a second complete particle tracker, duplicate validation, copied
particle-state snapshots, or a generic event framework. After this sub-plan is
complete and approved, the next main-plan step is Step 4, assigned to Sol.
