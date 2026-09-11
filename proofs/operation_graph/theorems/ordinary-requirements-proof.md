# Correspondence for Ordinary Creates and Moves

## Scope

Fix ordinary operation occurrences obtained from a valid serial interpretation,
with their particular particles, positions, and Action Executions resolved as
specified by Identifying Particles and Positions. Destruction's preserved
occupancy is handled separately.

The result establishes correspondence of Create and Move effects and their
occupancy and lifetime requirements. Geometric legality additionally uses the
[relationship conditions](relationship-ordering.md).

## Resolution from source

Resolve a local position by its declaration and Action Execution. Resolve an
implied quality from the action's parent particle. Resolve an interface position
from its action and declaration. For a further name in a chain, the serial
occupant of the preceding position supplies the explicitly required quality.

Induction over the chain identifies its final position. The source validation
rules supply the first declaration, occupied intermediates, and explicit
constraints at each step. Moving a particle does not replace its qualities, so
the position identified through it retains the same defining particle through
subsequent Moves. A replacement supplies different identities.

This induction is performed in the serial interpretation. It does not assert
that the intermediates remain occupied during reordered execution. The
specification explicitly makes execution act on the position already identified.

## State representation

Record the occupant or vacancy of each actual position and the existence of each
particle. Positions retain their defining particles, including positions defined
by actions. A fresh identity is assigned to each Create occurrence; distinct
Action Executions do not reuse that identity.

Starting Define Programs supplies the view point position and its Create.
Declaring a local position supplies an empty position for that Action Execution,
not a separate Particle Operation. Its operations still require its defining
particle to exist. Atomic creation supplies all required qualities before
operations use them; constructor Particle Operations have their own effects.

## Enabledness and effects

A Create's resolved target must exist and be empty, and its particle must not
yet exist. These are exactly the specified requirements. It makes the particle
exist and fills that target. The occupied and empty values differ, and the
particle is fresh, so these changes are genuine.

A Move's resolved source must hold its selected particle and its resolved target
must exist and be empty. Its selected particle and both positions' defining
particles must exist. These requirements preserve the specified source and
destination, rather than accepting whichever occupant happens to be present. The
endpoints differ because they have different occupancy.

Destination quality constraints hold for the selected particle from source
validation and identity preservation; executing a Move does not change those
qualities. The Move empties its source and fills the target with that same
particle. It does not change occupancy of its own child positions.

Thus the source operation and the model effect have identical endpoint and
existence enabledness in both directions. To conclude full Move legality, also
require absence of a circular relationship in its resulting arrangement. That
additional requirement is not hidden in the occupancy model.

## Ordered position effects

For each actual position, project the serial interpretation to the Creates and
Moves filling or emptying it. Its setters form a chain in that order. Collection
includes the preceding setter, and Comparison preserves the reachability of
these candidate pairs.

Every execution respecting that reachability has the same projection at the
position. Induction along the projection gives the same required occupant or
vacancy before each effect. In particular, the proof preserves source-ordered
visits to a position even if two whole visits could otherwise exchange without
changing the final vacancy.

The initialized setters also supply all required creations. Prove this by
induction over collection. A position's first setter is its defining particle's
Create. Each subsequent setter follows that initial setter through the
position's preceding setters. An occupied source's setter filled it with the
selected particle: a Create supplies that particle directly, while a Move
inherits its particle's Create through its own source setter. Thus a Move or
Vacate also follows the selected particle's Create. Initially supplied positions
have their stipulated existence instead. No separate collection of these Creates
is needed.

This proof does not use the Vanish calculation or the relationship conditions.
Those later restrictions cannot invalidate its precedence paths. The same
induction applies to a destructor's inherited original setter.

Apply this argument independently to each position. A Move participates in two
projections but is one occurrence: its source and target changes are its one
specified effect. No reference chain is added to either projection. The
preceding induction supplies every required particle Create, so the required
defining particles also exist in this ordinary scope without Vanishes.

Consequently a respecting execution has the correct endpoint requirements and
the same final occupancies and particle identities as the serial interpretation.
This componentwise argument does not require its permitted orders to be
connected by adjacent legal exchanges.

## Spatial correspondence

The fixed defining-particle associations and the current occupancies determine
the relative spatial relationships. Moving a defining particle moves its child
positions, including empty ones, without changing these associations. An
independent child Create can occur before or after the parent Move; only the
former order moves the newly created child with it. Both orders have the same
resulting relative arrangement.

The relationship-period characterization checks circularity throughout the
execution, not merely at its end. Combining that result with ordered position
effects gives ordinary Create/Move safety without requiring intermediate
occupancy or an ancestor-wide lifetime.

## Mathematical and formalization boundary

The generic exact-effect collection and Comparison lemmas apply to these
occupancy and existence components. Their graph minimality results concern
ordinary precedence. They do not prove necessity of edges in the presence of
alternative relationship conditions, or minimality of the representation of
those conditions.

A structured-reference model that rechecks written intermediates at execution
time does not represent this construction. Formal source correspondence must use
serial resolution followed by these identified effects, and separately verify
the relationship conditions.
