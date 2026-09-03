# Operation Graph Execution Design

This document records the implementation design shared by Operation Graph
construction and resolution, action planning, literal code generation, and the
literal runtime. The [language specification](../spec/spec.md) remains
authoritative for Define semantics. Literal Python representation rules live in
the
[literal Python execution codegen design](codegen/literal/python/execution_codegen_design.md).

## Semantic authority

- Derive Particle Operation dependencies exclusively from the specification's
  Particle Operation Dependency Graph rules. Never derive an expected graph from
  current compiler behavior.
- Generated code must express exactly the resolved Operation Graph. It must not
  add serialization, omit dependencies, or hide a real runtime dependency from
  tracing.
- Preserve every opportunity for concurrency represented by the graph. When a
  fanout becomes runnable, schedule its independent branches rather than
  executing them serially.
- Action Execution initialization is not a Particle Operation and does not add
  an Operation Graph dependency.
- The Particle Operation that causes an Action Execution is not automatically a
  dependency of that execution's Particle Operations or Guarantees.

## Compilation boundaries

### Operation Graph and action resolution

- Represent Action Execution identity, Action Parent availability, Particle
  Operations, Guarantees, and dependency relationships as separate concepts.
- Each per-action Operation Graph must contain every minimal dependency it can
  determine from its own nodes and edges. Cross-action resolution must not
  repair missing graph construction or perform transitive reduction.
- Resolve only relationships between an action and its direct callees. The
  per-action resolver must not inspect callers or walk the complete reachable
  action call graph.
- The per-action resolver and the full-graph resolver must derive the same
  relationships.
- Operation Graph resolution must not choose generated methods, Action
  Fragments, joins, or other runtime structures.

### Action planning

- Consume resolved Operation Graph relationships and produce a complete static
  runtime plan.
- The plan identifies every Action Execution initialization, Action Fragment,
  Binding Hole fanout, dependency arrival, join, Guarantee publication and
  consumer, resolved Action Execution path, and Destruction Connection.
- A plan retains Operation Graph nodes, Action Execution objects, Action
  Fragments, and other semantic objects by reference. Later stages must not
  reconstruct identities, indexes, or relationships already known by lower
  layers.
- The plan decides join ownership and whether a caller must assign a join on a
  callee Action Execution.
- The plan gives codegen every resolved execution path it needs; codegen does
  not perform transitive Operation Graph analysis.
- Stable relationships between an action and its direct callees are expressed by
  that action. An outer caller performs only initialization, join assignment, or
  other work whose need depends on that caller.

### Code generation

- Codegen allocates names and renders the complete Action Plan. It does not
  infer dependencies, discover consumers, choose join ownership, or repair the
  plan.
- Language-specific codegen design owns syntax and representation choices.

### Runtime support

- Runtime primitives implement only behavior that cannot be expressed
  statically: task scheduling, multi-arrival joins, Guarantee publication, and
  Destruction Connections.
- Tracing observes the dependencies created by real generated code. Runtime or
  generated tracing paths must never suppress, replace, or invent dependencies.

## Modularity and scale

- Adding a caller must never change the generated code of its callee.
- Generate each action modularly after its direct callees, using only that
  action and its direct-callee interfaces. Do not inspect its callers or flatten
  the complete action call graph.
- Resolve a propagated Guarantee lazily for the specific Guarantee being
  consumed. Never eagerly construct or copy a complete Guarantee tree.
- Reuse paths already discovered by Operation Graph and Guarantee resolution. Do
  not add repeated transitive walks, copy every path prefix, or make work or
  memory use superlinear in the resolved relationships and generated source.

## Action Executions

- The entry action uses the same reusable Action Plan as every other action. A
  separate view-point Create plan identifies the ordinary Binding Holes and
  caller-resolved joins satisfied by creation of the view point; only generated
  `execute()` consumes that plan.
- An Action Execution becomes available when its Action Parent has a particle.
  Initialize it synchronously before releasing work that requires it.
- An Action Execution's constructor creates runtime state only. It never
  performs a Particle Operation or releases scheduled work, leaving callers a
  synchronous interval in which to complete registrations and join assignment.
- Immediately retain the specific Action object when a Particle Operation makes
  an Action Execution available. Do not look it up later after another Particle
  Operation may have moved or destroyed its particle.
- Repeated Action Executions have distinct runtime state and distinct
  Guarantees.
- Do not treat an Action Execution as one atomic call. Caller and callee work
  becomes available according to its resolved Operation Graph dependencies.

## Binding Holes, fragments, fanout, and joins

- Every Binding Hole with consumers is a stable callee interface, including when
  its current fanout has one consumer. Callers do not depend on the number or
  identity of callee consumers.
- A Binding Hole interface owns its complete callee-defined fanout of Action
  Fragments and direct-callee Binding Holes.
- A Move Rule or Empty Rule Binding Hole belongs to one Particle Operation. It
  may receive multiple dependency arrivals, but it does not fan out to multiple
  consumers.
- Action Parent and Requirement Binding Holes may fan out to multiple consumers,
  but each receives exactly one caller Particle Operation. No Binding Hole
  therefore requires both multi-arrival joining and multi-consumer fanout.
- A Particle Operation directly releases intrinsic Action Fragment arrivals
  known by its action.
- Preserve distinct dependency arrivals even when they invoke the same generated
  method.
- Consecutive Particle Operations in one Action Fragment remain together.
- An action creates a join when its own resolved plan knows every predecessor.
  When a caller supplies the complete resolution, the caller assigns the join on
  the affected Action Execution.
- Never create a one-arrival join. A reusable join site with one resolved
  predecessor proceeds without synchronization.
- Action Execution initialization is synchronous setup, not a special join
  arrival; `Join` represents only dependency arrivals.
- Code following a direct call may rely on its Particle Operation only when the
  call is statically guaranteed to perform that operation. Work following a
  multi-arrival join is released by the operation's Guarantee.

## Guarantees

- Each Action Execution has distinct Guarantees. Parent executions do not reuse
  a child's Guarantees for another Action Execution.
- Initialize ordinary and Destructor Action Executions synchronously before
  releasing ordinary Guarantee consumers.
- Register a propagated Guarantee consumer once on the terminal Guarantee
  through the realized Action Execution path, before releasing work capable of
  publishing that Guarantee.
- Install a consumer on a transitive Guarantee only when Guarantee resolution
  has already identified the Guarantee and its Action Fragment. Do not perform
  another transitive walk during planning or code generation.
- Use a Guarantee consumer when another Action Execution must observe the
  Particle Operation that actually completes, such as an operation reached
  through a multi-arrival join. Do not replace an intrinsic direct release with
  a dynamic callback.

## Destruction and Destructors

- Destructor execution has no generic completion dependency. A Destroy and
  unrelated Destructor Particle Operations remain concurrent unless the Particle
  Operation Dependency Graph gives them another dependency.
- Caller-contributed destruction work is represented with Destruction
  Connections while the callee's generated code remains independent of its
  callers.
- Retain a caller-known Position whose particle will be destroyed while that
  particle is available; do not look it up again after callee work may have
  moved or destroyed it.
- Synchronize Destroy operations only through dependencies present in the
  resolved Operation Graph. Do not add a runtime join for Action Execution
  creation or generic Destructor completion.

## Verification

- Use normal integration cases starting from Define source whenever feasible.
- Derive every expected Operation Graph from the specification rules before
  comparing it with compiler behavior.
- Verify generated runtime dependencies against the resolved Operation Graph,
  including fanout, joins, retriggering, and concurrency. Do not assert on
  implementation details when an Operation Graph or tracing case can demonstrate
  the behavior.
- Maintain explicit callee-independence coverage for new caller behavior.
