# Literal Code Generation

## Purpose

- Literal transpilation is a debugging, testing, and educational representation
  of Define. Generated source must make the relationship between Define source,
  compiler semantics, and execution easy to inspect.
- Prefer a direct, readable representation of Define semantics over an opaque
  optimization.

## Compilation Boundaries

- Codegen renders semantic decisions made by lower compiler layers. It must not
  rediscover, repair, or reinterpret operation dependencies.
- Generate each action modularly after its direct callees. Analysis for one
  action may inspect that action and direct-callee interfaces, but must not scan
  callers or analyze the complete reachable action call graph.
- Resolve guarantees lazily for the specific guarantee being consumed. Never
  flatten or eagerly expand a complete guarantee tree.

## Semantic Fidelity

- Preserve the operation graph's available parallelism, fan-outs, joins, Action
  Triggers, and guarantee publication timing. Do not serialize independent work
  merely to simplify generated code.
- Do not treat an Action Trigger as one atomic function call. Caller and callee
  work becomes available according to its operation-graph dependencies.
- When a Particle Operation causes an Action Trigger, generated code must
  immediately resolve and retain that specific Action object. It must not wait
  for the triggered action's other dependencies, because parallel Particle
  Operations may meanwhile move or destroy the particle through which the Action
  object is found.
- Preserve distinct dependency arrivals even when they invoke the same generated
  method.

## Names and Identity

- Generated names must be deterministic, source-readable, and unambiguous. You
  can use DLP 27 short names as appropriate.
- Retain operation nodes, `ActionTrigger` objects, fragments, and other semantic
  objects by direct reference during lowering.
- Do not invent identity with `id()`, enumeration indexes, node IDs, fragment
  IDs, or an object's index in another sequence.
- Represent generated position and action references with Python class objects,
  not string names.
