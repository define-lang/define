# Literal C Codegen

The Literal C code generator has a slightly different purpose than our other
code generators. It is primarily an experimental system to determine what is the
maximum performance level we could get while still maintaining literal Define
semantics. It lets us test out hardware-level operations, scheduling patterns,
etc.

Current studies:

- [Scheduler and Join ADR](scheduler_and_join_adr.md) and its retained
  [benchmark](scheduler_and_join_benchmark.c)
- [Pointer-free static execution design](pointer_free_static_design.md) and its
  retained [benchmark](pointer_free_static_benchmark.c)
- [Configurable pointer-free reference implementation](pointer_free_static_example.c)
- [Literal generated examples](generated_examples), derived from existing
  Operation Graph fixtures
