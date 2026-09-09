# Reference Shape and Ordinary Moves

## Purpose and scope

The requirement construction must not assume that two Moves are safe merely
because a generic occupancy map gives them different entries to change. Such a
map can describe positions that Define source cannot access, including a
particle placed in the private local position of its own Action Execution.
Moving that particle to one of its own implied positions would create a cycle,
despite the two written position names being different.

This argument concerns ordinary Create and Move operations and their position
references. The correspondence for selected vacancy and retained destructor
state is separate. It uses Local Naming is Enforced, Position References,
Interface Positions, No Transitive References, and Cannot Move a Particle Into a
Position It Defines. No compiler behavior supplies a premise.

## An auxiliary representation of accessibility

For this argument only, describe how a position can be named by attaching its
declaration to the particle whose quality supplies it. Distinguish an action's
interface declarations by that action quality. Also attach each Action
Execution's private local declarations to the identity of the particle assigned
that action, distinguishing separate executions.

The last attachment is a mathematical scope association, not a claim that a
private local position moves spatially with that particle or needs its continued
existence. It must not be used to add a dependency to the Particle Operation
Dependency Graph. This representation answers an accessibility question, not a
lifetime or spatial-movement question.

Connect a position to the particle occupying it. Each occupied particle has one
such incoming association. Each declaration has one supplying particle or, for
the initial anonymous position, no supplying particle. Action Execution
identities distinguish repeated private declarations without identifying them
with other executions' positions.

Every position reference in one Action Execution starts with a declaration
available to that execution: an implied quality, an interface position, or a
local position. It can then follow occupied positions and explicit qualities. It
cannot enter another execution's private local declaration. Position References
permits a local name after an action name only when the position is defined in
the Action Definition Block; private locals are instead defined in the Action
Statements Block.

Local Naming is Enforced prevents an action from using a second globally
qualified spelling where its local name is required. No Transitive References
prevents a path through an implied quality from providing an alternative access
to a quality on the same particle. Thus legitimate references from one execution
describe paths from that execution's supplying particle with distinguishable
first declarations. Their shared initial position names describe their shared
path; they do not provide independent aliases to an otherwise inaccessible
ancestor.

## Preservation of acyclicity

Begin with the initial particle and empty available declarations. Creation adds
a new particle at an empty position; assigning its qualities and introducing an
execution's locals adds empty declarations. These extensions introduce no cycle.
Multiple assignments of the same quality are not multiple declarations:
Duplicate Assignments makes only the first assignment take effect.

This describes introduction in the serial reference execution. It is not a
runtime requirement that every operation on a private local position wait for
creation of the action's assigned particle. When considering such early local
operations, keep the future particle identity and its private declarations in
the auxiliary representation without claiming that the particle exists yet. An
implied or interface reference still needs the assigned particle and cannot be
used early. Purely private references have no path to that future particle's
caller: private declarations cannot be traversed from another execution, and the
future particle has not acquired an incoming occupied position. Thus these early
operations can only create particles in the private declarations or operate on
particles accessible from them. Both references of any Move have that same
restriction. They cannot obtain the future assigned particle and place it in one
of its own private positions.

Introducing that assigned particle therefore joins its private declarations to
the position used by its creator without making a cycle. The creator's execution
cannot already reach those private declarations through a written reference to
the uncreated particle. Repeating this argument covers private operations of
further Action Executions triggered by the early Creates. These auxiliary
identities permit reasoning about source occurrences before their serial
placement; they do not make an uncreated particle available to an actual
position reference.

The provenance of those early private particles is essential to this argument.
In the serial reference execution, an Action Execution follows creation of its
assigned particle. Every particle created by its purely private work, and every
particle created by further executions reached solely through that work, is
therefore created later than that assigned particle in the serial execution. At
runtime, before the assigned particle has been created, no operation can import
an older particle into this private collection: an access through an implied or
interface position needs the uncreated particle, and an outside execution cannot
access its private declarations. Induction over these early private operations
preserves that restriction under Moves as well as Creates.

In particular, the assigned particle's own creator cannot be one of those early
private particles. The particle assigned its creator's Action Execution must
already exist in the serial execution, whereas each such private particle is
created later. Nor can that creator name a private declaration of an execution
it cannot access. This excludes a creation that would attach the future particle
below one of its own early private particles. Freshness alone, without this
source-order and accessibility argument, would not exclude that cycle. These
serial facts describe where source occurrences originate; they add no runtime
dependency on the Action Parent Rule.

Suppose the auxiliary associations are acyclic before a Move. Moving the source
particle changes its one incoming occupancy association. The only way this
change could create a cycle would be to place the directly moved particle at a
position reached from that same particle in the preceding associations.

Both Move references start from the same execution's available declarations. In
an acyclic structure with unique incoming associations, there is at most one
path from that starting particle to either final position. If the destination
were reached through the directly moved particle, the path to the source
position would therefore be an initial part of the path to the destination.
Since both paths are legitimate references of this execution, no intervening
private declaration can be bypassed by the destination reference. The source
reference would be a prefix of the destination reference. The specified Move
restriction rejects exactly that case, including identical references.

Thus the Move preserves acyclicity. This induction also excludes the generic map
counterexample described above: a particle in its own execution's private local
position would already form a cycle in the auxiliary scope associations. It
cannot be inserted as an arbitrary initial state of a proof about reachable
Define executions.

This is deliberately stronger than the statement that the physical positions
alone form an acyclic structure. The auxiliary private-scope associations are
used to establish which source references can coexist. They are discarded when
deriving which operations must actually wait for one another.

## Consequence for exchanging ordinary Moves

Suppose two consecutive ordinary Moves have disjoint changes and requirements in
the relative-occupancy representation: neither changes a final or intermediate
occupancy required by the other's actual references. Include both endpoints of
each Move in its requirements. Suppose also that all directly needed particles
and their required qualities have been supplied.

The second Move's references already resolve to the same particles and positions
before the first Move, since the first changed none of their occupancy
requirements. Its final source is occupied and its destination is empty. Its
written prefix restriction has not changed. The acyclicity argument above
therefore applies to executing it first; no additional cycle-prevention ordering
is needed for this exchange.

After that Move, the first Move's references and final occupancy requirements
likewise remain satisfied. Applying the argument again shows that it too is
legal. The two orders perform disjoint changes to relative occupancy and give
the same resulting associations. The induced physical locations, including
positions and particles moving transitively, agree afterward. Each operation
used the same directly moved particle and the positions described by its actual
references, even when the transitive particles moved vary between the orders.

This supplies the geometric part of the ordinary Move exchange. It does not
identify every possible safe reorientation of an entire program, and it does not
prove that destruction's saved states can be treated as ordinary current
occupancy. Those are different questions.
