# Regenerate compiler resource fixtures

Run these commands from the repository root.

## Action Guarantee expansion

Checks memory usage when shared action calls create many possible Action
Execution paths for guarantee propagation.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_action_graph_source -- \
  --output define/testdata/compiler_resources/guarantee_expansion.dfn \
  --layers 20 \
  --width 10 \
  --fan-out 10 \
  --destructor-fraction 0.5 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Deep Position Requirements

Checks memory usage when Position Requirements propagate through long chains of
callers.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_deep_pipeline_source -- \
  --output define/testdata/compiler_resources/deep_requirements.dfn \
  --pipelines 8 \
  --processing-stages 30 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Destruction Contracts

Checks memory usage when Destruction Contracts propagate through repeated calls
with shared child names.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_destruction_contracts_source -- \
  --output define/testdata/compiler_resources/destruction_contracts.dfn \
  --callers 4 \
  --call-depth 20 \
  --pass-through-actions 1 \
  --local-children 3 \
  --repetitions 2 \
  --shared-child-paths \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Large operation volume

Checks memory retained while parsing and validating many Particle Operations in
one action.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_large_define_source -- \
  --output define/testdata/compiler_resources/large_operation_volume.dfn \
  --lines 2500 \
  --fqun mv:define-lang.org:compiler_memory:/test
```

## Particle Operations

Checks memory usage while tracking particles through Move chains, repeated
action executions, and destruction.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_particle_operations_source -- \
  --output define/testdata/compiler_resources/particle_operations.dfn \
  --repetitions 12 \
  --move-chain-length 20 \
  --tree-depth 20 \
  --wide-children 28 \
  --pods 2 \
  --retriggers 2 \
  --independent-move-branches 96 \
  --independent-move-chain-length 96 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Many substantial actions

Checks validation and code-generation memory usage across many actions with
substantial bodies.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_action_codegen_source -- \
  --output define/testdata/compiler_resources/many_substantial_actions.dfn \
  --actions 650 \
  --chains-per-action 4 \
  --topology-groups 0 \
  --topology-width 1 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Wide destruction

Checks memory usage during Simultaneous Transitive Destruction with many child
Positions.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_action_codegen_source -- \
  --output define/testdata/compiler_resources/wide_destruction.dfn \
  --actions 0 \
  --chains-per-action 1 \
  --topology-groups 80 \
  --topology-width 40 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Many-file reference graph

Checks memory usage when loading and validating many files with shared global
references.

Remove `reference_graph_project/` before regenerating it; the generator requires
a new destination.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_reference_graph_project -- \
  --output define/testdata/compiler_resources/reference_graph_project \
  --modules 2000 \
  --layers 20 \
  --fan-out 3 \
  --utility-fraction 0.3 \
  --seed 7 \
  --universe-name mv:define-lang.org:compiler_memory
```

## Reference depth updates

Checks CPU growth from repeated reference-graph depth updates, comparing the
same dependency graph in adversarial and favorable reference orders.

Remove each destination directory before regenerating it.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_reference_graph_project -- \
  --output define/testdata/compiler_resources/reference_depth_updates_project \
  --shape depth-updates \
  --modules 16384

bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_reference_graph_project -- \
  --output define/testdata/compiler_resources/reference_depth_updates_control_project \
  --shape depth-updates \
  --modules 16384 \
  --reverse-references
```

## Pending Action Guarantees

Checks memory usage when many pending Action Guarantees coexist with destruction
of unrelated particles.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_pending_guarantees_source -- \
  --output define/testdata/compiler_resources/pending_guarantees.dfn \
  --pending-positions 512 \
  --destroyed-positions 512
```

## Quality Implications

Checks CPU growth as shared Quality Implications create exponentially many paths
through a linearly growing number of qualities.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_quality_implications_source -- \
  --output define/testdata/compiler_resources/quality_implications.dfn \
  --layers 32 --width 2 --fan-out 2 --assignments 1

bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_quality_implications_source -- \
  --output define/testdata/compiler_resources/quality_implications_control.dfn \
  --layers 12 --width 2 --fan-out 2 --assignments 1
```

## Pending Action Guarantee CPU growth

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_pending_guarantees_source -- \
  --output define/testdata/compiler_resources/pending_guarantees_growth_control.dfn \
  --pending-positions 1024 --destroyed-positions 102

bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_pending_guarantees_source -- \
  --output define/testdata/compiler_resources/pending_guarantees_growth.dfn \
  --pending-positions 8192 --destroyed-positions 819
```
