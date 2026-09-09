# Correspondence for Ordinary Creates and Moves

## Scope

This argument derives source correspondence for the ordinary part of the
[requirement construction](requirement-construction.md), before introducing
destruction. The [reference-shape proof](reference-shape-proof.md) supplies the
geometric invariant used below.

Fix the occurrences contributed by a valid serial reference execution. Preserve
their Action Executions, written references, and selected particles. This does
not impose serial runtime execution, require an action's assigned particle to
stay at the caller's position, or impose a dependency on every operation of that
action.

## State and requirements

Starting Define Programs supplies the initially empty view point position and
creates the view point there. Represent that position separately from an Action
Execution's private declarations. Its logical startup Create has no preceding
chained reference; subsequent access to qualities of the view point follows that
creation in the same way as access to qualities of any other particle.

Identify quality-defined positions by their defining particle and declaration,
distinguishing different actions' interface declarations. Identify private local
positions by their Action Execution and declaration. An occupancy component is
empty or gives its occupying particle's identity. Separately record the
existence of created particles with their assigned qualities.

A component alone does not make its position accessible to source code. Resolve
each actual reference from the declaration available to its Action Execution.
Require the exact particle at each intermediate position and the qualities
needed to continue the chain. An implied first position instead directly needs
its defining particle and quality, without a caller-position lookup.

A local declaration supplies its own initially empty position, without an
invented Particle Operation vertex. A Create supplies its new particle and the
qualities assigned by creation. Its defined positions are initially empty;
constructor occurrences contribute their own effects. Assignment and constructor
rules determine these occurrences, but do not make a whole constructor one
indivisible Particle Operation.

A Create requires its actual reference and an empty final position, and changes
that occupancy to its fresh particle. A Move requires both actual references,
the particle selected at its source, and an empty destination. It changes only
its two final occupancy components. It preserves the particle's qualities and
all relative occupancies of its defined positions, whose spatial locations
change transitively with it. Moving a particle does not silently assign
qualities.

## Enabledness in both directions

For the reference part of this correspondence, retain the reference's structure,
not merely its final position. A local reference records its Action Execution
and declaration. A direct implied reference records the assigned particle and
quality declaration. Each further child records its preceding reference, the
particle selected there in the serial execution, and the child declaration. At
execution it must still observe that selected particle at the preceding
position; recording the identity does not grant independent access to it.

An interface position additionally identifies its action declaration, so two
actions' equally spelled local interface names are not identified. Direct access
from that action, or through a directly implied action, requires the assigned
particle and action quality. Access through a caller's occupied position also
checks that preceding reference and its selected particle. Private positions
defined in an Action Statements Block are distinguished by Action Execution
instead and are not exposed as interface positions.

The observations of a local reference are empty. A direct implied reference
observes existence of its assigned particle. A further child additionally
observes its preceding position's occupant and that occupant's existence.
Required qualities are fixed by the same particle's atomic assignments and the
source's explicit-constraint restrictions, not by the runtime schedule.

Induction on this reference structure proves that its requirements hold in a new
state exactly when that state agrees with a valid serial reference state on all
these observations. In the local case there is no observation. In the implied
case the only changing observation is existence. In the child case the induction
hypothesis preserves the preceding reference, and the new occupancy observation
selects the same particle and hence the same child declaration. Both directions
are required: an extra observation could conceal an unnecessary dependency, and
a missing observation could permit a reference to select the wrong particle.
This lemma concerns reference access; it does not by itself prove the geometric
legality of Moves or the preservation of retained state.

If the source occurrence can execute on its specified positions and particles,
its model requirements hold by Position References, Creating Particles, and
Moving Particles. Each change is genuine: a fresh particle differs from every
existing particle; an occupied source differs from empty; an empty destination
differs from its arriving particle.

Conversely, suppose the model requirements hold in a source-reachable state.
Induction along the written reference shows it selects the same final position:
each intermediate supplies the required particle and explicit qualities. A
direct implied reference uses its assigned particle without looking it up in the
caller's position. The final occupancy satisfies the statement's condition. A
Move's selected particle retains the required destination qualities. Its
syntactic prefix restriction is unchanged, and the reference-shape invariant
excludes a cycle or an unrepresented alias between its endpoints. Thus the same
source occurrence can execute.

Both executions give the same relative occupancies and particle identities.
These determine the same spatial relationships, including empty positions
defined by moved particles. This does not freeze a Move's transitive child
particles to the list in the reference execution: an independent Create can fill
a moving position before or after that Move.

To obtain an exact effect, combine the reference observations with the final
occupancy requirements. For Create include nonexistence of its new particle; for
Move include both references and both final positions. At each observed
component require its value in the valid serial state. At every other component
make no requirement. This preserves exactly the source requirements by the
reference lemma and the final-position conditions, even when two references
observe the same component. No arbitrary choice between inconsistent
observations is needed: the valid serial state supplies their common value.

Create changes its target from empty to its fresh particle and changes that
particle's existence from absent to present. Move changes its occupied source to
empty and its empty destination to the selected particle. The endpoints of an
enabled Move differ, because one is occupied and the other is empty. Thus every
changed component was required and genuinely changes value. All other components
are unchanged. These facts derive exact-effect validity and equality of the
occupancy transitions; validity is not an additional premise imposed on Define
programs.

There is also a state invariant independent of reference accessibility: an
occupied position's particle exists, and a particle occupies at most one
position. It holds initially for empty positions. Create preserves it because
its selected fresh identity does not yet exist, hence cannot already occupy
another position. Move preserves it by emptying the selected particle's unique
source while filling the empty destination, without changing existence. This
does not prove the stronger geometric acyclicity invariant, but supplies the
single-occupancy premise that the reference-shape argument uses.

## Exchange and graph consequences

For two consecutive enabled occurrences, suppose neither changes a requirement
of the other. Both preserve the other's actual references, final occupancy, and
needed particle existence. The second is therefore enabled first, and the first
remains enabled afterward. Their disjoint relative changes give the same final
state. This proves Create/Create, Create/Move, and Move/Move exchange; the
reference-shape invariant supplies geometric validity at each step.

For a conflicting adjacent pair, reversal fails an actual requirement. An
unperformed Create has not supplied the needed particle or quality-defined
position. An unperformed occupancy change has not supplied the selected source
or intermediate particle, or has not emptied the destination. A Move executed
before an earlier use leaves that use's required position empty. These are
source failures by the two-direction correspondence, not merely changes in
compiler bookkeeping.

Orient conflicts by the reference execution. Last setters and intervening uses
have exactly that conflict reachability, by the
[exact-effect collection argument](../definitions/operation-effects.md#collecting-conflicts-without-comparing-every-pair).
Particle-existence requirements follow the unique creator; this scope has no
subsequent removal of existence. The respecting-permutation argument therefore
proves safety. Separately, the adjacent-cover argument proves necessity of each
cover edge. Combined with the independent reduction argument, this establishes
inclusion-minimal safety for this construction and chosen orientation within the
stated scope.

In particular, a directly implied Create can exchange with a Move of its
defining particle. A Create whose written reference goes through that Move's
destination cannot. Flattening both references to the same spatial name would
lose the correspondence proved here. Saved selections and retained destructor
state are handled by the [retained-state proof](retained-state-proof.md); they
cannot be added to this result just by calling their records occupancy
components.

## Formalized correspondence

`particle_requirements.lean` checks the structured-reference observation lemma,
both directions of operation enabledness, genuine effect changes, equality of
the occupancy transitions, and preservation of existence and single occupancy.
It also represents a selected vacancy separately from a written Vacate target:
the former has no invented reference chain, while the latter retains its
reference requirements. Neither removes particle existence as its vacancy
effect. Those distinctions use the separate destruction argument, not an
extension of ordinary Move geometry by assumption.

`particle_scheduling.lean` checks execution correspondence by induction over
schedules and applies the incremental calculation's scheduling and
edge-necessity theorems to these operations. It does not take exact-effect
validity as a source-specific premise. Valid source reference permissions and
geometric accessibility are derived by the English arguments above; they are not
checked by parsing or validating Define source in these Lean modules.
