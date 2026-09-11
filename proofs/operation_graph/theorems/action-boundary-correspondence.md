# Identified Effects Across Action Boundaries

## Source bindings

Fix a valid finite serial interpretation. An Action Execution's Requirements
identify particular incoming particles and the occupancy of its contracted
positions. Its Guarantees identify which original or newly created particle is
at each guaranteed position. Requirements Follow Particles preserves these
identities through Moves performed by the action.

Bind a callee's interface position to that position of the assigned action, not
to an unrelated caller position from which its occupant arrived. Bind its
incoming particle to the particular particle supplied by the caller. These are
different bindings: moving the supplied particle changes the interface's
occupancy, not the identity of either the particle or the interface position.

An implied position binds to its declaration on the action's parent particle. A
position declared in the Action Statements Block additionally distinguishes the
Action Execution. A fresh particle created by that execution distinguishes its
Create occurrence. Thus different executions reuse interface positions but not
their private positions or newly created particles.

## Resolving a contracted chain

For the first position in a reference, the appropriate binding supplies its
identified position. For an additional name, use the serial occupant and the
quality supplied by its explicit constraints. Induction over the chain gives the
same final position whether resolving in the callee and applying its bindings or
following the corresponding caller-supplied objects directly.

Move preserves the identities and assigned qualities used by this induction. A
Guarantee identifying an original particle therefore composes with another
action's incoming-particle binding. A Guarantee identifying a new particle
composes using its particular Create occurrence instead. Replacement never
identifies the original particle's positions with those of the replacement.

This is an identity correspondence in the serial interpretation. It does not
make every position used to determine those identities a runtime requirement.

## Interface occupancy and a supplied particle's positions

Suppose a particle P is created at `source`, and later moved into an interface
position `input` of an action assigned to another particle G. The action Creates
a particle at `input::/child`.

The identified target is P's `/child`, not the interface position. Its existence
requires P, and its initial setter is P's Create if no previous operation has
used it. It does not require G, the incoming Move, or the interface's occupancy.
Conversely, a Move directly from `input` uses a position defined by G and its
supplied occupant, so it requires G and the interface's occupied-state setter.

The normal integration fixture
`interface_child_work_can_precede_the_actions_parent_create` realizes both
operations. Its child Create may precede G's Create, while its direct interface
Move may not. G's Vanish also need not wait for the child Create; P's Vanish
must wait for the corresponding child-position uses.

This distinction follows from the identified endpoints. No rule says that every
operation contributed by an Action Execution acts on its action's parent
particle. Nor does the identity-binding proof supply a dependency on the
operation that triggered the action.

## Information required by composition

An occupancy Guarantee and an incoming-particle identity alone do not identify
every prerequisite needed for the graph calculation. Composition must preserve:

- The actual setters of contracted positions, including the defining particle's
  Create for a position with no preceding occupancy operation.
- The particular supplying Create separately from a later Move delivering its
  particle to an interface.
- Lifetime uses of supplied particles and of the particles defining actual
  endpoint positions.
- Shared original setters, selected Vacates, and last direct destruction Moves
  for the preserved occupancy used by destructors.
- Relationship periods contributed by the action, including relationships
  already present at its boundary and those continuing beyond it.

Substituting the identified particles, positions, and occurrences preserves the
operation requirements and effects: Create still fills its selected empty
position; Move still changes the same two endpoints with the same particle;
Vacate still refers to its selected original; Vanish still follows its actual
uses. Direct associations and their period boundaries refer to these same
identities, so substitution also preserves the relationship conditions.

Substitution must preserve actual equalities between shared positions and
particles and the distinct identities of private positions and fresh particles.
It must not give separate copies to accesses that refer to the same originals.

## Composition as a state transformation

For the finite resolved interpretation, an action's contribution can be
represented by its identified operations and the bindings above. Its dependency
calculation is a transformation of the construction state, not necessarily an
independently completed graph. The state consists of the accumulated graph,
position setters, particle Creates, selected Vacates, lifetime candidates, last
direct Moves, and unfinished relationship periods. Destruction selections and
the identities shared between operations are fixed by the serial interpretation.

Apply the specified phases to one operation to obtain its state transformation.
Apply a sequence by composing these transformations in processing order. For
sequences A and B and any admissible incoming state s, processing their
concatenation equals processing A from s and then processing B from that result.
Induct on the length of A: the empty sequence changes nothing; removing the
first operation gives the induction hypothesis on the state produced by that
operation. Each phase consults precisely this incoming state, so the argument
covers Comparison's reachability queries as well as the setter updates.

After substituting an action's bindings, each of its individual transformations
is the same as for its occurrences in the full serial interpretation. Induct
over the finite action expansion, replacing each callee contribution with its
transformation. The concatenation identity shows that the resulting state is
identical to the state obtained by processing all identified occurrences
directly. If a caller resumes between contributions, retain its transformed
state; an action boundary neither resets the records nor completes them.

In particular:

- Different executions have distinct occurrences and private positions, while
  shared interfaces consult the same evolving setters.
- Destructors inherit and update the shared original records rather than copies.
- A lifetime candidate collection continues across action boundaries. A local
  return is not a certificate that no later action requires the particle.
- A relationship period continues across a boundary until an actual change of
  defining parent or the specified end of occupancy. The boundary itself is
  neither an end nor a beginning.

Complete Vanishes and relationship conditions from this common final state.
Their inputs are identical, so both calculations give the same dependencies and
permitted execution orders. This proves composition for state-transformer
contributions without adding runtime action barriers. The sequencing in this
argument is the graph calculation's processing order, not its execution order.

This result does not justify substitution of independently minimized graphs.
Such a summary can discard a candidate later needed when bindings coincide, omit
lifetime uses outside the action, or lose a relationship spanning its boundary.
A smaller summary must separately be shown to implement the same state
transformation for every admissible incoming state. The construction above makes
no such compression assumption, and concerns finite expansion, not a finite
summary of an arbitrary infinite future.
