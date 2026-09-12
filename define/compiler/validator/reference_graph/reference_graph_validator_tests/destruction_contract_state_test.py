from __future__ import annotations

import typing
from pathlib import PurePosixPath
from unittest import mock

import pytest

from define.compiler.validator.reference_graph import (
    action_contract,
    child_state,
    position_occupancy,
    reference_graph_validation_state,
)
from define.compiler.validator.reference_graph.test_helpers import action_graph
from define.compiler.validator.test_helpers import assert_no_errors

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast, conftest


@pytest.fixture
def published_contracts() -> Iterator[dict[str, action_contract.ActionContract]]:
    contracts: dict[str, action_contract.ActionContract] = {}
    original = (
        reference_graph_validation_state.ReferenceGraphValidationState.publish_contract
    )

    def publish(
        state: reference_graph_validation_state.ReferenceGraphValidationState,
        action_name: ast.GlobalTypedName,
        contract: action_contract.ActionContract,
    ):
        contracts[action_name.full_typed_name] = contract
        original(state, action_name, contract)

    with mock.patch.object(
        reference_graph_validation_state.ReferenceGraphValidationState,
        "publish_contract",
        autospec=True,
        side_effect=publish,
    ):
        yield contracts


def test_particles_share_destroyer_state_but_have_independent_facts(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    _assert_shared_state_with_independent_facts(
        published_contracts["action<my.domain.com:my_lib:/middle>"]
    )


def test_particles_share_caller_state_but_have_independent_facts(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    _assert_shared_state_with_independent_facts(
        published_contracts["action<my.domain.com:my_lib:/middle>"]
    )


def _assert_shared_state_with_independent_facts(
    action: action_contract.ActionContract,
):
    (contracts,) = action.destruction_contracts
    first, second = contracts.particles
    assert contracts.propagation is not None
    assert first.destruction_fact is not second.destruction_fact
    assert first.destruction_fact.destruction is second.destruction_fact.destruction
    positions: list[tuple[str, ...]] = []
    for contract in contracts.particles:
        positions.append(
            contract.destroyed_position_contracted.canonical_chained_name_tuple
        )
        assert contract.verified_destructors.assignments == ()
    assert sorted(positions) == [
        ("position<run>",),
        ("position<run>", "position<my.domain.com:my_lib:/child>"),
    ]


def test_automatic_destruction_snapshots_each_target_before_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    first_contracts, second_contracts = published_contracts[
        "action<my.domain.com:my_lib:/middle>"
    ].destruction_contracts
    first, child = first_contracts.particles
    (second,) = second_contracts.particles
    assert first.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<first>",
    )
    assert child.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<first>",
        "position<my.domain.com:my_lib:/child>",
    )
    assert second.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<second>",
    )
    assert first_contracts.child_state is not second_contracts.child_state
    child_position = ("position<my.domain.com:my_lib:/child>",)
    occupied = first_contracts.child_state.get(child_position)
    assert occupied is not None
    assert occupied.state == position_occupancy.PositionOccupancyState.OCCUPIED
    assert occupied.filled_at is not None
    assert occupied.filled_at.file_path == PurePosixPath("middle.dfn")
    assert (
        second_contracts.child_state.get(child_position)
        == position_occupancy.EMPTY_OCCUPANCY
    )


def test_automatic_destruction_with_unrelated_pending_guarantees(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    first, second = published_contracts[
        "action<my.domain.com:my_lib:/middle>"
    ].destruction_contracts
    (first_particle,) = first.particles
    (second_particle,) = second.particles
    assert (
        first_particle.destroyed_position_contracted.canonical_chained_name_tuple
        == ("position<first>",)
    )
    assert (
        second_particle.destroyed_position_contracted.canonical_chained_name_tuple
        == ("position<second>",)
    )
    assert first.child_state is not second.child_state
    marker = ("position<my.domain.com:my_lib:/marker>",)
    assert first.child_state.get(marker) is None
    assert second.child_state.get(marker) is None
    assert action_graph(result.reference_graph_result) == [
        (
            "action<my.domain.com:my_lib:/outer>",
            "action<my.domain.com:my_lib:/filler>",
        ),
        (
            "action<my.domain.com:my_lib:/middle>",
            "action<my.domain.com:my_lib:/outer>",
        ),
        ("action<my.domain.com:my_lib:/test>", "action<my.domain.com:my_lib:/middle>"),
    ]


def test_large_child_states_share_extend_and_compact_from_source(
    validate_project: conftest.ValidateProject,
    published_contracts: dict[str, action_contract.ActionContract],
):
    # All six Actions pass the same particle toward stage0, which destroys it.
    # Each count is how many occupied child Positions that Action knows about.
    # The compiler works back from stage0 to its callers, adding their knowledge
    # to the destruction contracts. These counts let us check when it reuses a
    # snapshot, extends it, or combines the accumulated knowledge into a new one.
    counts = [16, 16, 18, 20, 20, 32]
    project: dict[str, str] = {}
    for index in range(counts[-1]):
        project[f"child{index}.dfn"] = (
            f"define the potential position<my.domain.com:my_lib:/child{index}>.\n"
        )
    for stage, count in enumerate(counts):
        lines = [f"define the potential action<my.domain.com:my_lib:/stage{stage}> {{"]
        if stage:
            lines.append(f"    it also assigns the action</stage{stage - 1}>.")
        lines.extend(
            [
                "    define the position<run> {",
                "        it may only contain particles where {",
            ]
        )
        for index in range(count):
            lines.append(f"            it has the position</child{index}>.")
        lines.extend(
            [
                "        }",
                "    }",
                "    it happens when {",
                "        the position<run> has a particle.",
                "    } and it does {",
                "        define the position<temporary>.",
            ]
        )
        # Declaring a child Position doesn't tell the compiler it is occupied.
        # These Moves require a particle there and put it back, so each Action
        # knows its chosen children are occupied when it passes on the parent.
        for index in range(count):
            lines.append(
                f"        move the particle in position<run>::position</child{index}> to position<temporary>."
            )
            lines.append(
                f"        move the particle in position<temporary> to position<run>::position</child{index}>."
            )
        if stage:
            lines.append(
                f"        move the particle in position<run> to action</stage{stage - 1}>::position<run>."
            )
        else:
            lines.append("        destroy the particle in position<run>.")
        lines.extend(["    }", "}"])
        project[f"stage{stage}.dfn"] = "\n".join(lines) + "\n"
    lines = [
        "define the potential action<my.domain.com:my_lib:/test> {",
        "    it also assigns the action</stage5>.",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
        "        define the position<item> {",
        "            it may only contain particles where {",
    ]
    for index in range(counts[-1]):
        lines.append(f"                it has the position</child{index}>.")
    lines.extend(
        [
            "            }",
            "        }",
            "        create a particle in position<item>.",
        ]
    )
    for index in range(counts[-1]):
        lines.append(
            f"        create a particle in position<item>::position</child{index}>."
        )
    lines.extend(
        [
            "        move the particle in position<item> to action</stage5>::position<run>.",
            "    }",
            "}",
        ]
    )
    project["test.dfn"] = "\n".join(lines) + "\n"
    result = validate_project(project, max_workers=1)
    assert_no_errors(result.program_result)
    snapshots: list[child_state.ChildState] = []
    for stage, count in enumerate(counts):
        (contracts,) = published_contracts[
            f"action<my.domain.com:my_lib:/stage{stage}>"
        ].destruction_contracts
        # There is one contract for the parent particle and one for each child
        # particle known to this Action. They describe the same destruction, so
        # they should share one snapshot rather than each storing a copy.
        assert len(contracts.particles) == count + 1
        snapshot = contracts.child_state
        snapshots.append(snapshot)
        # For example, stage2 knows about 18 occupied children, but stage0 must
        # still know about only 16 after compilation finishes. This catches both
        # lost knowledge and accidental changes to a snapshot shared with a callee.
        for index in range(count):
            occupancy = snapshot.get((f"position<my.domain.com:my_lib:/child{index}>",))
            assert occupancy is not None
            assert occupancy.state == position_occupancy.PositionOccupancyState.OCCUPIED
        assert snapshot.get(("position<unknown>",)) is None
        for index in range(count, counts[-1]):
            assert (
                snapshot.get((f"position<my.domain.com:my_lib:/child{index}>",)) is None
            )
    # Sixteen children reach the threshold for sharing. Stage1 adds nothing,
    # so it should keep exactly the snapshot stage0 already built.
    assert isinstance(snapshots[0], child_state.FlatChildState)
    assert snapshots[0] is snapshots[1]
    # Stages 2 and 3 each add two children: too few to justify copying the
    # original sixteen entries. Stage4 adds nothing and should reuse stage3's state.
    assert isinstance(snapshots[2], child_state.ExtendedChildState)
    assert isinstance(snapshots[3], child_state.ExtendedChildState)
    assert snapshots[3] is snapshots[4]
    # By stage5, the callers have added sixteen children in total. With as much
    # new knowledge as original knowledge, we expect a single combined dictionary.
    assert isinstance(snapshots[5], child_state.FlatChildState)


def test_caller_passed_child_of_local_parent_keeps_its_contract(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    (contracts,) = published_contracts[
        "action<my.domain.com:my_lib:/middle>"
    ].destruction_contracts
    (contract,) = contracts.particles
    assert contract.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<run>",
    )
    assert contract.position_in_child_state == (
        "position<my.domain.com:my_lib:/child>",
    )
    assert contract.verified_destructors.assignments == ()

    # Only the caller-passed child continues through middle; no particle in this
    # destruction needs to propagate beyond the Action that created it.
    assert (
        published_contracts["action<my.domain.com:my_lib:/test>"].destruction_contracts
        == []
    )


def test_shared_state_uses_each_moved_particles_own_origin(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    (contracts,) = published_contracts[
        "action<my.domain.com:my_lib:/middle>"
    ].destruction_contracts
    parent, child = contracts.particles
    assert parent.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<run>",
    )
    assert child.destroyed_position_contracted.canonical_chained_name_tuple == (
        "position<incoming>",
    )
    assert contracts.positions == {
        parent.position_in_child_state,
        child.position_in_child_state,
    }
    occupancy = contracts.child_occupancy(
        parent, ("position<my.domain.com:my_lib:/child>",)
    )
    assert occupancy is not None
    assert occupancy.state == position_occupancy.PositionOccupancyState.OCCUPIED
    assert (
        contracts.child_occupancy(child, ("position<my.domain.com:my_lib:/resource>",))
        is None
    )
    assert action_graph(result.reference_graph_result) == [
        (
            "action<my.domain.com:my_lib:/middle>",
            "action<my.domain.com:my_lib:/destroyer>",
        ),
        ("action<my.domain.com:my_lib:/test>", "action<my.domain.com:my_lib:/middle>"),
    ]


def test_repeated_executions_keep_distinct_shared_histories(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
    published_contracts: dict[str, action_contract.ActionContract],
):
    result = validate_testdata_project_with_reference_graph(max_workers=1)
    assert_no_errors(result.program_result)
    first, second = published_contracts[
        "action<my.domain.com:my_lib:/middle>"
    ].destruction_contracts
    outer_first, outer_second = published_contracts[
        "action<my.domain.com:my_lib:/outer>"
    ].destruction_contracts
    (first_particle,) = first.particles
    (second_particle,) = second.particles
    assert first.particles is not second.particles
    assert first_particle.destruction_fact is second_particle.destruction_fact
    assert (
        first_particle.destroyed_position_contracted.canonical_chained_name_tuple
        == ("position<run>",)
    )
    assert (
        second_particle.destroyed_position_contracted.canonical_chained_name_tuple
        == ("position<second>",)
    )
    assert first.child_state is second.child_state
    assert first.propagation is not None
    assert second.propagation is not None
    assert first.propagation is not second.propagation
    assert outer_first.propagation is not None
    assert outer_second.propagation is not None
    assert outer_first.propagation.step is outer_second.propagation.step
    assert outer_first.propagation.previous is first.propagation
    assert outer_second.propagation.previous is second.propagation
    assert list(outer_first.propagation_steps()) == [
        outer_first.propagation.step,
        first.propagation.step,
    ]
    assert list(outer_second.propagation_steps()) == [
        outer_second.propagation.step,
        second.propagation.step,
    ]
