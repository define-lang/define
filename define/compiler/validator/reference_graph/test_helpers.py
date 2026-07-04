# pyright: reportUnusedCallResult=false
"""Shared helpers for tests that inspect post-order validation results."""

from unittest import mock

from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors


def get_results(
    source: str,
) -> dict[str, definition_postorder_validator.PostorderValidationResult]:
    """Validate source and return each definition's post-order result, keyed by full typed name."""
    results: dict[str, definition_postorder_validator.PostorderValidationResult] = {}
    action_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def action_capture(
        self: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        result = action_analyze(self)
        results[self._definition.typed_name.full_typed_name] = result  # pyright: ignore[reportPrivateUsage]
        return result

    with mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=action_capture,
    ):
        structural = program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
        assert_no_errors(structural)
        reference_graph_validator.ReferenceGraphValidator(
            structural.reference_graph,
            structural.definition_results,
        ).validate()
    return results


def get_contracts(
    source: str,
) -> dict[str, action_contract.ActionContract]:
    """Validate source and return each definition's contract, keyed by full typed name."""
    return {name: result.contract for name, result in get_results(source).items()}
