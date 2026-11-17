"""The program's resolved associations: each value quality's encoding, and each logical operation's Encoding Operations."""

from __future__ import annotations

import typing

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


@typing.final
class Associations:
    """The program's resolved associations, which association resolution reads.

    Each value quality and logical operation is added once, concurrently with
    others, and only after everything that reads its associations is added.
    """

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the known definitions and no associations."""
        self._definition_results = definition_results
        # Each value quality's one encoding, by the value quality's full
        # typed name.
        self._value_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        # The Encoding Operations that each logical operation's associations
        # name, by the full typed names of the encodings that they list, in
        # order, by the logical operation's full typed name.
        self._encoding_operations: dict[
            str, dict[tuple[str, ...], ast.GlobalTypedNameReference]
        ] = {}

    def add_value(
        self, definition: ast.ValueDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Find the one encoding associated with a value quality, and return a diagnostic if it has none."""
        associated_encodings = self._definition_results[
            definition.typed_name
        ].associated_encodings
        encodings: list[ast.GlobalTypedNameReference] = []
        for encoding in associated_encodings:
            # A missing encoding was already reported when its reference was
            # resolved.
            if encoding in self._definition_results:
                encodings.append(encoding)
        if len(encodings) > 1:
            # TODO: Choose between a value quality's encodings when each
            # particle is created, as the spec allows.
            raise NotImplementedError(
                f"{definition.typed_name.source_typed_name} has more than one encoding:"
                + f" {[encoding.full_typed_name for encoding in encodings]}"
            )
        if encodings:
            self._value_encodings[definition.typed_name.full_typed_name] = encodings[0]
        # Only the value quality's own universe can associate it with an
        # encoding, so without one nothing can ever hold the value.
        if not associated_encodings:
            return [
                diagnostics.ValueHasNoEncodingDiagnostic(
                    location=definition.typed_name.location,
                    value_quality=definition.typed_name.source_typed_name,
                )
            ]
        return []

    def add_logical_operation(
        self, definition: ast.LogicalOperationDefinition
    ) -> tuple[
        list[validation_result.EncodingOperationAssociation],
        list[diagnostics.Diagnostic],
    ]:
        """Add a logical operation's associations with Encoding Operations.

        Returns the associations whose views match the logical operation's,
        and a diagnostic for each association that cannot be used.
        """
        logical_operation_name = definition.typed_name.source_typed_name
        fqun = definition.typed_name.name_content.fqun
        encoding_operations: dict[tuple[str, ...], ast.GlobalTypedNameReference] = {}
        association_diagnostics: list[diagnostics.Diagnostic] = []
        matching_associations: list[validation_result.EncodingOperationAssociation] = []
        for association in self._definition_results[
            definition.typed_name
        ].encoding_operation_associations:
            encoding_operation = association.edge.global_name_reference
            view_diagnostics = _view_name_diagnostics(definition, association)
            if view_diagnostics:
                association_diagnostics.extend(view_diagnostics)
                continue
            matching_associations.append(association)
            encodings: list[str] = []
            for view in association.views:
                encodings.append(
                    ast.GlobalTypedNameReference(
                        name_type=name_types.NameType.ENCODING,
                        name_content=view.encoding,
                        enclosing_fqun=fqun,
                        location=view.encoding.location,
                    ).full_typed_name
                )
            first = encoding_operations.setdefault(tuple(encodings), encoding_operation)
            if first is not encoding_operation:
                association_diagnostics.append(
                    diagnostics.DuplicateAssociatedEncodingOperationDiagnostic(
                        location=encoding_operation.location,
                        encoding_operation_name=encoding_operation.source_typed_name,
                        first_encoding_operation_name=first.source_typed_name,
                        logical_operation_name=logical_operation_name,
                        first_association_location=first.location,
                    )
                )
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            encoding_operations
        )
        return matching_associations, association_diagnostics

    def value_encoding(
        self, value_quality: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the value quality's encoding, or None if it is not defined or has none, which is already reported."""
        return self._value_encodings.get(value_quality.full_typed_name)

    def encoding_operation(
        self,
        logical_operation: ast.GlobalTypedNameReference,
        encodings: tuple[str, ...],
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Encoding Operation whose association with the logical operation lists the encodings with the full typed names ``encodings``, in their order, if one does."""
        return self._encoding_operations[logical_operation.full_typed_name].get(
            encodings
        )

    def value_encodings(self) -> Mapping[str, ast.GlobalTypedNameReference]:
        """Return each value quality's encoding, by the value quality's full typed name.

        Call it only once every value quality is added, since adding one
        changes what it returns.
        """
        return self._value_encodings


def _view_name_diagnostics(
    definition: ast.LogicalOperationDefinition,
    association: validation_result.EncodingOperationAssociation,
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each way the views that the association lists differ from the logical operation's, which must match in name and order."""
    encoding_operation_name = association.edge.global_name_reference.source_typed_name
    logical_operation_name = definition.typed_name.source_typed_name
    logical_views = definition.views
    # Views at the same place cannot be compared meaningfully when the counts
    # differ.
    if len(association.views) != len(logical_views):
        return [
            diagnostics.AssociationLogicalOperationViewCountDiagnostic(
                location=association.edge.global_name_reference.location,
                encoding_operation_name=encoding_operation_name,
                view_count=len(association.views),
                logical_operation_name=logical_operation_name,
                logical_operation_view_count=len(logical_views),
                definition_location=definition.typed_name.location,
            )
        ]
    view_diagnostics: list[diagnostics.Diagnostic] = []
    # ZIP: This relationship can only be created here because the
    # association and the logical operation are separate definitions, and
    # this checks the rule that the views the association lists are the
    # logical operation's views in the same order, so it compares the two
    # views at each position. A different number of views was reported above.
    for number, (associated_view, logical_view) in enumerate(
        zip(association.views, logical_views, strict=True), start=1
    ):
        if associated_view.name != logical_view.typed_name.name_content.name:
            view_diagnostics.append(
                diagnostics.AssociationLogicalOperationViewNameDiagnostic(
                    location=associated_view.name_location,
                    view_number=number,
                    view_name=associated_view.name,
                    encoding_operation_name=encoding_operation_name,
                    logical_operation_name=logical_operation_name,
                    logical_operation_view_name=logical_view.typed_name.name_content.name,
                    definition_location=logical_view.typed_name.location,
                )
            )
    return view_diagnostics
