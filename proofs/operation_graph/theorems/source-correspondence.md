# Source Correspondence of Particle Operation Scheduling

## Statement and scope

Fix a finite valid serial interpretation, including a permitted order of sharing
destructor operations. Retain its particular particles, positions, Action
Executions, and operation occurrences. Exclude the Action Parent Rule.

Ordinary dependencies preserve the ordered effects on those positions and supply
required Creates. Vanish dependencies preserve required particle existence.
Relationship conditions exclude exactly the circular arrangements among orders
respecting those dependencies. The completion search accepts exactly prefixes
extensible to such a complete order.

These claims concern the specified Particle Operations, not unspecified values
or external calls. They do not assert that ordinary edges and relationship
conditions together form an irredundant representation. Ordinary transitive
minimality is a separate graph-theoretic result.

## From source names to identified operations

The [ordinary correspondence](ordinary-requirements-proof.md) resolves each
Position Reference in the serial interpretation. Induction along the chain uses
its validated occupied intermediate positions and the selected particles'
assigned qualities to identify the final position.

Positions retain their defining particles through Moves. Replacements supply
different positions. Interface positions belong to the assigned action and
persist across executions; positions declared in an Action Statements Block
distinguish those executions. Both require the action's parent particle to
exist.

The [action-boundary correspondence](action-boundary-correspondence.md) applies
these bindings to contracted chains. A position defined by a particle supplied
through an interface requires that supplied particle, not the interface's
defining particle merely because the serial reference passed through it.

The specification makes execution act on these identified endpoints. It does not
repeat reference traversal in a reordered arrangement. Thus the chain induction
establishes identity, not a runtime requirement that every written intermediate
retain its serial occupancy.

A Create fills its identified empty position with a fresh particle. A Move
empties its identified source and fills its identified target with the same
selected particle. Its qualities and its own defined positions do not change.
Atomic Creation supplies those qualities; constructor operations remain separate
effects. Destination constraints concern the selected particle and therefore
remain satisfied when its operations are reordered.

For destruction, the [retained-state argument](retained-state-proof.md) keeps
the original selection distinct from current shared occupancy. Every Vacate has
its own selected particle and position. Sharing destructors use the same
changing originals, not copies or replacements. Nested destruction applies the
same rules to its selected particles, including temporary particles.

## Correspondence of the specified phases

| Spec calculation                  | Mathematical correspondence                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Position Setters                  | The last operation affecting each actual position, initialized with its defining particle's Create when present.               |
| Collection                        | Precedence between consecutive effects on each endpoint position.                                                              |
| Comparison                        | The maximal candidates under already-calculated prerequisite reachability.                                                     |
| Recording the Operation's Effects | Advance exactly the affected endpoint setters.                                                                                 |
| Processing Destructor Operations  | Inherit original setters and update shared destruction state, without a selected-Vacate barrier.                               |
| Recording Vanish Information      | Record every actual defining-particle or selected-particle requirement, not particles used only in serial name resolution.     |
| Completing Vanishes               | Keep exactly the lifetime candidates that can be last in a permitted non-Vanish order.                                         |
| Collecting Parent Relationships   | Merge successive direct associations with the same parent; end preservation after Vacate and the last direct destruction Move. |
| Relationship Conditions           | Exclude simultaneous presence of all relationships of any simple directed cycle.                                               |
| Choosing Among Permitted Orders   | Search jointly compatible alternatives, including any already executed prefix.                                                 |

The [construction proof](requirement-construction.md) proves the setter,
candidate, and Comparison invariants without assuming schedule safety.
Equal-recency Vacates affect distinct selected positions and cannot collect one
another through a reference traversal. Their enumeration adds no precedence.

The [Vanish proof](vanishment-proof.md) derives lifetime completeness and
independent insertion. The [relationship proof](relationship-ordering.md)
derives cycle exclusion from operation effects, including the occupied result of
a final destructor Move before preservation ends.

## Safety and equality of logical results

For each position, ordinary dependencies preserve its sequence of occupancy
visits. Induction over that sequence supplies each operation's required endpoint
values. Initial setters and successive occupied-source setters supply every
required Create. Vanish cannot precede an operation requiring its particle or a
position defined by that particle.

Each particle's direct Moves also retain their order. It therefore has at most
one current position. A destruction selection does not add another incoming
association, and ending occupancy preservation removes the current association
rather than restoring the selected position.

These facts establish endpoint and existence enabledness in both directions: the
identified operation is enabled exactly when its specified endpoint values and
required particles are available, subject also to relationship legality. The
relationship-period theorem supplies that additional condition at every
operation effect. It does not infer geometric legality from source spelling or
from ordinary dependency acyclicity.

The final projection at every position equals the serial projection; particle
identities and assigned qualities also agree. Ending preservation removes the
same selected incoming occupancies once their uses finish. The resulting
relative arrangement is therefore the same. This is a componentwise argument,
not an assumption that all permitted schedules are connected by legal adjacent
swaps.

## Exactness of the permitted orders

Conversely, an execution of these same identified occurrences that preserves the
specified occupancy visits, existence requirements, and acyclic arrangements
respects every setter precedence and lifetime requirement. Comparison preserves
their reachability. Its acyclic arrangements satisfy every relationship
condition by the interval characterization.

Thus the construction admits exactly those complete orders. A prefix belongs to
one of them precisely when the finite alternative search succeeds. This
equivalence permits alternative safe orientations rather than choosing one
during compilation.

This conclusion does not establish semantic necessity of each separately drawn
edge or each collected condition. Multiple relationship conditions can jointly
imply another condition or an ordinary precedence. The action-boundary theorem
establishes finite composition when each contribution preserves the specified
construction-state transformation. It does not justify substituting smaller
summaries that discard part of that transformation, or extending the finite
search to an unbounded future.

## Formalization boundary

The generic Lean Comparison and terminal-extension theorems apply to the
ordinary graph calculation when its candidates have the correspondence proved
above. A formal model that rechecks written intermediate occupancy instead has
different requirements and cannot discharge this source theorem.

Full formal correspondence requires serial identity resolution, identified
effects, shared destruction state, and relationship conditions in the same
model. Graph-theoretic verification alone does not prove those source facts.
