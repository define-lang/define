# T0 Specification Audit of Modified Existing Graph Tests

## Result and scope

Reviewed all 97 existing graph tests modified relative to baseline
`3a2b6a0d4f862eaf3599fe910851c23116e59001`: 75 have specification-supported
proposed expectations; 22 require a missing destructor-ordering rule. The latter
are **not approved as specification-derived expectations**.

This audit covers the changed dependency assertions and the expectations in
existing tests given new expected-failure markers. It does not certify every
unchanged test, the 22 new source projects, generated artifacts, or compiler
correctness.

The derivations below use the complete Define sources for each fixture and
[the language specification](define/spec/spec.md). Compiler graphs, generated
Python, test pass/fail results, implementation knowledge of callees, and
proposals were not used to decide the required dependencies. Existing and
proposed assertions were compared with the source-level derivations, not used as
evidence that their dependencies were correct. Dependency-list order is not a
semantic difference.

## Rules applied

1. [Moving Particles](define/spec/spec.md#moving-particles), quality
   constraints, and
   [Assignment Semantics](define/spec/spec.md#assignment-semantics) determine
   the particle and its qualities at every operation. Moving to a constrained
   position verifies existing qualities; it does not assign a second destructor.
   An action's interface positions are child names of its assigned particle;
   statement-local positions are not.
2. [When Destructors Are Checked](define/spec/spec.md#when-destructors-are-checked)
   puts destructor execution before destruction. It does not specify the
   relative order of multiple destructors on one particle.
3. [Simultaneous Transitive Destruction](define/spec/spec.md#simultaneous-transitive-destruction)
   and [Automatic Destruction](define/spec/spec.md#automatic-destruction)
   identify which Destroys share a logical event.
   [Particle Operation Recency](define/spec/spec.md#particle-operation-recency)
   gives those Destroys equal recency. They are not previous operations for each
   other.
4. [The Fill Rule](define/spec/spec.md#the-fill-rule) selects the latest
   previous operation on the filled position or a transitive parent.
5. [The Empty Rule](define/spec/spec.md#the-empty-rule) collects the latest
   operations on the position and its transitive parents and children, including
   now-empty child positions. A Move also operates on the moved particle's
   transitive child positions. Comparison excludes older operations on related
   positions and excludes equal-recency child Destroys in favor of parent
   Destroys. Move Correction then removes retained Moves already reached by
   another retained dependency.
6. [The Move Rule](define/spec/spec.md#the-move-rule) applies Comparison and
   Move Correction to the combined Empty and Fill Dependencies, then removes a
   Fill Dependency already reached by a remaining Empty Dependency.
7. [The Action Parent Rule](define/spec/spec.md#the-action-parent-rule) supplies
   a dependency only when the other rules supply none. Triggering an action does
   not automatically make its trigger operation a dependency.

An earlier explicit child Destroy and a simultaneous child Destroy must not be
confused. The former can precede a later parent Destroy; the latter cannot.
Similarly, unchanged occupancy does not mean that an Action Guarantee performed
no Particle Operations on that position.

## Unresolved ordering decision

The specification defines constructor order and quality-assignment order, but
does not state how either determines destructor order. The dependency rules
require logical recency; they cannot supply the missing execution order.

Several fixtures contain non-normative comments asserting reverse assignment
order. Some proposed assertions instead put callee-known destructors before
caller-known destructors. For example:

- `test_caller_destructor_between_two_destroyer_known_destructors` assigns
  earlier, caller, later, but proposes earlier, later, caller.
- `test_caller_interleaves_destructors_with_destroyer_known_destructors` assigns
  first through fifth, but proposes second, fourth, first, third, fifth.
- The diamond fixture assigns known and extra in opposite orders on its two
  paths, but proposes known then extra on both.

Neither the fixture comments nor the implementation's existing dependencies
resolve this specification gap. The 22 affected entries identify independently
provable parts and the ordering-dependent parts. Their tables and ordering
comments remain pending a language-design decision; no replacement order was
invented during this audit.

## Changes made during this audit

- Renamed the runtime tracing test to
  `test_guarantee_consumers_preserve_independent_trace_dependencies`.
- Corrected three comments that treated simultaneous child destruction as a
  dependency of parent destruction: one graph-test comment and two fixture
  explanations.
- Did not change any dependency expectation, expected-failure marker, production
  implementation, or specification.

## Verification of audit edits

The renamed runtime tracing test suite and Bazel runtime type checking passed.
Repository formatting and the Bazel build/lint check for the corrected
graph-test comment passed. Required testdata regeneration completed for all 347
codegen and 132 tracing cases, without changes to tracked generated artifacts.
These checks verify the edits; they are not evidence for the semantic
derivations below.

## Per-test derivations

“Verified” means that the audited proposed dependencies follow from the rules
above. “Specification gap” means that a complete exact graph cannot be selected
from the current specification, even when some changed edges can be verified.

### operation_graph_destructor_integration_test

#### `test_destructor_uses_callee_unchanged_guarantee_directly`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_uses_callee_unchanged_guarantee_directly/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Before box is destroyed its destructor triggers filler, which
explicitly destroys /implied and trigger_pos. These are child names of box
despite both being empty. Collection retains both Destroys and excludes box's
older Create.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_local_destruction_consumes_transitive_destructor_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/local_destruction_consumes_transitive_destructor_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor triggers forwarder and filler, then explicitly
creates and destroys /implied again. Box's Destroy collects the destructor's
final /implied Destroy and the independent forwarder and filler trigger_pos
Destroys. The destructor's later /implied Destroy supersedes filler's earlier
/implied Destroy.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_transitive_destructor_guarantee_precedes_parent_and_child_destruction`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/transitive_destructor_guarantee_precedes_parent_and_child_destruction/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** After the destructor's callees execute, box's Destroy collects
filler's final Move to /marker and the independent forwarder and filler
trigger_pos Destroys. The simultaneous /marker Destroy depends on the same final
Move, not on sibling trigger operations. It is not a dependency of box's
Destroy.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_diamond_callers_serialize_added_destructor_around_known_destructor`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/diamond_callers_serialize_added_destructor_around_known_destructor/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Both destructors Move the same /marker particle out and
back. The first invocation must consume the incoming Move, the second must
consume the first's return Move, and simultaneous target and marker Destroys
must consume the second's return Move. The spec does not select the first
destructor. The proposed table selects known then extra on both caller paths,
despite opposite quality-assignment orders and fixture comments specifying
reverse order. Independently, each later destroyer_particle Destroy must retain
its trigger Create and earlier target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_destructor_ordering_move_retains_independent_fill_dependency`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_ordering_move_retains_independent_fill_dependency/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** If known precedes extra, extra's first Move retains
known's /shared return Move and destroyer's independent /destination Destroy;
its return Move supplies the simultaneous target and shared Destroys. If extra
precedes known, the shared dependencies instead pass from extra to known. The
spec supplies no order. The proposed table assumes known first. The later
destroyer_particle Destroy independently retains the trigger Create and target
Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_destructor_ordering_fill_rule`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_ordering_fill_rule/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** After destroyer empties /marker, whichever destructor
runs first must Create after that Destroy. The other destructor's Create follows
the first destructor's /marker Destroy; target Destroy follows the second
destructor's Destroy. The proposed known-then-extra sequence is not selected by
the spec. The later destroyer_particle Destroy independently uses the trigger
Create and target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_destructor_between_two_destroyer_known_destructors`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_destructor_between_two_destroyer_known_destructors/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer explicitly empties /marker before all three
destructors. Fill Rule forms a Create/Destroy chain in their logical execution
order, but the spec does not determine that order. The proposed order is
earlier_assigned, later_assigned, caller, which is neither the DFN's assignment
order nor its comment's reverse assignment order. The later destroyer_particle
Destroy independently uses trigger Create and target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_interleaves_destructors_with_destroyer_known_destructors`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_interleaves_destructors_with_destroyer_known_destructors/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** All five destructors Create and Destroy the same /marker
position after destroyer empties it. Fill Rule requires serialization in their
logical order but cannot choose that order. The proposed sequence is second,
fourth, first, third, fifth; neither the full assignment sequence nor its
reversal follows this order. The later destroyer_particle Destroy independently
uses trigger Create and target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_destructor_ordering_move_retains_independent_empty_dependency`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_ordering_move_retains_independent_empty_dependency/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** If known precedes extra, extra's first Move retains
destroyer's independent /origin return Move plus known's final /destination
Destroy. Its return Move supplies target and origin Destroys. If known follows
extra, target additionally retains known's later destination Destroy and extra's
origin return Move. The spec does not choose between these. The proposed table
assumes known first; later destroyer_particle destruction independently uses
trigger Create and target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_destructor_ordering_action_parent_rule`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_ordering_action_parent_rule/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Whichever destructor runs first Creates /marker after
destroyer's final Move to target under the Fill Rule. The second Creates after
the first's /marker Destroy, and target destruction collects the second's
Destroy. The proposed known-then-extra order requires a missing logical ordering
rule. Later destroyer_particle destruction independently uses trigger Create and
target Destroy.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_auto_destruction_of_child_with_caller_known_destructor`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/auto_destruction_of_child_with_caller_known_destructor/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The child destructor only operates on statement-local _noop, which
is not a child name of the particle being destroyed. The most recent operation
on local and /extra remains destroyer's Move from run. Their simultaneous
Destroys both depend on that Move; the destructor's local Create also depends on
it by the Action Parent Rule.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_multiple_newly_known_children_with_destructors`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/multiple_newly_known_children_with_destructors/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Each child has one destructor, each using its own statement-local
_noop position. These local positions are not child names of local or its
/extra_a and /extra_b positions. All three simultaneous Destroys depend on
destroyer's final Move from run. No relative order of destructors on the same
particle is needed.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_on_passed_particle_with_newly_known_child`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_on_passed_particle_with_newly_known_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The parent destructor only creates a statement-local _noop
particle. Its operations do not change Collection on local or /extra. Both
simultaneous Destroys depend on destroyer's Move from run, and the destructor's
local Create uses the same Move under the Action Parent Rule.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison; Action
Parent Rule; Simultaneous Transitive Destruction.

#### `test_newly_known_grandchild_destructor_uses_callee_child_destroy`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/newly_known_grandchild_destructor_uses_callee_child_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The final Move back to run::/known operates on its /extra child
too. The grandchild destructor's statement-local _noop Create uses that Move
under the Action Parent Rule. Run, /known, and /extra are destroyed
simultaneously and each depends on that Move; no Destroy precedes another.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_caller_contributed_child_destructor_depends_on_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_contributed_child_destructor_depends_on_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor returns /required and /sibling with separate final
Moves. Both are retained for parent destruction, together with maker's
independent trigger_pos Destroy. The Move emptying maker::result is removed by
Move Correction because the later /required Move depends on it. Parent and the
two children are destroyed simultaneously.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_caller_known_destructor_precedes_destroyer_known_child_destroy`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_known_destructor_precedes_destroyer_known_child_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor's final Move back to /required and maker's
independent trigger_pos Destroy remain for parent destruction. Move Correction
removes the older Move emptying maker::result because the final /required Move
depends on it. The simultaneous required Destroy depends only on the final
/required Move.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_two_caller_known_destructors_precede_same_child_destroy`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/two_caller_known_destructors_precede_same_child_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Both destructors move /required out and back. Whichever
runs first consumes destroyer's final return Move; the other consumes that
destructor's final Move. The final return Move supplies simultaneous parent and
required Destroys, with maker's independent trigger Destroy also retained for
parent. The proposed a-then-b order conflicts with the fixture's reverse-order
comment and is not selected by the spec. Destroyer's explicit trigger Destroy is
independently correct.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_known_child_destroy_and_destructor_precede_parent_destroy`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_known_child_destroy_and_destructor_precede_parent_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The two destructors operate on independent /required and /sibling
positions, so their relative logical order cannot change these dependencies.
Parent collects both final return Moves. The /required and /extra Destroys
collect the same final /required Move because a Move also operates on transitive
children. All these Destroys are simultaneous.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_contributed_destructor_operates_on_child_of_occupied_requirement`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/contributed_destructor_operates_on_child_of_occupied_requirement/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor Creates /required::/work after destroyer's final
Move fills /required, then explicitly Destroys /work. The parent and required
Destroys collect that /work Destroy, which excludes the older ancestor Move.
Empty /work still contributes its most recent operation.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_contributed_destructor_depends_on_callee_move_with_two_dependencies`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/contributed_destructor_depends_on_callee_move_with_two_dependencies/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Destroyer's final Move back to /required retains the two earlier
explicit sibling Destroys of /left and /right. The destructor's /work Create
depends on that Move by the Fill Rule. Its /work Destroy supersedes that
ancestor Move for the later simultaneous parent and required Destroys. The
trigger is explicitly destroyed by test, not destroyer.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Destroyer's Move back to /required collects the two /extra
Creates. The destructor's subsequent /work Create and Destroy are later child
operations, so Comparison excludes the older Move for parent and required
destruction. The simultaneous /extra Destroys depend on the Move independently;
they do not precede parent or required.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_destructor_known_only_two_callers_up`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_known_only_two_callers_up/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Each /marker particle is returned by a final destructor Move.
Parent destruction retains these two independent Moves, excluding earlier
ancestor and child Moves. Each simultaneous child Destroy depends on its
respective final Move. The additional caller levels do not alter position
identity or remove assigned destructors.

Rules: When Destructors Are Checked; Empty Rule Collection/Comparison/Move
Correction; Fill Rule; Simultaneous Transitive Destruction.

#### `test_destructor_on_particle_from_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_on_particle_from_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The explicit result Destroy occurs before automatic box
destruction, so box collects that Destroy and the still-occupied run's Create.
Run destruction is simultaneous with box and cannot be a dependency. The
destructor's statement-local _noop operations do not change the result
position's last operation.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_on_particle_from_callee_guarantee_with_child_requirement`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_on_particle_from_callee_guarantee_with_child_requirement/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor's final /marker Move precedes the simultaneous
explicit result and marker Destroys. At the later automatic box destruction,
Collection retains the prior result Destroy, excluding its equal-recency marker
Destroy, plus the independent run Create. Run destruction is simultaneous with
box.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Moving temp to result preserves its assigned destructor. The
destructor only operates on a statement-local position, so the explicit result
Destroy depends on that Move. The later box Destroy collects the explicit result
Destroy and the run Create, not the simultaneous run Destroy.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_attached_in_callee_on_implied_position_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_attached_in_callee_on_implied_position_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Moving temp to /child preserves its assigned destructor. The
explicit child Destroy depends on that Move; the destructor's statement-local
operations do not affect Collection on /child. Box's later automatic Destroy
collects the earlier child Destroy and the run Create, excluding its
simultaneous run Destroy.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_on_particle_from_transitive_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_on_particle_from_transitive_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The returned result's marker is moved by the destructor before the
result and marker are destroyed simultaneously. Gateway's later automatic
Destroy retains the result Destroy over its equal-recency marker Destroy, plus
middle::run's Create. Middle's statement-local box and its operations are not
child names of gateway.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_on_implied_position_from_transitive_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_on_implied_position_from_transitive_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Box's automatic Destroy collects the earlier explicit /child
Destroy, middle's explicit /inner::run Destroy, and the still-occupied
/middle::run's Create. All three positions are independent children of box. The
simultaneous /middle::run Destroy is excluded from previous operations.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_destructor_with_children_known_only_two_callers_up`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_with_children_known_only_two_callers_up/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The child destructor's two final marker Moves are the latest
operations on independent transitive children of run and /extra. Both parent
Destroys collect those Moves; each marker Destroy collects its own Move. All
four Destroys are simultaneous. The parent's destructor creates statement-local
work, whose automatic Destroy must exist and depends on its Create, but neither
work operation is a dependency of run destruction.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_multiple_destructors_on_particle_from_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/multiple_destructors_on_particle_from_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Each destructor operates only on its own statement-local _noop
position, so their relative order cannot affect this graph. Each Create depends
on maker's result Create by the Action Parent Rule. The explicit result Destroy
also depends on maker's Create; later automatic box destruction retains that
earlier Destroy and the run Create, not the simultaneous run Destroy.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Action Parent Rule; Simultaneous Transitive Destruction.

#### `test_all_positions_three_destroyer_occupied_caller_occupied`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/all_positions_three_destroyer_occupied_caller_occupied/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer fills /first and /third; the caller fills
/second. Each destructor initially Moves its named particle using that
position's latest fill, then returns it. Independently, all destructors Create
then Destroy shared /marker. Their logical order is unspecified; the proposed
table chooses first through last. Target destruction must retain every final
operation on the separate named positions plus the last /marker Destroy, but the
identity of that last destructor cannot be proved. Simultaneous child Destroys
do not precede target.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_all_positions_five_destroyer_occupied_caller_occupied`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/all_positions_five_destroyer_occupied_caller_occupied/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller fills /first, /third, and /fifth; destroyer
fills /second and /fourth. Each destructor initially Moves its named particle
using that position's latest fill, then returns it. Independently, all
destructors Create then Destroy shared /marker. Their logical order is
unspecified; the proposed table chooses first through last. Target destruction
must retain every final operation on the separate named positions plus the last
/marker Destroy, but the identity of that last destructor cannot be proved.
Simultaneous child Destroys do not precede target.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_all_positions_three_destroyer_empty_caller_occupied`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/all_positions_three_destroyer_empty_caller_occupied/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer explicitly Creates and Destroys /first and
/third; the caller supplies occupied /second. The first and third destructors'
Creates depend on the corresponding destroyer Destroys, while the second
destructor's initial Move depends on the caller's parent Move. Independently,
all destructors Create then Destroy shared /marker. Their logical order is
unspecified; the proposed table chooses first through last. Target destruction
must retain every final operation on the separate named positions plus the last
/marker Destroy, but the identity of that last destructor cannot be proved.
Simultaneous child Destroys do not precede target.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_all_positions_five_destroyer_empty_caller_occupied`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/all_positions_five_destroyer_empty_caller_occupied/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer explicitly Creates and Destroys /second and
/fourth; the caller supplies occupied /first, /third, and /fifth. The second and
fourth destructors' Creates depend on corresponding destroyer Destroys; the
other destructors' initial Moves depend on the caller's parent Move.
Independently, all destructors Create then Destroy shared /marker. Their logical
order is unspecified; the proposed table chooses first through last. Target
destruction must retain every final operation on the separate named positions
plus the last /marker Destroy, but the identity of that last destructor cannot
be proved. Simultaneous child Destroys do not precede target.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_three_occupied_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_three_occupied_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer fills /first and /third, while the caller
supplies /second. Each named position's final operation is its destructor's
return Move. All named-position final operations independently precede target
destruction; simultaneous occupied-child Destroys do not. Every destructor also
Creates then Destroys shared /marker, and target must retain the last such
Destroy. The spec does not select their order. The proposed table chooses first,
third, second, which cannot be derived from the full quality-assignment order
without an additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_five_occupied_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_five_occupied_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** Destroyer fills /second and /fourth, while the caller
supplies /first, /third, and /fifth. Each named position's final operation is
its destructor's return Move. All named-position final operations independently
precede target destruction; simultaneous occupied-child Destroys do not. Every
destructor also Creates then Destroys shared /marker, and target must retain the
last such Destroy. The spec does not select their order. The proposed table
chooses second, fourth, first, third, fifth, which cannot be derived from the
full quality-assignment order without an additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_three_empty_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_three_empty_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller explicitly empties /second before its parent
Move; destroyer explicitly empties /first and /third after it. Each destructor's
first Create depends on its respective latest parent Move or explicit Destroy.
Each named position ends with its destructor's explicit Destroy. All
named-position final operations independently precede target destruction;
simultaneous occupied-child Destroys do not. Every destructor also Creates then
Destroys shared /marker, and target must retain the last such Destroy. The spec
does not select their order. The proposed table chooses first, third, second,
which cannot be derived from the full quality-assignment order without an
additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_five_empty_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_five_empty_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller explicitly empties /first, /third, and /fifth
before its parent Move; destroyer explicitly empties /second and /fourth after
it. Each destructor's first Create uses its respective latest parent Move or
explicit Destroy. Each named position ends with its destructor's explicit
Destroy. All named-position final operations independently precede target
destruction; simultaneous occupied-child Destroys do not. Every destructor also
Creates then Destroys shared /marker, and target must retain the last such
Destroy. The spec does not select their order. The proposed table chooses
second, fourth, first, third, fifth, which cannot be derived from the full
quality-assignment order without an additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_three_empty_children_between_occupied_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_three_empty_children_between_occupied_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller supplies empty /second, while destroyer fills
/first and /third. Final named-position operations are the first and third
destructors' return Moves and the second destructor's explicit Destroy. All
named-position final operations independently precede target destruction;
simultaneous occupied-child Destroys do not. Every destructor also Creates then
Destroys shared /marker, and target must retain the last such Destroy. The spec
does not select their order. The proposed table chooses first, third, second,
which cannot be derived from the full quality-assignment order without an
additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_five_empty_children_between_occupied_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_five_empty_children_between_occupied_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller supplies empty /first, /third, and /fifth,
while destroyer fills /second and /fourth. Final named-position operations are
the second and fourth return Moves and the first, third, and fifth explicit
Destroys. All named-position final operations independently precede target
destruction; simultaneous occupied-child Destroys do not. Every destructor also
Creates then Destroys shared /marker, and target must retain the last such
Destroy. The spec does not select their order. The proposed table chooses
second, fourth, first, third, fifth, which cannot be derived from the full
quality-assignment order without an additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_three_occupied_children_between_empty_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_three_occupied_children_between_empty_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller supplies occupied /second, while destroyer
explicitly empties /first and /third. Final named-position operations are the
second return Move and the first and third explicit Destroys. All named-position
final operations independently precede target destruction; simultaneous
occupied-child Destroys do not. Every destructor also Creates then Destroys
shared /marker, and target must retain the last such Destroy. The spec does not
select their order. The proposed table chooses first, third, second, which
cannot be derived from the full quality-assignment order without an additional
rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_caller_introduces_five_occupied_children_between_empty_children`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_introduces_five_occupied_children_between_empty_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The caller supplies occupied /first, /third, and /fifth,
while destroyer explicitly empties /second and /fourth. Final named-position
operations are the first, third, and fifth return Moves and the second and
fourth explicit Destroys. All named-position final operations independently
precede target destruction; simultaneous occupied-child Destroys do not. Every
destructor also Creates then Destroys shared /marker, and target must retain the
last such Destroy. The spec does not select their order. The proposed table
chooses second, fourth, first, third, fifth, which cannot be derived from the
full quality-assignment order without an additional rule.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_creator_reverse_child_order_is_canonical_across_three_actions`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/creator_reverse_child_order_is_canonical_across_three_actions/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The creator assigns destructors in order fifth, fourth,
third, second, first. Worker Creates /first_interface and /second_interface; the
caller Creates /third, middle Creates /first, /second, and /fifth, and destroyer
returns /second and Creates /fourth. Every numbered position's final operation
is its destructor's independent return Move. The latest operation on both
worker-created positions is middle's parent Move, which Comparison excludes in
favor of later descendant operations. Thus simultaneous child Destroys do not
precede target. Shared /marker operations still require an unspecified
destructor order; both proposed tables choose second, fourth, first, fifth,
third, which is not justified by the spec.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_creator_nonoverlapping_child_order_is_canonical_across_three_actions`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/creator_nonoverlapping_child_order_is_canonical_across_three_actions/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Specification gap.** The creator assigns destructors in order third, fifth,
second, fourth, first. Worker Creates /first_interface and /second_interface;
the caller Creates /third, middle Creates /first, /second, and /fifth, and
destroyer returns /second and Creates /fourth. Every numbered position's final
operation is its destructor's independent return Move. The latest operation on
both worker-created positions is middle's parent Move, which Comparison excludes
in favor of later descendant operations. Thus simultaneous child Destroys do not
precede target. Shared /marker operations still require an unspecified
destructor order; both proposed tables choose second, fourth, first, fifth,
third, which is not justified by the spec.

Rules: Particle Operation Recency; When Destructors Are Checked; Fill/Empty/Move
Rules.

#### `test_direct_destructor_with_mixed_implied_position_state`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/direct_destructor_with_mixed_implied_position_state/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The destructor's final operation on /occupied_first::/transitive
is its return Move, which supersedes the earlier Move of /occupied_first. The
final /empty Destroy and /occupied_last return Move are independent sibling
operations. Target's Destroy retains all three; /occupied_first and /transitive
Destroys both depend on the transitive return Move and are simultaneous with
target.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_caller_contributed_destructor_with_mixed_implied_position_state`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_contributed_destructor_with_mixed_implied_position_state/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The same destructor body runs even though destroyer does not
constrain its action. Target Collection retains the final /empty Destroy,
/occupied_last return Move, and /occupied_first::/transitive return Move. The
last of these supersedes the earlier /occupied_first Move. Simultaneous child
Destroys do not precede target or /occupied_first.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_destructor_implied_position_state_completed_by_creator`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_implied_position_state_completed_by_creator/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The creator supplies /occupied_first and /transitive; middle
supplies /occupied_last before its Move to destroyer. The destructor's later
operations supersede those earlier sources. Target collects the final /empty
Destroy and the two independent return Moves of /occupied_last and
/occupied_first::/transitive. The latter also supplies both simultaneous
/occupied_first and /transitive Destroys.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_destructor_requirements_resolved_across_three_callers`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_requirements_resolved_across_three_callers/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The DFN explicitly Creates and Destroys source::/middle_known, so
both operations must be present. The initial source Move collects both sibling
/callee_known and /middle_known Destroys plus the /creator_known Create. At
final destruction, the destructor's independent /callee_known return Move,
/middle_known Destroy, and /creator_known return Move supersede all earlier
operations on those positions. Simultaneous child Destroys add no edges.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_callee_child_state_precedes_destructor_knowledge`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/callee_child_state_precedes_destructor_knowledge/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Destroyer Creates /occupied and Creates then Destroys /empty
before the destructor runs. The destructor's occupied Move depends on the
/occupied Create; its /empty Create depends on the prior /empty Destroy. Target
destruction retains the destructor's final occupied return Move and empty
Destroy, not the simultaneous occupied Destroy.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_direct_and_implied_destructor_executes_once`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/direct_and_implied_destructor_executes_once/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The particle created at /bundle already has /destructor through
its constraints. Moving it to direct verifies the required quality rather than
assigning another action. A single destructor invocation returns /marker, and
target and marker are then destroyed simultaneously, both depending on that
return Move.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_destructor_reached_through_two_implication_paths`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/destructor_reached_through_two_implication_paths/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The particle created at /left already has /destructor and /marker.
Moving it to /right verifies those qualities rather than creating another
assignment. After the Move to destroyer, one destructor invocation returns
/marker. The simultaneous target and marker Destroys both depend on that final
return Move.

Rules: When Destructors Are Checked; Moving Particles; Empty Rule
Collection/Comparison; Simultaneous Transitive Destruction.

#### `test_nested_repeated_destructor_with_caller_known_child`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/nested_repeated_destructor_with_caller_known_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Both inner destructors operate only on their own statement-local
work positions, so their relative order cannot affect the graph. In each
invocation, target and /extra destruction are simultaneous and both depend on
that invocation's incoming Move. The second incoming Move retains the first
target Destroy as its Fill Dependency. The outer destructor's local
inner_destroyer_particle is later destroyed after the second target Destroy; its
local operations do not become operations on outer.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Move Rule; Simultaneous Transitive Destruction.

#### `test_separate_child_contract_paths`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/separate_child_contract_paths/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** The parent destructor's final Move back to /left also operates on
/left::/extra. The child destructor on /right only uses statement-local work, so
the latest operation on /right remains destroyer's final right return Move.
Target destruction retains both independent return Moves; simultaneous /left and
/extra Destroys use the parent destructor's Move, while /right uses destroyer's
right Move.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Move Rule; Simultaneous Transitive Destruction.

#### `test_repeated_destructor_uses_distinct_requirement_sources`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/repeated_destructor_uses_distinct_requirement_sources/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Each invocation's destructor initially Moves /marker using that
particle's incoming Move, then returns it. The target and marker Destroys are
simultaneous and both depend on the invocation's return Move. The second
incoming Move retains the first target Destroy as its Fill Dependency and the
second source's marker Create as its independent Empty Dependency.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Move Rule; Simultaneous Transitive Destruction.

#### `test_caller_destroy_with_multiple_callee_and_destructor_guarantees`

[Source](define/testdata/reference_graph/operation_graph_destructor_integration/caller_destroy_with_multiple_callee_and_destructor_guarantees/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_destructor_integration_test.py)

**Verified.** Before parent destruction, maker explicitly Destroys first and
second, the parent destructor explicitly Destroys /marker, and
maker::trigger_pos remains occupied after its Create. Parent Collection retains
those three independent Destroys and the trigger Create. The earlier incoming
parent Move is superseded; simultaneous destruction of /sibling and
maker::trigger_pos does not add edges.

Rules: When Destructors Are Checked; Automatic Destruction; Empty Rule
Collection/Comparison; Move Rule; Simultaneous Transitive Destruction.

### operation_graph_many_actions_integration_test

#### `test_binding_hole_fans_out_to_multiple_fragments_and_multiple_callee_bindings`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/binding_hole_fans_out_to_multiple_fragments_and_multiple_callee_bindings/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** gateway's assigned /middle implies /child_a and /child_b on that
same particle. Their trigger positions and /middle's trigger are its child
names. Its final automatic Destroy collects the three explicit trigger Destroys,
with none excluded because the positions are siblings. Local first, second, and
scratch positions belong to statement blocks and are not child names of gateway.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Move Rule.

#### `test_empty_rule_adds_a_caller_child_operation_to_a_move`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/empty_rule_adds_a_caller_child_operation_to_a_move/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Moving source to holder collects the caller's /marker Create and
/child's trigger Destroy; /child's local scratch operations are not operations
on source's child positions. After the Move, the explicit /marker Destroy is the
newest operation on holder's transitive children, superseding the Move; the
later holder Destroy depends on that explicit Destroy. The final gateway Destroy
must collect the latest operations on all its interface children, but not local
scratch.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Move Rule.

#### `test_caller_consumes_a_child_guarantee_after_an_empty_rule_move`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/caller_consumes_a_child_guarantee_after_an_empty_rule_move/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** After the final Move fills holder, the caller Moves
holder::/result to its local result position and /middle destroys
holder::/child::trigger_pos. Empty Rule Collection for holder retains both those
later, independent child operations, excluding the older ancestor Move. The
/marker particle is destroyed simultaneously with holder, so its Destroy is not
a dependency. This holds after one or two parent Moves.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Move Rule.

#### `test_moved_particle_requirement_does_not_affect_replacement_at_origin`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/moved_particle_requirement_does_not_affect_replacement_at_origin/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The old particle moves from source to holder then to
inner_holder::/inner::input. The replacement source is created separately, then
its /item is Created and explicitly Destroyed, so its parent Destroy depends on
that new /item Destroy, not operations on the old particle. Automatic
destruction of local inner_holder collects /inner's explicit input::/item
Destroy plus the trigger Create; any remaining input and trigger particles are
destroyed simultaneously with inner_holder. For gateway itself, Collection must
also retain the Move emptying /middle::holder: the old particle moved to a
different local particle, and subsequent Destroys there are not on gateway's
child names. That Move is independent of the replacement source Destroy and of
/middle's trigger Destroy.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Move Rule.

#### `test_caller_consumes_a_child_guarantee_after_two_action_parent_moves`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/caller_consumes_a_child_guarantee_after_two_action_parent_moves/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** After the final Move fills holder, the caller Moves
holder::/result to its local result position and /middle destroys
holder::/child::trigger_pos. Empty Rule Collection for holder retains both those
later, independent child operations, excluding the older ancestor Move. The
/marker particle is destroyed simultaneously with holder, so its Destroy is not
a dependency. This holds after one or two parent Moves.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Move Rule.

#### `test_parent_destroy_excludes_guaranteed_move_on_later_dependency_path`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/parent_destroy_excludes_guaranteed_move_on_later_dependency_path/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The final automatic parent Destroy collects the Move emptying
source, the caller's explicit destination Destroy, and mover's run Destroy. The
destination Destroy depends through the second Move on the source Move, so Move
Correction removes the source Move. Only the two Destroys remain.

Rules: Empty Rule Collection/Comparison/Move Correction; Simultaneous Transitive
Destruction.

#### `test_child_guarantee_with_distinct_occupied_action_parent_and_empty_rule_binding_holes`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/child_guarantee_with_distinct_occupied_action_parent_and_empty_rule_binding_holes/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The holder Destroy collects the caller's Move emptying /result and
middle's Destroy of /child::trigger_pos. Both supersede the older Move filling
holder. /marker is destroyed simultaneously, so its Destroy is not a dependency.

Rules: Empty Rule Collection/Comparison/Move Correction; Simultaneous Transitive
Destruction.

#### `test_empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_implied_position_child`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_implied_position_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The gw Destroy collects inner's Create of /holder::/a and middle's
explicit Destroy of /inner::trigger_pos. These are independent child positions;
both supersede older ancestor Creates. Simultaneous destruction of /holder and
/a contributes no additional dependency.

Rules: Empty Rule Collection/Comparison/Move Correction; Simultaneous Transitive
Destruction.

#### `test_implied_action_inherits_the_current_actions_parent_position`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/implied_action_inherits_the_current_actions_parent_position/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Automatic destruction of local and its /parent particle is
simultaneous. Both collect the caller's explicit /middle::trigger_pos Destroy
and middle's /inner::trigger_pos Destroy, which operate on independent child
positions. The inner action's statement-local scratch is not a child name of
local.

Rules: Empty Rule Collection/Comparison/Move Correction; Simultaneous Transitive
Destruction.

#### `test_intermediate_callee_operation_suppresses_only_its_caller_path`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/intermediate_callee_operation_suppresses_only_its_caller_path/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Middle's explicit /grandchild Destroy and simultaneous
/greatgrandchild Destroy collect the caller's last /greatgrandchild Create.
Inner's later parent Destroy collects middle's /grandchild Destroy and the
caller's independent /sibling Create. Equal-recency Comparison removes the
earlier /greatgrandchild Destroy; simultaneous child and sibling Destroys cannot
precede parent.

Rules: Empty Rule Collection/Comparison/Move Correction; Simultaneous Transitive
Destruction.

#### `test_input_carried_through_two_moves_reaches_the_triggered_inner`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/input_carried_through_two_moves_reaches_the_triggered_inner/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The inner_holder destruction is simultaneous with destruction of
its /inner::run particle. Collection retains the run Create and inner's earlier
explicit input Destroy; it cannot collect the simultaneous run Destroy. The
separate middle_holder destruction retains outer's explicit /middle::run Destroy
and middle's Move emptying input into its statement-local inner_holder;
subsequent operations on that local particle are not operations on
middle_holder's child names.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_callee_move_of_a_position_filled_two_levels_up_waits_on_the_caller_child_fill`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/callee_move_of_a_position_filled_two_levels_up_waits_on_the_caller_child_fill/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Middle's first Move depends on the caller's /a Create. Inner's
later Move supersedes that first Move on both the particle and its /a child.
Middle's holder and /a Destroys are simultaneous, and both depend on inner's
final Move.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_callee_move_waits_on_two_caller_child_operations_and_one_intermediate_child_operation`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/callee_move_waits_on_two_caller_child_operations_and_one_intermediate_child_operation/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Inner's Move collects the caller's separate Moves emptying /second
and /third and middle_action's /first Create. None supersedes another because
the positions are siblings. The subsequent holder and /first Destroys both
depend on inner's Move, which operates on the moved particle's child positions;
they are simultaneous.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_transitive_child_guarantee_follows_particle_through_move`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/transitive_child_guarantee_follows_particle_through_move/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Each statement-local action particle is automatically destroyed
simultaneously with its still-occupied trigger particle. At inner_holder,
Collection retains the trigger Create and the Move emptying input back to
inner_parent. At middle_holder it retains the trigger Create and the Move
emptying inner_parent to destination. Subsequent result Moves are on the
particles at their new positions, not child names of the old action particles.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_propagated_empty_rule_combines_caller_operation_and_callee_guarantee`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/propagated_empty_rule_combines_caller_operation_and_callee_guarantee/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Mover's Move collects the caller's /direct_child Create and
filler's /guaranteed_child Create, which are independent sibling operations.
This Move then becomes the most recent operation on destination and both
children. Middle's destination destruction destroys all three simultaneously;
each Destroy depends on that Move.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_propagated_destroy_empty_rule_retains_two_intermediate_caller_child_operations`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/propagated_destroy_empty_rule_retains_two_intermediate_caller_child_operations/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Before destroyer's /parent destruction, the latest child
operations are middle's /first Create and /second Create. Both exclude the older
parent Create, and neither excludes the other. The parent and child Destroys are
simultaneous, so the parent Destroy depends directly on both Creates.

Rules: Empty Rule Collection/Comparison; Move Rule; Simultaneous Transitive
Destruction.

#### `test_destruction_cascade_child_state_crosses_two_actions`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_cascade_child_state_crosses_two_actions/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The Move by middle from run to inner_run is the latest operation
on the particle and its /a and /b children. Inner destroys all three
simultaneously; each Destroy depends on that Move.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_destruction_cascade_implied_child_state_crosses_two_actions`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_cascade_implied_child_state_crosses_two_actions/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Neither callee moves /parent. Collection retains the caller's
independent /a and /b Creates and excludes the older parent Create. Inner
destroys parent and both children simultaneously, so the parent Destroy depends
directly on the two child Creates.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_auto_destruction_child_state_crosses_two_actions`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/auto_destruction_child_state_crosses_two_actions/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Inner's Move to its statement-local local position is the latest
operation on the particle and its /a and /b children. Automatic destruction of
all three is simultaneous and each Destroy depends on that Move.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_destruction_cascade_includes_disjoint_child_paths_from_two_callers`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_cascade_includes_disjoint_child_paths_from_two_callers/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Each invocation's run and its one child are destroyed
simultaneously after the respective caller's Move of box into run. Both Destroys
depend on that invocation's Move. The later explicit destroyer_holder Destroy
depends on the prior run Destroy, excluding the child Destroy of equal recency.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_destruction_cascade_includes_shared_child_path_from_two_callers_once`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_cascade_includes_shared_child_path_from_two_callers_once/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Each separate particle's /child is destroyed with that
invocation's run particle. Both Destroys depend on the respective caller's Move
of box into run. Identical child names across distinct invocations do not create
cross-invocation dependencies. The later destroyer_holder Destroy retains the
run Destroy over the equal-recency child Destroy.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_caller_contribution_and_callee_guarantee_precede_parent_destroy`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/caller_contribution_and_callee_guarantee_precede_parent_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Destroyer's parent Destroy collects its /maker::trigger_pos Create
and maker's result Destroy. Both exclude the earlier Move filling parent;
/sibling's most recent operation is also that earlier Move. The remaining
occupied trigger and sibling particles are destroyed simultaneously with parent,
so those Destroys are not dependencies.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_destruction_cascade_mixes_known_child_states_with_caller_dependent_state`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_cascade_mixes_known_child_states_with_caller_dependent_state/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** The local Destroy collects the Move emptying /known_empty into
/destination and the Create filling /known_occupied. These sibling operations
supersede the older Move to local. The /maybe_child and /known_occupied
particles are destroyed simultaneously with local, so neither contributes its
Destroy as a dependency.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_same_callee_callers_assign_child_qualities_in_opposite_orders`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/same_callee_callers_assign_child_qualities_in_opposite_orders/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** In each invocation the final Move from keeper to run::/child
supersedes the caller's earlier Move on the parent and /sibling. Run, /child and
/sibling are destroyed simultaneously, so run's Destroy depends only on that
final child Move. Reversing earlier child quality assignment and Create order
does not affect this result.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_guarantee_inits_execution_and_satisfies_two_empty_rules`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/guarantee_inits_execution_and_satisfies_two_empty_rules/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Worker's first and second Creates each depend on carrier's Move
filling result; their explicit Destroys depend on the corresponding Creates. The
result Destroy collects worker's three sibling Destroys of first, second, and
run. The subsequent box Destroy collects the result Destroy and carrier's run
Destroy; Move Correction removes carrier's source-to-result Move because the
result Destroy already depends on it.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

#### `test_destruction_association_with_multiple_binding_sources`

[Source](define/testdata/reference_graph/operation_graph_many_actions_integration/destruction_association_with_multiple_binding_sources/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_many_actions_integration_test.py)

**Verified.** Mover destroys discard and its /caller_only child simultaneously.
The caller's Move of trash into discard is the most recent operation on both
positions and supersedes their earlier Creates. Both Destroys depend on that
Move; the independent operations on guaranteed_parent and caller_parent do not
affect them.

Rules: Empty Rule Collection/Comparison/Move Correction; Fill Rule; Simultaneous
Transitive Destruction.

### operation_graph_retriggering_integration_test

#### `test_destroying_action_reused_with_known_child_empty_then_occupied`

[Source](define/testdata/reference_graph/operation_graph_retriggering_integration/destroying_action_reused_with_known_child_empty_then_occupied/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_retriggering_integration_test.py)

**Verified.** The second particle has an occupied /child. Its final Move from
run to /target is an operation on both /target and that particle's child. Both
Destroys collect that Move; neither collects the simultaneous other Destroy. The
first particle's /child was already destroyed before its Move, so no
first-execution child Destroy exists.

Rules: Simultaneous Transitive Destruction; Empty Rule Collection/Comparison.

#### `test_reused_callee_receives_distinct_destruction_connections_per_execution`

[Source](define/testdata/reference_graph/operation_graph_retriggering_integration/reused_callee_receives_distinct_destruction_connections_per_execution/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_retriggering_integration_test.py)

**Verified.** Each particle has its own distinct child position. For each
invocation, the last Move from run to /target supersedes earlier operations on
that particle's child. Both parent Destroys depend on their own Move, not their
simultaneous child Destroy.

Rules: Simultaneous Transitive Destruction; Empty Rule Collection/Comparison.

#### `test_repeated_destroying_action_invocations_include_caller_dependent_children`

[Source](define/testdata/reference_graph/operation_graph_retriggering_integration/repeated_destroying_action_invocations_include_caller_dependent_children/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_retriggering_integration_test.py)

**Verified.** Each Move from the caller fills run and also operates on its
particle's /child. The parent and child Destroys therefore depend on that
invocation's Move. The second Move also retains the preceding parent Destroy as
its Fill Dependency; its first-execution child Destroy is excluded by
equal-recency Comparison.

Rules: Simultaneous Transitive Destruction; Empty Rule Collection/Comparison;
Fill Rule.

#### `test_only_relevant_retrigger_receives_forwarded_destruction_connections`

[Source](define/testdata/reference_graph/operation_graph_retriggering_integration/only_relevant_retrigger_receives_forwarded_destruction_connections/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_retriggering_integration_test.py)

**Verified.** The first particle's /child moves with it into /destroyer::run.
The parent and child Destroys collect middle's same Move. The replacement local
particle has no /child, and its Move depends on the prior parent Destroy, not a
child belonging to the first particle.

Rules: Simultaneous Transitive Destruction; Empty Rule Collection/Comparison;
Fill Rule.

### operation_graph_trigger_position_integration_test

#### `test_destroy_of_trigger_particle_uses_caller_fragment_for_occupied_child`

[Source](define/testdata/reference_graph/operation_graph_trigger_position_integration/destroy_of_trigger_particle_uses_caller_fragment_for_occupied_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_trigger_position_integration_test.py)

**Verified.** The Move from run to /target operates on the particle's /a child
too. Both Destroys collect this Move; their equal recency forbids a dependency
from one to the other. The prior comment incorrectly said the child must finish
first; it was corrected during this audit.

Rules: Simultaneous Transitive Destruction; Empty Rule Collection/Comparison.

### operation_graph_two_actions_integration_test

#### `test_callee_destroy_of_a_caller_filled_position_waits_on_the_caller_child_fill`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/callee_destroy_of_a_caller_filled_position_waits_on_the_caller_child_fill/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** Immediately before /other destroys input::/item, the latest
operation on its /deep child is the caller's Create. Comparison excludes earlier
ancestor Creates. The /item and /deep Destroys are simultaneous and both depend
on that Create.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_caller_operation_waits_on_callee_output_not_later_callee_operations`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/caller_operation_waits_on_callee_output_not_later_callee_operations/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The callee's late interface position is a child name of gateway.
The caller's automatic Destroy of gateway collects the callee's last Destroy of
late, the caller's Destroy of the other occupied interface position, and its
Destroy of trigger_pos. These positions are siblings; none supersedes another.
Their being empty does not remove their last operations from Collection.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_intermediate_callee_emptying_reaches_a_deeper_caller_operation`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/intermediate_callee_emptying_reaches_a_deeper_caller_operation/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The initial explicit Destroy of /grandchild and its simultaneous
/greatgrandchild Destroy both collect the caller's final Create of
/greatgrandchild. For the later parent destruction, equal-recency Comparison
retains the prior /grandchild Destroy instead of /greatgrandchild; the
simultaneously destroyed /child does not precede parent. No expectation changed;
the marker acknowledges this same required graph.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_trigger_inlines_callee_internal_dependencies`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/trigger_inlines_callee_internal_dependencies/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The callee's scratch interface position is a child name of
gateway. The caller's automatic Destroy of gateway collects the callee's last
Destroy of scratch, the caller's Destroy of the other occupied interface
position, and its Destroy of trigger_pos. These positions are siblings; none
supersedes another. Their being empty does not remove their last operations from
Collection.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_callee_known_child_and_caller_unknown_sibling_are_disjoint`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/callee_known_child_and_caller_unknown_sibling_are_disjoint/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** Before destroying parent, the most recent operation on /child is
the Move from keeper back to parent::/child; /sibling's most recent operation is
the earlier Move of parent. Comparison removes that ancestor Move in favor of
the later /child Move. The two child Destroys and parent Destroy are
simultaneous, so no child Destroy is a dependency. Reversing the earlier child
Creates has no effect.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_caller_only_child_assigned_before_callee_known_child_is_disjoint`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/caller_only_child_assigned_before_callee_known_child_is_disjoint/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** Before destroying parent, the most recent operation on /child is
the Move from keeper back to parent::/child; /sibling's most recent operation is
the earlier Move of parent. Comparison removes that ancestor Move in favor of
the later /child Move. The two child Destroys and parent Destroy are
simultaneous, so no child Destroy is a dependency. Reversing the earlier child
Creates has no effect.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_local_cascade_uses_caller_fragment_for_occupied_child`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/local_cascade_uses_caller_fragment_for_occupied_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The final Move from /target to local is an operation on the moved
particle's /a child as well as local. Both the explicit/automatic local Destroy
and /a Destroy collect that Move. Neither simultaneous Destroy precedes the
other.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_auto_destruction_uses_caller_fragment_for_occupied_child`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/auto_destruction_uses_caller_fragment_for_occupied_child/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The final Move from /target to local is an operation on the moved
particle's /a child as well as local. Both the explicit/automatic local Destroy
and /a Destroy collect that Move. Neither simultaneous Destroy precedes the
other.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_caller_contributed_child_destruction_precedes_later_operation`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/caller_contributed_child_destruction_precedes_later_operation/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The first statement destroys run::/run and its /child
simultaneously. Both collect the caller's final Move of source into
/destroyer::run. The following distinct Destroy of run collects that earlier
/run Destroy, excluding its equal-recency /child Destroy.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_caller_contributes_one_destroy_before_shared_callee_destroy`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/caller_contributes_one_destroy_before_shared_callee_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** The explicit /grandchild destruction collects the caller's Create
of /greatgrandchild, and /greatgrandchild is destroyed simultaneously. The later
parent and /child destruction also collect the independent /sibling Create.
Equal-recency Comparison excludes the earlier /greatgrandchild Destroy in favor
of /grandchild; simultaneous /child destruction does not precede parent.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.

#### `test_caller_contributions_share_a_parent_destroy_before_callee_destroy`

[Source](define/testdata/reference_graph/operation_graph_two_actions_integration/caller_contributions_share_a_parent_destroy_before_callee_destroy/test.dfn)
·
[Assertion](define/compiler/validator/reference_graph/reference_graph_validator_tests/operation_graph_two_actions_integration_test.py)

**Verified.** One explicit parent destruction destroys /branch, /a, and /b
simultaneously. The caller's Move of source to /destroyer::parent is the most
recent operation on every one of those positions and supersedes their earlier
Creates. Each Destroy depends directly on that same Move, with no intermediate
Destroy dependency.

Rules: Empty Rule Collection/Comparison; Simultaneous Transitive Destruction;
Fill Rule.
