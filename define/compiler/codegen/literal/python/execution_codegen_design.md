# Literal Python Execution Codegen Design

This document records the literal Python representation of the shared
[Operation Graph execution design](../../../operation_graph_execution_design.md).
The [Define-source and generated-Python examples](action_execution_examples.md)
are canonical. Before intentionally changing generated source shown there,
update the affected example as part of the design change so the intended form is
reviewed before implementation diverges.

## Rendering responsibilities

- Codegen allocates names and renders the complete Action Plan. It does not
  infer dependencies, discover consumers, choose join ownership, or repair the
  plan.
- Jinja templates own generated Python syntax. Python generator modules provide
  structured semantic data and allocated identifiers rather than Python source
  fragments.
- Generated source remains a direct, readable representation of Define semantics
  and the resolved Operation Graph.

## Action Executions

- An Action Execution's `__init__` constructs runtime state only. It never
  performs a Particle Operation or releases scheduled work.
- Immediately retain the specific Action object when a Particle Operation makes
  an Action Execution available. Do not look it up later after another Particle
  Operation may have moved or destroyed its particle.
- Each Action Execution constructs its own fresh Guarantees. Parent executions
  do not construct, inject, or reuse child Guarantees trees.
- Construct caller-specific Destruction Connections with the Action Execution
  that receives them, when the particle providing that Action Execution is
  available.

## Methods, fanout, and joins

- Every Binding Hole with consumers is a stable callee method, including when
  its current fanout has one consumer. The method owns its complete
  callee-defined fanout of Action Fragments and direct-callee Binding Holes.
- Every Action Parent Binding Hole with consumers is named
  `on_action_parent_occupied`.
- A fanout schedules zero-argument Action Fragment or Binding Hole methods and
  runs one branch on the current thread.
- Consecutive Particle Operations in one Action Fragment remain together. Add a
  separate generated method only for a stable Binding Hole, scheduling, a join,
  reuse, caller-specific work, or another actual runtime role.
- Emit caller-owned work preceding a callee Binding Hole inline unless it needs
  one of those runtime roles.
- Never create a one-arrival `Join`. Assign `literal.NO_JOIN` when a reusable
  join site has one resolved predecessor.
- Code following a direct method call may rely on its Particle Operation only
  when the call is statically guaranteed to perform that operation. Work
  following a multi-arrival join is released by the operation's Guarantee.

## Guarantees

- `Guarantee.inits` synchronously initializes ordinary and Destructor Action
  Executions; it does not trigger them. Every initializer completes before any
  ordinary consumer is released.
- Guarantee consumers are actual Action Fragment or Binding Hole tasks. Do not
  add a method whose only role is to dispatch a predetermined consumer list.
- Register a propagated Guarantee consumer once on the terminal Guarantee
  through the realized Action Execution path, before releasing work capable of
  publishing that Guarantee.
- Install a consumer on a transitive Guarantee only when Guarantee resolution
  has already identified the Guarantee and its Action Fragment. Codegen does not
  perform another transitive walk.
- Use a Guarantee consumer when another Action Execution must observe the
  Particle Operation that actually completes, such as an operation reached
  through a multi-arrival join. Do not replace an intrinsic direct release with
  a dynamic callback.

## Destruction

- A fanout schedules zero-argument Action Fragment or Binding Hole methods,
  including Destroy fragment methods.
- Every Destroy that accepts Destruction Connections has a zero-argument
  fragment method that calls `literal.continue_destruction`. A predecessor calls
  that method directly, and a fanout can schedule it. Its separate continuation
  contains the fragment body after the Destruction Connection.

## Names and identity

- Generated names are deterministic, source-readable, and unambiguous. Derive
  identity from semantic objects rather than `id()`, enumeration indexes, node
  IDs, fragment IDs, or positions in another sequence. DLP 27 short names may be
  used where appropriate.
- Use Action References and Position References directly when their surrounding
  generated names already identify the concept. Do not add redundant `trigger_`
  or `guarantee_` prefixes.
- Generated position and action references use Python class objects rather than
  string names.
