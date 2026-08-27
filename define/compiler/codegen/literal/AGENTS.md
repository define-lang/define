# Literal Code Generation

Before changing literal code generation, read
[the shared execution design](../../operation_graph_execution_design.md).

## Purpose

- Literal transpilation is a debugging, testing, and educational representation
  of Define. Generated source must make the relationship between Define source,
  compiler semantics, and execution easy to inspect.
- Prefer a direct, readable representation of Define semantics over an opaque
  optimization.
