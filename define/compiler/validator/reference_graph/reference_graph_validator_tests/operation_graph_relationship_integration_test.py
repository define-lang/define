from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest


# These cases preserve examples from the unfinished relationship-scheduling
# investigation. Their expected graphs are research candidates, not a claim
# that the current spec implements these rules; unresolved conditions have TODOs.
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Identified interface-child operations and separate Vacates and Vanishes are not implemented.",
)
def test_interface_child_work_can_precede_the_actions_parent_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(gateway)": [],
        "test.move(source, gateway::/worker::input)": [
            "test.create(source)",
            "test.create(gateway)",
        ],
        "worker.create(input::/child)": [
            # This position belongs to the particle created in source, not to
            # gateway. Identifying it through the future interface binding does
            # not require gateway to exist or the incoming Move to finish.
            "test.create(source)",
        ],
        "worker.move(input, result)": [
            "test.move(source, gateway::/worker::input)",
        ],
        "test.move(gateway::/worker::result, returned)": [
            "worker.move(input, result)",
        ],
        "test.vacate(returned::/child)": ["worker.create(input::/child)"],
        "test.vacate(gateway)": ["test.create(gateway)"],
        "test.vacate(returned)": ["test.move(gateway::/worker::result, returned)"],
        "test.vanish(returned::/child)": ["test.vacate(returned::/child)"],
        "test.vanish(gateway)": [
            # The child Create never acts on a position defined by gateway.
            # Gateway's last use is instead the Move from its interface.
            "test.move(gateway::/worker::result, returned)",
            "test.vacate(gateway)",
        ],
        "test.vanish(returned)": [
            "test.vacate(returned::/child)",
            "test.vacate(returned)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Relationship alternatives and separate Vacates and Vanishes are not implemented.",
)
def test_alternative_paths_imply_a_lifetime_order(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/p)": ["test.create(parent)"],
        "test.create(parent::/q)": ["test.create(parent)"],
        "test.move(parent::/p, parent::/q::/child)": [
            "test.create(parent::/p)",
            "test.create(parent::/q)",
        ],
        "test.create(helper)": [],
        "test.move(parent::/q::/child, helper::/left)": [
            "test.move(parent::/p, parent::/q::/child)",
            "test.create(helper)",
        ],
        "test.move(parent::/q, helper::/left::/child)": [
            # TODO: Either the first particle reaches helper::/left before
            # this Move, or the second reaches helper::/right before the first
            # Move into parent::/q::/child. Their temporary parent relationships
            # must not overlap; the written reference adds no other ordering.
            "test.create(parent::/p)",
            "test.create(parent::/q)",
        ],
        "test.move(helper::/left::/child, helper::/right)": [
            "test.move(parent::/q, helper::/left::/child)",
            "test.create(helper)",
        ],
        "test.vacate(parent)": ["test.create(parent)"],
        "test.vacate(helper)": ["test.create(helper)"],
        "test.vacate(helper::/left)": [
            "test.move(parent::/q::/child, helper::/left)",
        ],
        "test.vacate(helper::/right)": [
            "test.move(helper::/left::/child, helper::/right)",
        ],
        "test.vanish(parent)": [
            # Both original children must leave parent's positions. Whichever
            # safe Move order is chosen, one must first reach a position of
            # helper. Thus create(helper) necessarily precedes this Vanish,
            # without a separate ordinary dependency on that Create.
            "test.move(parent::/p, parent::/q::/child)",
            "test.move(parent::/q, helper::/left::/child)",
            "test.vacate(parent)",
        ],
        "test.vanish(helper)": [
            "test.vacate(helper)",
            "test.vacate(helper::/left)",
            "test.vacate(helper::/right)",
        ],
        "test.vanish(helper::/left)": [
            "test.vacate(helper::/left)",
            "test.move(helper::/left::/child, helper::/right)",
        ],
        "test.vanish(helper::/right)": [
            "test.vacate(helper::/right)",
            "test.move(parent::/q::/child, helper::/left)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Separate Vacates and Vanishes are not implemented.",
)
def test_nested_destruction_reuses_the_original_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.vacate(parent)": ["test.create(parent)"],
        "destroy_parent.create(/temporary)": ["test.create(parent)"],
        "destroy_parent.vacate(/temporary)": ["destroy_parent.create(/temporary)"],
        "destroy_parent.create(/temporary)#2": [
            # The same surviving parent defines /temporary for both Creates.
            # Being in a destructor does not make this nested vacancy optional.
            "destroy_parent.vacate(/temporary)",
        ],
        "destroy_parent.vacate(/temporary)#2": ["destroy_parent.create(/temporary)#2"],
        "destroy_parent.vanish(/temporary)": ["destroy_parent.vacate(/temporary)"],
        "destroy_parent.vanish(/temporary)#2": ["destroy_parent.vacate(/temporary)#2"],
        "test.vanish(parent)": [
            "test.vacate(parent)",
            # The parent provides the position used by the final Vacate, but
            # it need not wait for either temporary particle's Vanish.
            "destroy_parent.vacate(/temporary)#2",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Separate Vacates and Vanishes are not implemented.",
)
def test_retriggered_actions_have_distinct_local_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::item)": ["test.create(gateway)"],
        "worker.move(item, held)": ["test.create(gateway::/worker::item)"],
        "test.create(gateway::/worker::item)#2": [
            # This is the same interface position, emptied by the first Move.
            "worker.move(item, held)",
        ],
        "worker#2.move(item, held)": [
            # The two held positions are different. This Move does not need
            # worker.vacate(held) to empty its target first.
            "test.create(gateway::/worker::item)#2",
        ],
        "worker.vacate(held)": ["worker.move(item, held)"],
        "worker#2.vacate(held)": ["worker#2.move(item, held)"],
        "worker.vanish(held)": ["worker.vacate(held)"],
        "worker#2.vanish(held)": ["worker#2.vacate(held)"],
        "test.vacate(gateway)": ["test.create(gateway)"],
        "test.vanish(gateway)": [
            "test.vacate(gateway)",
            # Both local positions belong to actions assigned to gateway's
            # particle, which must exist until their occupants vacate.
            "worker.vacate(held)",
            "worker#2.vacate(held)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Relationship permissions and separate Vanishes are not implemented.",
)
def test_joint_relationship_conditions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.create(third)": [],
        "test.move(third, first::/first_right)": [
            "test.create(first)",
            "test.create(third)",
        ],
        "test.move(first, second::/second_right)": [
            "test.create(first)",
            "test.create(second)",
            # TODO: If second's original particle has already moved to first's
            # /first_left, it must vacate before this Move can reverse that parent
            # relationship. Otherwise the later reverse Move must wait for
            # first's original particle to move away from second's particle.
        ],
        "test.move(second::/second_right::/first_right, second::/second_left)": [
            "test.create(second)",
            "test.move(third, first::/first_right)",
            # TODO: This visit to second's /second_left cannot overlap second's
            # original particle occupying third's /third_left. Either visit may
            # finish before the other starts; these lists cannot express it.
        ],
        "test.move(second::/second_left, third)": [
            "test.move(second::/second_right::/first_right, second::/second_left)"
        ],
        "test.move(second, third::/third_left)": [
            "test.create(second)",
            "test.create(third)",
        ],
        "test.move(third::/third_left::/second_right, third::/third_left::/second_left)": [
            "test.move(first, second::/second_right)",
            # This is the same actual /second_left previously occupied by third's
            # particle. Together with the two permissions above, its vacancy
            # also rules out the three-particle cycle; no third permission is
            # needed for that cycle.
            "test.move(second::/second_left, third)",
        ],
        "test.move(third::/third_left::/second_left, returned_first)": [
            "test.move(third::/third_left::/second_right, third::/third_left::/second_left)",
        ],
        "test.move(third::/third_left, returned_first::/first_left)": [
            "test.create(first)",
            "test.move(second, third::/third_left)",
        ],
        "test.vacate(returned_first)": [
            "test.move(third::/third_left::/second_left, returned_first)"
        ],
        "test.vacate(returned_first::/first_left)": [
            "test.move(third::/third_left, returned_first::/first_left)"
        ],
        "test.vacate(third)": ["test.move(second::/second_left, third)"],
        "test.vanish(returned_first)": [
            "test.vacate(returned_first)",
            "test.vacate(returned_first::/first_left)",
        ],
        "test.vanish(returned_first::/first_left)": [
            "test.move(third::/third_left::/second_left, returned_first)",
            "test.vacate(returned_first::/first_left)",
        ],
        "test.vanish(third)": [
            "test.move(third::/third_left, returned_first::/first_left)",
            "test.vacate(third)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Relationship permissions and separate Vanishes are not implemented.",
)
def test_relationship_excursions_can_run_in_either_order(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.move(first, second::/child)": [
            "test.create(first)",
            "test.create(second)",
            # TODO: Either pair may start first. If the second pair has
            # started, this Move must wait for its return Move; no fixed
            # ordering between the two pairs preserves both possibilities.
        ],
        "test.move(second::/child, first)": ["test.move(first, second::/child)"],
        "test.move(second, first::/child)": [
            "test.create(first)",
            "test.create(second)",
            # TODO: If the first pair has started, its return Move must
            # finish before this Move. Both temporary parent relationships
            # together would put each particle below the other.
        ],
        "test.move(first::/child, second)": ["test.move(second, first::/child)"],
        "test.vacate(first)": ["test.move(second::/child, first)"],
        "test.vacate(second)": ["test.move(first::/child, second)"],
        "test.vanish(first)": [
            "test.vacate(first)",
            # Vacation need not wait, but first's particle must exist while
            # the other pair uses the /child position that belongs to it.
            "test.move(first::/child, second)",
        ],
        "test.vanish(second)": [
            "test.vacate(second)",
            "test.move(second::/child, first)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved destructor relationships and separate Vanishes are not implemented.",
)
def test_last_destructor_move_and_occupancy_release(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.create(parent::/child::/leaf)": ["test.create(parent::/child)"],
        "test.create(parent::/helper)": ["test.create(parent)"],
        "test.move(parent::/child::/leaf, detached)": [
            "test.create(parent::/child::/leaf)"
        ],
        "test.move(parent, detached::/return)": [
            "test.create(parent::/child::/leaf)",
            # TODO: Moving /child to the vacated helper's /hold can permit
            # this Move. The later destructor Move restores /child and ends
            # its last occupancy use; their interaction is not yet expressed.
        ],
        "destroy_parent.move(/child, /helper::/hold)": [
            "test.create(parent::/child)",
            "test.create(parent::/helper)",
        ],
        "destroy_parent.move(/helper::/hold, /child)": [
            "destroy_parent.move(/child, /helper::/hold)",
            # TODO: If the parent Move has already run, restoring /child
            # needs either the leaf Move or the parent's Vacate to break the
            # cycle. Ending the child's occupancy after this Move cannot
            # excuse a cycle created by the Move itself. These lists do not
            # express that conditional permission.
        ],
        "test.vacate(detached)": ["test.move(parent::/child::/leaf, detached)"],
        "test.vacate(detached::/return)": ["test.move(parent, detached::/return)"],
        "test.vacate(detached::/return::/child)": ["test.create(parent::/child)"],
        "test.vacate(detached::/return::/helper)": ["test.create(parent::/helper)"],
        "test.vanish(detached)": [
            "test.vacate(detached)",
            "test.vacate(detached::/return)",
        ],
        "test.vanish(detached::/return)": [
            "test.vacate(detached::/return)",
            "test.vacate(detached::/return::/child)",
            "test.vacate(detached::/return::/helper)",
            "destroy_parent.move(/helper::/hold, /child)",
        ],
        "test.vanish(detached::/return::/child)": [
            "test.vacate(detached::/return::/child)",
            "test.move(parent::/child::/leaf, detached)",
            "destroy_parent.move(/helper::/hold, /child)",
        ],
        "test.vanish(detached::/return::/helper)": [
            "test.vacate(detached::/return::/helper)",
            "destroy_parent.move(/helper::/hold, /child)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved destructor relationships and separate Vanishes are not implemented.",
)
def test_sharing_destructors_preserve_occupancy_until_last_use(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.create(parent::/child::/leaf)": ["test.create(parent::/child)"],
        "test.move(parent::/child::/leaf, detached)": [
            "test.create(parent::/child::/leaf)"
        ],
        "test.move(parent, detached::/return)": [
            "test.create(parent::/child::/leaf)",
            # The first destructor cannot release occupancy still needed by
            # the second. Only the leaf Move, or Vacation together with the
            # last destructor use, permits the relationship reversal.
            # TODO: Express this Join within a FirstArrival in the eventual
            # resolved dependency syntax.
            "test.move(parent::/child::/leaf, detached) | (test.vacate(detached::/return::/child) & other_destructor.move(held, /child))",
        ],
        "destroy_parent.move(/child, held)": ["test.create(parent::/child)"],
        "destroy_parent.move(held, /child)": ["destroy_parent.move(/child, held)"],
        "other_destructor.move(/child, held)": [
            # These destructors share /child, not their local held positions.
            # Either destructor ordering is allowed; this expectation chooses
            # destroy_parent first and requires restoration before the next use.
            "destroy_parent.move(held, /child)"
        ],
        "other_destructor.move(held, /child)": ["other_destructor.move(/child, held)"],
        "test.vacate(detached)": ["test.move(parent::/child::/leaf, detached)"],
        "test.vacate(detached::/return)": ["test.move(parent, detached::/return)"],
        "test.vacate(detached::/return::/child)": ["test.create(parent::/child)"],
        "test.vanish(detached)": [
            "test.vacate(detached)",
            "test.vacate(detached::/return)",
        ],
        "test.vanish(detached::/return)": [
            "test.vacate(detached::/return)",
            "test.vacate(detached::/return::/child)",
            "other_destructor.move(held, /child)",
        ],
        "test.vanish(detached::/return::/child)": [
            "test.vacate(detached::/return::/child)",
            "test.move(parent::/child::/leaf, detached)",
            "other_destructor.move(held, /child)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved destructor relationships and separate Vanishes are not implemented.",
)
def test_destructor_local_moves_preserve_parent_relationship(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.create(parent::/child::/leaf)": ["test.create(parent::/child)"],
        "test.move(parent::/child::/leaf, detached)": [
            "test.create(parent::/child::/leaf)"
        ],
        "test.move(parent, detached::/return)": [
            "test.create(parent::/child::/leaf)",
            # Either /leaf leaves, or /child has vacated and its last
            # destructor use has finished. Merely moving /child to held
            # does not detach it: held belongs to the same parent particle.
            # TODO: Express this alternative with the resolved graph's
            # eventual syntax for a Join within a FirstArrival.
            "test.move(parent::/child::/leaf, detached) | (test.vacate(detached::/return::/child) & destroy_parent.move(held, /child))",
        ],
        "destroy_parent.move(/child, held)": ["test.create(parent::/child)"],
        "destroy_parent.move(held, /child)": ["destroy_parent.move(/child, held)"],
        "test.vacate(detached)": ["test.move(parent::/child::/leaf, detached)"],
        "test.vacate(detached::/return)": ["test.move(parent, detached::/return)"],
        "test.vacate(detached::/return::/child)": ["test.create(parent::/child)"],
        "test.vanish(detached)": [
            "test.vacate(detached)",
            "test.vacate(detached::/return)",
        ],
        "test.vanish(detached::/return)": [
            "test.vacate(detached::/return)",
            "test.vacate(detached::/return::/child)",
            "destroy_parent.move(held, /child)",
        ],
        "test.vanish(detached::/return::/child)": [
            "test.vacate(detached::/return::/child)",
            # The child particle is still needed to define /leaf even if
            # its destructor's two Moves have already completed.
            "test.move(parent::/child::/leaf, detached)",
            "destroy_parent.move(held, /child)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved relationship alternatives and separate Vanishes are not implemented.",
)
def test_same_parent_moves_preserve_relationship_constraints(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(seed)": [],
        "test.create(seed::/companion_home)": ["test.create(seed)"],
        "test.vacate(seed::/companion_home)": ["test.create(seed::/companion_home)"],
        "test.vanish(seed::/companion_home)": ["test.vacate(seed::/companion_home)"],
        "test.create(seed::/branch)": ["test.create(seed)"],
        "test.create(seed::/branch::/left)": ["test.create(seed::/branch)"],
        "test.create(other)": [],
        "test.create(other::/parent_home)": ["test.create(other)"],
        "test.vacate(other::/parent_home)": ["test.create(other::/parent_home)"],
        "test.vanish(other::/parent_home)": ["test.vacate(other::/parent_home)"],
        "test.create(other::/companion_home)": ["test.create(other)"],
        "test.vacate(other::/companion_home)": ["test.create(other::/companion_home)"],
        "test.vanish(other::/companion_home)": ["test.vacate(other::/companion_home)"],
        "test.move(seed::/branch::/left, seed::/branch::/right)": [
            "test.create(seed::/branch::/left)"
        ],
        "test.move(seed::/branch, other::/visit)": [
            "test.create(seed::/branch)",
            "test.create(other)",
        ],
        "test.move(seed, parent)": ["test.create(seed)"],
        "test.move(other::/visit, detached)": [
            "test.move(seed::/branch, other::/visit)"
        ],
        "test.create(detached::/left)": [
            "test.move(seed::/branch::/left, seed::/branch::/right)"
        ],
        "test.vacate(detached::/left)": ["test.create(detached::/left)"],
        "test.vanish(detached::/left)": ["test.vacate(detached::/left)"],
        "test.move(parent, detached::/right::/parent_home)": [
            "test.move(seed, parent)",
            # Moving between /left and /right does not detach their particle
            # from /branch's particle. /branch must leave before its old parent
            # can move to a position defined by that grandchild.
            "test.move(seed::/branch, other::/visit)",
            "test.create(seed::/branch::/left)",
        ],
        "test.move(detached::/right, parent)": [
            "test.move(seed::/branch::/left, seed::/branch::/right)",
            "test.move(parent, detached::/right::/parent_home)",
        ],
        "test.move(other, parent::/companion_home)": [
            "test.create(seed::/branch::/left)",
            # Either removing the particle from /visit or removing its child
            # from /right breaks the potential cycle. Requiring both would
            # unnecessarily prevent one of the safe execution orders.
            "test.move(other::/visit, detached) | test.move(detached::/right, parent)",
        ],
        "test.move(parent::/companion_home, detached::/right)": [
            "test.move(other, parent::/companion_home)",
            "test.move(detached::/right, parent)",
        ],
        "test.vacate(parent)": ["test.move(detached::/right, parent)"],
        "test.vacate(parent::/parent_home)": [
            "test.move(parent, detached::/right::/parent_home)"
        ],
        "test.vacate(detached)": ["test.move(other::/visit, detached)"],
        "test.vacate(detached::/right)": [
            "test.move(parent::/companion_home, detached::/right)"
        ],
        "test.vanish(parent)": [
            "test.vacate(parent)",
            "test.vacate(parent::/parent_home)",
            "test.move(parent::/companion_home, detached::/right)",
        ],
        "test.vanish(parent::/parent_home)": [
            "test.vacate(parent::/parent_home)",
            "test.vacate(seed::/companion_home)",
        ],
        "test.vanish(detached)": [
            "test.vacate(detached)",
            "test.vacate(detached::/right)",
            "test.vacate(detached::/left)",
        ],
        "test.vanish(detached::/right)": [
            "test.vacate(detached::/right)",
            "test.move(other::/visit, detached)",
            "test.vacate(other::/parent_home)",
            "test.vacate(other::/companion_home)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved-position dependencies and separate Vanishes are not implemented.",
)
def test_future_moves_must_remain_executable(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(other)": [],
        "test.create(visitor)": [],
        "test.create(parent::/inner)": ["test.create(parent)"],
        "test.vacate(parent::/inner)": ["test.create(parent::/inner)"],
        "test.vanish(parent::/inner)": ["test.vacate(parent::/inner)"],
        "test.create(other::/inner)": ["test.create(other)"],
        "test.vacate(other::/inner)": ["test.create(other::/inner)"],
        "test.vanish(other::/inner)": ["test.vacate(other::/inner)"],
        "test.create(visitor::/landing)": ["test.create(visitor)"],
        "test.vacate(visitor::/landing)": ["test.create(visitor::/landing)"],
        "test.vanish(visitor::/landing)": ["test.vacate(visitor::/landing)"],
        "test.move(visitor, parent::/landing)": [
            "test.create(parent)",
            "test.create(visitor)",
        ],
        "test.move(parent::/landing, other::/landing)": [
            "test.move(visitor, parent::/landing)",
            "test.create(other)",
        ],
        "test.move(parent, other::/landing::/inner)": [
            # The visitor must finish its visit to parent's /landing first.
            # Otherwise this acyclic Move prevents that visit from completing,
            # and none of the later Moves or Vacates can release the obstruction.
            "test.move(parent::/landing, other::/landing)"
        ],
        "test.move(other, visitor)": [
            "test.move(visitor, parent::/landing)",
            "test.create(other)",
        ],
        "test.move(visitor::/landing::/inner, other)": [
            "test.move(parent, other::/landing::/inner)",
            "test.move(other, visitor)",
        ],
        "test.vacate(other)": ["test.move(visitor::/landing::/inner, other)"],
        "test.vacate(visitor)": ["test.move(other, visitor)"],
        "test.vacate(visitor::/landing)#2": [
            "test.move(parent::/landing, other::/landing)"
        ],
        "test.vanish(other)": [
            "test.vacate(other)",
            "test.vacate(parent::/inner)",
        ],
        "test.vanish(visitor)": [
            "test.vacate(visitor)",
            "test.vacate(visitor::/landing)#2",
            "test.vacate(other::/inner)",
        ],
        "test.vanish(visitor::/landing)#2": [
            "test.move(visitor::/landing::/inner, other)",
            "test.vacate(visitor::/landing)#2",
            "test.vacate(visitor::/landing)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Relationship exclusions and separate Vacates and Vanishes are not implemented.",
)
def test_disjoint_relationship_visits_share_departure_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.create(third)": [],
        "test.create(fourth)": [],
        "test.move(first, second::/child)": [
            "test.create(first)",
            "test.create(second)",
        ],
        "test.move(second::/child, handoff_to_fourth)": [
            "test.move(first, second::/child)",
        ],
        "test.move(handoff_to_fourth, first)": [
            "test.move(second::/child, handoff_to_fourth)",
        ],
        "test.move(third, fourth::/child)": [
            "test.create(third)",
            "test.create(fourth)",
        ],
        "test.move(fourth::/child, handoff_to_second)": [
            "test.move(third, fourth::/child)",
        ],
        "test.move(handoff_to_second, third)": [
            "test.move(fourth::/child, handoff_to_second)",
        ],
        "test.move(second, first::/child)": [
            # TODO: This visit and first's visit to second cannot overlap.
            # It must also coordinate with fourth's entry below until either
            # forward visit ends. Neither reverse entry is a fixed predecessor.
            "test.create(first)",
            "test.create(second)",
        ],
        "test.move(first::/child, handoff_to_second)": [
            "test.move(second, first::/child)",
            # The earlier occupant must complete its use of this same position,
            # even when the position is still empty before that use begins.
            "test.move(handoff_to_second, third)",
        ],
        "test.move(fourth, third::/child)": [
            # TODO: This visit and third's visit to fourth cannot overlap.
            # The two reverse entries must not both precede both forward exits:
            # they would block the departures required to release each other.
            "test.create(third)",
            "test.create(fourth)",
        ],
        "test.move(third::/child, handoff_to_fourth)": [
            "test.move(fourth, third::/child)",
            "test.move(handoff_to_fourth, first)",
        ],
        "test.vacate(first)": ["test.move(handoff_to_fourth, first)"],
        "test.vacate(third)": ["test.move(handoff_to_second, third)"],
        "test.vacate(handoff_to_second)": [
            "test.move(first::/child, handoff_to_second)",
        ],
        "test.vacate(handoff_to_fourth)": [
            "test.move(third::/child, handoff_to_fourth)",
        ],
        "test.vanish(first)": [
            "test.move(first::/child, handoff_to_second)",
            "test.vacate(first)",
        ],
        "test.vanish(handoff_to_second)": [
            "test.move(second::/child, handoff_to_fourth)",
            "test.vacate(handoff_to_second)",
        ],
        "test.vanish(third)": [
            "test.move(third::/child, handoff_to_fourth)",
            "test.vacate(third)",
        ],
        "test.vanish(handoff_to_fourth)": [
            "test.move(fourth::/child, handoff_to_second)",
            "test.vacate(handoff_to_fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved-position dependencies and separate Vanishes are not implemented.",
)
def test_relationship_flip_waits_for_detachment(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.move(parent::/child, detached)": ["test.create(parent::/child)"],
        "test.move(parent, detached::/inner)": [
            # The child must leave before its old parent becomes its child.
            "test.move(parent::/child, detached)"
        ],
        "test.vacate(detached)": ["test.move(parent::/child, detached)"],
        "test.vacate(detached::/inner)": ["test.move(parent, detached::/inner)"],
        "test.vanish(detached::/inner)": ["test.vacate(detached::/inner)"],
        "test.vanish(detached)": [
            "test.vacate(detached)",
            "test.vacate(detached::/inner)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="The operation graph cannot represent Fan In (any).",
)
def test_either_detachment_allows_relationship_flip(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.create(parent::/child::/inner)": ["test.create(parent::/child)"],
        "test.move(parent::/child, detached_child)": ["test.create(parent::/child)"],
        "test.move(detached_child::/inner, detached_grandchild)": [
            "test.create(parent::/child::/inner)"
        ],
        "test.move(parent, detached_grandchild::/end)": [
            "test.create(parent::/child::/inner)",
            # Either detachment breaks the old parent's relationship to the
            # grandchild. The Move must not wait for both detachments.
            "test.move(parent::/child, detached_child) | test.move(detached_child::/inner, detached_grandchild)",
        ],
        "test.vacate(detached_child)": ["test.move(parent::/child, detached_child)"],
        "test.vacate(detached_grandchild)": [
            "test.move(detached_child::/inner, detached_grandchild)"
        ],
        "test.vacate(detached_grandchild::/end)": [
            "test.move(parent, detached_grandchild::/end)"
        ],
        "test.vanish(detached_grandchild::/end)": [
            "test.move(parent::/child, detached_child)",
            "test.vacate(detached_grandchild::/end)",
        ],
        "test.vanish(detached_child)": [
            "test.move(detached_child::/inner, detached_grandchild)",
            "test.vacate(detached_child)",
        ],
        "test.vanish(detached_grandchild)": [
            "test.vacate(detached_grandchild)",
            "test.vacate(detached_grandchild::/end)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Dependencies for competing relationship changes are not yet representable.",
)
def test_competing_relationship_changes_preserve_safe_orders(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.create(third)": [],
        "test.move(parent::/child, detached_child)": ["test.create(parent::/child)"],
        # TODO: Either of these two Moves can run first, but together they can
        # create a cycle. Another Move or Vacate must remove a relationship
        # before both run; these lists cannot express that permission choice.
        "test.move(parent, third::/end)": [
            "test.create(parent)",
            "test.create(third)",
        ],
        "test.move(third, detached_child::/inner)": [
            "test.create(parent::/child)",
            "test.create(third)",
        ],
        "test.vacate(detached_child)": ["test.move(parent::/child, detached_child)"],
        "test.vacate(detached_child::/inner)": [
            "test.move(third, detached_child::/inner)"
        ],
        "test.vacate(detached_child::/inner::/end)": ["test.move(parent, third::/end)"],
        "test.vanish(detached_child::/inner::/end)": [
            "test.move(parent::/child, detached_child)",
            "test.vacate(detached_child::/inner::/end)",
        ],
        "test.vanish(detached_child::/inner)": [
            "test.vacate(detached_child::/inner)",
            "test.vacate(detached_child::/inner::/end)",
        ],
        "test.vanish(detached_child)": [
            "test.vacate(detached_child)",
            "test.vacate(detached_child::/inner)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Resolved-position dependencies and separate Vanishes are not implemented.",
)
def test_independent_departure_preserves_both_visit_orders(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(parent)": [],
        "test.create(other)": [],
        "test.create(visitor)": [],
        "test.create(parent::/inner)": ["test.create(parent)"],
        "test.vacate(parent::/inner)": ["test.create(parent::/inner)"],
        "test.vanish(parent::/inner)": ["test.vacate(parent::/inner)"],
        "test.create(other::/inner)": ["test.create(other)"],
        "test.vacate(other::/inner)": ["test.create(other::/inner)"],
        "test.vanish(other::/inner)": ["test.vacate(other::/inner)"],
        "test.create(visitor::/landing)": ["test.create(visitor)"],
        "test.vacate(visitor::/landing)": ["test.create(visitor::/landing)"],
        "test.vanish(visitor::/landing)": ["test.vacate(visitor::/landing)"],
        "test.move(visitor, parent::/landing)": [
            "test.create(parent)",
            "test.create(visitor)",
        ],
        "test.move(parent::/landing, other::/landing)": [
            "test.move(visitor, parent::/landing)",
            "test.create(other)",
        ],
        "test.move(parent, other::/landing::/inner)": [
            # Either this visit finishes before visitor enters parent, or
            # visitor leaves parent before this visit begins. The independent
            # result position permits both orders; neither is a fixed dependency.
            # TODO: Express that exclusion in the graph assertion format.
            "test.create(parent)",
            "test.create(visitor)",
        ],
        "test.move(other, visitor)": [
            "test.move(visitor, parent::/landing)",
            "test.create(other)",
        ],
        "test.move(visitor::/landing::/inner, result)": [
            "test.move(parent, other::/landing::/inner)",
        ],
        "test.vacate(result)": ["test.move(visitor::/landing::/inner, result)"],
        "test.vacate(visitor)": ["test.move(other, visitor)"],
        "test.vacate(visitor::/landing)#2": [
            "test.move(parent::/landing, other::/landing)"
        ],
        "test.vanish(result)": [
            # P must remain alive for visitor to leave its /landing even when
            # P has already reached result and vacated it.
            "test.move(parent::/landing, other::/landing)",
            "test.vacate(result)",
            "test.vacate(parent::/inner)",
        ],
        "test.vanish(visitor)": [
            "test.vacate(visitor)",
            "test.vacate(visitor::/landing)#2",
            "test.vacate(other::/inner)",
        ],
        "test.vanish(visitor::/landing)#2": [
            "test.move(visitor::/landing::/inner, result)",
            "test.vacate(visitor::/landing)#2",
            "test.vacate(visitor::/landing)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Shared relationship exclusions and separate Vacates and Vanishes are not implemented.",
)
def test_three_departure_dependencies_need_one_shared_exclusion(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.create(third)": [],
        "test.create(fourth)": [],
        "test.create(fifth)": [],
        "test.create(sixth)": [],
        "test.move(first, second::/child)": [
            "test.create(first)",
            "test.create(second)",
        ],
        "test.move(second::/child, handoff_one)": [
            "test.move(first, second::/child)",
        ],
        "test.move(handoff_one, first)": [
            "test.move(second::/child, handoff_one)",
        ],
        "test.move(third, fourth::/child)": [
            "test.create(third)",
            "test.create(fourth)",
        ],
        "test.move(fourth::/child, handoff_two)": [
            "test.move(third, fourth::/child)",
        ],
        "test.move(handoff_two, third)": [
            "test.move(fourth::/child, handoff_two)",
        ],
        "test.move(fifth, sixth::/child)": [
            "test.create(fifth)",
            "test.create(sixth)",
        ],
        "test.move(sixth::/child, handoff_three)": [
            "test.move(fifth, sixth::/child)",
        ],
        "test.move(handoff_three, fifth)": [
            "test.move(sixth::/child, handoff_three)",
        ],
        "test.move(second, first::/child)": [
            # TODO: Exclude overlap with this pair's forward visit.
            # All three reverse entries also share one conditional exclusion
            # until any forward visit ends. Any two early reverse entries must
            # remain possible; three pairwise exclusions would be too strong.
            "test.create(first)",
            "test.create(second)",
        ],
        "test.move(first::/child, handoff_two)": [
            "test.move(second, first::/child)",
            "test.move(handoff_two, third)",
        ],
        "test.move(fourth, third::/child)": [
            # TODO: Exclude overlap with this pair's forward visit.
            # All three reverse entries also share one conditional exclusion
            # until any forward visit ends. Any two early reverse entries must
            # remain possible; three pairwise exclusions would be too strong.
            "test.create(third)",
            "test.create(fourth)",
        ],
        "test.move(third::/child, handoff_three)": [
            "test.move(fourth, third::/child)",
            "test.move(handoff_three, fifth)",
        ],
        "test.move(sixth, fifth::/child)": [
            # TODO: Exclude overlap with this pair's forward visit.
            # All three reverse entries also share one conditional exclusion
            # until any forward visit ends. Any two early reverse entries must
            # remain possible; three pairwise exclusions would be too strong.
            "test.create(fifth)",
            "test.create(sixth)",
        ],
        "test.move(fifth::/child, handoff_one)": [
            "test.move(sixth, fifth::/child)",
            "test.move(handoff_one, first)",
        ],
        "test.vacate(first)": [
            "test.move(handoff_one, first)",
        ],
        "test.vacate(handoff_two)": [
            "test.move(first::/child, handoff_two)",
        ],
        "test.vanish(first)": [
            "test.vacate(first)",
            "test.move(first::/child, handoff_two)",
        ],
        "test.vanish(handoff_two)": [
            "test.vacate(handoff_two)",
            "test.move(second::/child, handoff_one)",
        ],
        "test.vacate(third)": [
            "test.move(handoff_two, third)",
        ],
        "test.vacate(handoff_three)": [
            "test.move(third::/child, handoff_three)",
        ],
        "test.vanish(third)": [
            "test.vacate(third)",
            "test.move(third::/child, handoff_three)",
        ],
        "test.vanish(handoff_three)": [
            "test.vacate(handoff_three)",
            "test.move(fourth::/child, handoff_two)",
        ],
        "test.vacate(fifth)": [
            "test.move(handoff_three, fifth)",
        ],
        "test.vacate(handoff_one)": [
            "test.move(fifth::/child, handoff_one)",
        ],
        "test.vanish(fifth)": [
            "test.vacate(fifth)",
            "test.move(fifth::/child, handoff_one)",
        ],
        "test.vanish(handoff_one)": [
            "test.vacate(handoff_one)",
            "test.move(sixth::/child, handoff_three)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
