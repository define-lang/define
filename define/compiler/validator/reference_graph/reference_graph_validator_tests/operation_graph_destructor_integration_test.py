from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_contributed_destructor_move_removes_fill_after_two_destruction_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker)": ["test.create(source)"],
        "test.create(parent_source)": [],
        "test.move(parent_source, /parent)": ["test.create(parent_source)"],
        "test.move(source, /caller::run)": ["test.create(source::/marker)"],
        "caller.move(run, /middle::run)": ["test.move(source, /caller::run)"],
        "middle.move(run, /parent::/destroyer::target)": [
            "caller.move(run, /middle::run)",
            "test.move(parent_source, /parent)",
        ],
        "middle.create(/parent::/destroyer::trigger_pos)": [
            "test.move(parent_source, /parent)"
        ],
        "middle.destroy(/parent::/destroyer::trigger_pos)": [
            "middle.create(/parent::/destroyer::trigger_pos)"
        ],
        "destroyer.move(target::/marker, retained_marker)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "destroyer.move(retained_marker, target::/marker)": [
            "destroyer.move(target::/marker, retained_marker)"
        ],
        "destroyer.create(target::/destinations)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        # The Move Rule retains both the last Move on /marker and the Create
        # on /destinations: the Empty Dependency and Fill Dependency are independent.
        "extra_destructor.move(/marker, /destinations::/second)": [
            "destroyer.move(retained_marker, target::/marker)",
            "destroyer.create(target::/destinations)",
        ],
        # The preceding Move already depends on the Create on /destinations,
        # so the Move Rule removes that Fill Dependency from this Move.
        "extra_destructor.move(/destinations::/second, /destinations::/third)": [
            "extra_destructor.move(/marker, /destinations::/second)"
        ],
        "extra_destructor.move(/destinations::/third, /marker)": [
            "extra_destructor.move(/destinations::/second, /destinations::/third)"
        ],
        "destroyer.destroy(target)": [
            "extra_destructor.move(/destinations::/third, /marker)"
        ],
        "destroyer.destroy(target::/marker)": [
            "extra_destructor.move(/destinations::/third, /marker)"
        ],
        "destroyer.destroy(target::/destinations)": [
            "extra_destructor.move(/destinations::/third, /marker)"
        ],
        "middle.destroy(/parent)": [
            "middle.destroy(/parent::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: retain contributed Destructor operations and resolve their destruction dependencies",
)
def test_contributed_destructor_calls_action_with_child_destruction(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(parent_source)": [],
        "test.move(parent_source, /parent)": ["test.create(parent_source)"],
        "test.move(source, /caller::run)": ["test.create(source)"],
        "caller.move(run, /middle::run)": ["test.move(source, /caller::run)"],
        "middle.move(run, /parent::/destroyer::target)": [
            "caller.move(run, /middle::run)",
            "test.move(parent_source, /parent)",
        ],
        "middle.create(/parent::/destroyer::trigger_pos)": [
            "test.move(parent_source, /parent)"
        ],
        "middle.destroy(/parent::/destroyer::trigger_pos)": [
            "middle.create(/parent::/destroyer::trigger_pos)"
        ],
        "extra_destructor.create(source)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "extra_destructor.create(source::/child)": ["extra_destructor.create(source)"],
        "extra_destructor.move(source, /marker)": [
            "extra_destructor.create(source::/child)"
        ],
        "extra_destructor.create(/cleaner::trigger_pos)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "extra_destructor.destroy(/cleaner::trigger_pos)": [
            "extra_destructor.create(/cleaner::trigger_pos)"
        ],
        "child_destructor.create(/child_marker)": [
            "extra_destructor.move(source, /marker)"
        ],
        "child_destructor.destroy(/child_marker)": [
            "child_destructor.create(/child_marker)"
        ],
        # The caller-known Destructor calls /cleaner, which destroys a particle
        # whose /child has its own Destructor. Both simultaneous Destroys depend
        # on that child's Destructor restoring /child_marker to empty.
        "cleaner.destroy(/marker::/child)": ["child_destructor.destroy(/child_marker)"],
        "cleaner.destroy(/marker)": ["child_destructor.destroy(/child_marker)"],
        # The Destructor's Action Guarantee on /marker is fulfilled by /cleaner,
        # so destruction of target depends on /cleaner's Destroy.
        "destroyer.destroy(target)": ["cleaner.destroy(/marker)"],
        "middle.destroy(/parent)": [
            "middle.destroy(/parent::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_destructor_after_independent_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(parent_source)": [],
        "test.move(parent_source, /parent)": ["test.create(parent_source)"],
        "test.move(source, /caller::run)": ["test.create(source)"],
        "caller.move(run, /middle::run)": ["test.move(source, /caller::run)"],
        # The Move needs both the particle in run and the particle in /parent
        # that has /destroyer assigned; neither preceding Move depends on the other.
        "middle.move(run, /parent::/destroyer::target)": [
            "caller.move(run, /middle::run)",
            "test.move(parent_source, /parent)",
        ],
        "middle.create(/parent::/destroyer::trigger_pos)": [
            "test.move(parent_source, /parent)"
        ],
        "middle.destroy(/parent::/destroyer::trigger_pos)": [
            "middle.create(/parent::/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # The Destruction Contract includes /caller's additional Destructor.
        # The Fill Rule makes its Create on /marker follow the callee-known
        # Destructor's Destroy on that same position.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "middle.destroy(/parent)": [
            "middle.destroy(/parent::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_only_destructor_after_independent_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(parent_source)": [],
        "test.move(parent_source, /parent)": ["test.create(parent_source)"],
        "test.move(source, /caller::run)": ["test.create(source)"],
        "caller.move(run, /middle::run)": ["test.move(source, /caller::run)"],
        "middle.move(run, /parent::/destroyer::target)": [
            "caller.move(run, /middle::run)",
            "test.move(parent_source, /parent)",
        ],
        "middle.create(/parent::/destroyer::trigger_pos)": [
            "test.move(parent_source, /parent)"
        ],
        "middle.destroy(/parent::/destroyer::trigger_pos)": [
            "middle.create(/parent::/destroyer::trigger_pos)"
        ],
        # The Destructor is known only to the caller. With no previous operation
        # on /marker, the Action Parent Rule makes its Create depend on the Move
        # of the particle being destroyed, not the Destroy of trigger_pos.
        "extra_destructor.create(/marker)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "middle.destroy(/parent)": [
            "middle.destroy(/parent::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_multiple_destroys_after_independent_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker)": ["test.create(source)"],
        "test.create(parent_source)": [],
        "test.move(parent_source, /parent)": ["test.create(parent_source)"],
        "test.move(source, /caller::run)": ["test.create(source::/marker)"],
        "caller.move(run, /middle::run)": ["test.move(source, /caller::run)"],
        "middle.move(run, /parent::/destroyer::target)": [
            "caller.move(run, /middle::run)",
            "test.move(parent_source, /parent)",
        ],
        "middle.create(/parent::/destroyer::trigger_pos)": [
            "test.move(parent_source, /parent)"
        ],
        "middle.destroy(/parent::/destroyer::trigger_pos)": [
            "middle.create(/parent::/destroyer::trigger_pos)"
        ],
        "destroyer.move(target::/marker, retained_marker)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "destroyer.move(retained_marker, target::/marker)": [
            "destroyer.move(target::/marker, retained_marker)"
        ],
        "known_destructor.move(/marker, retained_marker)": [
            "destroyer.move(retained_marker, target::/marker)"
        ],
        "known_destructor.move(retained_marker, /marker)": [
            "known_destructor.move(/marker, retained_marker)"
        ],
        "known_destructor.create(/empty_marker)": [
            "middle.move(run, /parent::/destroyer::target)"
        ],
        "known_destructor.destroy(/empty_marker)": [
            "known_destructor.create(/empty_marker)"
        ],
        # The Destructor needs /marker occupied and /empty_marker empty.
        # The Move Rule retains both operations fulfilling those requirements;
        # neither is a dependency of the other.
        "extra_destructor.move(/marker, /empty_marker)": [
            "known_destructor.move(retained_marker, /marker)",
            "known_destructor.destroy(/empty_marker)",
        ],
        "extra_destructor.move(/empty_marker, /marker)": [
            "extra_destructor.move(/marker, /empty_marker)"
        ],
        # The Destructor's final Move restores /marker. The parent and child
        # particles are destroyed simultaneously, so both depend on that Move
        # rather than the parent Destroy depending on the child Destroy.
        "destroyer.destroy(target::/marker)": [
            "extra_destructor.move(/empty_marker, /marker)"
        ],
        "destroyer.destroy(target)": ["extra_destructor.move(/empty_marker, /marker)"],
        "middle.destroy(/parent)": [
            "middle.destroy(/parent::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_multiple_destroys_after_separate_binding_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(carrier_source)": [],
        "test.create(payload_source)": [],
        "test.create(payload_source::/marker)": ["test.create(payload_source)"],
        "test.move(payload_source, carrier_source::/payload)": [
            "test.create(carrier_source)",
            "test.create(payload_source::/marker)",
        ],
        "test.move(carrier_source, source::/carrier)": [
            "test.create(source)",
            "test.move(payload_source, carrier_source::/payload)",
        ],
        "test.move(source, /wrapper::run)": [
            "test.move(carrier_source, source::/carrier)"
        ],
        "wrapper.move(run::/carrier, run::/outer::run)": [
            "test.move(source, /wrapper::run)"
        ],
        "outer.move(run::/payload, run::/middle::run)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(run::/payload, run::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.move(/marker, retained_marker)": [
            "inner.move(run, /destroyer::target)"
        ],
        "known_destructor.move(retained_marker, /marker)": [
            "known_destructor.move(/marker, retained_marker)"
        ],
        "extra_destructor.move(/marker, retained_marker)": [
            "known_destructor.move(retained_marker, /marker)"
        ],
        "extra_destructor.move(retained_marker, /marker)": [
            "extra_destructor.move(/marker, retained_marker)"
        ],
        # The /payload particle retains its caller-assigned Destructor through
        # Moves of its parent particles. That Destructor's final Move on /marker
        # precedes both simultaneous Destroys of the particle and its child.
        "destroyer.destroy(target::/marker)": [
            "extra_destructor.move(retained_marker, /marker)"
        ],
        "destroyer.destroy(target)": [
            "extra_destructor.move(retained_marker, /marker)"
        ],
        "outer.destroy(run)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
        "wrapper.destroy(run)": ["outer.destroy(run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_destructor_after_callee_guarantee_and_local_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "seeder.create(/result)": [],
        "test.create(/seeder::run)": [],
        "test.destroy(/seeder::run)": ["test.create(/seeder::run)"],
        "test.create(payload_source)": [],
        "test.move(payload_source, source::/payload)": [
            "test.create(source)",
            "test.create(payload_source)",
        ],
        "test.move(source, /outer::run)": [
            "test.move(payload_source, source::/payload)"
        ],
        "outer.create(/filler::run)": [],
        "outer.destroy(/filler::run)": ["outer.create(/filler::run)"],
        "filler.create(scratch)": [],
        "filler.destroy(scratch)": ["filler.create(scratch)"],
        "filler.move(/result, scratch)": [
            "filler.destroy(scratch)",
            "seeder.create(/result)",
        ],
        "filler.destroy(scratch)#2": ["filler.move(/result, scratch)"],
        "outer.move(run, receiver)": ["test.move(source, /outer::run)"],
        "outer.move(receiver, /result)": [
            "outer.move(run, receiver)",
            "filler.move(/result, scratch)",
        ],
        "outer.move(/result::/payload, /result::/middle::run)": [
            "outer.move(receiver, /result)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(/result::/payload, /result::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": ["outer.move(receiver, /result)"],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # After /filler empties /result, /outer fills it with the caller's particle.
        # The /payload particle still has its additional Destructor; the Fill Rule
        # makes its Create on /marker follow the callee-known Destructor's Destroy.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "outer.destroy(/result)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_later_caller_configures_destructor_after_separate_binding_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /caller::run)": ["test.create(source)"],
        "caller.create(source)": [],
        "caller.create(carrier_source)": [],
        "caller.move(run, carrier_source::/payload)": [
            "caller.create(carrier_source)",
            "test.move(source, /caller::run)",
        ],
        "caller.move(carrier_source, source::/carrier)": [
            "caller.create(source)",
            "caller.move(run, carrier_source::/payload)",
        ],
        "caller.move(source, /wrapper::run)": [
            "caller.move(carrier_source, source::/carrier)"
        ],
        "wrapper.move(run::/carrier, run::/outer::run)": [
            "caller.move(source, /wrapper::run)"
        ],
        "outer.move(run::/payload, run::/middle::run)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(run::/payload, run::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        # Destruction Contracts include the Destructors known by both /caller
        # and /test. Their shared /marker makes the Fill Rule order /test's
        # Destructor after the Destroy performed by /caller's Destructor.
        "later_destructor.create(/marker)": ["extra_destructor.destroy(/marker)"],
        "later_destructor.destroy(/marker)": ["later_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["later_destructor.destroy(/marker)"],
        "outer.destroy(run)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
        "wrapper.destroy(run)": ["outer.destroy(run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_configures_destructor_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/maker::run)": [],
        "test.create(/destroyer::trigger_pos)": [],
        "test.destroy(/maker::run)": ["test.create(/maker::run)"],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
        "maker.create(source)": [],
        "maker.move(source, /target)": ["maker.create(source)"],
        "known_destructor.create(/marker)": ["maker.move(source, /target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # The particle guaranteed in /target has /extra_destructor assigned by
        # /maker, although /destroyer knows only /known_destructor. The Fill Rule
        # orders their operations on the shared implied position /marker.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(/target)": ["extra_destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_destructor_after_callee_initializes_fanout_owner(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(crate_source)": [],
        "test.create(carrier_source)": [],
        "test.create(payload_source)": [],
        "test.move(payload_source, carrier_source::/payload)": [
            "test.create(carrier_source)",
            "test.create(payload_source)",
        ],
        "test.move(carrier_source, crate_source::/carrier)": [
            "test.create(crate_source)",
            "test.move(payload_source, carrier_source::/payload)",
        ],
        "test.move(crate_source, source::/crate)": [
            "test.create(source)",
            "test.move(carrier_source, crate_source::/carrier)",
        ],
        "test.move(source, /starter::run)": ["test.move(crate_source, source::/crate)"],
        "starter.move(run, gateway)": ["test.move(source, /starter::run)"],
        "starter.move(gateway::/crate, gateway::/wrapper::run)": [
            "starter.move(run, gateway)"
        ],
        "wrapper.move(run::/carrier, run::/outer::run)": [
            "starter.move(gateway::/crate, gateway::/wrapper::run)"
        ],
        "outer.move(run::/payload, run::/middle::run)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(run::/payload, run::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # Moves of the particles in /crate, /carrier, and /payload preserve the
        # Destructor assigned to the /payload particle. Its Create on /marker
        # depends on the callee-known Destructor's Destroy by the Fill Rule.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "outer.destroy(run)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
        "wrapper.destroy(run)": ["outer.destroy(run)"],
        "starter.destroy(gateway)": ["wrapper.destroy(run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_destructor_after_three_separate_binding_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(carrier_source)": [],
        "test.create(payload_source)": [],
        "test.move(payload_source, carrier_source::/payload)": [
            "test.create(carrier_source)",
            "test.create(payload_source)",
        ],
        "test.move(carrier_source, source::/carrier)": [
            "test.create(source)",
            "test.move(payload_source, carrier_source::/payload)",
        ],
        "test.move(source, /wrapper::run)": [
            "test.move(carrier_source, source::/carrier)"
        ],
        "wrapper.move(run::/carrier, run::/outer::run)": [
            "test.move(source, /wrapper::run)"
        ],
        "outer.move(run::/payload, run::/middle::run)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(run::/payload, run::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [
            "wrapper.move(run::/carrier, run::/outer::run)"
        ],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # The Destruction Contract for the /payload particle reaches /test through
        # the callers that move its parent particles. The additional Destructor's
        # Create depends on the previous Destructor's Destroy of the same /marker.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "outer.destroy(run)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
        "wrapper.destroy(run)": ["outer.destroy(run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_caller_configures_destructor_after_two_separate_binding_inits(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(payload_source)": [],
        "test.move(payload_source, source::/payload)": [
            "test.create(source)",
            "test.create(payload_source)",
        ],
        "test.move(source, /outer::run)": [
            "test.move(payload_source, source::/payload)"
        ],
        "outer.move(run::/payload, run::/middle::run)": [
            "test.move(source, /outer::run)"
        ],
        "middle.move(run, /inner::run)": [
            "outer.move(run::/payload, run::/middle::run)"
        ],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": ["test.move(source, /outer::run)"],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # Moving the /payload particle to /middle does not remove the Destructor
        # known by /test. Its Create on /marker must follow the callee-known
        # Destructor's Destroy by the Fill Rule.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "outer.destroy(run)": [
            "inner.destroy(/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_later_caller_adds_independent_destructor_to_contributed_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(child_source)": [],
        "test.move(child_source, source::/child)": [
            "test.create(source)",
            "test.create(child_source)",
        ],
        "test.move(source, /middle::target)": [
            "test.move(child_source, source::/child)"
        ],
        "middle.move(target::/child, retained_child)": [
            "test.move(source, /middle::target)"
        ],
        "middle.move(retained_child, target::/child)": [
            "middle.move(target::/child, retained_child)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.move(retained_child, target::/child)"
        ],
        "destroyer.move(target, holder)": ["middle.move(target, /destroyer::target)"],
        "destructor.create(work)": ["destroyer.move(target, holder)"],
        "destructor.destroy(work)": ["destructor.create(work)"],
        # The caller-known child's Destructor operates only on its local work
        # position. Neither its operations nor the simultaneous parent Destroy
        # is collected by the Empty Rule for holder::/child; the parent Move is.
        "destroyer.destroy(holder::/child)": ["destroyer.move(target, holder)"],
        "destroyer.destroy(holder)": ["destroyer.move(target, holder)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_later_caller_adds_destructor_to_contributed_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(child_source)": [],
        "test.move(child_source, source::/child)": [
            "test.create(source)",
            "test.create(child_source)",
        ],
        "test.move(source, /middle::target)": [
            "test.move(child_source, source::/child)"
        ],
        "middle.move(target::/child, retained_child)": [
            "test.move(source, /middle::target)"
        ],
        "middle.move(retained_child, target::/child)": [
            "middle.move(target::/child, retained_child)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.move(retained_child, target::/child)"
        ],
        "destroyer.move(target, holder)": ["middle.move(target, /destroyer::target)"],
        "destructor.create(/marker)": ["destroyer.move(target, holder)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
        # The caller adds a Destructor to a child unknown to /destroyer.
        # Its Action Guarantee on /marker precedes destruction of both the child
        # and parent particles, without ordering their simultaneous Destroys.
        "destroyer.destroy(holder::/child)": ["destructor.destroy(/marker)"],
        "destroyer.destroy(holder)": ["destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_transitive_caller_configures_destructor_created_by_guarantee_binding(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /outer::run)": ["test.create(source)"],
        "outer.move(run, /middle::run)": ["test.move(source, /outer::run)"],
        "middle.move(run, /inner::run)": ["outer.move(run, /middle::run)"],
        "inner.move(run, /filler::run)": ["middle.move(run, /inner::run)"],
        "filler.move(run, /target)": ["inner.move(run, /filler::run)"],
        "inner.create(/destroyer::trigger_pos)": [],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["filler.move(run, /target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # /filler guarantees that /target has the same particle passed by /test,
        # including its additional Destructor. The Fill Rule orders that
        # Destructor's Create after the callee-known Destructor's Destroy.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(/target)": ["extra_destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_transitive_caller_configures_destructor_created_by_propagated_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /target)": ["test.create(source)"],
        "test.create(run_source)": [],
        "test.move(run_source, /outer::run)": ["test.create(run_source)"],
        "outer.move(run, /middle::run)": ["test.move(run_source, /outer::run)"],
        "middle.move(run, /inner::run)": ["outer.move(run, /middle::run)"],
        "inner.destroy(run)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["test.move(source, /target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # The propagated Action Requirement on /target is satisfied by /test's
        # particle, including its additional Destructor. Both Destructors use
        # the same /marker, so the Fill Rule requires this dependency.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(/target)": ["extra_destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_known_child_destroy_uses_binding_initialized_callee_fanout(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(payload_source)": [],
        "test.create(payload_source::/child)": ["test.create(payload_source)"],
        "test.move(payload_source, source::/payload)": [
            "test.create(source)",
            "test.create(payload_source::/child)",
        ],
        "test.move(source, /outer::run)": [
            "test.move(payload_source, source::/payload)"
        ],
        "outer.move(run::/payload, run::/destroyer::target)": [
            "test.move(source, /outer::run)"
        ],
        "destroyer.move(target, holder)": [
            "outer.move(run::/payload, run::/destroyer::target)"
        ],
        "destroyer.destroy(holder)": ["destroyer.move(target, holder)"],
        # A Move is an operation on every transitive child position of its particle.
        # The Empty Rule therefore makes this caller-known child's Destroy depend
        # on the callee's Move, not the simultaneous Destroy of holder.
        "destroyer.destroy(holder::/child)": ["destroyer.move(target, holder)"],
        "outer.destroy(run)": ["destroyer.move(target, holder)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_transitive_caller_configures_destructor_created_by_binding_hole(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /outer::run)": ["test.create(source)"],
        "outer.move(run, /middle::run)": ["test.move(source, /outer::run)"],
        "middle.move(run, /inner::run)": ["outer.move(run, /middle::run)"],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "known_destructor.create(/marker)": ["inner.move(run, /destroyer::target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # Destruction Contracts preserve /test's knowledge of the additional
        # Destructor through /outer, /middle, and /inner. The Fill Rule orders
        # its Create after the callee-known Destructor's Destroy on /marker.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_transitive_caller_configures_destructor_created_by_local_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /outer::run)": ["test.create(source)"],
        "outer.move(run, /middle::run)": ["test.move(source, /outer::run)"],
        "middle.move(run, /inner::run)": ["outer.move(run, /middle::run)"],
        "inner.move(run, /destroyer::target)": ["middle.move(run, /inner::run)"],
        "inner.create(/destroyer::trigger_pos)": [],
        "inner.destroy(/destroyer::trigger_pos)": [
            "inner.create(/destroyer::trigger_pos)"
        ],
        "destroyer.move(target, holder)": ["inner.move(run, /destroyer::target)"],
        "destroyer.move(holder, target)": ["destroyer.move(target, holder)"],
        "known_destructor.create(/marker)": ["destroyer.move(holder, target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        # The callee's Moves to holder and back preserve the particle's assigned
        # Destructors. The caller-known Destructor's Create still follows the
        # callee-known Destructor's Destroy on /marker by the Fill Rule.
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_contributed_destruction_follows_transitive_move_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/child)"],
        "destroyer.move(run, /mover::run)": ["test.move(source, /destroyer::run)"],
        "mover.move(run, result)": ["destroyer.move(run, /mover::run)"],
        "destroyer.destroy(/mover::result)": ["mover.move(run, result)"],
        # /mover's Guarantee preserves the caller-known child on the moved particle.
        # The Empty Rule collects that Move for the child Destroy, not the
        # simultaneous parent Destroy or the Destructor's unrelated local work.
        "destroyer.destroy(/mover::result::/child)": ["mover.move(run, result)"],
        "destructor.create(work)": ["mover.move(run, result)"],
        "destructor.destroy(work)": ["destructor.create(work)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: distinguish contributed Destructor operations and preserve simultaneous Destroys",
)
def test_caller_known_child_has_same_destructor_as_callee_known_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/child)"],
        "destroyer.destroy(run)": ["test.move(source, /destroyer::run)"],
        "destroyer.destroy(run::/child)": ["test.move(source, /destroyer::run)"],
        # The two particles each execute the Destructor. Their independent
        # Creates use the same preceding Move through the Action Parent Rule.
        "destroyer:destructor.create(work)": ["test.move(source, /destroyer::run)"],
        "destroyer:test:destructor.create(work)": [
            "test.move(source, /destroyer::run)"
        ],
        "destroyer:destructor.destroy(work)": ["destroyer:destructor.create(work)"],
        "destroyer:test:destructor.destroy(work)": [
            "destroyer:test:destructor.create(work)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_known_child_destroy_is_independent_of_callee_sibling_moves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/known)": ["test.create(source)"],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": [
            "test.create(source::/known)",
            "test.create(source::/extra)",
        ],
        "destroyer.move(run, incoming)": ["test.move(source, /destroyer::run)"],
        "destroyer.move(incoming, parent)": ["destroyer.move(run, incoming)"],
        "destroyer.move(parent::/known, holder)": ["destroyer.move(incoming, parent)"],
        "destroyer.move(holder, parent::/known)": [
            "destroyer.move(parent::/known, holder)"
        ],
        # Collection for /extra includes its parent's Move, but neither Move
        # of /known: those operate on a sibling, not a parent or child of /extra.
        "destroyer.destroy(parent::/extra)": ["destroyer.move(incoming, parent)"],
        "destroyer.destroy(parent::/known)": ["destroyer.move(holder, parent::/known)"],
        # Comparison for parent excludes the parent's Move in favor of the
        # later Move of /known; the simultaneous child Destroys are not collected.
        "destroyer.destroy(parent)": ["destroyer.move(holder, parent::/known)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_independent_chains_and_operation_after_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "test.create(box)#2": ["test.destroy(box)"],
        "destructor.create(first)": ["test.create(box)"],
        "destructor.create(second)": ["test.create(box)"],
        "destructor.destroy(first)": ["destructor.create(first)"],
        "destructor.destroy(second)": ["destructor.create(second)"],
        "destructor#2.create(first)": ["test.create(box)#2"],
        "destructor#2.create(second)": ["test.create(box)#2"],
        "destructor#2.destroy(first)": ["destructor#2.create(first)"],
        "destructor#2.destroy(second)": ["destructor#2.create(second)"],
        "test.destroy(box)#2": ["test.create(box)#2"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_uses_callee_unchanged_guarantee_directly(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": [
            "filler.destroy(/implied)",
            "filler.destroy(trigger_pos)",
        ],
        "destructor.create(/filler::trigger_pos)": ["test.create(box)"],
        "filler.create(/implied)": ["test.create(box)"],
        # Returning the contracted position to its required empty state produces
        # the callee guarantee that the Destructor consumes directly.
        "filler.destroy(/implied)": ["filler.create(/implied)"],
        "filler.destroy(trigger_pos)": ["destructor.create(/filler::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_local_destruction_consumes_transitive_destructor_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": [
            "destructor.destroy(/implied)",
            "forwarder.destroy(trigger_pos)",
            "filler.destroy(trigger_pos)",
        ],
        "destructor.create(/forwarder::trigger_pos)": ["test.create(box)"],
        "forwarder.create(/filler::trigger_pos)": ["test.create(box)"],
        "forwarder.destroy(trigger_pos)": [
            "destructor.create(/forwarder::trigger_pos)"
        ],
        "filler.create(/implied)": ["test.create(box)"],
        "filler.destroy(/implied)": ["filler.create(/implied)"],
        "filler.destroy(trigger_pos)": ["forwarder.create(/filler::trigger_pos)"],
        # The Fill Rule uses the transitive callee's last operation on /implied,
        # even though the direct callee does not itself operate on that Position.
        "destructor.create(/implied)": ["filler.destroy(/implied)"],
        "destructor.destroy(/implied)": ["destructor.create(/implied)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_transitive_destructor_guarantee_precedes_parent_and_child_destruction(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/marker)": ["test.create(box)"],
        "destructor.create(/forwarder::trigger_pos)": ["test.create(box)"],
        "forwarder.create(/filler::trigger_pos)": ["test.create(box)"],
        "forwarder.destroy(trigger_pos)": [
            "destructor.create(/forwarder::trigger_pos)"
        ],
        "filler.move(/marker, holder)": ["test.create(box::/marker)"],
        "filler.move(holder, /marker)": ["filler.move(/marker, holder)"],
        "filler.destroy(trigger_pos)": ["forwarder.create(/filler::trigger_pos)"],
        # The Empty Rule for both Positions uses the transitive callee's final
        # Move on the child, not its earlier Create or the simultaneous Destroy.
        "test.destroy(box)": [
            "filler.move(holder, /marker)",
            "forwarder.destroy(trigger_pos)",
            "filler.destroy(trigger_pos)",
        ],
        "test.destroy(box::/marker)": ["filler.move(holder, /marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_deep_diamond_operations_on_the_same_implied_position_with_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/left::trigger_pos)": [],
        "test.create(/right::trigger_pos)": [],
        "left.create(/left_child::trigger_pos)": [],
        "left_child.create(/marker)": [],
        "right.create(/right_child::trigger_pos)": [],
        "right_child.destroy(/marker)": ["left_child.create(/marker)"],
        # The caller-supplied occupied requirement both orders destruction and
        # fires the directly known destructor.
        "destructor.create(_noop)": ["left_child.create(/marker)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "left.destroy(/left_child::trigger_pos)": [
            "left.create(/left_child::trigger_pos)"
        ],
        "right.destroy(/right_child::trigger_pos)": [
            "right.create(/right_child::trigger_pos)"
        ],
        "test.destroy(/left::trigger_pos)": ["test.create(/left::trigger_pos)"],
        "test.destroy(/right::trigger_pos)": ["test.create(/right::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_diamond_callers_order_added_destructor_around_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/caller_a::trigger_pos)": [],
        "test.create(/caller_b::trigger_pos)": [],
        "caller_a.create(destroyer_particle)": [],
        "caller_a.create(carrier)": [],
        "caller_a.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_a.create(destroyer_particle)",
            "caller_a.create(carrier)",
        ],
        "caller_a.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle)"
        ],
        "caller_a:destroyer.destroy(target)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        # Logical trigger order does not serialize the Destructors' independent
        # Particle Operations.
        "caller_a:destroyer:extra_destructor.create(work)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:extra_destructor.destroy(work)": [
            "caller_a:destroyer:extra_destructor.create(work)"
        ],
        "caller_a:destroyer:known_destructor.create(work)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:known_destructor.destroy(work)": [
            "caller_a:destroyer:known_destructor.create(work)"
        ],
        "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_a.destroy(destroyer_particle)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)",
            "caller_a:destroyer.destroy(target)",
        ],
        "caller_b.create(destroyer_particle)": [],
        "caller_b.create(carrier)": [],
        "caller_b.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_b.create(destroyer_particle)",
            "caller_b.create(carrier)",
        ],
        "caller_b.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle)"
        ],
        "caller_b:destroyer.destroy(target)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        # The opposite logical trigger order likewise creates no dependency
        # between the independent Particle Operations.
        "caller_b:destroyer:known_destructor.create(work)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:known_destructor.destroy(work)": [
            "caller_b:destroyer:known_destructor.create(work)"
        ],
        "caller_b:destroyer:extra_destructor.create(work)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:extra_destructor.destroy(work)": [
            "caller_b:destroyer:extra_destructor.create(work)"
        ],
        "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_b.destroy(destroyer_particle)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)",
            "caller_b:destroyer.destroy(target)",
        ],
        "test.destroy(/caller_a::trigger_pos)": ["test.create(/caller_a::trigger_pos)"],
        "test.destroy(/caller_b::trigger_pos)": ["test.create(/caller_b::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: resolve dependencies between contributed and callee-known Destructor operations",
)
def test_diamond_callers_serialize_added_destructor_around_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/caller_a::trigger_pos)": [],
        "test.create(/caller_b::trigger_pos)": [],
        "caller_a.create(destroyer_particle)": [],
        "caller_a.create(carrier)": [],
        "caller_a.create(carrier::/marker)": ["caller_a.create(carrier)"],
        "caller_a.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_a.create(destroyer_particle)",
            "caller_a.create(carrier::/marker)",
        ],
        "caller_a.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle)"
        ],
        # Both Destructors operate on /marker, so the caller's Move consumes
        # the callee-known Destructor's final Move through the Empty Rule.
        "caller_a:destroyer:extra_destructor.move(/marker, holder)": [
            "caller_a:destroyer:known_destructor.move(holder, /marker)"
        ],
        "caller_a:destroyer:extra_destructor.move(holder, /marker)": [
            "caller_a:destroyer:extra_destructor.move(/marker, holder)"
        ],
        "caller_a:destroyer:known_destructor.move(/marker, holder)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:known_destructor.move(holder, /marker)": [
            "caller_a:destroyer:known_destructor.move(/marker, holder)"
        ],
        "caller_a:destroyer.destroy(target::/marker)": [
            "caller_a:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_a:destroyer.destroy(target)": [
            "caller_a:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_a.destroy(destroyer_particle)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)",
            "caller_a:destroyer.destroy(target)",
        ],
        "caller_a.destroy(trigger_pos)": ["test.create(/caller_a::trigger_pos)"],
        "caller_b.create(destroyer_particle)": [],
        "caller_b.create(carrier)": [],
        "caller_b.create(carrier::/marker)": ["caller_b.create(carrier)"],
        "caller_b.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_b.create(destroyer_particle)",
            "caller_b.create(carrier::/marker)",
        ],
        "caller_b.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle)"
        ],
        # The caller's quality assignment order does not change the callee's
        # existing dependencies on their shared Position.
        "caller_b:destroyer:known_destructor.move(/marker, holder)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:known_destructor.move(holder, /marker)": [
            "caller_b:destroyer:known_destructor.move(/marker, holder)"
        ],
        "caller_b:destroyer:extra_destructor.move(/marker, holder)": [
            "caller_b:destroyer:known_destructor.move(holder, /marker)"
        ],
        "caller_b:destroyer:extra_destructor.move(holder, /marker)": [
            "caller_b:destroyer:extra_destructor.move(/marker, holder)"
        ],
        "caller_b:destroyer.destroy(target::/marker)": [
            "caller_b:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_b:destroyer.destroy(target)": [
            "caller_b:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_b.destroy(destroyer_particle)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)",
            "caller_b:destroyer.destroy(target)",
        ],
        "caller_b.destroy(trigger_pos)": ["test.create(/caller_b::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: remove redundant dependencies when binding contributed Destructor operations",
)
def test_destructor_ordering_move_retains_independent_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.create(carrier::/shared)": ["test.create(carrier)"],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier::/shared)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target::/shared, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target::/shared)": [
            "destroyer.move(target::/shared, holder)"
        ],
        "destroyer.create(target::/destination)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/destination)": [
            "destroyer.create(target::/destination)"
        ],
        "known_destructor.move(/shared, holder)": [
            "destroyer.move(holder, target::/shared)"
        ],
        "known_destructor.move(holder, /shared)": [
            "known_destructor.move(/shared, holder)"
        ],
        # The Move Rule retains the independent Fill Dependency because the
        # preceding Destructor Guarantee does not depend on it.
        "extra_destructor.move(/shared, /destination)": [
            "known_destructor.move(holder, /shared)",
            "destroyer.destroy(target::/destination)",
        ],
        "extra_destructor.move(/destination, /shared)": [
            "extra_destructor.move(/shared, /destination)"
        ],
        "destroyer.destroy(target::/shared)": [
            "extra_destructor.move(/destination, /shared)"
        ],
        "destroyer.destroy(target)": ["extra_destructor.move(/destination, /shared)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_destructor_ordering_fill_rule(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        # The Fill Rule selects each preceding Destroy as the single most recent
        # operation on /marker.
        "known_destructor.create(/marker)": ["destroyer.destroy(target::/marker)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_destructor_between_two_destroyer_known_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        "later_assigned_destructor.create(/marker)": [
            "earlier_assigned_destructor.destroy(/marker)"
        ],
        "later_assigned_destructor.destroy(/marker)": [
            "later_assigned_destructor.create(/marker)"
        ],
        # The caller-assigned Destructor's Fill Rule consumes the callee's final
        # Guarantee on their shared Position.
        "caller_destructor.create(/marker)": [
            "later_assigned_destructor.destroy(/marker)"
        ],
        "caller_destructor.destroy(/marker)": ["caller_destructor.create(/marker)"],
        # The callee's first Destructor retains the callee's preceding Destroy;
        # adding a caller does not change this dependency.
        "earlier_assigned_destructor.create(/marker)": [
            "destroyer.destroy(target::/marker)"
        ],
        "earlier_assigned_destructor.destroy(/marker)": [
            "earlier_assigned_destructor.create(/marker)"
        ],
        "destroyer.destroy(target)": ["caller_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_interleaves_destructors_with_destroyer_known_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        "fifth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        # The callee-known Destructors retain their existing relationship on
        # the shared Position.
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        # The caller-known Destructors consume each other's latest operations
        # on the shared Position.
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        # The callee's first Destructor still consumes its preceding Destroy.
        "second_destructor.create(/marker)": ["destroyer.destroy(target::/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        # The first caller-known Destructor consumes the callee's final Guarantee.
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["fifth_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: remove redundant dependencies when binding contributed Destructor operations",
)
def test_destructor_ordering_move_retains_independent_empty_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.create(carrier::/origin)": ["test.create(carrier)"],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier::/origin)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target::/origin, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target::/origin)": [
            "destroyer.move(target::/origin, holder)"
        ],
        "destroyer.create(target::/destination)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/destination)": [
            "destroyer.create(target::/destination)"
        ],
        "known_destructor.create(/destination)": [
            "destroyer.destroy(target::/destination)"
        ],
        "known_destructor.destroy(/destination)": [
            "known_destructor.create(/destination)"
        ],
        # Replacing the target Fill Dependency does not replace the independent
        # Empty Dependency selected for /origin.
        "extra_destructor.move(/origin, /destination)": [
            "destroyer.move(holder, target::/origin)",
            "known_destructor.destroy(/destination)",
        ],
        "extra_destructor.move(/destination, /origin)": [
            "extra_destructor.move(/origin, /destination)"
        ],
        "destroyer.destroy(target::/origin)": [
            "extra_destructor.move(/destination, /origin)"
        ],
        "destroyer.destroy(target)": ["extra_destructor.move(/destination, /origin)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_destructor_ordering_action_parent_rule(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target)": ["destroyer.move(target, holder)"],
        # The Fill Rule selects the latest operation on /marker's parent. Modular
        # resolution represents that relationship through the Action Parent Rule.
        "known_destructor.create(/marker)": ["destroyer.move(holder, target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_child_carried_by_parent_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(staging)": [],
        "test.create(staging::/child)": ["test.create(staging)"],
        "test.move(staging, box)": ["test.create(staging::/child)"],
        # The parent move is the firing Particle Operation for the destructor
        # assigned to the particle in its child position.
        "destructor.create(_noop)": ["test.move(staging, box)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/child)": ["test.move(staging, box)"],
        # Simultaneous parent and child destruction both follow the Move that
        # last operated on the particle and all of its child positions.
        "test.destroy(box)": ["test.move(staging, box)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_and_known_children_with_caller_known_occupancy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker_a)": ["test.create(source)"],
        "test.create(source::/marker_b)": ["test.create(source)"],
        "test.create(source::/maybe_empty)": ["test.create(source)"],
        "test.destroy(source::/maybe_empty)": ["test.create(source::/maybe_empty)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/marker_a)",
            "test.create(source::/marker_b)",
            "test.destroy(source::/maybe_empty)",
        ],
        "middle.move(run::/marker_a, holder_a)": ["test.move(source, /middle::run)"],
        "middle.move(holder_a, run::/marker_a)": [
            "middle.move(run::/marker_a, holder_a)"
        ],
        "middle.move(run::/marker_b, holder_b)": ["test.move(source, /middle::run)"],
        "middle.move(holder_b, run::/marker_b)": [
            "middle.move(run::/marker_b, holder_b)"
        ],
        "middle.create(run::/maybe_empty)": ["test.move(source, /middle::run)"],
        "middle.destroy(run::/maybe_empty)": ["middle.create(run::/maybe_empty)"],
        "middle.move(run, /destroyer::run)": [
            "middle.move(holder_a, run::/marker_a)",
            "middle.move(holder_b, run::/marker_b)",
            "middle.destroy(run::/maybe_empty)",
        ],
        "destroyer.move(run::/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_a, run::/marker_a)": [
            "destroyer.move(run::/marker_a, holder_a)"
        ],
        "destroyer.move(run::/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_b, run::/marker_b)": [
            "destroyer.move(run::/marker_b, holder_b)"
        ],
        # A directly known Destructor executes as an action even when the
        # particles satisfying its occupied requirements came from the caller.
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        # Each child Destroy follows the Destructor's final operation on that
        # Position.
        "destroyer.destroy(run::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "destroyer.destroy(run::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
        # Caller-known empty occupancy remains available when /destroyer creates
        # a particle in /maybe_empty.
        "destroyer.create(run::/maybe_empty)": ["middle.move(run, /destroyer::run)"],
        "destroyer.destroy(run::/maybe_empty)": ["destroyer.create(run::/maybe_empty)"],
        "destroyer.destroy(run)": [
            "destroyer.destroy(run::/maybe_empty)",
            "destruct.move(holder_a, /marker_a)",
            "destruct.move(holder_b, /marker_b)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="The compiler still makes vacancy wait for destructor work on retained particles",
)
def test_destructor_fragments_finish_before_cascade_frees_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/marker_a)": ["test.create(box)"],
        "test.create(box::/marker_b)": ["test.create(box)"],
        # The destructor's two occupied implied-position requirements bind
        # independently to the operations that filled their particles.
        "destruct.move(/marker_a, holder_a)": ["test.create(box::/marker_a)"],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": ["test.create(box::/marker_b)"],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        # Vacation does not wait for the destructor's temporary Moves through
        # the original positions, whose occupancy is preserved for destruction.
        "test.destroy(box::/marker_a)": ["test.create(box::/marker_a)"],
        "test.destroy(box::/marker_b)": ["test.create(box::/marker_b)"],
        "test.destroy(box)": [
            "test.create(box::/marker_a)",
            "test.create(box::/marker_b)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_auto_destruction_of_child_with_caller_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/extra)"],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # The callee's parent move is also an operation on the child position, so
        # it is the Destructor's most recent Action Parent operation.
        "child_destruct.create(_noop)": ["destroyer.move(run, local)"],
        "child_destruct.destroy(_noop)": ["child_destruct.create(_noop)"],
        # The Destructor does not operate on /extra, so its independent work does
        # not precede the caller-contributed child Destroy.
        "destroyer.destroy(local::/extra)": ["destroyer.move(run, local)"],
        # Simultaneous parent and child Destroys consume the same preceding Move.
        "destroyer.destroy(local)": ["destroyer.move(run, local)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_multiple_newly_known_children_with_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra_a)": ["test.create(source)"],
        "test.create(source::/extra_b)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": [
            "test.create(source::/extra_a)",
            "test.create(source::/extra_b)",
        ],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # The callee's parent move is the most recent Action Parent operation for
        # each newly known child's independently contributed Destructor.
        "destruct_a.create(_noop_a)": ["destroyer.move(run, local)"],
        "destruct_a.destroy(_noop_a)": ["destruct_a.create(_noop_a)"],
        "destruct_b.create(_noop_b)": ["destroyer.move(run, local)"],
        "destruct_b.destroy(_noop_b)": ["destruct_b.create(_noop_b)"],
        "destroyer.destroy(local::/extra_a)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local::/extra_b)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local)": ["destroyer.move(run, local)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_destructor_on_passed_particle_with_newly_known_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/extra)"],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # Discovering child destruction in the same Destruction Contract must
        # not suppress the passed particle's Destructor or its dependency on the
        # callee's most recent Action Parent operation.
        "parent_destruct.create(_noop)": ["destroyer.move(run, local)"],
        "parent_destruct.destroy(_noop)": ["parent_destruct.create(_noop)"],
        "destroyer.destroy(local::/extra)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local)": ["destroyer.move(run, local)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_newly_known_grandchild_destructor_uses_callee_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/known)": ["test.create(source)"],
        "test.create(source::/known::/extra)": ["test.create(source::/known)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/known::/extra)"],
        "destroyer.move(run::/known, holder)": ["test.move(source, /destroyer::run)"],
        "destroyer.move(holder, run::/known)": ["destroyer.move(run::/known, holder)"],
        # Restoring the child is also an operation on its caller-known grandchild,
        # making it the Destructor's most recent Action Parent operation.
        "grandchild_destruct.create(_noop)": ["destroyer.move(holder, run::/known)"],
        "grandchild_destruct.destroy(_noop)": ["grandchild_destruct.create(_noop)"],
        "destroyer.destroy(run::/known::/extra)": [
            "destroyer.move(holder, run::/known)"
        ],
        # Every simultaneous Destroy follows the Move that last operated on the
        # child particle and its transitive child Positions.
        "destroyer.destroy(run::/known)": ["destroyer.move(holder, run::/known)"],
        "destroyer.destroy(run)": ["destroyer.move(holder, run::/known)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_contributed_child_destructor_depends_on_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.move(held_result, /required)": [
            "destruct.move(/required, held_result)"
        ],
        "destruct.move(/sibling, held_sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destruct.move(held_sibling, /sibling)": [
            "destruct.move(/sibling, held_sibling)"
        ],
        # The caller-known Destructor operates on this callee-guaranteed child
        # before the callee destroys it.
        "destroyer.destroy(parent::/required)": [
            "destruct.move(held_result, /required)"
        ],
        # The same Destructor also operates on the later caller-contributed child
        # before its contributed destruction fragment runs.
        "destroyer.destroy(parent::/sibling)": [
            "destruct.move(held_sibling, /sibling)"
        ],
        "destroyer.destroy(parent)": [
            "destruct.move(held_result, /required)",
            "destruct.move(held_sibling, /sibling)",
            "maker.destroy(trigger_pos)",
        ],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_known_destructor_precedes_destroyer_known_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /destroyer::parent)": ["test.create(source)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.move(held_result, /required)": [
            "destruct.move(/required, held_result)"
        ],
        # The caller-known Destructor's final Move fills /required before its
        # Destroy.
        "destroyer.destroy(parent::/required)": [
            "destruct.move(held_result, /required)"
        ],
        "destroyer.destroy(parent)": [
            "destruct.move(held_result, /required)",
            "maker.destroy(trigger_pos)",
        ],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_two_caller_known_destructors_precede_same_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        # Both Destructors operate on /required, so the Empty Rule makes the
        # second Destructor consume the first Destructor's final Move.
        "destruct_b.move(/required, held_result)": [
            "destruct_a.move(held_result, /required)"
        ],
        "destruct_b.move(held_result, /required)": [
            "destruct_b.move(/required, held_result)"
        ],
        "destruct_a.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct_a.move(held_result, /required)": [
            "destruct_a.move(/required, held_result)"
        ],
        # The final Destructor's last Move fills the child position before the
        # destruction cascade in /destroyer destroys its particle.
        "destroyer.destroy(parent::/required)": [
            "destruct_b.move(held_result, /required)"
        ],
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent)": [
            "destruct_b.move(held_result, /required)",
            "maker.destroy(trigger_pos)",
        ],
        "destroyer.destroy(trigger_pos)": ["test.create(/destroyer::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_known_child_destroy_and_destructor_precede_parent_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.create(source::/required::/extra)": ["test.create(source::/required)"],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": [
            "test.create(source::/required::/extra)",
            "test.create(source::/sibling)",
        ],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct_required.move(/required, held_required)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct_required.move(held_required, /required)": [
            "destruct_required.move(/required, held_required)"
        ],
        "destruct_sibling.move(/sibling, held_sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destruct_sibling.move(held_sibling, /sibling)": [
            "destruct_sibling.move(/sibling, held_sibling)"
        ],
        # The Empty Rule for /extra collects the Destructor's final Move on
        # its parent Position, even though another contribution records it.
        "destroyer.destroy(parent::/required::/extra)": [
            "destruct_required.move(held_required, /required)"
        ],
        # The simultaneous parent Destroy also consumes the Destructor's Move;
        # it does not depend on the child Destroy.
        "destroyer.destroy(parent::/required)": [
            "destruct_required.move(held_required, /required)"
        ],
        "destroyer.destroy(parent::/sibling)": [
            "destruct_sibling.move(held_sibling, /sibling)"
        ],
        "destroyer.destroy(parent)": [
            "destruct_required.move(held_required, /required)",
            "destruct_sibling.move(held_sibling, /sibling)",
        ],
        "destroyer.destroy(trigger_pos)": ["test.create(/destroyer::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_contributed_destructor_operates_on_child_of_occupied_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        # The Fill Rule makes the Destructor's Create depend on /destroyer's
        # final Move into the parent position of its empty /required::/work.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required)": ["destruct.destroy(/required::/work)"],
        "destroyer.destroy(parent)": ["destruct.destroy(/required::/work)"],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: remove redundant dependencies when binding contributed Destructor operations",
)
def test_contributed_destructor_depends_on_callee_move_with_two_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.create(held_required::/left)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.create(held_required::/right)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.destroy(held_required::/left)": [
            "destroyer.create(held_required::/left)"
        ],
        "destroyer.destroy(held_required::/right)": [
            "destroyer.create(held_required::/right)"
        ],
        # The Move Rule retains both sibling child Destroys as independent Empty
        # Dependencies of the Move back to /required.
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.destroy(held_required::/left)",
            "destroyer.destroy(held_required::/right)",
        ],
        # The Fill Rule makes the Destructor's Create depend on the completed
        # Move rather than either of the Move's dependencies directly.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required)": ["destruct.destroy(/required::/work)"],
        "destroyer.destroy(parent)": ["destruct.destroy(/required::/work)"],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: remove redundant dependencies when binding contributed Destructor operations",
)
def test_callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.create(held_required::/extra_a)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.create(held_required::/extra_b)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.create(held_required::/extra_a)",
            "destroyer.create(held_required::/extra_b)",
        ],
        # The Fill Rule makes the Destructor's Create depend on /destroyer's
        # final Move into the parent position of its empty /required::/work.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required::/extra_a)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destroyer.destroy(parent::/required::/extra_b)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        # The Destructor's final operation follows the Move that most recently
        # operated on /extra_a and /extra_b, so the Empty Rule retains only it.
        "destroyer.destroy(parent::/required)": ["destruct.destroy(/required::/work)"],
        "destroyer.destroy(parent)": ["destruct.destroy(/required::/work)"],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_destructor_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker_a)": ["test.create(source)"],
        "test.create(source::/marker_b)": ["test.create(source)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/marker_a)",
            "test.create(source::/marker_b)",
        ],
        "middle.move(run::/marker_a, holder_a)": ["test.move(source, /middle::run)"],
        "middle.move(holder_a, run::/marker_a)": [
            "middle.move(run::/marker_a, holder_a)"
        ],
        "middle.move(run::/marker_b, holder_b)": ["test.move(source, /middle::run)"],
        "middle.move(holder_b, run::/marker_b)": [
            "middle.move(run::/marker_b, holder_b)"
        ],
        "middle.move(run, /destroyer::run)": [
            "middle.move(holder_a, run::/marker_a)",
            "middle.move(holder_b, run::/marker_b)",
        ],
        "destroyer.move(run::/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_a, run::/marker_a)": [
            "destroyer.move(run::/marker_a, holder_a)"
        ],
        "destroyer.move(run::/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_b, run::/marker_b)": [
            "destroyer.move(run::/marker_b, holder_b)"
        ],
        # The Destruction Contract from /test propagates through /middle so its
        # caller-known Destructor executes when /destroyer destroys the particle.
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        # /destroyer's destruction cascade waits for the transitively contributed
        # Destructor before destroying the caller-supplied children.
        "destroyer.destroy(run::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "destroyer.destroy(run::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
        "destroyer.destroy(run)": [
            "destruct.move(holder_a, /marker_a)",
            "destruct.move(holder_b, /marker_b)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_default_empty_destructor_position_uses_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/callee::src)": ["test.create(carrier)"],
        "test.create(carrier::/callee::trigger_pos)": ["test.create(carrier)"],
        "callee.destroy(src)": ["destructor.destroy(/marker)"],
        # Only the caller knows that /marker started empty, so its creation of
        # the parent particle supplies the destructor's empty requirement.
        "destructor.create(/marker)": ["test.create(carrier::/callee::src)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
        "test.destroy(carrier::/callee::trigger_pos)": [
            "test.create(carrier::/callee::trigger_pos)"
        ],
        "test.destroy(carrier)": [
            "test.destroy(carrier::/callee::trigger_pos)",
            "callee.destroy(src)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_emptied_destructor_position_uses_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(source)": [],
        "test.create(source::/marker)": ["test.create(source)"],
        "test.destroy(source::/marker)": ["test.create(source::/marker)"],
        "test.move(source, carrier::/callee::src)": [
            "test.create(carrier)",
            "test.destroy(source::/marker)",
        ],
        "test.create(carrier::/callee::trigger_pos)": ["test.create(carrier)"],
        "callee.destroy(src)": ["destructor.destroy(/marker)"],
        # Only the caller knows that its destroy made /marker empty. The parent
        # move depends on that destroy and supplies the destructor requirement.
        "destructor.create(/marker)": ["test.move(source, carrier::/callee::src)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
        "test.destroy(carrier::/callee::trigger_pos)": [
            "test.create(carrier::/callee::trigger_pos)"
        ],
        "test.destroy(carrier)": [
            "test.destroy(carrier::/callee::trigger_pos)",
            "callee.destroy(src)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_moves_callee_guaranteed_particle_before_destroying(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(temp)": ["test.create(box)"],
        "maker.move(temp, result)": ["maker.create(temp)"],
        "test.move(box::/maker::result, held)": ["maker.move(temp, result)"],
        # After the move, it is the operation that fires the destructor.
        "destructor.create(_noop)": ["test.move(box::/maker::result, held)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(held)": ["test.move(box::/maker::result, held)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        # The parent Destroy follows the operations that most recently operated
        # on its now-empty result Position and occupied run Position.
        "test.destroy(box)": [
            "test.create(box::/maker::run)",
            "test.move(box::/maker::result, held)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        # The Guarantee both fires the destructor and is the caller operation bound
        # to the destructor's Action Parent Binding Hole.
        "destructor.create(_noop)": ["maker.create(result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/maker::result)": ["maker.create(result)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.create(box::/maker::run)",
            "test.destroy(box::/maker::result)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_callee_guarantee_with_child_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        "maker.create(result::/marker)": ["maker.create(result)"],
        # The child Guarantee is the most recent operation satisfying the
        # Destructor's occupied requirement and follows its Action Parent Create.
        "destructor.move(/marker, holder)": ["maker.create(result::/marker)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "test.destroy(box::/maker::result::/marker)": [
            "destructor.move(holder, /marker)"
        ],
        "test.destroy(box::/maker::result)": ["destructor.move(holder, /marker)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.create(box::/maker::run)",
            "test.destroy(box::/maker::result)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/make_thing::run)": ["test.create(box)"],
        "make_thing.create(temp)": ["test.create(box)"],
        "make_thing.move(temp, result)": ["make_thing.create(temp)"],
        # The move propagates the destructor even though result has no such constraint.
        "destructor.create(_noop)": ["make_thing.move(temp, result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/make_thing::result)": ["make_thing.move(temp, result)"],
        "test.destroy(box::/make_thing::run)": ["test.create(box::/make_thing::run)"],
        "test.destroy(box)": [
            "test.create(box::/make_thing::run)",
            "test.destroy(box::/make_thing::result)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_attached_in_callee_on_implied_position_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(temp)": ["test.create(box)"],
        "maker.move(temp, /child)": ["maker.create(temp)"],
        # The implied-position guarantee propagates and fires the destructor that
        # /maker attached to the particle.
        "destructor.create(_noop)": ["maker.move(temp, /child)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/child)": ["maker.move(temp, /child)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.create(box::/maker::run)",
            "test.destroy(box::/child)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_transitive_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::run)": ["test.create(gateway)"],
        "middle.create(box)": ["test.create(gateway)"],
        "middle.create(box::/inner::run)": ["middle.create(box)"],
        "inner.create(result)": ["middle.create(box)"],
        "inner.create(result::/marker)": ["inner.create(result)"],
        "middle.move(box::/inner::result::/marker, held_marker)": [
            "inner.create(result::/marker)"
        ],
        "middle.move(box::/inner::result, result)": [
            "middle.move(box::/inner::result::/marker, held_marker)"
        ],
        "middle.move(held_marker, result::/marker)": [
            "middle.move(box::/inner::result, result)"
        ],
        "middle.destroy(box::/inner::run)": ["middle.create(box::/inner::run)"],
        "middle.destroy(box)": [
            "middle.move(box::/inner::result, result)",
            "middle.destroy(box::/inner::run)",
        ],
        # The explicitly transferred result guarantee fires the Destructor and
        # supplies the particle bound to its Action Parent Binding Hole.
        "destructor.create(_noop)": ["middle.move(box::/inner::result, result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        # Explicitly transferring the child supplies the Destructor's occupied
        # requirement without exposing /inner's interface position to /test.
        "destructor.move(/marker, holder)": [
            "middle.move(held_marker, result::/marker)"
        ],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "test.destroy(gateway::/middle::result::/marker)": [
            "destructor.move(holder, /marker)"
        ],
        "test.destroy(gateway::/middle::result)": ["destructor.move(holder, /marker)"],
        "test.destroy(gateway::/middle::run)": ["test.create(gateway::/middle::run)"],
        "test.destroy(gateway)": [
            "test.create(gateway::/middle::run)",
            "test.destroy(gateway::/middle::result)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_implied_position_from_transitive_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::run)": ["test.create(box)"],
        "middle.create(/inner::run)": ["test.create(box)"],
        "inner.create(/child)": ["test.create(box)"],
        # The transitive implied-position guarantee fires the destructor.
        "destructor.create(_noop)": ["inner.create(/child)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "middle.destroy(/inner::run)": ["middle.create(/inner::run)"],
        "test.destroy(box::/child)": ["inner.create(/child)"],
        "test.destroy(box::/middle::run)": ["test.create(box::/middle::run)"],
        "test.destroy(box)": [
            "test.create(box::/middle::run)",
            "test.destroy(box::/child)",
            "middle.destroy(/inner::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_destructor_with_children_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "destruct.destroy(work)": ["destruct.create(work)"],
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.create(source::/extra::/marker_a)": ["test.create(source::/extra)"],
        "test.create(source::/extra::/marker_b)": ["test.create(source::/extra)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/extra::/marker_a)",
            "test.create(source::/extra::/marker_b)",
        ],
        "middle.move(run, /destroyer::run)": ["test.move(source, /middle::run)"],
        "destruct.create(work)": ["middle.move(run, /destroyer::run)"],
        "child_destruct.move(/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "child_destruct.move(holder_a, /marker_a)": [
            "child_destruct.move(/marker_a, holder_a)"
        ],
        "child_destruct.move(/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "child_destruct.move(holder_b, /marker_b)": [
            "child_destruct.move(/marker_b, holder_b)"
        ],
        "destroyer.destroy(run::/extra::/marker_a)": [
            "child_destruct.move(holder_a, /marker_a)"
        ],
        "destroyer.destroy(run::/extra::/marker_b)": [
            "child_destruct.move(holder_b, /marker_b)"
        ],
        "destroyer.destroy(run::/extra)": [
            "child_destruct.move(holder_a, /marker_a)",
            "child_destruct.move(holder_b, /marker_b)",
        ],
        "destroyer.destroy(run)": [
            "child_destruct.move(holder_a, /marker_a)",
            "child_destruct.move(holder_b, /marker_b)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_destructors_all_fire_on_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.create(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.create(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_destructors_on_particle_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        # One guarantee independently fires both destructors.
        "destruct_a.create(_noop)": ["maker.create(result)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["maker.create(result)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
        "test.destroy(box::/maker::result)": ["maker.create(result)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.create(box::/maker::run)",
            "test.destroy(box::/maker::result)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_fires_in_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        "destructor.create(_noop)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_discovers_callees_and_their_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        "destructor.create(worker)": ["test.move(carrier, box::/callee::target)"],
        "destructor.create(source)": ["test.move(carrier, box::/callee::target)"],
        "destructor.move(source, worker::/worker::target)": [
            "destructor.create(worker)",
            "destructor.create(source)",
        ],
        "worker.create(target::/child)": [
            "destructor.move(source, worker::/worker::target)"
        ],
        "worker:child_destructor.create(work)": ["worker.create(target::/child)"],
        "worker:child_destructor.destroy(work)": [
            "worker:child_destructor.create(work)"
        ],
        # Local Destructor work does not add dependencies to either Destroy.
        "worker.destroy(target::/child)": ["worker.create(target::/child)"],
        "worker.destroy(target)": ["worker.create(target::/child)"],
        "destructor.create(source)#2": [
            "destructor.move(source, worker::/worker::target)"
        ],
        "destructor.move(source, worker::/worker::target)#2": [
            "destructor.create(source)#2",
            "worker.destroy(target)",
        ],
        "worker#2.create(target::/child)": [
            "destructor.move(source, worker::/worker::target)#2"
        ],
        "worker#2:child_destructor.create(work)": ["worker#2.create(target::/child)"],
        "worker#2:child_destructor.destroy(work)": [
            "worker#2:child_destructor.create(work)"
        ],
        "worker#2.destroy(target::/child)": ["worker#2.create(target::/child)"],
        "worker#2.destroy(target)": ["worker#2.create(target::/child)"],
        "destructor.create(contributor)": ["test.move(carrier, box::/callee::target)"],
        "destructor.move(contributor, worker::/nested_worker::target)": [
            "destructor.create(worker)",
            "destructor.create(contributor)",
        ],
        "nested_worker.destroy(target)": [
            "destructor.move(contributor, worker::/nested_worker::target)"
        ],
        "inner_destructor.create(work)": [
            "destructor.move(contributor, worker::/nested_worker::target)"
        ],
        "inner_destructor.destroy(work)": ["inner_destructor.create(work)"],
        "destructor.create(contributor)#2": [
            "destructor.move(contributor, worker::/nested_worker::target)"
        ],
        "destructor.move(contributor, worker::/nested_worker::target)#2": [
            "destructor.create(contributor)#2",
            "nested_worker.destroy(target)",
        ],
        "nested_worker#2.destroy(target)": [
            "destructor.move(contributor, worker::/nested_worker::target)#2"
        ],
        "inner_destructor#2.create(work)": [
            "destructor.move(contributor, worker::/nested_worker::target)#2"
        ],
        "inner_destructor#2.destroy(work)": ["inner_destructor#2.create(work)"],
        "destructor.destroy(worker)": [
            "worker#2.destroy(target)",
            "nested_worker#2.destroy(target)",
        ],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_fans_out_from_action_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # Both independent Destructor chains receive the same Action Parent
        # dependency from the operation that moved the destroyed particle.
        "destructor.create(work_a)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(work_a)": ["destructor.create(work_a)"],
        "destructor.create(work_b)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(work_b)": ["destructor.create(work_b)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_with_later_action_execution(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(later_box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(carrier)#2": ["test.move(carrier, box::/callee::target)"],
        "test.move(carrier, later_box::/later::target)": [
            "test.create(later_box)",
            "test.create(carrier)#2",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # The two direct Action Executions independently fire the same
        # caller-contributed Destructor from their respective particle Moves.
        "destructor.create(_noop)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.create(later_box::/later::run)": ["test.create(later_box)"],
        "later.destroy(target)": ["test.move(carrier, later_box::/later::target)"],
        "destructor#2.create(_noop)": ["test.move(carrier, later_box::/later::target)"],
        "destructor#2.destroy(_noop)": ["destructor#2.create(_noop)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
        "test.destroy(later_box::/later::run)": ["test.create(later_box::/later::run)"],
        "test.destroy(later_box)": [
            "test.create(later_box::/later::run)",
            "later.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_multiple_destructors_fire_in_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # The same callee Destroy independently fires both caller-added
        # Destructors from the operation that moved their parent particle.
        "destructor_a.create(work)": ["test.move(carrier, box::/callee::target)"],
        "destructor_a.destroy(work)": ["destructor_a.create(work)"],
        "destructor_b.create(work)": ["test.move(carrier, box::/callee::target)"],
        "destructor_b.destroy(work)": ["destructor_b.create(work)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_and_destructors_modify_same_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(/marker)": ["test.create(box)"],
        "construct_b.move(/marker, holder)": ["construct_a.create(/marker)"],
        "construct_b.move(holder, /marker)": ["construct_b.move(/marker, holder)"],
        "destruct_a.move(/marker, holder)": ["construct_b.move(holder, /marker)"],
        "destruct_a.move(holder, /marker)": ["destruct_a.move(/marker, holder)"],
        "destruct_b.move(/marker, holder)": ["destruct_a.move(holder, /marker)"],
        "destruct_b.move(holder, /marker)": ["destruct_b.move(/marker, holder)"],
        "test.destroy(box::/marker)": ["destruct_b.move(holder, /marker)"],
        # Both simultaneous Destroys follow the last Destructor operation on
        # the shared implied Position.
        "test.destroy(box)": ["destruct_b.move(holder, /marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_run_in_parallel_with_destroy_and_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(scratch)": ["test.create(box)"],
        "construct_a.destroy(scratch)": ["construct_a.create(scratch)"],
        "construct_b.create(scratch)": ["test.create(box)"],
        "construct_b.destroy(scratch)": ["construct_b.create(scratch)"],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.create(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.create(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_all_positions_three_destroyer_occupied_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "second_destructor.move(holder, /second)",
            "third_destructor.move(holder, /third)",
            "third_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_all_positions_five_destroyer_occupied_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "fifth_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "second_destructor.move(holder, /second)",
            "third_destructor.move(holder, /third)",
            "fourth_destructor.move(holder, /fourth)",
            "fifth_destructor.move(holder, /fifth)",
            "fifth_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_empty_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "second_destructor.destroy(/second)",
            "third_destructor.destroy(/third)",
            "third_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_empty_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "fifth_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "second_destructor.destroy(/second)",
            "third_destructor.destroy(/third)",
            "fourth_destructor.destroy(/fourth)",
            "fifth_destructor.destroy(/fifth)",
            "fifth_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_occupied_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "second_destructor.destroy(/second)",
            "third_destructor.move(holder, /third)",
            "third_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_occupied_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "fifth_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "second_destructor.move(holder, /second)",
            "third_destructor.destroy(/third)",
            "fourth_destructor.move(holder, /fourth)",
            "fifth_destructor.destroy(/fifth)",
            "fifth_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_all_positions_three_destroyer_empty_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "second_destructor.move(holder, /second)",
            "third_destructor.destroy(/third)",
            "third_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_all_positions_five_destroyer_empty_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Position's Fill and Empty Rules serialize the Destructor
        # operations.
        "fifth_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "second_destructor.destroy(/second)",
            "third_destructor.move(holder, /third)",
            "fourth_destructor.destroy(/fourth)",
            "fifth_destructor.move(holder, /fifth)",
            "fifth_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_three_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "second_destructor.move(holder, /second)",
            "second_destructor.destroy(/marker)",
            "first_destructor.move(holder, /first)",
            "third_destructor.move(holder, /third)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_five_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "fifth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "third_destructor.move(holder, /third)",
            "fifth_destructor.move(holder, /fifth)",
            "fifth_destructor.destroy(/marker)",
            "second_destructor.move(holder, /second)",
            "fourth_destructor.move(holder, /fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_three_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "second_destructor.destroy(/second)",
            "second_destructor.destroy(/marker)",
            "first_destructor.destroy(/first)",
            "third_destructor.destroy(/third)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_five_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "fifth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "third_destructor.destroy(/third)",
            "fifth_destructor.destroy(/fifth)",
            "fifth_destructor.destroy(/marker)",
            "second_destructor.destroy(/second)",
            "fourth_destructor.destroy(/fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_three_empty_children_between_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "second_destructor.destroy(/second)",
            "second_destructor.destroy(/marker)",
            "first_destructor.move(holder, /first)",
            "third_destructor.move(holder, /third)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_five_empty_children_between_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "fifth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "first_destructor.destroy(/first)",
            "third_destructor.destroy(/third)",
            "fifth_destructor.destroy(/fifth)",
            "fifth_destructor.destroy(/marker)",
            "second_destructor.move(holder, /second)",
            "fourth_destructor.move(holder, /fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_three_occupied_children_between_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "second_destructor.move(holder, /second)",
            "second_destructor.destroy(/marker)",
            "first_destructor.destroy(/first)",
            "third_destructor.destroy(/third)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_introduces_five_occupied_children_between_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "fifth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "third_destructor.move(holder, /third)",
            "fifth_destructor.move(holder, /fifth)",
            "fifth_destructor.destroy(/marker)",
            "second_destructor.destroy(/second)",
            "fourth_destructor.destroy(/fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_creator_reverse_child_order_is_canonical_across_three_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "worker.create(/first_interface)": ["test.create(carrier)"],
        "worker.create(/second_interface)": ["test.create(carrier)"],
        "test.move(carrier, /middle::target)": [
            "test.create(carrier::/third)",
            "worker.create(/first_interface)",
            "worker.create(/second_interface)",
        ],
        "middle.create(target::/first)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/second)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/fifth)": ["test.move(carrier, /middle::target)"],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/first)",
            "middle.create(target::/second)",
            "middle.create(target::/fifth)",
        ],
        "destroyer.move(target::/second, second_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.move(second_holder, target::/second)": [
            "destroyer.move(target::/second, second_holder)"
        ],
        "destroyer.create(target::/fourth)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(/first, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.move(second_holder, target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": [
            "middle.move(target, /destroyer::target)"
        ],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "third_destructor.move(/third, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "destroyer.destroy(target::/second_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target::/first_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "fifth_destructor.move(/fifth, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        "fifth_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "fifth_destructor.move(holder, /fifth)",
            "third_destructor.move(holder, /third)",
            "third_destructor.destroy(/marker)",
            "second_destructor.move(holder, /second)",
            "fourth_destructor.move(holder, /fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_creator_nonoverlapping_child_order_is_canonical_across_three_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "worker.create(/first_interface)": ["test.create(carrier)"],
        "worker.create(/second_interface)": ["test.create(carrier)"],
        "test.move(carrier, /middle::target)": [
            "test.create(carrier::/third)",
            "worker.create(/first_interface)",
            "worker.create(/second_interface)",
        ],
        "middle.create(target::/first)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/second)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/fifth)": ["test.move(carrier, /middle::target)"],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/first)",
            "middle.create(target::/second)",
            "middle.create(target::/fifth)",
        ],
        "destroyer.move(target::/second, second_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.move(second_holder, target::/second)": [
            "destroyer.move(target::/second, second_holder)"
        ],
        "destroyer.create(target::/fourth)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(/first, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        # The shared Position's Fill and Empty Rules connect the caller's
        # Destructors to the callee's final Guarantee.
        "first_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "second_destructor.move(/second, holder)": [
            "destroyer.move(second_holder, target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": [
            "middle.move(target, /destroyer::target)"
        ],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "fifth_destructor.move(/fifth, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        "fifth_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "third_destructor.move(/third, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "destroyer.destroy(target::/second_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target::/first_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target)": [
            "first_destructor.move(holder, /first)",
            "fifth_destructor.move(holder, /fifth)",
            "third_destructor.move(holder, /third)",
            "third_destructor.destroy(/marker)",
            "second_destructor.move(holder, /second)",
            "fourth_destructor.move(holder, /fourth)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_direct_destructor_with_mixed_implied_position_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/occupied_first)": ["test.create(source)"],
        "test.create(source::/occupied_first::/transitive)": [
            "test.create(source::/occupied_first)"
        ],
        "test.create(source::/occupied_last)": ["test.create(source)"],
        "test.move(source, /destroyer::target)": [
            "test.create(source::/occupied_first::/transitive)",
            "test.create(source::/occupied_last)",
        ],
        # The directly known Destructor starts after the Move of its Action
        # Parent and the occupied implied-position particles it uses.
        "destructor.move(/occupied_first, first_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(first_holder, /occupied_first)": [
            "destructor.move(/occupied_first, first_holder)"
        ],
        "destructor.move(/occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, /occupied_first)"
        ],
        "destructor.move(transitive_holder, /occupied_first::/transitive)": [
            "destructor.move(/occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(/empty)": ["test.move(source, /destroyer::target)"],
        "destructor.destroy(/empty)": ["destructor.create(/empty)"],
        "destructor.move(/occupied_last, last_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(last_holder, /occupied_last)": [
            "destructor.move(/occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/occupied_last)": [
            "destructor.move(last_holder, /occupied_last)"
        ],
        "destroyer.destroy(target::/occupied_first::/transitive)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/occupied_first)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destructor.destroy(/empty)",
            "destructor.move(last_holder, /occupied_last)",
            "destructor.move(transitive_holder, /occupied_first::/transitive)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: remove redundant dependencies when binding contributed Destructor operations",
)
def test_caller_contributed_destructor_with_mixed_implied_position_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/occupied_first)": ["test.create(source)"],
        "test.create(source::/occupied_first::/transitive)": [
            "test.create(source::/occupied_first)"
        ],
        "test.create(source::/occupied_last)": ["test.create(source)"],
        "test.move(source, /destroyer::target)": [
            "test.create(source::/occupied_first::/transitive)",
            "test.create(source::/occupied_last)",
        ],
        # The caller-contributed Destructor retains the caller's Move as the
        # predecessor for both its Action Parent and occupied Requirements.
        "destructor.move(/occupied_first, first_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(first_holder, /occupied_first)": [
            "destructor.move(/occupied_first, first_holder)"
        ],
        "destructor.move(/occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, /occupied_first)"
        ],
        "destructor.move(transitive_holder, /occupied_first::/transitive)": [
            "destructor.move(/occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(/empty)": ["test.move(source, /destroyer::target)"],
        "destructor.destroy(/empty)": ["destructor.create(/empty)"],
        "destructor.move(/occupied_last, last_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(last_holder, /occupied_last)": [
            "destructor.move(/occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/occupied_last)": [
            "destructor.move(last_holder, /occupied_last)"
        ],
        "destroyer.destroy(target::/occupied_first::/transitive)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/occupied_first)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destructor.destroy(/empty)",
            "destructor.move(last_holder, /occupied_last)",
            "destructor.move(transitive_holder, /occupied_first::/transitive)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_destructor_implied_position_state_completed_by_creator(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/bundle)": [],
        "test.create(/bundle::/occupied_first)": ["test.create(/bundle)"],
        "test.create(/bundle::/occupied_first::/transitive)": [
            "test.create(/bundle::/occupied_first)"
        ],
        "test.move(/bundle, /middle::target)": [
            "test.create(/bundle::/occupied_first::/transitive)"
        ],
        "middle.create(target::/occupied_last)": [
            "test.move(/bundle, /middle::target)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/occupied_last)"
        ],
        # The final Move combines the creator-known and callee-created implied
        # position state before the Destructor can use its occupied Requirements.
        "destructor.move(/occupied_first, first_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(first_holder, /occupied_first)": [
            "destructor.move(/occupied_first, first_holder)"
        ],
        "destructor.move(/occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, /occupied_first)"
        ],
        "destructor.move(transitive_holder, /occupied_first::/transitive)": [
            "destructor.move(/occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(/empty)": ["middle.move(target, /destroyer::target)"],
        "destructor.destroy(/empty)": ["destructor.create(/empty)"],
        "destructor.move(/occupied_last, last_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(last_holder, /occupied_last)": [
            "destructor.move(/occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/occupied_last)": [
            "destructor.move(last_holder, /occupied_last)"
        ],
        "destroyer.destroy(target::/occupied_first::/transitive)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/occupied_first)": [
            "destructor.move(transitive_holder, /occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destructor.destroy(/empty)",
            "destructor.move(last_holder, /occupied_last)",
            "destructor.move(transitive_holder, /occupied_first::/transitive)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_two_destruction_facts_with_distinct_destructor_sets(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_source)": [],
        "test.create(second_source)": [],
        "test.move(first_source, /destroyer::first)": ["test.create(first_source)"],
        "test.move(second_source, /destroyer::second)": ["test.create(second_source)"],
        "test.create(/destroyer::run)": [],
        # Each Destruction Fact resolves only the Destructors assigned to its
        # particle without creating edges between their independent work.
        "extra_destructor.create(work)": ["test.move(first_source, /destroyer::first)"],
        "extra_destructor.destroy(work)": ["extra_destructor.create(work)"],
        "shared_destructor.create(work)": [
            "test.move(first_source, /destroyer::first)"
        ],
        "shared_destructor.destroy(work)": ["shared_destructor.create(work)"],
        "direct_destructor.create(work)": [
            "test.move(first_source, /destroyer::first)"
        ],
        "direct_destructor.destroy(work)": ["direct_destructor.create(work)"],
        "destroyer.destroy(first)": ["test.move(first_source, /destroyer::first)"],
        "shared_destructor#2.create(work)": [
            "test.move(second_source, /destroyer::second)"
        ],
        "shared_destructor#2.destroy(work)": ["shared_destructor#2.create(work)"],
        "destroyer.destroy(second)": ["test.move(second_source, /destroyer::second)"],
        "test.destroy(/destroyer::run)": ["test.create(/destroyer::run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_destroyer_executions_receive_own_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(a_only)": [],
        "test.move(a_only, /destroyer::target)": ["test.create(a_only)"],
        "destructor_a.create(work)": ["test.move(a_only, /destroyer::target)"],
        "destructor_a.destroy(work)": ["destructor_a.create(work)"],
        "destroyer.destroy(target)": ["test.move(a_only, /destroyer::target)"],
        "test.create(a_and_b)": [],
        "test.move(a_and_b, /destroyer::target)": [
            "test.create(a_and_b)",
            "destroyer.destroy(target)",
        ],
        "destructor_a#2.create(work)": ["test.move(a_and_b, /destroyer::target)"],
        "destructor_a#2.destroy(work)": ["destructor_a#2.create(work)"],
        "destructor_b.create(work)": ["test.move(a_and_b, /destroyer::target)"],
        "destructor_b.destroy(work)": ["destructor_b.create(work)"],
        "destroyer#2.destroy(target)": ["test.move(a_and_b, /destroyer::target)"],
        "test.create(b_only)": [],
        "test.move(b_only, /destroyer::target)": [
            "test.create(b_only)",
            "destroyer#2.destroy(target)",
        ],
        "destructor_b#2.create(work)": ["test.move(b_only, /destroyer::target)"],
        "destructor_b#2.destroy(work)": ["destructor_b#2.create(work)"],
        "destroyer#3.destroy(target)": ["test.move(b_only, /destroyer::target)"],
        "test.create(none)": [],
        "test.move(none, /destroyer::target)": [
            "test.create(none)",
            "destroyer#3.destroy(target)",
        ],
        "destroyer#4.destroy(target)": ["test.move(none, /destroyer::target)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: include and distinguish caller-contributed Destructor operations",
)
def test_destructor_requirements_resolved_across_three_callers(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source::/middle_known)": ["test.create(source)"],
        "test.destroy(source::/middle_known)": ["test.create(source::/middle_known)"],
        "test.create(source)": [],
        "test.create(source::/callee_known)": ["test.create(source)"],
        "test.destroy(source::/callee_known)": ["test.create(source::/callee_known)"],
        "test.create(source::/creator_known)": ["test.create(source)"],
        "test.move(source, /middle::target)": [
            "test.destroy(source::/callee_known)",
            "test.destroy(source::/middle_known)",
            "test.create(source::/creator_known)",
        ],
        "middle.create(target::/middle_known)": ["test.move(source, /middle::target)"],
        "middle.destroy(target::/middle_known)": [
            "middle.create(target::/middle_known)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.destroy(target::/middle_known)"
        ],
        "middle.create(/destroyer::run)": [],
        "destroyer.create(target::/callee_known)": [
            "middle.move(target, /destroyer::target)"
        ],
        # The callee, middle caller, and creator respectively supply the last
        # known states of these three Destructor requirement Positions.
        "destructor.move(/callee_known, callee_holder)": [
            "destroyer.create(target::/callee_known)"
        ],
        "destructor.move(callee_holder, /callee_known)": [
            "destructor.move(/callee_known, callee_holder)"
        ],
        "destructor.create(/middle_known)": ["middle.move(target, /destroyer::target)"],
        "destructor.destroy(/middle_known)": ["destructor.create(/middle_known)"],
        "destructor.move(/creator_known, creator_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(creator_holder, /creator_known)": [
            "destructor.move(/creator_known, creator_holder)"
        ],
        "destroyer.destroy(target::/callee_known)": [
            "destructor.move(callee_holder, /callee_known)"
        ],
        "destroyer.destroy(target::/creator_known)": [
            "destructor.move(creator_holder, /creator_known)"
        ],
        "destroyer.destroy(target)": [
            "destructor.move(callee_holder, /callee_known)",
            "destructor.destroy(/middle_known)",
            "destructor.move(creator_holder, /creator_known)",
        ],
        "destroyer.destroy(run)": ["middle.create(/destroyer::run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_callee_child_state_precedes_destructor_knowledge(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /middle::target)": ["test.create(source)"],
        "test.create(/middle::trigger)": [],
        "middle.move(target, /destroyer::target)": [
            "test.move(source, /middle::target)"
        ],
        "middle.create(/destroyer::trigger)": [],
        "middle.destroy(trigger)": ["test.create(/middle::trigger)"],
        "destroyer.create(target::/occupied)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.create(target::/empty)": ["middle.move(target, /destroyer::target)"],
        "destroyer.destroy(target::/empty)": ["destroyer.create(target::/empty)"],
        # The complete Child State originates in /destroyer, but only /middle
        # knows the Destructor assignment and therefore verifies this execution.
        "destructor.move(/occupied, holder)": ["destroyer.create(target::/occupied)"],
        "destructor.move(holder, /occupied)": ["destructor.move(/occupied, holder)"],
        "destructor.create(/empty)": ["destroyer.destroy(target::/empty)"],
        "destructor.destroy(/empty)": ["destructor.create(/empty)"],
        "destroyer.destroy(target::/occupied)": ["destructor.move(holder, /occupied)"],
        "destroyer.destroy(target)": [
            "destructor.move(holder, /occupied)",
            "destructor.destroy(/empty)",
        ],
        "destroyer.destroy(trigger)": ["middle.create(/destroyer::trigger)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_direct_and_implied_destructor_executes_once(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/bundle)": [],
        "test.create(/bundle::/marker)": ["test.create(/bundle)"],
        "test.move(/bundle, direct)": ["test.create(/bundle::/marker)"],
        "test.move(direct, /destroyer::target)": ["test.move(/bundle, direct)"],
        # The Position Constraint and the direct destination constraint assign
        # one Destructor quality to the same particle, so destruction creates
        # one Action Execution.
        "destructor.move(/marker, holder)": ["test.move(direct, /destroyer::target)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destructor.move(holder, /marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_destructor_reached_through_two_implication_paths(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/left)": [],
        "test.create(/left::/marker)": ["test.create(/left)"],
        "test.move(/left, /right)": ["test.create(/left::/marker)"],
        "test.move(/right, /destroyer::target)": ["test.move(/left, /right)"],
        # Moving the particle through the second implied Position does not
        # duplicate the Destructor first assigned in /left.
        "destructor.move(/marker, holder)": ["test.move(/right, /destroyer::target)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destructor.move(holder, /marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_nested_caller_contributed_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(outer)": [],
        "outer_destructor.create(inner_destroyer_particle)": ["test.create(outer)"],
        "outer_destructor.create(inner_source)": ["test.create(outer)"],
        "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(inner_destroyer_particle)",
            "outer_destructor.create(inner_source)",
        ],
        "inner_destroyer.destroy(target)": [
            "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor.create(work)": [
            "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor.destroy(work)": ["inner_destructor.create(work)"],
        "outer_destructor.destroy(inner_destroyer_particle)": [
            "inner_destroyer.destroy(target)"
        ],
        "test.destroy(outer)": ["test.create(outer)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_nested_repeated_destructor_with_caller_known_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(outer)": [],
        "outer_destructor.create(inner_destroyer_particle)": ["test.create(outer)"],
        "outer_destructor.create(first_source)": ["test.create(outer)"],
        "outer_destructor.create(first_source::/extra)": [
            "outer_destructor.create(first_source)"
        ],
        "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(inner_destroyer_particle)",
            "outer_destructor.create(first_source::/extra)",
        ],
        "inner_destructor_a.create(work_a)": [
            "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_a.destroy(work_a)": ["inner_destructor_a.create(work_a)"],
        "inner_destroyer.destroy(target::/extra)": [
            "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destroyer.destroy(target)": [
            "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "outer_destructor.create(second_source)": ["test.create(outer)"],
        "outer_destructor.create(second_source::/extra)": [
            "outer_destructor.create(second_source)"
        ],
        "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(second_source::/extra)",
            "inner_destroyer.destroy(target)",
        ],
        "inner_destructor_a#2.create(work_a)": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_a#2.destroy(work_a)": ["inner_destructor_a#2.create(work_a)"],
        "inner_destructor_b.create(work_b)": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_b.destroy(work_b)": ["inner_destructor_b.create(work_b)"],
        "inner_destroyer#2.destroy(target::/extra)#2": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destroyer#2.destroy(target)": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "outer_destructor.destroy(inner_destroyer_particle)": [
            "inner_destroyer#2.destroy(target)"
        ],
        "test.destroy(outer)": ["test.create(outer)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_executions_each_destroy_two_particles(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_a)": [],
        "test.create(first_none)": [],
        "test.move(first_a, /destroyer::first)": ["test.create(first_a)"],
        "test.move(first_none, /destroyer::second)": ["test.create(first_none)"],
        "test.create(/destroyer::run)": [],
        "destroyer.move(run, used_run)": ["test.create(/destroyer::run)"],
        "destroyer.destroy(used_run)": ["destroyer.move(run, used_run)"],
        "destructor_a.create(work_a)": ["test.move(first_a, /destroyer::first)"],
        "destructor_a.destroy(work_a)": ["destructor_a.create(work_a)"],
        "destroyer.destroy(first)": ["test.move(first_a, /destroyer::first)"],
        "destroyer.destroy(second)": ["test.move(first_none, /destroyer::second)"],
        "test.create(second_b)": [],
        "test.create(second_a_and_b)": [],
        "test.move(second_b, /destroyer::first)": [
            "test.create(second_b)",
            "destroyer.destroy(first)",
        ],
        "test.move(second_a_and_b, /destroyer::second)": [
            "test.create(second_a_and_b)",
            "destroyer.destroy(second)",
        ],
        "test.create(/destroyer::run)#2": ["destroyer.move(run, used_run)"],
        "destroyer#2.move(run, used_run)": ["test.create(/destroyer::run)#2"],
        "destroyer#2.destroy(used_run)": ["destroyer#2.move(run, used_run)"],
        # The second Action Execution's two Destruction Facts receive different
        # contribution sets, and neither fact acquires dependencies from the
        # first execution's Destructor.
        "destructor_b.create(work_b)": ["test.move(second_b, /destroyer::first)"],
        "destructor_b.destroy(work_b)": ["destructor_b.create(work_b)"],
        "destroyer#2.destroy(first)": ["test.move(second_b, /destroyer::first)"],
        "destructor_a#2.create(work_a)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
        "destructor_a#2.destroy(work_a)": ["destructor_a#2.create(work_a)"],
        "destructor_b#2.create(work_b)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
        "destructor_b#2.destroy(work_b)": ["destructor_b#2.create(work_b)"],
        "destroyer#2.destroy(second)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_separate_child_contract_paths(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(left_source)": [],
        "test.create(left_source::/extra)": ["test.create(left_source)"],
        "test.move(left_source, source::/left)": [
            "test.create(source)",
            "test.create(left_source::/extra)",
        ],
        "test.create(right_source)": [],
        "test.move(right_source, source::/right)": [
            "test.create(source)",
            "test.create(right_source)",
        ],
        "test.move(source, /destroyer::target)": [
            "test.move(left_source, source::/left)",
            "test.move(right_source, source::/right)",
        ],
        "destroyer.move(target::/left, left_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destroyer.move(left_holder, target::/left)": [
            "destroyer.move(target::/left, left_holder)"
        ],
        "destroyer.move(target::/right, right_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destroyer.move(right_holder, target::/right)": [
            "destroyer.move(target::/right, right_holder)"
        ],
        # The parent Destructor and the caller-known child Destroy share the
        # /left path, while /right's Destructor remains an independent chain.
        "parent_destructor.move(/left, holder)": [
            "destroyer.move(left_holder, target::/left)"
        ],
        "parent_destructor.move(holder, /left)": [
            "parent_destructor.move(/left, holder)"
        ],
        "destroyer.destroy(target::/left::/extra)": [
            "parent_destructor.move(holder, /left)"
        ],
        "destroyer.destroy(target::/left)": ["parent_destructor.move(holder, /left)"],
        "child_destructor.create(work)": [
            "destroyer.move(right_holder, target::/right)"
        ],
        "child_destructor.destroy(work)": ["child_destructor.create(work)"],
        "destroyer.destroy(target::/right)": [
            "destroyer.move(right_holder, target::/right)"
        ],
        "destroyer.destroy(target)": [
            "parent_destructor.move(holder, /left)",
            "destroyer.move(right_holder, target::/right)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_repeated_destructor_uses_distinct_requirement_sources(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_source)": [],
        "test.create(first_source::/marker)": ["test.create(first_source)"],
        "test.move(first_source, /destroyer::target)": [
            "test.create(first_source::/marker)"
        ],
        "destructor.move(/marker, holder)": [
            "test.move(first_source, /destroyer::target)"
        ],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destructor.move(holder, /marker)"],
        "test.create(second_source)": [],
        "test.create(second_source::/marker)": ["test.create(second_source)"],
        "test.move(second_source, /destroyer::target)": [
            "test.create(second_source::/marker)",
            "destroyer.destroy(target)",
        ],
        # Each Destructor Action Execution receives the parent Move belonging
        # to its own destroyed particle as its occupied requirement dependency.
        "destructor#2.move(/marker, holder)": [
            "test.move(second_source, /destroyer::target)"
        ],
        "destructor#2.move(holder, /marker)": ["destructor#2.move(/marker, holder)"],
        "destroyer#2.destroy(target::/marker)#2": [
            "destructor#2.move(holder, /marker)"
        ],
        "destroyer#2.destroy(target)": ["destructor#2.move(holder, /marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="S5: compose destruction dependencies without ordering simultaneous Destroys",
)
def test_caller_destroy_with_multiple_callee_and_destructor_guarantees(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(first)": ["test.move(source, /destroyer::parent)"],
        "maker.create(second)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(first)": ["maker.create(first)"],
        "maker.destroy(second)": ["maker.create(second)"],
        "destruct.create(/marker)": ["test.move(source, /destroyer::parent)"],
        "destruct.destroy(/marker)": ["destruct.create(/marker)"],
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent::/maker::trigger_pos)": [
            "destroyer.create(parent::/maker::trigger_pos)"
        ],
        # Collection includes both callee Guarantees, the Destructor Guarantee,
        # and the trigger-position Create, but not simultaneous child Destroys.
        "destroyer.destroy(parent)": [
            "destruct.destroy(/marker)",
            "destroyer.create(parent::/maker::trigger_pos)",
            "maker.destroy(first)",
            "maker.destroy(second)",
        ],
        "destroyer.destroy(trigger_pos)": ["test.create(/destroyer::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
