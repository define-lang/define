# pyright: reportUnusedCallResult=false

from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from define.compiler.validator.reference_graph import (
    definition_postorder_validator,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.validator import validation_result

_ACTION_TEMPLATE = (
    "define the potential action<my.domain.com:my_lib:/{name}> {{\n"
    "    define the position<run>.\n"
    "    it happens when {{\n"
    "        the position<run> has a particle.\n"
    "    }} and it does {{\n"
    "        define the position<item>.\n"
    "        create a particle in position<item>.\n"
    "    }}\n"
    "}}\n"
)

_CALLEE_NAME = "action<my.domain.com:my_lib:/callee>"
_SECOND_CALLEE_NAME = "action<my.domain.com:my_lib:/second_callee>"
_CALLER_NAME = "action<my.domain.com:my_lib:/caller>"
_OTHER_CALLER_NAME = "action<my.domain.com:my_lib:/other_caller>"
_CALLEE_AND_POSITION_SOURCE = (
    "define the potential action<my.domain.com:my_lib:/callee> {\n"
    "    define the position<made>.\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        create a particle in position<made>.\n"
    "    }\n"
    "}\n"
    "define the potential position<my.domain.com:my_lib:/gateway> {\n"
    "    it may only contain particles where {\n"
    "        it has the action</callee>.\n"
    "    }\n"
    "}\n"
)


def _caller_source(name: str) -> str:
    return (
        f"define the potential action<my.domain.com:my_lib:/{name}> {{\n"
        "    define the position<run>.\n"
        "    define the position<gateway> {\n"
        "        it may only contain particles where {\n"
        "            it has the position</gateway>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<gateway>.\n"
        "    }\n"
        "}\n"
    )


_CALLEE_AND_CALLER_SOURCE = _CALLEE_AND_POSITION_SOURCE + _caller_source("caller")
_TWO_CALLEE_AND_CALLER_SOURCE = _CALLEE_AND_POSITION_SOURCE.replace(
    "define the potential position<my.domain.com:my_lib:/gateway>",
    _ACTION_TEMPLATE.format(name="second_callee")
    + "define the potential position<my.domain.com:my_lib:/gateway>",
).replace(
    "        it has the action</callee>.\n",
    "        it has the action</callee>.\n        it has the action</second_callee>.\n",
) + _caller_source("caller")


def _structural_result(source: str) -> validation_result.ProgramValidationResult:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source, max_workers=1
        )
    )
    assert_no_errors(result)
    return result


def test_independent_actions_validate_in_parallel():
    structural_result = _structural_result(
        _ACTION_TEMPLATE.format(name="first") + _ACTION_TEMPLATE.format(name="second")
    )
    validation_barrier = threading.Barrier(2)
    original_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def synchronized_analyze(
        validator: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        validation_barrier.wait(timeout=5)
        return original_analyze(validator)

    with mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=synchronized_analyze,
    ):
        result = reference_graph_validator.ReferenceGraphValidator(
            structural_result.reference_graph,
            structural_result.definition_results,
            entry_action=structural_result.entry_action,
        ).validate(max_workers=2)

    assert_no_errors(structural_result)
    assert len(result.operation_graphs) == 2


def test_referenced_action_finishes_before_referencing_action_starts():
    structural_result = _structural_result(_CALLEE_AND_CALLER_SOURCE)
    completed_actions: set[str] = set()
    completed_actions_lock = threading.Lock()
    original_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def record_order(
        validator: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        action_name = validator._definition.typed_name.full_typed_name  # pyright: ignore[reportPrivateUsage]
        if action_name == _CALLER_NAME:
            with completed_actions_lock:
                assert _CALLEE_NAME in completed_actions
        result = original_analyze(validator)
        with completed_actions_lock:
            completed_actions.add(action_name)
        return result

    with mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=record_order,
    ):
        reference_graph_validator.ReferenceGraphValidator(
            structural_result.reference_graph,
            structural_result.definition_results,
            entry_action=structural_result.entry_action,
        ).validate(max_workers=2)

    assert completed_actions == {_CALLEE_NAME, _CALLER_NAME}


def test_shared_referenced_definition_is_validated_once():
    structural_result = _structural_result(
        _CALLEE_AND_CALLER_SOURCE + _caller_source("other_caller")
    )
    validation_count_by_action: dict[str, int] = {}
    validation_count_lock = threading.Lock()
    original_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def count_validation(
        validator: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        action_name = validator._definition.typed_name.full_typed_name  # pyright: ignore[reportPrivateUsage]
        with validation_count_lock:
            validation_count_by_action[action_name] = (
                validation_count_by_action.get(action_name, 0) + 1
            )
        return original_analyze(validator)

    with mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=count_validation,
    ):
        reference_graph_validator.ReferenceGraphValidator(
            structural_result.reference_graph,
            structural_result.definition_results,
            entry_action=structural_result.entry_action,
        ).validate(max_workers=3)

    assert validation_count_by_action == {
        _CALLEE_NAME: 1,
        _CALLER_NAME: 1,
        _OTHER_CALLER_NAME: 1,
    }


def test_reference_failure_prevents_referencing_action_validation():
    structural_result = _structural_result(_TWO_CALLEE_AND_CALLER_SOURCE)
    analyzed_actions: set[str] = set()

    def fail_callee(
        validator: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        action_name = validator._definition.typed_name.full_typed_name  # pyright: ignore[reportPrivateUsage]
        analyzed_actions.add(action_name)
        if action_name == _CALLER_NAME:
            raise AssertionError("the caller must not be validated")
        raise RuntimeError(f"{action_name} validation failed")

    with (
        mock.patch.object(
            definition_postorder_validator.ActionPostorderValidator,
            "analyze",
            autospec=True,
            side_effect=fail_callee,
        ),
        pytest.raises(RuntimeError, match="/callee> validation failed"),
    ):
        reference_graph_validator.ReferenceGraphValidator(
            structural_result.reference_graph,
            structural_result.definition_results,
            entry_action=structural_result.entry_action,
        ).validate(max_workers=2)

    assert analyzed_actions == {_CALLEE_NAME, _SECOND_CALLEE_NAME}
