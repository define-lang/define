# Compiler memory testdata

The fixtures in this directory are used by
`//define/compiler:memory_integration_test`. Each one targets a different
dimension that could accidentally retain relationships per action or per
Particle Operation. They share the `mv:define-lang.org:compiler_memory` universe
declared in `.define/project/config.defcl`.

## Action Guarantee expansion

`guarantee_expansion.dfn` is a dense layered action graph. Its possible Action
Execution paths grow exponentially with the number of layers, exercising lazy
resolution of nested Action Guarantee Binding Holes along with Position
Requirements, Destruction Contracts, and destructor verification.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_action_graph_source -- \
  --output define/testdata/compiler_memory/guarantee_expansion.dfn \
  --layers 20 \
  --width 10 \
  --fan-out 10 \
  --destructor-fraction 0.5 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Deep Position Requirements

`deep_requirements.dfn` propagates Position Requirements through many
independent chains of callers. It guards against retaining caller state for
every transitive path or multiplying requirement state at each action.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_deep_pipeline_source -- \
  --output define/testdata/compiler_memory/deep_requirements.dfn \
  --pipelines 8 \
  --processing-stages 30 \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Destruction fragments

`destruction_fragments.dfn` propagates modular Destruction Contracts through
many callers, with repeated executions and shared child paths. It guards the
sparse lookup and merging of destruction contributions and occupied children.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_destruction_fragments_source -- \
  --output define/testdata/compiler_memory/destruction_fragments.dfn \
  --callers 4 \
  --call-depth 20 \
  --pass-through-actions 1 \
  --local-children 3 \
  --repetitions 2 \
  --shared-child-paths \
  --fqun-prefix mv:define-lang.org:compiler_memory
```

## Large operation volume

`large_operation_volume.dfn` places many syntactically varied Particle
Operations in one action. It covers parser and AST retention as well as state
that could accidentally be copied or retained for every Particle Operation.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_large_define_source -- \
  --output define/testdata/compiler_memory/large_operation_volume.dfn \
  --lines 2500 \
  --fqun mv:define-lang.org:compiler_memory:/test
```

## Operation dependencies

`operation_dependencies.dfn` combines Move chains, deep and wide position
shapes, independent Move branches, repeated action executions, and operations on
guaranteed positions. It guards against dense per-operation relationship tables
and copies of child-operation state.

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_operation_graph_source -- \
  --output define/testdata/compiler_memory/operation_dependencies.dfn \
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
