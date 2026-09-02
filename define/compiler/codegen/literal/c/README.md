# Literal C Codegen

The Literal C code generator has a slightly different purpose than our other
code generators. It is primarily an experimental system to determine what is the
maximum performance level we could get while still maintaining literal Define
semantics. It lets us test out hardware-level operations, scheduling patterns,
etc.

Current studies:

- [Scheduler and Join ADR](scheduler_and_join_adr.md) and its retained
  [benchmark](scheduler_and_join_benchmark.c)
- [Thread scheduler and runtime benchmark](thread_runtime_benchmark.c), covering
  direct serial execution, fresh and persistent pthread workers, spinning, futex
  parking, conditional and unconditional wakes, generated publication and
  completion specializations, and rejected raw-clone comparison controls
- [Pointer-free static execution design](pointer_free_static_design.md) and its
  retained [benchmark](pointer_free_static_benchmark.c)
- [Advanced literal C experiments](advanced_literal_c_experiments.md), covering
  fused Join updates, hybrid scheduling regions, large generated code, and
  overlapping Action Executions
- [Configurable pointer-free reference implementation](pointer_free_static_example.c)
- [Literal generated examples](generated_examples), derived from existing
  Operation Graph fixtures
