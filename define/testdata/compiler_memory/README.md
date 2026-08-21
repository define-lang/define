# Compiler memory testdata

`guarantee_expansion.dfn` is a dense layered action graph used by
`//define/compiler:memory_integration_test`. Its possible Action Execution paths
grow exponentially with the number of layers, exercising lazy resolution of
nested Action Guarantee Binding Holes along with Position Requirements,
Destruction Contracts, and destructor verification.

Regenerate it from the repository root with:

```sh
bazelisk run --noshow_progress --ui_event_filters=-info \
  //tools/generators:generate_action_graph_source -- \
  --output define/testdata/compiler_memory/guarantee_expansion.dfn \
  --layers 20 \
  --width 10 \
  --fan-out 10 \
  --destructor-fraction 0.5
```

The 20-layer, width-10, fan-out-10 configuration was selected by measuring the
real compiler. It raised peak RSS from the approximately 77 MiB process baseline
to approximately 99 MiB while still completing in under one second on the
calibration machine. The destructor fraction is the generator's default, so half
of the generated actions also exercise destruction processing.
