# Boolean Logic in the Compiler

How the compiler represents boolean logic, checks the rules of DLP 56 (Logical
Operations for Boolean Values) and DLP 57 (One Way to Write Boolean Logic), and
decides whether two boolean values are always the same.

The proposals say what programs may write. This note says how the compiler does
the work. The research behind it is in
[Representations of Boolean Logic](../define/proposals/background/boolean-logic-representations.md),
and the measurements are in the research repository's
[boolean_equality_checking](https://github.com/define-lang/research/tree/main/boolean_equality_checking)
directory. Every number below comes from there, measured on generated value
operations, not real programs.

## What the Compiler Checks

For each value operation definition, once:

1. **Limits:** at most 256 boolean statements and at most twenty boolean inputs.
2. **Order:** the statements and the values given to interchangeable views are
   in DLP 57's order.
3. **Redundant values:** no boolean statement computes a value that's always
   true, always false, always the same as a boolean input, or always the same as
   an earlier value.
4. **Matches:** no group of statements computes one value from at most four
   other values the way a registered operation does.
5. **Wrappers:** no value operation wraps a registered operation, only the
   standard library wraps `and` and `not`, and value operations don't execute
   those wrappers. These only look at the statements, not at what they compute.

Each value operation is checked once, however many places execute it, so the
total work is the sum over definitions.

## Programs That Compile Have No Equalities

A redundant value is an error, and the programmer has to replace it, often with
an execution of a value operation. So in a program that compiles, no value is
the same as any other, and the logic is a tree of executions of value operations
instead of repeated logic. That changes what the usual work is:

- **The usual job is showing that values differ.** One assignment of the boolean
  inputs where two values disagree proves that they differ, and it's easy to
  check. Random simulation finds such assignments for almost every pair at once,
  so in a value operation that compiles, nearly every value ends up alone in its
  simulation group, and no solver is needed. Only values that differ on a tiny
  fraction of input combinations need more than simulation.
- **Proving equality only happens on the way to an error.** DLP 57 reports only
  the first redundant value in each value operation, so the compiler stops
  checking that value operation after its first proof of equality. The expensive
  part of the check runs at most once for each value operation that fails, and
  never on one that compiles.
- **Executions make repeated logic structural.** Where the same logic would have
  been written twice, a program that compiles executes one value operation
  instead. The same execution given the same values is the same node under
  structural hashing, without any reasoning.

The measurements below planted a redundancy in about 8% of the statements, so
most of their time went to proving equalities. They're upper bounds for value
operations that compile, not typical costs.

## Representation

The boolean statements of a value operation become an and-inverter graph (AIG):
every node is an `and` of two literals, and a literal is a node plus whether
it's negated. `not` is a mark on a literal, not a node, so `not (not x)` is `x`
without any rule. The leaves are the boolean inputs and the constant false.

Nodes are hash-consed: the compiler keeps one table of every node it has built,
and building a node that already exists returns the existing one. Each `and` has
its two literals sorted, and these rules apply as it's built:

- `x and x` is `x`.
- `x and not x` is false.
- `x and true` is `x`, and `x and false` is false.

This is structural hashing. It's cheap (about 2 microseconds for 256 statements)
and it merges about 28% of the redundant values in the generated operations as a
side effect, before any other check runs.

A View Setting Statement adds nothing to the graph: the copy is the same literal
as the value it was copied from.

### The Normalized Form That Wasn't Chosen

A stronger form makes every node an `and` of a _set_ of literals, built by
flattening inputs that are themselves `and`s, sorting, and removing duplicates,
so that compositions that differ only by associativity or commutativity are the
same node. It has one choice: flattening a node that's used more than once
copies it into every place that uses it, which is quadratic in the worst case,
while flattening only nodes used once keeps the size linear but only matches
compositions that share the same nodes.

It isn't needed. Every equality it finds, the exact check below finds too, and
it only merged 30–32% of the redundant values (against 28% for structural
hashing) at about thirteen times the cost.

### Executions of Boolean Value Operations

An execution of a boolean value operation is one node in the caller's graph: a
reference to that value operation, with the values it was given. Its results are
the logic it computes, but the caller only needs that logic as a function of the
values it was given. DLP 57's rules only look at values that the caller's own
statements compute, never at the values inside an executed value operation, and
the executed value operation's own rules were already checked once, where it's
defined. So the caller's graph grows with the number of statements it has, no
matter how deeply executions are nested.

Each method uses the reference in its own way:

- **Simulation and truth tables:** a boolean value operation reads at most
  twenty views, so the compiler records a truth table of at most 128 KB for each
  view it writes, and evaluating an execution is one lookup in that table for
  each combination.
- **OBDDs:** the compiler records each boolean value operation's OBDDs in view
  order, and an execution is the composition of those OBDDs with the OBDDs of
  the values it was given. Reduced OBDDs are canonical, so the result's size
  depends only on what it computes, not on how it was written.
- **SAT:** the solver needs clauses for what an execution computes, with
  variables for the values it was given. The compiler can add those clauses only
  when a question needs them: first it treats the execution's results as free
  variables, and if the solver finds an assignment, it checks the executions in
  it against their truth tables. If they all agree, the assignment is real. If
  one doesn't, the compiler adds clauses for that execution and asks again. This
  is counterexample-guided abstraction refinement. It always ends, because each
  execution only has so many clauses to add.

Copying the executed value operation's graph into the caller instead, which is
what the generated workloads did, would let one SAT sweeping pass run over a
single flat graph. But copies can contain copies, so the caller's graph can grow
exponentially with how deeply executions are nested.

DLP 57's interchangeable views come from the same equality check as redundant
values: two read views are interchangeable when every written view is always the
same with the two views swapped.

## Statement Order Is the Input Order

DLP 57's statement order computes each value right before the statement that
first uses it. So the order in which boolean inputs are first used is fixed by
the program, and the compiler uses it as the input order for every OBDD it
builds within the value operation. One value operation has one input order.

That order matters. With 128 inputs and 256 statements, OBDDs took a median of
1.3 ms in first-use order and 2.8 s with the inputs in numbered order.

## Finding Redundant Values

The check is exact: every method below, run to completion, gives the same
answer, so limits on any one method only change how long checking takes, never
which programs compile. That's what makes the rule predictable for the
programmer, and the same on every machine. The methods are the ones Kuehlmann,
Paruthi, Krohm, and Ganai combined in "Robust Boolean Reasoning for Equivalence
Checking and Functional Property Verification" (IEEE TCAD 21(12), 2002).

1. **Structural hashing** as the graph is built, above.
2. **Simulation:** the compiler evaluates every node on the value operation's
   stored patterns from earlier compiles (below), and on 1,024 combinations of
   the boolean inputs from a random generator with a fixed seed (sixteen 64-bit
   words per node). Two values that differ on any combination aren't the same,
   and every node gets a signature. Constants and boolean inputs get signatures
   too.
3. **Proving candidates, in statement order:** for each node, the candidates are
   the constants, the boolean inputs, and the earlier nodes with the same
   signature. Each candidate pair goes to the first of these that decides it:
   - **Every combination:** if the two nodes read at most twelve boolean inputs
     between them, the compiler evaluates them on every combination of those
     inputs.
   - **SAT:** otherwise, an incremental SAT solver is asked whether `f xor g`
     can be true, with the Tseitin encoding of the two cones, and with a limit
     of 1,000 conflicts.
   - **OBDDs:** if the solver reaches that limit, the compiler builds OBDDs of
     the two nodes in first-use order, up to 4 million nodes. Equal nodes are
     the same OBDD node.
   - **SAT without a limit,** if the OBDDs get too large.
4. **Counterexamples:** an assignment that shows two nodes differ becomes a new
   simulation pattern, which splits other candidates that it separates too.
5. **Stopping:** a node proved the same as a candidate is a redundant value. The
   compiler reports it, along with what it's the same as, and stops checking
   that value operation. Since the candidates are checked in statement order,
   it's the first one.

The methods cover each other's worst cases. SAT alone timed out on parity in a
different input order from 48 inputs, while OBDDs decide it in milliseconds in
any order. OBDDs grew about four times for every four inputs on the hidden
weighted bit function (1.3 s at 40 inputs), while SAT took about 100 ms.

| Value operation size                       | Time                         |
| ------------------------------------------ | ---------------------------- |
| Tens of statements                         | 8–18 µs                      |
| Up to 256 statements, 4–128 boolean inputs | median 55 µs, slowest 1.0 ms |
| 1,024 statements (past DLP 57's limit)     | slowest 7.6 ms               |

### The Worst Case

Some logic is hard for every method: two multipliers written in different ways
defeated every one from 11 bits, growing five to six times for each bit. The
limit of twenty boolean inputs bounds this. Truth tables over every boolean
input take time that depends only on the number of inputs and statements, never
on what the logic computes:

| Boolean inputs | Truth tables for 256 statements |
| -------------- | ------------------------------- |
| 16             | 2 ms                            |
| 20             | 52 ms                           |
| 24             | 0.5–2.3 s                       |

So the compiler runs the methods above with a total budget, and when the budget
runs out, it decides the rest with truth tables. Either way the answer is the
same. A truth table for twenty inputs is 128 KB, and the compiler frees each one
after its node's last use, keeping one for each node it still needs to compare.

With executions of boolean value operations, the fallback does one table lookup
per execution for each combination instead of one bitwise `and` per 64
combinations, so its worst case is larger than the measured one. That's argued,
not measured.

## Checking Again on Later Compiles

### Stored Patterns

When a value operation compiles, the compiler stores the assignments that the
solvers found, the ones that showed two of its values differ, with the value
operation. The random patterns don't need storing, because they come from a
fixed seed. On a later compile of the same value operation, simulating with the
stored patterns separates every value again, with no solver, in time
proportional to the number of statements times the number of patterns.

Few patterns ever need storing. Each pattern that's kept splits at least one
group of values that simulation couldn't tell apart, and a value operation with
`n` values can only be split `n - 1` times, so at most 255 assignments of at
most twenty bits each are needed for 256 statements.

Stored patterns can't change the answer, because the check is exact either way.
They only move work out of the solver. If a value operation changes, its old
patterns are still valid assignments of its boolean inputs, as long as it has
the same ones, and still usually separate most of its values.

### What a Caller Depends On

A value operation's check depends on what each boolean value operation it
executes computes, not on how that value operation is written. So the compiler
records a hash of each boolean value operation's truth tables, and checks a
value operation again only when its own statements change or the hash of
something it executes changes. Rewriting a boolean value operation without
changing what it computes doesn't check anything that executes it again.

Matches also depend on the registered operations, so a change to which
operations are registered, or to what one computes, checks matches again in
every value operation they apply to, but not redundant values.

## Counting Boolean Inputs

One pass over the statements collects the distinct boolean inputs: interface
views and values computed by statements that aren't boolean statements, read by
a boolean statement. The compiler reports the statement that first uses the
21st. The count doesn't depend on any solver, so every compiler gives the same
answer.

## Finding Matches

This is how logic synthesis tools find parts of a circuit that a library's
predesigned gates can replace.

1. **Cuts:** for every value a boolean statement computes, the compiler finds
   its _cuts_: sets of at most four values that it can be computed from. A
   value's cuts are the set holding only itself, plus every union of one cut of
   each of its inputs, when that union has at most four values. A boolean input
   only has the cut holding itself.
2. **Truth tables:** for each cut, the compiler computes the value for every
   combination of the cut's values, sixteen bits for four values, from the truth
   tables of the inputs' cuts with a few bitwise operations.
3. **Lookup:** the compiler rewrites each truth table into a standard order of
   its values, so that the same function always has the same table no matter
   which order its values are in, and looks it up in a hash table of the
   registered operations, built the same way.

The statements of a match are the ones between the cut's values and the value
computed from them.

Enumerating every cut with no pruning took 1–3 ms at 256 statements, slower than
the whole redundant-value check, because some nodes have hundreds of cuts. Logic
synthesis tools usually keep only a few of the best cuts for each node, but DLP
57 needs every match, so the pruning would have to keep every cut that could
match a registered operation.

## Across a Whole Program

DLP 57 doesn't need equality across value operations, because its rules are
about one value operation at a time. If the compiler wants program-wide
equalities for optimization:

| Method                                                      | Program    | Time   | Memory | Finds                   |
| ----------------------------------------------------------- | ---------- | ------ | ------ | ----------------------- |
| Structural hashing                                          | 8.3M nodes | 0.46 s | 600 MB | 70–77% of planted pairs |
| Exact SAT sweeping, program split into regions like actions | 7.0M nodes | 120 s  | 1.4 GB | everything              |
| Exact SAT sweeping, one long dataflow                       | 2.2M nodes | 369 s  | 1 GB   | everything              |

At that size the SAT solver has to be replaced with a new one as it grows:
without that, 1.8M nodes took 334 s instead of 21 s.

## What Doesn't Work

- **A width limit.** An earlier version of this note chose between OBDDs and SAT
  by the operation's _width_, the largest number of values that are live between
  two statements: with inputs in first-use order, the OBDD has at most 2^k nodes
  at each level when the width is `k` (Berman, 1991). The measured widths were
  17 to 74 at 256 statements, because a condition that's read again later stays
  live the whole time, while the OBDDs had thousands of nodes, far below what
  2^k allows. Any limit small enough to matter would send nearly every value
  operation past it.
- **A solver budget as the rule.** With a conflict limit and nothing after it,
  which pairs are left undecided depends on the limit, the solver's heuristics,
  and its version. A budget is only safe in front of something exact.
- **Replacing values with new inputs** once the logic gets too large. It never
  reports a false equality, but which real equalities it misses depends on where
  the cut happened to fall.
- **Other primitives.** Exclusive or as a primitive would make parity
  structural, but the exact check already decides parity in milliseconds, and
  multipliers are just as hard with exclusive or. This is argued from the
  measurements, not measured with another set of gates.

## Open Questions

- **Exact matches.** Matches could be defined like redundant values, over the
  whole value operation: a value that's always the same as a registered
  operation applied to values the operation already has. Whether that's
  affordable, and whether the four-read-view limit would still be needed, is
  being investigated.
- **Measuring value operations that compile.** The workloads planted
  redundancies, so they mostly measured proving equality. How long the check
  takes on value operations with no redundant values, with stopping at the first
  one, with stored patterns, and with checking again only when what an executed
  value operation computes changes, hasn't been measured.
- **Measuring references.** The generated workloads copied executed value
  operations into the caller. How SAT sweeping with references and abstraction
  refinement compares with copying hasn't been measured.
- **Redundancy through other statements.** `(x < 3) and (x < 5)` is always the
  same as `x < 3`, but the boolean inputs are treated as independent. Catching
  it means checking with what the comparisons compute: an SMT solver decides
  linear comparisons of numbers quickly, and numbers of a fixed width can always
  be turned into bits, though multiplication is as hard there as it is here.
- **Redundancy in actions.** The particles in a position can change between two
  executions in an action, so the same expression at two points isn't always the
  same value. Checking actions also needs a bound: the compiler could look
  through executions while the action's logic stays within the input limit, and
  treat executions' results as inputs past that, which is deterministic because
  the boundaries are the executions the program wrote.
- **The number twenty.** It's a choice of about 50 ms as the worst case for one
  value operation, and nobody knows yet how many boolean inputs real value
  operations have.
- **Error messages.** A redundant value is reported with the value it's always
  the same as. The compiler could also show an assignment of the boolean inputs
  for near misses, or the statements a proof depended on, but how to present
  either is open.
- **Values that aren't single bits.** Everything here is about boolean values.
  Numbers would need a different way to compare what statements compute.
