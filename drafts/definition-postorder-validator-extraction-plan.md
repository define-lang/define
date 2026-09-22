# Definition postorder validator extraction plan

Split
`define/compiler/validator/reference_graph/definition_postorder_validator.py`
into focused components while preserving behavior, diagnostic ordering, and
code-generation input.

Implement the three extractions sequentially. After each extraction, complete
validation and present the changes for review. Stop until the user approves
continuing to the next extraction. Do not commit unless requested.

## 1. Extract DestructionContractValidator

- Create `destruction_contract_validator.py` in the reference graph package.
- Move `_check_destruction_contracts` through `_resolve_destructor_requirement`,
  along with `_ResolvedRequirement` and `_DestructionContractInCaller`.
- Give the component explicit dependencies: the current definition, definition
  results, validation state, and particle tracker.
- Have its public operation return diagnostics, propagated Destruction
  Contracts, and destruction connections. Keep overall result accumulation in
  `ActionPostorderValidator`.
- Preserve Child State sharing, propagation history, traversal order, and
  existing allocation optimizations.
- Keep direct destruction and Destructor execution orchestration in
  `ActionPostorderValidator`.
- Complete the validation checklist below and stop for review before
  extraction 2.

## 2. Extract ChainedNameValidator

- Create `chained_name_validator.py` in the reference graph package.
- Move `_validate_chained_name` through `_emit_chain_after_action_diagnostic`.
- Give the component definition results and the particle tracker; pass the scope
  and chained name to its validation operation.
- Keep constraint-use tracking in `ActionPostorderValidator`, immediately before
  invoking chained-name validation.
- Preserve diagnostics and tracker error marking, including behavior when
  definitions failed to load.
- Complete the validation checklist below and stop for review before
  extraction 3.

## 3. Extract PositionQualityResolver

- Create `position_quality_resolver.py` in the reference graph package.
- Move `_get_direct_required_qualities`, `_get_transitive_required_qualities`,
  `_build_quality_assignments`, and `_local_definition_cache_key`.
- Give the component the current Action Definition, definition results, and
  validation state; pass scope and Position to resolution operations.
- Update consumers in `ActionPostorderValidator` to use the resolver.
- Preserve Quality assignment order, cache keys, shared caching, and
  unresolved-definition behavior. Keep the shared cache in
  `ReferenceGraphValidationState`.
- Complete the validation checklist below and stop for final review.

## Design constraints

- Use composition with explicit dependencies. Do not pass the whole validator to
  extracted components or distribute its methods across mixins.
- Keep statement processing, triggering Actions, direct destruction, and final
  contract assembly coordinated by `ActionPostorderValidator`.
- Preserve sequencing dependencies, including capturing Child State before
  running Destructors and changing particle state.
- Preserve existing comments and remove superseded methods without adding
  forwarding wrappers.
- Preserve computational complexity and shared data structures; avoid copying
  tracker state or accumulated contracts as part of extraction.

## Validation and review checklist for each extraction

1. Add the manually maintained Bazel target in alphabetical order with narrow
   visibility and direct dependencies. Update consumer dependencies and the
   applicable `pyright_test` dependencies.
2. Before running local Python, generate the local development environment:
   `bazelisk run --noshow_progress --ui_event_filters=-info //tools:setup_local_dev`.
3. Check changed Python imports and targets with
   `uv run tools/check_python_deps.py <changed files>`.
4. Run the repository formatter:
   `bazelisk run --noshow_progress --ui_event_filters=-info //tools:format`.
5. Run relevant Bazel lint and type checks. Use existing behavior tests, adding
   targeted tests only where needed to verify a meaningful coverage gap.
6. Use repository-wide coverage for final test validation:
   `bazelisk coverage --noshow_progress --ui_event_filters=-info --combined_report=lcov //...`.
   Do not also run the full test suite immediately before or after coverage.
7. Run coverage analysis after coverage:
   `bazelisk run --noshow_progress --ui_event_filters=-info //tools:analyze_coverage`.
   Inspect the combined report for coverage of moved or changed production
   branches, excluding unreachable defensive checks and code only needed for
   type narrowing.
8. Run the required validator fuzz test explicitly:
   `bazelisk test --noshow_progress --ui_event_filters=-info //define/compiler:driver_fuzz_test`.
9. Review the diff for behavior changes, diagnostic ordering, code-generation
   input, and unintended edits. Present the new API, dependency boundaries,
   validation results, and any unresolved concerns for user review.

Run each Bazel command outside the Codex sandbox, with that invocation as the
entire shell command, according to the repository instructions.
