from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    action_contract,
    quality_assignment,
    reference_graph_validation_state,
)

_LOCATION = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="example.com", location=_LOCATION),
    universe=ast.Universe(name="test", location=_LOCATION),
    location=_LOCATION,
)


def _action(name: str) -> ast.GlobalTypedNameReference:
    return ast.GlobalTypedNameReference(
        name_type=ast.NameType.ACTION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=None,
            path=ast.GlobalPathName(name=f"/{name}", location=_LOCATION),
            location=_LOCATION,
        ),
        enclosing_fqun=_FQUN,
        location=_LOCATION,
    )


def test_contract_access():
    state = reference_graph_validation_state.ReferenceGraphValidationState()
    action_name = _action("published")
    contract = action_contract.ActionContract(
        requirements={},
        guarantees=action_contract.Guarantees(own=[], nested=()),
        destruction_contracts=[],
        trigger_position_name="position<trigger>",
    )

    assert state.get_contract_or_none(action_name) is None
    state.publish_contract(action_name, contract)
    assert state.get_contract(action_name) is contract
    assert state.get_contract_or_none(action_name) is contract


def test_concurrent_quality_assignment_builds_publish_one_value():
    state = reference_graph_validation_state.ReferenceGraphValidationState()
    builders_ready = Barrier(2)
    first = quality_assignment.QualityAssignments(())
    second = quality_assignment.QualityAssignments(())

    def build(
        candidate: quality_assignment.QualityAssignments,
    ) -> quality_assignment.QualityAssignments:
        _ = builders_ready.wait(timeout=5)
        return candidate

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            state.get_or_build_quality_assignments,
            ("shared",),
            lambda: build(first),
        )
        second_future = executor.submit(
            state.get_or_build_quality_assignments,
            ("shared",),
            lambda: build(second),
        )
        first_result = first_future.result()
        second_result = second_future.result()

    assert first_result is second_result
    assert first_result is first or first_result is second

    def fail_if_called() -> quality_assignment.QualityAssignments:
        raise AssertionError("a cache hit must not rebuild quality assignments")

    assert (
        state.get_or_build_quality_assignments(("shared",), fail_if_called)
        is first_result
    )
