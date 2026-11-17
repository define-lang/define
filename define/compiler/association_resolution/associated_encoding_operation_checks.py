"""Checks of the loaded Encoding Operations that a logical operation's associations name, against those associations and against the logical operation."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from crates.source_rendering.python import rendering
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


def _direction(view: ast.ViewDefinition) -> str:
    if view.is_input and view.is_output:
        return "read/write"
    if view.is_input:
        return "read"
    return "written"


def check(
    definition: ast.LogicalOperationDefinition,
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ],
    associations: Iterable[validation_result.EncodingOperationAssociation],
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each way a loaded Encoding Operation that one of the logical operation's associations names differs from that association, or from the logical operation in the direction of a view."""
    check_diagnostics: list[diagnostics.Diagnostic] = []
    for association, encoding_operation in _loaded_encoding_operations(
        definition_results, associations
    ):
        check_diagnostics.extend(
            _association_diagnostics(association, encoding_operation)
        )
        check_diagnostics.extend(
            _direction_diagnostics(
                definition,
                encoding_operation,
                association.edge.global_name_reference.location,
            )
        )
    return check_diagnostics


def _direction_diagnostics(
    definition: ast.LogicalOperationDefinition,
    encoding_operation: ast.EncodingOperationDefinition,
    association_location: rendering.SourceLocation,
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each view of the Encoding Operation whose direction differs from the logical operation's view of the same name."""
    direction_diagnostics: list[diagnostics.Diagnostic] = []
    for encoding_view in encoding_operation.views:
        view_name = encoding_view.typed_name.source_typed_name
        logical_view = definition.get_view(view_name)
        # A view that the logical operation does not have is reported
        # where the association lists it, or where it differs from the
        # Encoding Operation.
        if logical_view is None:
            continue
        if _direction(encoding_view) != _direction(logical_view):
            direction_diagnostics.append(
                diagnostics.AssociatedEncodingOperationViewDirectionDiagnostic(
                    location=encoding_view.typed_name.location,
                    view_name=view_name,
                    direction=_direction(encoding_view),
                    encoding_operation_name=encoding_operation.typed_name.source_typed_name,
                    logical_operation_direction=_direction(logical_view),
                    logical_operation_name=definition.typed_name.source_typed_name,
                    association_location=association_location,
                )
            )
    return direction_diagnostics


def _association_diagnostics(
    association: validation_result.EncodingOperationAssociation,
    encoding_operation: ast.EncodingOperationDefinition,
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each way the Interface Views that the association lists differ from the Encoding Operation's, which must match in name, encoding, and order."""
    encoding_operation_name = encoding_operation.typed_name.source_typed_name
    encoding_views = encoding_operation.views
    # Views at the same place cannot be compared meaningfully when the
    # counts differ.
    if len(association.views) != len(encoding_views):
        return [
            diagnostics.AssociationViewCountDiagnostic(
                location=association.edge.global_name_reference.location,
                encoding_operation_name=encoding_operation_name,
                view_count=len(association.views),
                encoding_operation_view_count=len(encoding_views),
                definition_location=encoding_operation.typed_name.location,
            )
        ]
    association_diagnostics: list[diagnostics.Diagnostic] = []
    # ZIP: This relationship can only be created here because the
    # association and the Encoding Operation are separate definitions, and
    # this checks the rule that the association lists the Encoding
    # Operation's views in the same order, so it compares the two views at
    # each position. A different number of views was reported above.
    for number, (associated_view, encoding_view) in enumerate(
        zip(association.views, encoding_views, strict=True), start=1
    ):
        view_name = encoding_view.typed_name.source_typed_name
        if associated_view.name != encoding_view.typed_name.name_content.name:
            association_diagnostics.append(
                diagnostics.AssociationViewNameDiagnostic(
                    location=associated_view.name_location,
                    view_number=number,
                    view_name=associated_view.name,
                    encoding_operation_name=encoding_operation_name,
                    encoding_operation_view_name=encoding_view.typed_name.name_content.name,
                    definition_location=encoding_view.typed_name.location,
                )
            )
            continue
        encoding = encoding_view.quality_assignment_block.encoding
        # A view without an encoding was already reported when the
        # Encoding Operation's definition was validated.
        if encoding is None:
            continue
        associated_encoding = associated_view.encoding
        if associated_encoding.full_typed_name != encoding.full_typed_name:
            association_diagnostics.append(
                diagnostics.AssociationViewEncodingDiagnostic(
                    location=associated_encoding.location,
                    view_name=view_name,
                    encoding_name=associated_encoding.full_typed_name,
                    encoding_operation_name=encoding_operation_name,
                    encoding_operation_encoding_name=encoding.full_typed_name,
                    definition_location=encoding.location,
                )
            )
    return association_diagnostics


def _loaded_encoding_operations(
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ],
    associations: Iterable[validation_result.EncodingOperationAssociation],
) -> Iterator[
    tuple[
        validation_result.EncodingOperationAssociation,
        ast.EncodingOperationDefinition,
    ]
]:
    """Yield the Encoding Operation of each of the associations that the program loaded, with its association.

    A program loads the Encoding Operations of a logical operation only if
    it executes the logical operation.
    """
    for association in associations:
        reference = association.edge.global_name_reference
        result = definition_results.get(reference)
        # A missing Encoding Operation, or a definition of another type,
        # was already reported when its reference was resolved.
        if result is not None and isinstance(
            result.definition, ast.EncodingOperationDefinition
        ):
            yield association, result.definition
