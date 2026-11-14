"""Reference graph validation of a logical operation definition: checking the Encoding Operations associated with it, and indexing them by the encodings of their views."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import validation_result

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from crates.source_rendering.python import rendering
    from define.compiler.data_structures import typed_name_dict


def _direction(view: ast.ViewDefinition) -> str:
    if view.is_input and view.is_output:
        return "read/write"
    if view.is_input:
        return "read"
    return "written"


@typing.final
class LogicalOperationDefinitionValidator:
    """Validates the Encoding Operations that perform a logical operation and indexes them by the encodings of their views."""

    def __init__(
        self,
        definition: ast.LogicalOperationDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the Logical Operation Definition and known definitions."""
        self._definition = definition
        self._definition_results = definition_results

    def analyze(self) -> validation_result.LogicalOperationPostorderValidationResult:
        """Validate the definition and return its validation result."""
        result_diagnostics: list[diagnostics.Diagnostic] = []
        encoding_operations: dict[tuple[str, ...], ast.EncodingOperationDefinition] = {}
        # Where the association of each Encoding Operation in
        # encoding_operations is written.
        association_locations: dict[tuple[str, ...], rendering.SourceLocation] = {}
        for association, encoding_operation in self._loaded_encoding_operations():
            view_diagnostics = self._view_diagnostics(
                encoding_operation, association.location
            )
            if view_diagnostics:
                result_diagnostics.extend(view_diagnostics)
                continue
            encodings = encoding_operation.view_encodings()
            # A view without an encoding was already reported when the
            # Encoding Operation's definition was validated.
            if encodings is None:
                continue
            first = encoding_operations.get(encodings)
            if first is not None:
                result_diagnostics.append(
                    diagnostics.DuplicateAssociatedEncodingOperationDiagnostic(
                        location=encoding_operation.typed_name.location,
                        encoding_operation_name=encoding_operation.typed_name.source_typed_name,
                        first_encoding_operation_name=first.typed_name.source_typed_name,
                        logical_operation_name=self._definition.typed_name.source_typed_name,
                        association_location=association.location,
                        first_association_location=association_locations[encodings],
                    )
                )
                continue
            encoding_operations[encodings] = encoding_operation
            association_locations[encodings] = association.location
        return validation_result.LogicalOperationPostorderValidationResult(
            diagnostics=result_diagnostics, encoding_operations=encoding_operations
        )

    def _view_diagnostics(
        self,
        encoding_operation: ast.EncodingOperationDefinition,
        association_location: rendering.SourceLocation,
    ) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each way the Encoding Operation's views differ from the logical operation's, which must match in name, direction, and order."""
        encoding_operation_name = encoding_operation.typed_name.source_typed_name
        logical_operation_name = self._definition.typed_name.source_typed_name
        logical_views = self._definition.views
        encoding_views = encoding_operation.views
        # Views at the same place cannot be compared meaningfully when the
        # counts differ.
        if len(logical_views) != len(encoding_views):
            return [
                diagnostics.AssociatedEncodingOperationViewCountDiagnostic(
                    location=encoding_operation.typed_name.location,
                    encoding_operation_name=encoding_operation_name,
                    view_count=len(encoding_views),
                    logical_operation_name=logical_operation_name,
                    logical_operation_view_count=len(logical_views),
                    association_location=association_location,
                )
            ]
        view_diagnostics: list[diagnostics.Diagnostic] = []
        for number, (logical_view, encoding_view) in enumerate(
            zip(logical_views, encoding_views, strict=True), start=1
        ):
            view_name = encoding_view.typed_name.source_typed_name
            logical_view_name = logical_view.typed_name.source_typed_name
            if view_name != logical_view_name:
                view_diagnostics.append(
                    diagnostics.AssociatedEncodingOperationViewNameDiagnostic(
                        location=encoding_view.typed_name.location,
                        view_number=number,
                        encoding_operation_name=encoding_operation_name,
                        view_name=view_name,
                        logical_operation_name=logical_operation_name,
                        logical_operation_view_name=logical_view_name,
                        association_location=association_location,
                    )
                )
            elif _direction(encoding_view) != _direction(logical_view):
                view_diagnostics.append(
                    diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
                        location=encoding_view.typed_name.location,
                        view_name=view_name,
                        direction=_direction(encoding_view),
                        encoding_operation_name=encoding_operation_name,
                        logical_operation_direction=_direction(logical_view),
                        logical_operation_name=logical_operation_name,
                        association_location=association_location,
                    )
                )
        return view_diagnostics

    def _loaded_encoding_operations(
        self,
    ) -> Iterator[tuple[ast.GlobalTypedNameReference, ast.EncodingOperationDefinition]]:
        """Yield each associated Encoding Operation that the program loaded, with the reference that its association makes.

        A program loads the Encoding Operations of a logical operation only if
        it executes the logical operation.
        """
        for edge in self._definition_results[
            self._definition.typed_name
        ].encoding_operation_edges:
            reference = edge.global_name_reference
            result = self._definition_results.get(reference)
            # A missing Encoding Operation, or a definition of another type,
            # was already reported when its reference was resolved.
            if result is not None and isinstance(
                result.definition, ast.EncodingOperationDefinition
            ):
                yield reference, result.definition
