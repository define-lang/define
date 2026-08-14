# Action Code Generation Design

This document records the conceptual design for lowering DLP 44 operation graphs
into executable code. It supplements the language specification; the
specification remains authoritative.

## Core Invariant

An action fragment is a maximal direct-call chain in the planner's fragment
topology.

Two adjacent Particle Operations belong to the same fragment when:

- the second operation has exactly one effective predecessor, the first
  operation;
- the first operation has exactly one continuation, the second operation; and
- their boundary neither publishes a guarantee nor triggers another action.

Fragmentation happens after symbolic dependencies have been interpreted for the
action's compilation boundary. Raw counts of `RequirementNode`, `GuaranteeNode`,
or other symbolic nodes do not determine fragment boundaries.

Literal Python names a fragment after its first Particle Operation, using every
typed-name element in that operation's source and target chains. Global names
use their DLP 27 source form, with enough FQUN information to distinguish them
from names in other universes or multiverses. Equal names receive deterministic
numeric suffixes. The method, join, submissions, and guarantee dependencies all
refer to that allocated fragment name. The plan connects fragment objects
directly; it does not assign fragment IDs.

## Compilation Boundaries

There are two action compilation contexts:

| Context          | Treatment of caller dependencies                             |
| ---------------- | ------------------------------------------------------------ |
| Executed action  | Do not contribute dependency arrivals                        |
| Triggered action | Remain caller inputs connected through each Action Execution |

Only the entry action is invoked through `execute()`. It is inherently a
zero-input dataflow component. For example, the effective DAG for
`two_dependent_operations` is:

```text
create(item) -> move(item, dest)
```

Its caller inputs contribute no dependency arrivals because the executed action
has no caller. The two operations therefore form one fragment.

Caller inputs remain first-class for a triggered action because different caller
operations may satisfy them independently. Such an action can genuinely need an
additional fragment or join.

## Reusable Action Plans

Each non-entry action has one reusable triggered plan containing:

- Particle Operation fragments;
- caller inputs and their consumers;
- direct Action Executions and their triggered inputs;
- destructors fired by guarantees;
- guarantee publications and dependencies; and
- dependency counts for fragments and triggered inputs.

Resolution for a caller inspects only the caller's graph, each directly
triggered callee's resolved caller-input interface, and the Action Execution's
requirement bindings. It connects caller dependencies to callee inputs without
constructing or retaining a resolved operation graph for the whole program.

The entry action receives the zero-input executed form. Every other action,
including every destructor, receives the reusable caller-input form. In an
acyclic reachable action call graph, the entry action cannot also be reached as
a callee without forming a cycle.

## Dependency Normalization

`ResolvedActions` retains one `ResolvedAction` per action definition. Before
fragmentation, resolution:

1. Partitions every Particle Operation's direct dependencies into local Particle
   Operations, guarantees, and dependencies supplied by the caller.
2. Records each caller input and the Particle Operations that consume it.
3. Resolves every direct callee input through its `ActionExecution`, recording
   its dependencies in the caller and the caller inputs that consume it.
4. Associates each resolved Action Execution with its trigger operation,
   represented in the caller's Operation Graph by a `PositionOperationNode`,
   `GuaranteeNode`, or `RequirementNode`.

`ResolvedAction` retains all resolved Action Executions, while
`_ActionExecutionResolution` provides the reverse indexes required by planning.
An Action Execution whose trigger operation is a `PositionOperationNode` is
indexed by that operation. A destructor Action Execution whose trigger operation
is represented by a `GuaranteeNode` retains that node. A destructor on a child
of a particle from the caller is attached to the corresponding caller input.

`ResolvedAction` is independent of whether the action will execute directly or
be triggered. The planner applies that compilation-context decision after
resolution.

Resolution and planning do not repair the graph, infer missing dependencies,
compute a transitive reduction, or expand the complete program graph.

## Action Executions and Guarantees

An `ActionExecution` describes wiring rather than a synchronous call boundary.
Its `trigger_operation` records the operation that triggers it:

- a `PositionOperationNode` for a Particle Operation in the action body;
- a `GuaranteeNode` standing in for the Particle Operation in a callee's
  Operation Graph; or
- a `RequirementNode` for a destructor on a child of a particle supplied by the
  caller.

These sources affect where codegen connects the Action Execution. They do not
change the triggered action's plan or the meaning of its inputs.

The operation that causes an action's trigger conditions to become true is not
automatically a dependency of that action's Particle Operations. Each callee
input is resolved through its `ActionExecution` to the dependencies in the
caller that satisfy it. Those dependencies become continuations from caller
fragments or inputs.

- Caller inputs release eligible callee fragments and triggered inputs.
- Every Action Execution has separate local positions, joins, and a callee
  execution.
- A callee publishes a guarantee immediately after its final relevant Particle
  Operation.
- Caller fragments waiting on that guarantee become eligible immediately.
- Neither action waits for the other action to finish as a whole.

Literal Python represents each Action Execution with an execution object.
Fragments, generated caller-input methods, and direct-callee wiring are methods
of that object; the action quality retains its runtime identity and interface
positions. A `Scheduler` is passed explicitly into each execution and then into
every callee execution; it is execution context, not state of the action
quality. The entry action inherits the runtime's `EntryPoint` action role. Every
other action, including a destructor, inherits `Action`. Only the entry action
defines `execute()`.

A caller fragment invokes the appropriate execution method after its final
Particle Operation, submitting all but one ready continuation and directly
calling the remaining continuation. Filling a trigger position does not invoke
the action. Only the generated caller wiring releases callee fragments, so the
runtime cannot execute the action a second time or impose a false dependency on
the trigger position.

For an Action Execution fired by a Particle Operation, the fragment ending with
that operation directly calls a generated initialization method before releasing
any of its other continuations. That method obtains the action object and
creates the one callee execution for the Action Execution. The fragment then
supplies one dependency arrival to every callee input. Other dependencies may
arrive before or after that arrival; an input invokes the stored execution only
after all of its arrivals. Initialization always remains on the fragment's
current thread, so a parallel branch cannot first move or destroy the particle
through which the action is referenced.

This implements DLP 44's rule that actions are not atomic units of execution.

### Guarantee routing

Guarantee routing must never scan callers of an action, collect requests across
the reachable program, compute a whole-program fixed point, or specialize one
action's plan for the set of callers in a particular program.

`GuaranteeNode` already identifies the complete callee route with its
`execution`, `nested_executions`, and `guaranteed_position`; it needs no
additional operation-graph metadata. `OperationGraphs.resolve_guarantee()` uses
the final callee graph to return the complete `ActionExecution` list and final
Particle Operation node.

This resolution is definition-level and independent of action instances. The
resolver, planner, and code generator retain the operation nodes and
ActionExecution objects themselves; no numeric or `id()`-based identity survives
the lowering. Literal Python lowers the result to generated guarantee classes
with public task lists named after local guarantee publications and public
guarantee objects named after direct Action Executions. A generated execution
registers its bound consumer method by following the resolved chain of
direct-callee attributes and appending it to the final publication's task list.
Each execution passes one direct-execution guarantee object to its callee
execution. The final execution releases that publication's tasks immediately
after the Particle Operation.

The generated guarantee objects belong to action executions, not reusable action
plans. This is necessary because a caller can receive a contextual guarantee
through an intermediate action even when that guarantee is absent from the
intermediate action's own contract. Each generated guarantee class describes
only its action's local publications and direct Action Executions. An
intermediate execution treats a direct callee's guarantee object as opaque and
passes it down without flattening descendant guarantees into its own API.

Resolution is lazy and path-specific: resolving one consumed guarantee follows
only that guarantee's callee chain and never visits sibling guarantees. Codegen
does not flatten descendant guarantees or enumerate contextual guarantees merely
to define an action's execution API.

### Destructor trigger operations represented by guarantees

When an action creates or moves a particle in one of its positions, the caller
may know that particle only through the resulting guarantee. If the particle has
a destructor and the caller destroys it, the validator records an ordinary
Action Execution whose `trigger_operation` is that `GuaranteeNode`.

The resolver first resolves every destructor input exactly like the inputs of
any other triggered action. The planner then resolves the trigger operation's
`GuaranteeNode` to a `GuaranteePath` and records a
`TriggerForDestroyedCalleeGuaranteeParticle` containing:

- the destructor's ordinary `ActionExecution`;
- the guarantee path to the trigger operation; and
- the ordinary `TriggeredActionInput` values for the destructor.

Codegen registers one generated callback on the task list at the end of that
guarantee path. When the publishing Particle Operation releases the task list,
the callback initializes the destructor execution and supplies the Action
Execution arrival to each destructor input. Each input's other dependencies are
registered separately. For example, the same guarantee can both fire the
destructor and satisfy its Action Parent input, while a child guarantee
satisfies an occupied requirement.

Every triggered input counts the Action Execution arrival in addition to its
Particle Operation, guarantee, and caller-input dependencies. Its generated join
therefore invokes the destructor execution only after the Action Execution has
created that execution and all normal dependencies have arrived. Releasing the
guarantee does not synchronously execute the destructor.

This routing applies only to directly known destructors already recorded in the
operation graph. The planner does not discover destructors or interpret
Destruction Contracts.

### Triggered execution lifetime

The execution for an Action Execution must obtain its action object when the
Action Execution is released. It must not postpone that lookup until a later
callee input arrival: a parallel Particle Operation may move or destroy the
particle in the meantime even though the already-triggered action remains valid.

A firing fragment initializes the execution before invoking any triggered input.
A guarantee callback does the same before supplying its Action Execution
arrivals. A caller-input method initializes a destructor on a child of a
particle from the caller before releasing that destructor's inputs. Every
triggered input then uses that same stored execution. This preserves the
operation graph's parallelism while making the Python object lifetime
independent of later position lookup.

## Fan-Outs and Joins

After a fragment runs its Particle Operations:

- one ready successor remains on the current thread through a direct method
  call;
- other ready successors are passed to `Scheduler.submit()`;
- a successor with multiple distinct dependencies has a per-execution `Join`;
  and
- the dependency making the final join arrival directly calls the successor.

This design does not require a trampoline.

## Expected Fragment Shapes

- `single_create`: one fragment.
- `two_dependent_operations`: one fragment.
- `three_operation_chain`: one fragment.
- Two independent chains: two fragments started concurrently.
- Fan-out: the shared serial prefix ends at the fan-out.
- Join: the joined operation starts a new fragment.
- Guarantee publication: in a triggered-action plan, a boundary exists when
  publication creates another continuation.
- Action triggering: a boundary exists when the callee and a local continuation
  can proceed concurrently.

## Destructors

A destructor is a normal triggered action. It uses the same reusable plan,
fragments, caller inputs, triggered inputs, joins, guarantees, and direct-callee
wiring as every other non-entry action. It has no runtime `execute()` method.

The operation graph records the destructor's Action Execution during the
Destruction Cascade. The planner merely routes that already-recorded Action
Execution from its triggering Particle Operation, guarantee, or caller
requirement. The Action Execution source initializes the destructor execution
and supplies one arrival to each destructor input; the destructor's fragments
become eligible through the normal dependency machinery.

## Planner API

`ActionPlans` receives `OperationGraphs` and an entry action. Its caller passes
definitions to `plan_for()` in direct-callee-first order. `ResolvedActions`
resolves each action from its graph and its already-resolved direct callees.
Resolution therefore crosses only one caller/callee relationship and never
recursively analyzes the reachable program. The planner connects operation
nodes, caller inputs, Action Executions, and fragments by direct object
reference. It selects the executed form only for the entry action and the
triggered form for every other action. The code generator supplies the postorder
definitions but does not resolve dependencies itself.

The planner internally lowers one operation graph after its direct-callee inputs
have been resolved. Its two compilation contexts are:

- `build_executed_action()` omits caller inputs and local guarantee publications
  and directly starts zero-dependency fragments. It is used only for the entry
  action.
- `build_triggered_action()` retains caller inputs for later `ActionExecution`
  wiring. It is used for every non-entry action, including destructors.

For a directly executed action, the planner excludes caller-input contributions
from the dependency counts and consumers of both Particle Operations and direct
callee inputs. This lets an implied action whose Action Parent is the entry
particle begin in parallel with the entry action's independent Particle
Operations. The planner contracts the resulting local graph directly; it does
not use a raw symbolic dependency count. An `ActionExecution` is also a
continuation, so an operation with both an `ActionExecution` and a local
successor ends its fragment.

Reference-graph validation records only the action's own guaranteed positions
that are published by its local Particle Operations, grouped by operation node
object. Contextual guarantees and guarantees produced by callees are not local
publication boundaries. Triggered-action planning treats the recorded local
publications as continuations; executed-action planning ignores them because an
executed action has no caller. Codegen therefore does not retain action
contracts merely to find guarantee boundaries.

The completed `ActionPlan` contains Particle Operations rather than requiring a
renderer to index back into an operation graph. It also contains directly
executed fragments, direct Action Executions, caller-input and triggered-input
consumers, dependency counts, guarantee publications, guarantee-fired
destructors, and the resolved `GuaranteePath`s needed by fragments, triggered
inputs, and destructor Action Executions. A renderer assigns target-language
names and expressions to this plan; it does not receive operation graphs,
resolve dependencies, discover continuations, or calculate joins.
