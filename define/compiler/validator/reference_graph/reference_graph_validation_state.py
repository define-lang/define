"""State shared by concurrent reference graph action validators."""

from __future__ import annotations

import typing

from define.compiler.data_structures import interned_set

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from define.compiler import ast, chained_name
    from define.compiler.validator.reference_graph import (
        action_contract,
        quality_assignment,
    )


class ReferenceGraphValidationState:
    """State shared by concurrent reference graph action validators.

    This module encapsulates the shared state that is concurrently _written_
    to by multiple action_definition_validator instances at once. It does
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
        # Shared so that actions implying the same qualities share the sets
        # of what they transitively imply.
        self.implied_quality_name_sets: interned_set.InternedSets = (
            interned_set.InternedSets()
        )
        self._implied_quality_by_name: dict[str, ast.GlobalTypedNameReference] = {}
        self._quality_assignments_by_key: dict[
            chained_name.PositionReferenceTuple, quality_assignment.QualityAssignments
        ] = {}
        self._encoding_operations_by_logical_operation: dict[
            str, dict[tuple[str, ...], ast.EncodingOperationDefinition]
        ] = {}

    def publish_contract(
        self,
        action_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        contract: action_contract.ActionContract,
    ):
        """Publish a validated action's contract."""
        self._contract_by_name[action_name.full_typed_name] = contract

    def get_contract(
        self, action_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    ) -> action_contract.ActionContract:
        """Return a previously published action contract."""
        return self._contract_by_name[action_name.full_typed_name]

    def get_contract_or_none(
        self, action_name: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    ) -> action_contract.ActionContract | None:
        """Return a published action contract, if one exists."""
        return self._contract_by_name.get(action_name.full_typed_name)

    def publish_implied_qualities(
        self, qualities: Iterable[ast.GlobalTypedNameReference]
    ):
        """Record a reference to each quality that an action's Quality Implication Statements name."""
        for quality in qualities:
            # Many actions imply the same qualities, and setdefault takes the
            # dict's lock even when the key is already there. Checking first
            # lets every action after the first just read, which takes no
            # lock on free-threaded Python. setdefault still settles two
            # threads publishing a new quality at once.
            if quality.full_typed_name not in self._implied_quality_by_name:
                _ = self._implied_quality_by_name.setdefault(
                    quality.full_typed_name, quality
                )

    def get_implied_quality(self, name: str) -> ast.GlobalTypedNameReference:
        """Return a published reference to the implied quality whose full typed name is ``name``."""
        return self._implied_quality_by_name[name]

    def publish_encoding_operations(
        self,
        logical_operation_name: ast.GlobalTypedName[
            ast.GlobalNameContent[ast.Fqun | None]
        ],
        encoding_operations: dict[tuple[str, ...], ast.EncodingOperationDefinition],
    ):
        """Publish a validated logical operation's Encoding Operations."""
        self._encoding_operations_by_logical_operation[
            logical_operation_name.full_typed_name
        ] = encoding_operations

    def get_encoding_operations(
        self,
        logical_operation_name: ast.GlobalTypedName[
            ast.GlobalNameContent[ast.Fqun | None]
        ],
    ) -> dict[tuple[str, ...], ast.EncodingOperationDefinition]:
        """Return a previously published logical operation's Encoding Operations."""
        return self._encoding_operations_by_logical_operation[
            logical_operation_name.full_typed_name
        ]

    def get_or_build_quality_assignments(
        self,
        cache_key: chained_name.PositionReferenceTuple,
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
