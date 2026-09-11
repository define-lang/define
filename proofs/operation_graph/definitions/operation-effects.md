# Exact Requirements and Changes

## Scope

This mathematical model supplies generic occupancy and graph lemmas. Its
exchange and noncommutation results do not include Define's relationship
conditions: componentwise enabledness alone cannot exclude a circular particle
arrangement. The final section states the scope of its source correspondence.

Fix a set of state components `K` and a value type `V`. A state assigns a value
to every component. An effect specifies a partial assignment `requires` and a
partial assignment `changes`. It is enabled when every required component has
the specified value. Executing it replaces the changed components and leaves all
other components unchanged.

Call an effect valid when each changed component has a required preceding value
and the new value differs from that preceding value. This is a mathematical
property to prove for a translation, not an additional Define rule. Requiring
the preceding value means the model preserves each operation's observations, not
just its final state.

Two effects conflict when either changes a component required by the other.
Every changed component is also required, so this includes conflicts between two
changes. They are independent when there is no such conflict.

## Independent adjacent effects exchange

Suppose `A` is enabled in `s`, and `B` is enabled after executing `A`. If they
are independent, `A` changed none of the components required by `B`. Thus `B`
was already enabled in `s`. Conversely `B` changes none of `A`'s required
components, so `A` remains enabled after executing `B` first.

At each component either neither effect changes it, or exactly one does. Both
orders therefore give the same final value at every component. All requirements
of both effects are observed in both orders. This proves the adjacent exchange
without any graph or minimality premise.

## A conflicting adjacent pair cannot exchange

Suppose again that `A` and then `B` are enabled.

If `A` changes a component that `B` requires, let its preceding value be `x` and
its changed value `y`. Validity gives `x ≠ y`, and enabledness of `B` after `A`
means that `B` requires `y`. Executing `B` first instead observes `x`, so it is
not enabled.

Otherwise the conflict is a component changed by `B` and required by `A`. If `B`
is not enabled first, the reversal is already invalid. If it is enabled first,
its preceding required value is the value that `A` observes in `s`. `B` changes
that value to a different one, so `A` is not enabled afterward.

Thus the reversed pair cannot be enabled. The proof depends on genuine changes
and exact requirements. It cannot be applied to a made-up bookkeeping change or
to a redundant requirement added solely to force a desired ordering.

## Scheduling exact effects

Fix one valid serial execution of these mathematical effects. Orient every
conflicting pair according to that execution and take transitive closure.
Adjacent incomparable occurrences are independent, so the exchange lemma is the
semantic ingredient for schedule safety. Apply the
[finite linear-extension correspondence](../theorems/external-results.md#finite-schedules-and-adjacent-exchanges):
conflict reachability is a strict partial order, and the two duplicate-free
schedules list the same finite occurrence set. The cited connectivity result
supplies the sequence of incomparable adjacent exchanges. Its Lean counterpart
is `respecting_permutations_connected` in `finite_schedule_order.lean`.

Lift an exchange through a whole schedule by executing its unchanged prefix,
exchanging the enabled adjacent pair in the state reached there, and executing
the unchanged suffix from the equal resulting state. Induction over the finite
exchange sequence proves that every respecting permutation executes with the
same final state and every effect's exact requirements satisfied. This is the
conditional theorem `respecting_permutation_executes` in
`effect_scheduling.lean`; its hypothesis explicitly requires distinct
incomparable occurrences to have independent effects. It does not assume an
unproved source-to-effect translation.

## Necessity for a fixed orientation

Write `A < B` when the oriented conflict relation has a path from `A` to `B`.
This is an irreflexive transitive relation: every step strictly advances in the
reference execution. Consider a pair `A < B` in the standard
[cover relation](../theorems/external-results.md#cover-relations). It must be a
direct conflicting pair. A longer conflict path would supply such an `X`.

The following construction makes the pair adjacent in a respecting schedule.
Take all predecessors of `B` other than `A`, in reference order, then `A`, then
`B`, then every remaining occurrence in reference order. This is a permutation
of the reference schedule. Its first part is closed under predecessors: a
predecessor of a predecessor of `B` is also a predecessor of `B`, and cannot be
`A`, since that would contradict the cover property. Every predecessor of `A` is
in the first part, by transitivity. Every predecessor of `B` is now before `B`.
Finally, a remaining occurrence's predecessors either were placed in the first
parts or retain their reference order in the last part. Thus the whole schedule
respects `<`.

Safety, proved above without minimality, supplies an execution of this schedule.
Exchanging just the adjacent `A` and `B` makes that execution fail by the
conflicting-pair lemma. The exchange changes no other pair's relative order.
Consequently any graph contained in `<` that omits the cover edge admits an
invalid schedule. In particular, every graph with the same reachability must
contain it, and removing it from the cover graph is unsafe.

This is inclusion-minimal safety within the chosen orientation. It does not
assert that an edge is present in every safe graph with a different orientation.
The two-destructor example shows why that stronger assertion is false. The
generic finite adjacent-cover construction is formalized by
`cover_pair_has_adjacent_respecting_permutation` in
`finite_schedule_order.lean`. The execution obstruction is
`conflicting_cover_has_unsafe_reversal` in `effect_scheduling.lean`. Its
hypotheses retain both the conflict of the selected cover pair and independence
of distinct incomparable occurrences; deriving these from the chosen conflict
closure is separate from source correspondence.

## Collecting conflicts without comparing every pair

Assume a finite reference execution in which each effect mentions finitely many
state components. For each component, keep the most recent effect that changed
it and the effects that have required it without changing it since that change.
Initially there is no preceding change and the latter collection is empty.

Process the occurrences in reference order. An occurrence that only requires a
component follows its most recent change, if any, and joins that component's
collection of requirements. An occurrence that changes a component follows that
component's most recent change and all its collected requirements; it then
becomes the most recent change and clears the collection. Process a change once,
not also as a separate requirement by the same occurrence.

Every edge obtained this way is an oriented conflict. Conversely, consider two
conflicting occurrences sharing a component. If the earlier one changes the
component, successive changes form a chain from it to the last change before the
later occurrence. The later occurrence follows that last change. If the earlier
occurrence only requires the component, the later one must change it. The first
intervening change follows the collected requirement; successive changes then
lead to the later occurrence. If there is no intervening change, the later
occurrence directly follows the collected requirement. In all cases the
collected graph has a path for the original conflict. Its transitive closure is
therefore exactly `<`.

This construction uses work proportional to the total number of mentioned
components and emitted candidate edges: a requirement is collected once and
consumed at most once for that component. It does not compare every pair of
occurrences. This is a bound for the explicit mathematical effects, not a bound
for compiling Define: expanding a Move into every transitive child position may
itself be too expensive.

The componentwise collection is formalized by `Collected` in
[`effect_collection.lean`](../theorems/effect_collection.lean). Its
`collected_reachability_iff` theorem proves equality with oriented conflict
reachability, and `incomparable_collected_independent` derives independence
instead of taking it as an additional scheduling premise. These are generic
effect results. The
[scheduling argument](../theorems/requirement-scheduling-proof.md) separately
checks relationship conditions for Define; it does not infer geometric legality
from independence in this component model.

The union of these edges is not necessarily transitively minimal. For example,
start with `x = y = 0`. Let `A` change `x` to `1`; let `B` require `x = 1` and
change `y` to `1`; let `C` require `x = y = 1`. Collection produces `A → B`,
`B → C`, and `A → C`. The last edge is redundant even though it comes from the
most recent change of `x`. Thus this collection supplies a complete candidate
set, not a proof that keeping its union achieves the specified minimality. A
Comparison must therefore exclude redundant candidates before they become
dependencies. The
[requirement construction](../theorems/requirement-construction.md) proves that
Comparison itself produces transitive minimality, independently of schedule
safety. Its formalization in `effect_graph.lean` checks the incremental
calculation using already-calculated dependencies and proves that it preserves
exactly the collected reachability. The cover-graph characterization describes
the result; it adds no construction step or generic minimization algorithm.

## Source correspondence and geometric scope

Applying these component lemmas to Define's occupancy calculation requires:

- State components describe actual semantic distinctions: particle identity,
  occupancy and the distinction between vacancy and retained destructor access.
  Reused position names alone do not identify all these components.
- The required values are exactly what the source operation needs. In
  particular, an implied-position access by a destructor must not acquire an
  invented requirement that its assigned particle still occupies its former
  position.
- A Move's representation preserves its transitive spatial effects, including
  empty defined positions. It must not require a fixed list of transitively
  moved particles: the
  [ordinary correspondence](../theorems/ordinary-requirements-proof.md#spatial-correspondence)
  permits a moving defined position to be filled before or after the Move. A
  representation using relative occupancy must preserve the identities selected
  by explicit chained references, without retraversing them during execution.
- Simultaneous vacancy uses the common selected particles. Changes in the
  representation must not clear the original state still used by destructors.
  Distinct destructors using the same original particle must access the same
  changing state, not independent snapshots.
- Every changed component genuinely changes, and every required component is
  necessary for the claimed observation. Artificial requirements would prove
  minimality only for an unnecessarily restrictive model.
- Endpoint enabledness corresponds in both directions, preserving the chosen
  particles and positions. Full Define enabledness additionally requires the
  relationship conditions; an enabled component transformation can otherwise
  form a transitive cycle.

The [ordinary correspondence](../theorems/ordinary-requirements-proof.md),
[retained-state argument](../theorems/retained-state-proof.md), and
[scheduling proof](../theorems/requirement-scheduling-proof.md) address these
obligations in English. The generic Lean effect theorems do not themselves
formalize that source correspondence. Their adjacent-exchange results cannot
show that all legal Define schedules are connected by legal exchanges, or that
an ordinary cover edge is necessary when relationship conditions already imply
its ordering.

The model does not prescribe storing one record per affected transitive child
position in the compiler. The collection bound above is not a bound on the
compiler's representation or on the reachability queries used by Comparison.
