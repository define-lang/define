# Particle Operation Dependency Graph Minimality

## Claim

For every finite valid Define program, the complete Fill, Empty, Move, and
Action Parent Rules in [`define/spec/spec.md`](../define/spec/spec.md) produce a
Particle Operation Dependency Graph that is a directed acyclic graph and is
transitively reduced. This includes operations reached through Action
Executions, Action Requirements, Action Guarantees, automatic destruction, and
Destruction Contracts.

The proof is about the complete graph of concrete Particle Operations. Every
Action Execution is expanded separately, every Action Requirement and Action
Guarantee is resolved to its concrete contribution, if any, and every automatic
or contributed Destroy Particle Statement is included before the graph is
considered complete.

The corresponding executable proof is
[`particle_operation_dependency_graph_minimality.lean`](particle_operation_dependency_graph_minimality.lean).

## Definitions

### Resolved Particle Operations

Each execution of a Particle Operation statement is a separate vertex, even when
two vertices execute the same statement through two Action Executions.

Let `V` be the finite set of these vertices. For `O` and `D` in `V`, an edge

```text
O -> D
```

means that `O` directly depends on `D`.

Write `O > D` when there is a nonempty directed path from `O` to `D`. Write

```text
D(O) = {D | O -> D}
```

for the direct dependency set of `O`.

The graph is _transitively reduced_ when removing any edge changes `>`. In a
directed acyclic graph, an edge `O -> D` is redundant exactly when some other
member `X` of `D(O)` satisfies `X > D`.

A set of vertices is a _reachability antichain_ when no two distinct members are
related by `>` in either direction.

### Position Relationships

Write `p <= q` when `p` is the same position as `q` or a transitive parent
position of `q`. Write `p ~ q` when either `p <= q` or `q <= p`.

The relation `~` is symmetric but not transitive. Two different child positions
can each have the same parent position without being related to each other by
`~`.

Let `positions(O)` be the positions operated on by `O`. A Create or Destroy has
one such position. A Move has its source and target positions.

### Previous Operations

Let `<` be the strict operation order used by the words “previous,” “most
recent,” and “more recent” in the four rules. Each execution of an action has
its own operation occurrences in this order. Resolving an Action Execution
places the callee occurrences at that execution, and resolving a destructor
places its occurrences at the corresponding destruction.

The rules select only previous Particle Operations. Action Requirement
resolution selects an operation in the caller that precedes the callee's use of
the required state. Action Guarantee resolution selects the callee's final
operation on the guaranteed position, which precedes a caller operation waiting
for that guarantee. A Destroy contributed through a Destruction Contract
precedes the Destroy to which it contributes.

Consequently, `<` is well-founded on the resolved Particle Operations and

```text
O -> D implies D < O.
```

### Facts supplied by program validity

The proof uses three occupancy facts from the definitions of the Particle
Operations:

1. A position is filled only while it is empty and emptied only while it is
   occupied.
2. A transitive child position is available only while every transitive parent
   position needed to name it is occupied.
3. Moving a particle preserves that particle and its transitive child positions;
   destroying and later replacing a particle does not preserve that particle's
   occupancy.

These facts are premises of the graph rules for a valid program, rather than
claims about transitive reduction. They are used below only to identify the
operation that must occur between an earlier child-position operation and a
later fill of an empty parent position.

### Most-recent entries

For proof purposes, call the operation remembered as most recent on a position
its _most-recent entry_. A Create or Destroy written on `q` can be the
most-recent entry for `q`. A Move written with `q` as its source or target can
also be that entry. Under the Empty Rule, moving a particle additionally makes
that Move the most-recent entry for the moved particle's transitive child
positions. A later applicable Particle Operation replaces the entry in the
ordinary way.

This is only shorthand for the position history queried by the rules; it does
not add a graph vertex or a dependency. As the Empty Rule specifies, the Move's
additional entries on transitive child positions are used by later Empty Rule
calculations. The Fill Rule continues to select among operations actually on the
filled position and its transitive parent positions.

### Collection

The word _candidate_ is used only in this proof as shorthand for a Particle
Operation in the Empty Rule's Collection or the Fill dependency combined with
that Collection by the Move Rule.

For an operation that fills `t`, let `F(t)` be the single most recent previous
Particle Operation among the operations on `t` and its transitive parent
positions, if one exists.

For an operation that empties `s`, let `E(s)` contain the most-recent entry for
`s` and for each transitive parent and child position of `s`, wherever one
exists.

Duplicate selections of the same Particle Operation denote one candidate.

### Comparison

For a finite candidate set `C`, define its Comparison result as

```text
P(C) = {
    A in C
    | there is no B in C more recent than A
      with some a in positions(A), b in positions(B), and a ~ b
}.
```

This is the simultaneous meaning of “only the more recent Particle Operation
remains.” A more recent candidate participates in this comparison even when an
even more recent candidate also excludes it.

### Move Correction

Define the Empty Rule's Move Correction result as

```text
M(C) = {
    A in P(C)
    | A is not a Move, or no B in P(C) distinct from A satisfies B > A
}.
```

An Empty operation collects `E(s)` and finishes with `M(E(s))`. A Move initially
uses

```text
C(s, t) = E(s) union {F(t)},
```

omitting `F(t)` when it does not exist, and applies the Comparison and Move
Correction to produce `M(C(s, t))`. A member of `E(s)` is called _source-side_
even when the same operation is also `F(t)`. The Move Rule then removes `F(t)`
if it remains and a distinct remaining source-side candidate depends on it
directly or indirectly.

If the resulting set is empty, the Action Parent Rule adds at most one
dependency. Otherwise the resulting set is `D(O)`.

## Acyclicity

Every direct dependency is earlier in `<`. Along any directed path, `<`
therefore decreases strictly. A directed cycle would make one operation both
earlier and later than itself, which is impossible.

The resolved graph is finite because a valid program has finitely many
statements and its definition reference graph has no reference cycle. Expanding
an Action Execution or a destructor therefore cannot continue indefinitely.

Thus the complete Particle Operation Dependency Graph is a finite directed
acyclic graph.

## The Incremental Reduction Theorem

Suppose `G` is a transitively reduced directed acyclic graph. Add a new vertex
`O`, add edges from `O` to every member of a set `S` of existing vertices, and
add no edge from an existing vertex to `O`.

The new graph is transitively reduced if and only if `S` is a reachability
antichain.

### Proof

No edge already in `G` can become redundant. A path containing `O` must start at
`O`, because no existing vertex has an edge to `O`. Any newly redundant edge
must therefore be one of the edges `O -> D` for `D` in `S`.

If distinct `X` and `D` in `S` satisfy `X > D`, then

```text
O -> X -> ... -> D
```

is an alternate path for `O -> D`, so that edge is redundant.

Conversely, if `O -> D` is redundant, an alternate path from `O` to `D` must
start with `O -> X` for some `X` in `S` distinct from `D`. The remainder of the
path proves `X > D`.

Therefore the new graph is transitively reduced exactly when `S` is a
reachability antichain. ∎

## Structural Invariants of Define Operation Graphs

The antichain proofs use properties that a generic directed acyclic graph does
not have.

### Candidate-position invariant

Suppose the Empty Rule selects an operation `A` as the most-recent entry for a
position `q`.

- If `A` is a Create or Destroy, its only operated position is `q` from the
  resolved caller's perspective.
- If `A` is a Move, at least one of its source and target positions is `q` or a
  transitive parent position of `q` from that perspective.

#### Proof

Consider the last event that determines the most-recent entry for `q`.

A Create or Destroy written on `q` records that statement on `q`. A Move written
with `q` as its source or target records a Move with `q` as one of its
positions.

If the particle defining `q` subsequently moves, the Empty Rule makes that Move
the most-recent entry for `q`. One of the Move's positions is the moved
particle's position and is therefore `q` or a transitive parent position of `q`.
The same selection applies again after every later Move. A later applicable
statement replaces that entry in the ordinary way.

Resolving a caller binding replaces the callee's position prefix with the bound
caller position prefix. This preserves same-position and parent/child
relationships. Resolving a guarantee exposes the concrete Create, Move, or
Destroy that produced the guarantee. Repeating the argument through every caller
proves the invariant for the complete graph. ∎

### Direct-dependency position lemma

For every direct dependency `O -> D`, some position operated on by `O` has a
parent/child relationship with some position operated on by `D`.

#### Proof

The Fill Rule selects an operation on the filled position or one of its
transitive parent positions. The Empty Rule selects an operation for the emptied
position or one of its transitive parent or child positions; the
candidate-position invariant covers a Move that became most recent because its
particle moved. The Move Rule is the union of those two cases.

The Action Parent Rule selects an operation on the current action's parent
position or one of that position's transitive parent positions. From the
resolved caller's perspective, every position belonging to that Action Execution
is a transitive child position of the action's parent position. A position that
uses the same global position definition in a different Action Execution is a
different position and is not selected by this Action Parent Rule calculation.

Requirement and guarantee resolution preserves these relationships, as shown in
the candidate-position invariant. The rule comparisons only delete dependencies;
they never add an edge with different provenance. ∎

### Ordering, comparison, and replacement invariants

The following statements hold after every Particle Operation:

1. If `B` is more recent than `A` and a position operated on by `B` has a
   parent/child relationship with a position operated on by `A`, then `B > A`.
2. The operation in a most-recent entry reaches every earlier operation that the
   entry replaced.
3. After all applicable rule stages for an operation `O`, `O` reaches every
   candidate in the Collection.

#### Proof

Proceed by induction over Particle Operations in `<` order. The statements are
vacuous before the first operation. Assume they hold for all previous operations
and consider a new operation `O`.

First prove statement 3 for `O`. Every candidate of `O` is a previous operation,
so statement 1 is already available for every pair of candidates. If the
Comparison excludes `A` in favor of a more recent related candidate `B`, then
`B > A`. If `B` is also excluded, follow the excluding candidates. Recency
increases strictly, so the finite chain ends at a retained candidate that
reaches `A`.

For the Move Correction, consider any excluded Move `A` in `P(C)`. Among the
members of `P(C)` that reach `A`, choose one that no other member of `P(C)`
reaches. It is not removed by the Move Correction and it reaches `A`. The Move
Rule's Fill Dependency removal removes only `F(t)`, and only when a remaining
source-side candidate reaches `F(t)`. Thus each stage leaves some final
dependency reaching every candidate it removed. Since `O` depends on every final
dependency, statement 3 holds for `O`.

Next prove statement 1 for pairs containing `O`. Let `A` be an earlier operation
with a position related to a position of `O`.

- If `O` empties `s`, the Empty Rule selects the most-recent entry for the
  applicable position of `A`. That entry is `A` or, by induction statement 2,
  reaches `A`; by the newly proved statement 3, `O` reaches the entry.
- If `O` fills `t` and `A` operates on `t` or a transitive parent position of
  `t`, the Fill Rule selects an operation `B` at least as recent as `A` on that
  parent/child chain. If `B` is distinct from `A`, induction statement 1 gives
  `B > A`; statement 3 then gives `O > A` in either case.
- If `O` fills `t` and `A` operates on a strict child position of `t`, validity
  requires an intervening operation `K` that empties `t` or a transitive parent
  position of `t`; otherwise `t` could not be empty before `O`. The Empty Rule
  for `K` gives `K > A` by induction. The Fill Rule for `O` selects an operation
  at least as recent as `K` on `t` or its transitive parent positions. Induction
  statement 1 and statement 3 give `O > K > A`.
- A Move combines the Empty case for its source with the Fill case for its
  target.
- The Action Parent Rule is used only if the other rules leave no dependency. If
  `A` is on the action's parent position or one of its transitive parent
  positions, the rule selects an operation `B` at least as recent as `A`. The
  edge `O -> B` reaches `A` directly when `B` is `A`, and induction statement 1
  gives `B > A` otherwise. A related `A` on any other position would have
  supplied an Empty or Fill candidate in one of the preceding cases. Thus the
  Action Parent case adds no exception.

This proves statement 1 for `O`.

Finally prove statement 2 for entries changed by `O`. When `O` directly operates
on a position, statement 1 makes `O` reach the previous entry and statement 2
for that entry supplies all earlier replacements. When `O` is a Move, the Empty
Rule selects the previous entry for every transitive child position of the moved
particle. Statement 3 makes `O` reach those entries, and the induction
hypothesis makes those entries reach everything they replaced. It is therefore
valid to make `O` the most-recent entry for all those transitive child
positions.

All three statements hold after `O`. ∎

### Moved-child replacement lemma

It is correct for a Move to become the most recent operation on the moved
particle's transitive child positions.

#### Proof

This is the Move case in the final paragraph of the invariant proof. A later
operation may depend on the Move instead of repeating an earlier child-position
dependency because every such dependency remains reachable through the Move. ∎

### Later-related-entry lemma

Let a Create or Destroy `Y` be selected as the most-recent entry for `y` while
calculating `E(s)`. If a later previous operation `Z` operates on a position `z`
such that both `z ~ y` and `z ~ s`, the Comparison excludes `Y`.

#### Proof

Because `z ~ s`, `E(s)` includes the most-recent entry `B` for `z`. The entry
`B` is at least as recent as `Z`, and is therefore more recent than `Y`.

If `B` is a Create or Destroy, it operates on `z`. If `B` is a Move, the
candidate-position invariant gives it an operated position equal to `z` or a
transitive parent position of `z`. Since `z ~ y`, that position is also related
to `y`. Thus `B` and `Y` participate in the Comparison and `B` excludes `Y`. The
comparison is simultaneous, so this conclusion still holds if a third candidate
excludes `B`. ∎

## The Key Empty-candidate Lemma

Let `O` empty an occupied source position `s`. After the Empty Rule's
Comparison, suppose a remaining source-side candidate `Y` is a Create or
Destroy. No other remaining candidate `X` can satisfy `X > Y`.

This statement also allows `X` to be the dependency required for filling a
Move's target position.

### Proof

By the candidate-position invariant, the sole position `y` operated on by `Y` is
the position for which the Empty Rule selected `Y`, so `y ~ s`.

First suppose `s <= y`. Let

```text
X -> ... -> Z -> Y
```

be a dependency path, where `Z -> Y` is the final edge. By the direct-dependency
position lemma, `Z` operates on some position `z` related to `y`. Because `y` is
`s` or a child position of `s`, `z` is also related to `s`.

The later-related-entry lemma therefore says that the Comparison excludes `Y`,
contrary to the premise.

Now suppose `y < s`, so `y` is a strict parent position of the occupied source.

If `X` is another source-side candidate, the candidate-position invariant gives
`X` a position related to `s`. Every such position is also related to the parent
position `y`. Because `X > Y`, `X` is more recent, so the Comparison would
exclude `Y`.

The remaining possibility is that `X` is only the Fill Dependency of a Move. A
Destroy on `y` leaves `s` unavailable. A Create on `y` creates a new particle
for which the strict child position `s` is empty. In either case, a later
Particle Operation must fill `s` or move a particle that supplies `s` and its
required transitive parent positions. That operation has a position `z` on the
parent/child chain from `y` to `s`. The later-related-entry lemma again says
that the Comparison excludes `Y`.

Every case contradicts the premise that `Y` remains. ∎

This lemma is the Define-specific reason the Empty Rule does not need a generic
reachability comparison for every dependency. After the Comparison, a reachable
source-side dependency can remain only when that dependency is a Move; the Move
Correction covers exactly that case.

## Each Rule Produces a Reachability Antichain

The cases below are exhaustive. A Create uses the Fill Rule and, if needed, the
Action Parent Rule. A Destroy uses the Empty Rule and, if needed, the Action
Parent Rule. A Move uses the combined Move Rule and, if needed, the Action
Parent Rule. Automatic and contributed Destroys are Destroy Particle Statements,
so they use the Destroy case rather than adding another case.

### Fill Rule

The Fill Rule supplies at most one dependency. A set with at most one member is
a reachability antichain.

### Action Parent Rule

The Action Parent Rule applies only when the other rules leave no dependency and
supplies at most one dependency. Its result is a reachability antichain.

### Empty Rule

Suppose distinct remaining dependencies `X` and `Y` satisfy `X > Y` after the
Empty Rule's Comparison and Move Correction.

If `Y` is a Move, the Move Correction removes it. If `Y` is a Create or Destroy,
the key Empty-candidate lemma says it could not have remained after the
Comparison. Both possibilities are contradictions.

Therefore the Empty Rule's final dependency set is a reachability antichain.

### Move Rule

Suppose distinct dependencies `X` and `Y` remain after applying the Move Rule
and satisfy `X > Y`.

If `Y` is a Move, the Move Correction removes it because the Move Rule applies
the Empty Rule's Comparison and Move Correction to the combined set.

Suppose `Y` is a Create or Destroy. If `Y` is a source-side candidate, the key
Empty-candidate lemma says it could not remain, whether `X` is another
source-side candidate or the Fill Dependency. If `Y` is the Fill Dependency, `X`
must be a source-side candidate, and the Move Rule removes `Y` because `X`
depends on it directly or indirectly.

These cases cover every member of the combined set. Therefore the Move Rule's
final dependency set is a reachability antichain.

## Caller Resolution Preserves the Proof

Action boundaries introduce no additional kind of concrete dependency.

An occupied Action Requirement resolves to the caller operation that most
recently supplied that particle and the caller's applicable transitive
child-position operations. An empty Action Requirement used by a Move resolves
to the caller operation required for filling the target, if one exists; it
contributes no operation when the required position was empty without a previous
Particle Operation. An Action Guarantee resolves to the callee's final concrete
Particle Operation on the guaranteed position. The Action Parent input resolves
to the caller's most recent operation on the action's parent position or one of
that position's transitive parent positions, if one exists.

For one contracted particle, resolving position names replaces the callee's
contracted-position prefix with the caller's bound-position prefix. Within that
binding, prefix replacement preserves and reflects equality and every transitive
parent/child relationship. It also preserves Particle Operation kind and `<`.
Resolving every edge of a dependency path preserves that path. The final Empty
Rule selection considers the Move from the caller's perspective in which the
moved particle and its transitive child positions are known, so the
candidate-position invariant also survives resolution.

Bindings of different contracted positions can make two concrete positions
related even when their unresolved callee positions were not related. Caller
resolution therefore applies the comparisons to the complete concrete candidate
set; it does not assume that every unresolved survivor must remain. This can
only remove a candidate under the exact comparisons proved above.

### Resolution lemma

After an Action Execution's inputs are fully resolved, its concrete candidate
set is the candidate set that the four rules select when the callee operations
are viewed from the caller's perspective.

#### Proof

For an occupied requirement, the caller binding supplies exactly the most-recent
entry for the contracted position and the entries for the applicable transitive
child positions. These are the entries in `E(s)`. For an empty target
requirement, its caller binding supplies exactly `F(t)`, or no operation when
`F(t)` does not exist. A guarantee supplies the final concrete operation on its
bound position, which is the corresponding most-recent entry. An Action Parent
input supplies exactly the operation named by the Action Parent Rule.

Prefix replacement preserves every position predicate in `P`. Resolving a
placeholder exposes the concrete operation's kind and the dependency paths
between concrete candidates, so the predicates in `M` and the Move Rule's target
Fill comparison are evaluated using the final `>` relation. Duplicate
resolutions of the same operation denote one candidate, as in the candidate-set
definition.

Apply this argument once for each caller in the finite Action Execution chain.
After the final resolution, every placeholder has become the exact concrete
candidate selected by the rules or has contributed no operation. ∎

The Empty and Move comparisons are comparisons on the complete set of concrete
dependencies. A modular compiler may perform a comparison before a caller is
known only when the result cannot change after resolution; otherwise it must
retain enough information to finish the same comparison afterward. An unresolved
requirement, guarantee, or Action Parent input is not a vertex of the complete
graph. By the resolution lemma, all preceding antichain arguments apply
unchanged after resolution.

Automatic destruction contributes ordinary Destroy Particle Operations.
Expanding a Destruction Contract can contribute additional ordinary Destroy
Particle Operations on transitive child positions before the contracted Destroy.
The specification places those operations at the moment of destruction, and each
uses the Empty and Action Parent Rules from the same resolved caller
perspective. Values used by a modular compiler to connect the contributions are
not Particle Operations and are not vertices of the complete graph. Destruction
therefore introduces no additional case in the antichain proof.

## Semantic Model Lemma

Every finite valid Define program, after caller and destruction resolution,
gives an instance of the `ResolvedDefineGraph` structure used by the Lean proof.

### Proof

Give every concrete Particle Operation occurrence its own number, including two
occurrences of the same statement reached through different Action Executions.
The semantic state changes of a valid program can be sequentialized while
preserving every ordering denoted by “previous”; choose one such finite order.
This number is both the occurrence's identity in the model and its order. The
choice does not impose source-code execution order: Particle Operations that are
allowed to execute concurrently can be placed in either permitted order.

Use an injective numeric encoding of each fully resolved position identity as
its position value. Names local to an Action Execution include that execution's
identity, while a contracted position resolves to the caller position to which
it is bound. A caller binding therefore replaces one contracted-position prefix
with its caller-position prefix and preserves and reflects equality and
transitive parent/child relationships within that binding. Operation occurrence
numbers keep operations from different Action Executions distinct even if their
statements and resolved position names are otherwise equal.

For each occurrence `O`, define its rule calculation directly from the
specification:

- its source candidates are the most-recent entries selected for `E(s)`, tagged
  by the positions for which they were selected;
- its optional Fill candidate is `F(t)`;
- its optional Action Parent candidate is the operation selected by the Action
  Parent Rule; and
- its final dependencies are exactly the candidates left by the simultaneous
  Comparison, the Move Correction, the Move Rule's Fill Dependency removal, and
  the Action Parent fallback, in that order.

The Lean types contain structurally possible Particle Operation values that are
not occurrences in this program. Give each such value an empty candidate set and
no dependency. This makes the formal functions total without adding a graph
vertex or a semantic premise.

This immediately gives the formal rule equation. It also gives the cases for
each operation kind required by that equation: a Create has only a Fill
calculation, a Destroy has only an Empty calculation, and a Move has both source
and target calculations. There is at most one Fill candidate and at most one
Action Parent candidate because both rules choose a single most recent
operation.

The source-candidate obligations follow from the definition of `E(s)`. The
tagged position is related to `s`; a non-Move candidate operates on exactly that
position; and a Move candidate operates on that position or a transitive parent
position by the candidate-position invariant. Every candidate is a previous
concrete operation. Most importantly, if a previous operation directly operates
on any position considered by `E(s)`, that position's most-recent entry is
either that operation or a more recent one. This is the formal
`latest_source_candidate` obligation; it is a position-history fact and says
nothing about reachability or minimality.

The Fill obligations follow directly from `F(t)`: if it exists, it is a previous
concrete operation on `t` or a transitive parent position of `t`. The Action
Parent obligations follow in the same way. From the resolved caller's
perspective, every position operated on by an Action Execution is the same as or
a transitive child position of that action's parent position. Thus the Action
Parent candidate's position is related to every position of the operation that
uses it.

Take `occupiedBefore(n, p)` from the valid program state immediately before
occurrence number `n`. Position-reference validity gives parent occupancy and
the required occupied source and empty target preconditions. Create fills its
target, Destroy empties its target and transitive child positions, and Move
relocates the occupied source particle together with its transitive child
positions to the target. These are exactly the transitions in
`ExactOccupancyExecution`. An unused number, if the numbering has one, leaves
occupancy unchanged. None of these obligations mentions graph reachability.

The resolution lemma shows that Action Requirements, Action Guarantees, and the
Action Parent input produce exactly these concrete candidates. For destruction,
each automatic or contributed operation is an ordinary concrete Destroy. A
modular connection before a contribution resolves to the concrete candidates
that precede the first contributed Destroy; a connection after a contribution
resolves to the last concrete child-position operations seen by the contracted
Destroy's Empty calculation. The connection value itself then disappears. Thus
destruction resolution adds concrete Destroy occurrences and their ordinary rule
calculations, but no additional vertex or edge kind.

All fields of `ResolvedDefineGraph` have now been obtained from valid Define
semantics. In particular, neither the reachability-antichain conclusion nor any
equivalent minimality premise was used. ∎

### Validity boundary

The Semantic Model Lemma starts with a valid Define program. Its construction
uses only the operation occurrences and states that the program's validity
permits: every Move source and Destroy position is occupied, every Move target
and Create position is empty, every referenced transitive parent position is
occupied, and every caller input resolves according to its requirement,
guarantee, or Action Parent relationship. It never introduces an operation
sequence merely to make a proof case possible.

`ResolvedDefineGraph` deliberately omits validity conditions that are unrelated
to dependency minimality. For example, its types can describe an abstract Move
with no Fill candidate even though a valid Move cannot reach caller resolution
in that state. Such values enlarge the universal theorem's domain; they are not
used by the Semantic Model Lemma and are not assumptions about valid Define
programs. Proving the result for those extra values cannot supply a missing
premise in the valid-program case.

The Lean theorem file contains no concrete witnesses. The separate
[`particle_operation_dependency_graph_minimality_witnesses.lean`](particle_operation_dependency_graph_minimality_witnesses.lean)
file imports the theorem, so a witness cannot supply any premise to it. The
witness itself has a valid operation history: an entry action creates its
assigned implied position and then destroys it, as in the
[`create_and_destroy_of_an_implied_position` test](../define/testdata/reference_graph/operation_graph_single_action_integration/create_and_destroy_of_an_implied_position/test.dfn).

## Whole-rule-set Theorem

The Particle Operation Dependency Graph produced by the specified rules is a
transitively reduced directed acyclic graph.

### Proof

Acyclicity was proved above. Choose any linear extension of the precedence order
and add the resolved Particle Operations in that order.

The empty graph is transitively reduced. Assume the graph of preceding
operations is transitively reduced and consider the next operation `O`.

- The Fill Rule produces a reachability antichain.
- The Empty Rule produces a reachability antichain.
- The Move Rule produces a reachability antichain.
- When the Action Parent Rule applies, it produces a reachability antichain.

Caller resolution preserves the candidate sets and comparisons used in those
four conclusions. Thus `D(O)` is a reachability antichain in every case.

The Incremental Reduction Theorem proves that adding `O` preserves transitive
reduction. Induction over all resolved Particle Operations proves that the
complete graph is transitively reduced. ∎

Because a finite directed acyclic graph has a unique transitive reduction, this
is the unique graph with the same dependency reachability and no redundant edge.

## Machine-checked proof boundary

From the repository directory, check the executable proof with:

```text
mkdir -p /tmp/define-operation-graph-proof/proofs
lean -t0 -DwarningAsError=true -o /tmp/define-operation-graph-proof/proofs/particle_operation_dependency_graph_minimality.olean proofs/particle_operation_dependency_graph_minimality.lean
env LEAN_PATH=/tmp/define-operation-graph-proof lean -t0 -DwarningAsError=true proofs/particle_operation_dependency_graph_minimality_witnesses.lean
```

The Lean proof represents positions as finite chained names and represents only
concrete Create, Destroy, and Move Particle Operations as graph vertices. Its
rule calculation is definitionally the following complete sequence:

1. the Empty Rule Collection and optional Fill dependency;
2. the simultaneous Comparison;
3. the Empty Rule's Move Correction;
4. the Move Rule's Fill Dependency removal; and
5. the Action Parent fallback exactly when the preceding result is empty.

The relation `RuleGraph.exact_dependency` states that an edge exists if and only
if this calculation retains its dependency. The semantic obligations in
`ResolvedDefineGraph` are direct consequences of valid Define execution:
candidates are previous concrete Particle Operations with the specified position
provenance, the position history returns a candidate at least as recent as every
applicable earlier operation, and Create, Destroy, and Move have their exact
occupancy transitions. The Action Parent position relationship is stated
separately because it crosses an Action Execution boundary.

The structure omits validity constraints that are irrelevant to this theorem.
That omission enlarges the class of graphs covered by Lean: every graph produced
by exact valid Define semantics satisfies these obligations, while some abstract
graphs satisfying them need not come from source code. Proving minimality for
that larger class strengthens the conclusion and cannot make it vacuous.

No premise says that direct dependencies form an antichain, that an edge is
necessary, or that the graph is transitively minimal. Even acyclicity is not a
premise: Lean derives that every edge points to a previous operation from the
candidate rules and then derives acyclicity.

The key non-Move source-candidate lemma is derived from the occupancy
transitions. In particular, Lean proves that after an earlier Create or Destroy
on a strict parent position, the later occupied source must have changed from
empty to occupied at some intervening operation. The most-recent entry selected
for that operation's position then excludes the earlier candidate. The rest of
the proof exhaustively considers Create, Destroy, Move, and Action Parent
results and derives a reachability antichain for every direct dependency set.

Caller-prefix resolution is proved injective and is proved to preserve position
relationships, Particle Operation kinds, operation order, and dependency paths.
The final theorem is quantified over the completely resolved graph, whose vertex
type cannot represent an unresolved requirement, guarantee, Action Parent input,
or modular destruction value. Automatic and contributed Destroy Particle
Statements therefore enter the same exhaustive Destroy case.

Finally, the separate witness file constructs a concrete valid occupancy
execution with a real Create-to-Destroy dependency. This proves that the
combined semantic premises are inhabited by a nonempty graph. The rule cases
themselves are exhaustive conditional proofs; they do not require a fabricated
operation history to make every branch inhabited.

## Scope

This document proves the complete transitive-minimality claim for the Particle
Operation Dependency Graph and proves that the rule comparisons preserve
reachability to the candidates they remove.

It does not attempt to prove every independent semantic premise of the
concurrency system, such as the validity of Action Requirement inference or the
runtime implementation of concurrent execution. Those are separate language
correctness theorems. Given the Fill, Empty, Move, and Action Parent candidate
definitions in the specification, no additional transitive-reduction pass over
the complete graph is required.
