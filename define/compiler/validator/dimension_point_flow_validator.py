"""Phase B validator: resolves deferred move constraints after all files are validated."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler.validator import validation_result


class DimensionPointFlowValidator:
    """Resolves deferred move constraint checks after all definitions are registered.

    Runs after all file validation completes (Phase B). Uses position
    constraint lookups from the completed definition results to resolve
    quality requirements for each side of a deferred move.
    """

    _definition_results: dict[str, validation_result.DefinitionValidationResult]

    def __init__(
        self,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
    ):
        """Initialize with the completed definition results map."""
        self._definition_results = definition_results

    def resolve_deferred_checks(
        self,
        deferred_checks: Sequence[validation_result.DeferredMoveConstraintCheck],
    ) -> list[tuple[ast.QualityDefinition, diagnostics.Diagnostic]]:
        """Resolve all deferred move constraint checks.

        Returns a list of (enclosing_definition, diagnostic) pairs for
        any constraint violations found.
        """
        results: list[tuple[ast.QualityDefinition, diagnostics.Diagnostic]] = []
        for check in deferred_checks:
            diagnostic = self._resolve_check(check)
            if diagnostic is not None:
                results.append((check.enclosing_definition, diagnostic))
        return results

    def _resolve_check(
        self,
        check: validation_result.DeferredMoveConstraintCheck,
    ) -> diagnostics.Diagnostic | None:
        """Resolve a single deferred move constraint check."""
        fqun = check.enclosing_definition.typed_name.name_content.fqun

        from_qualities = check.from_qualities
        if from_qualities is None:
            from_qualities = self._get_required_qualities_for_position(
                check.statement.source_position.chain, fqun
            )

        to_qualities = check.to_qualities
        if to_qualities is None:
            to_qualities = self._get_required_qualities_for_position(
                check.statement.target_position.chain, fqun
            )

        if from_qualities is None or to_qualities is None:
            return None

        missing = to_qualities - from_qualities
        if missing:
            return diagnostics.MoveViolatesConstraintsDiagnostic(
                position=check.statement.target_position.position,
                source_position=check.statement.source_position.chain.source_chained_name,
                target_position=check.statement.target_position.chain.source_chained_name,
                missing_qualities=sorted(missing),
            )
        return None

    def _get_required_qualities_for_position(
        self,
        chain: ast.ChainedName,
        fqun: ast.Fqun,
    ) -> frozenset[str] | None:
        """Resolve the constraint qualities for the last position in a chain.

        Returns None when the target definition hasn't been registered.
        """
        # TODO: This uses the last chain element's constraints as a proxy for what
        # qualities a DP has. A DP may actually have more qualities than the last
        # position requires (from its original creation site), and we lose that
        # knowledge by only looking at its current location.
        last_element = chain.typed_names[-1]

        if isinstance(last_element, ast.GlobalTypedNameReference):
            lookup_key = last_element.full_typed_name(in_universe=fqun)
        else:
            # If the last element is a local reference, then per the
            # guarantees provided by file_validator, it _must_ be
            # a chain with more than one item in it, and the parent
            # must be a globally-named action.
            parent = chain.typed_names[-2]
            if not isinstance(parent, ast.GlobalTypedNameReference):
                raise ValueError("got a local name where a global name was expected")
            lookup_key = parent.full_typed_name(in_universe=fqun)

        definition_result = self._definition_results.get(lookup_key)
        if definition_result is None:
            return None

        if isinstance(last_element, ast.GlobalTypedNameReference):
            return definition_result.position_constraint_names
        locals_map = definition_result.action_local_position_constraint_names
        return locals_map.get(last_element.name_content.name, frozenset())
