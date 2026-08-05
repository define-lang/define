"""State shared by concurrent reference graph action validators."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.validator.reference_graph import (
        action_contract,
        quality_assignment,
    )


class ReferenceGraphValidationState:
    """State shared by concurrent reference graph action validators.

    This module encapsulates the shared state that is concurrently _written_
    to by multiple definition_postorder_validator instances at once. It does
    this so that we can guarantee that only thread-safe actions occur, to
    some degree.

    Note that the class does not actually do anything to guarantee thread safety
    beyond Python's basic guarantees of atomicity on dictionaries. However, the
    nature of the validator is such that it should never query for a key in any
    dictionary before that key is added, so there should be no TOCTOU conflicts
    or anything like that in actual practice.
    """

    def __init__(self):
        """Create empty shared validation state."""
        self._contract_by_name: dict[str, action_contract.ActionContract] = {}
        self._quality_assignments_by_key: dict[
            tuple[str, ...], quality_assignment.QualityAssignments
        ] = {}

    def publish_contract(
        self,
        action_name: ast.GlobalTypedName,
        contract: action_contract.ActionContract,
    ):
        """Publish a validated action's contract."""
        self._contract_by_name[action_name.full_typed_name] = contract

    def get_contract(
        self, action_name: ast.GlobalTypedName
    ) -> action_contract.ActionContract:
        """Return a previously published action contract."""
        return self._contract_by_name[action_name.full_typed_name]

    def get_contract_or_none(
        self, action_name: ast.GlobalTypedName
    ) -> action_contract.ActionContract | None:
        """Return a published action contract, if one exists."""
        return self._contract_by_name.get(action_name.full_typed_name)

    def get_or_build_quality_assignments(
        self,
        cache_key: tuple[str, ...],
        build: Callable[[], quality_assignment.QualityAssignments],
    ) -> quality_assignment.QualityAssignments:
        """Return cached quality assignments, building them when absent."""
        cached = self._quality_assignments_by_key.get(cache_key)
        if cached is not None:
            return cached
        result = build()
        # Both supported Python runtimes make setdefault atomic. Concurrent
        # duplicate builds are harmless, and every caller receives the value
        # selected for the cache.
        return self._quality_assignments_by_key.setdefault(cache_key, result)
