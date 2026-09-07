# Requirements Derived from Particle Operations

## Premises and scope

Position requirements and particle requirements are categories used by this
proof, not additional Define rules. Their premises are Position References,
Assignment Semantics, Requirements Follow Particles, Creating Particles, Moving
Particles, and Destroying Particles in the specification, interpreted using the
[conceptual definitions](definitions.md#conceptual-meaning-of-particles-positions-and-operations).

These semantic requirements are derived independently of the graph calculation.

## What an operation must preserve

### The position described by the actual reference

A reference describes a position from the perspective of an Action Execution.
Each intermediate position in a written chain must be occupied. The particle at
each such position supplies the qualities needed to continue the chain. Merely
finding some particle there is insufficient when that would select a different
particle's defined position.

A direct implied-position reference instead refers to a quality assigned to the
action's own particle. Assignment Semantics makes that quality directly
available to the action. Moving the particle does not remove the quality or
replace the position it defines. No rule requires that particle to stay at the
position through which the caller originally created or accessed it.

Consequently the same position can be accessed with different requirements:

| Written access                                 | What supplies the position                | Additional occupancy requirement        |
| ---------------------------------------------- | ----------------------------------------- | --------------------------------------- |
| Constructor's `position</marker>`              | Its assigned particle and implied quality | None at the caller's `source` or `dest` |
| Caller's `position<source>::position</marker>` | The particle occupying `source`           | That particle must occupy `source`      |
| Caller's `position<dest>::position</marker>`   | The particle occupying `dest`             | That particle must occupy `dest`        |

Each access additionally needs the final position's occupancy required by its
statement. These distinctions must survive resolution from the caller's
perspective. Recording only a full spatial name loses the reason that the
position is accessible.

The absence of a requirement to occupy `source` is not the absence of all
particle requirements. The particle defining `/marker` and the quality defining
that position must exist and be available to the operation. Preservation of
particle identity alone does not grant arbitrary access through a position
reference whose required occupancy no longer holds.

### Final-position occupancy and particle identity

Create requires its target empty and makes it occupied by a new particle. Move
requires its source occupied by the selected particle and its destination empty;
it empties the source and fills the destination with that same particle. It also
requires distinct source and destination references, the specified restriction
against moving a particle into a position it defines, and the destination's
required qualities.

Vacate requires a particle selected for destruction. A Destroy Particle
Statement selects its target and the particles in its transitive child positions
from the common state immediately before destruction. Its individual Vacates are
not fresh evaluations of the statement after preceding Vacates.

These occupancy and identity requirements are different. Moving a particle away
and putting another at its former position restores occupancy but does not
restore the original particle or its defined positions. Replacing a destroyed
parent can restore the same spatial child position without making a retained
original child the replacement's child.

### Spatial movement versus occupancy of a defined position

Let `P` define position `q`. The position of `P` in space and the occupancy of
`q` are separate facts. A Move of `P` changes the former. It moves `q` and, if
present, the particle occupying `q`; it does not fill or empty `q` relative to
`P`. The same statement applies transitively to positions defined by those
particles. Empty defined positions move as well.

A representation may describe these spatial effects by recording which particle
defines each position and which particle occupies it, then deriving spatial
relationships from those associations. That is a representation of physical
movement, not a claim that movement is only a change of names. It must still
check the occupied intermediates of each actual position reference.

In particular, the transitive particles moved need not be a fixed list copied
from the serial reference execution. An independent Create may fill a moving
defined position before or after the Move. In the former case the new particle
moves with it; in the latter case the empty position moves and is then filled.
The operations must preserve their specified requirements, not an invented
requirement that every transitively moved particle already exist.

### Vacancy and continued existence

A Vacate vertex denotes vacancy, not completion of destruction. Original
particles remain available for destructor operations under Simultaneous
Transitive Destruction. Distinct destructors share those particles and their
changing state. There is no separate original particle for each destructor.

An ordinary operation requiring an occupied position can conflict with the
vacancy of that position. A destructor's operation requiring the continued
existence of an original particle instead constrains when that particle may
cease to exist. The latter does not, by itself, constrain its vacancy vertex.

The [Vanish rules](../theorems/vanishment-proof.md) distinguish an actual
requirement for a particle's existence from movement with an ancestor. The
latter does not, by itself, prolong lifetime after Vacation or change child
occupancy.

## An exchange proved from these requirements

Let `P` occupy `source`, let `dest` be empty, and let `P` define an empty
`/marker`. A constructor on `source` accesses `/marker` directly as an implied
position. Compare its Create with the caller's Move of `P` from `source` to
`dest`. Assume no additional destination constraints beyond qualities already
assigned to `P`, and no other operations between the pair.

The constructor's Create needs `P`, its position quality, and an empty
`/marker`. The Move changes none of those requirements. The Move needs `P` at
`source` and an empty `dest`; creating the marker changes neither. Both
operations are therefore enabled in both orders. In both orders the constructor
creates the same new particle in the position defined by `P`, and the caller
moves the same `P` between the same two positions. Afterward `P` occupies
`dest`, its `/marker` is occupied, and `source` is empty. Both the operation
requirements and the resulting spatial relationships are preserved.

This does not assume that identity permits retargeting a chained reference. A
Create written as `source::/marker` would require occupancy at `source`, which
the Move removes. A Create written as `dest::/marker` would require occupancy at
`dest`, which the Move supplies. Those explicit accesses cannot exchange with
this Move in the same way.

For a direct implied Vacate of the marker particle with no destructors of its
own, the argument is analogous. The selected target is the position defined by
`P`, not a reference through the caller's `source`. The Move preserves both `P`
and the marker's occupancy relative to it. Vacate empties only that defined
position and does not change occupancy at `source` or `dest`. No external effect
or additional destructor operation is part of this particular exchange.

This justifies the constructor integration example with two constructors that
successively Create and Vacate particles in the same implied `/marker`. Their
four operations remain ordered by occupancy of `/marker`. The parent Move need
not wait for them. The caller's subsequent Create at `dest::/marker` must wait
for both the Move and the final constructor vacancy: they satisfy different
requirements of that one Create.

## Ancestor destruction does not extend every lifetime

Suppose `P` occupies `parent` and defines `/child`, occupied by `Q`. The
position quality `/child` requires the constructor `/construct_child`. That
constructor implies `/leaf` and Creates `R` using the direct reference
`position</leaf>`. The caller's relevant statements are:

```text
create a particle in position<parent>.
create a particle in position<parent>::position</child>.
destroy the particle in position<parent>.
```

The second Create triggers `/construct_child`. In the serial reference
execution, its Create of `R` precedes the caller's destruction, which selects
`P`, `Q`, and `R` for simultaneous destruction.

The individual Vacates share logical recency. That does not require every
individual Vacate to wait for all ordinary operations preceding the group in the
reference execution. The Vacate of `R` must wait for the Create of `R`; that
Create in turn requires the creation of `Q`, which supplies the implied position
to the triggered constructor. The Create of `R` does not traverse `parent` or
use `P` to obtain `/leaf`.

Consequently `P`'s vacancy can precede the Create of `R`. This is not justified
by assuming that `P` remains alive for that Create: in the absence of another
actual interaction requiring `P`, its destruction can finish before the Create
of `R` as well. The fact that `Q` occupied a position defined by `P` does not
make every subsequent operation on a position defined by `Q` an interaction with
`P`.

Requirements on a particle must not be propagated to every transitive ancestor
merely because those relationships occur in the serial reference execution.

This conclusion supplies neither an order between Vacates nor an exemption from
an actual interaction. A destructor that accesses contracted positions can still
impose the lifetime constraints specified by Destruction Ordering During
Destructors.

## General exchanges and graph construction

These examples alone are not a complete classification of Particle Operations.
The [general construction](../theorems/requirement-construction.md) and
[scheduling argument](../theorems/requirement-scheduling-proof.md) handle both
references of Moves, geometric restrictions, selected vacancies, and shared
retained state. In particular, they do not treat a simultaneous selection as
repeated current-state reads by its individual Vacates.

The [exact-effect lemmas](operation-effects.md) can be used only after the
chosen representation preserves these requirements. Representing every
transitive spatial change as a write to a fixed spatial-name occupancy component
would reject the exchange just proved. Likewise, omitting reference requirements
to make more pairs independent would admit invalid explicit accesses.

Future value operations and external calls are not premises of this proof. If
they require ordering, their specified interactions will need to be represented
by the Particle Operation Dependency Graph; the current exchange does not prove
that unspecified observations commute with movement.
