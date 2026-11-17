"""The program's resolved associations: each value quality's encoding, and each logical operation's Encoding Operations."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.graphs import reference_graph
    from define.compiler.validator import validation_result


class ChosenEncodingOperation(msgspec.Struct, frozen=True):
    """An Encoding Operation that association resolution chose for an execution of a logical operation."""

    logical_operation: ast.LogicalOperationDefinition
    # The association of the logical operation that names the Encoding
    # Operation.
    encoding_operation_association: validation_result.EncodingOperationAssociation


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
        # The edge to each value quality's one encoding, by the value
        # quality's full typed name.
        self._value_encodings: dict[str, reference_graph.ReferenceEdge] = {}
        # Each logical operation, and its associations, by the full typed
        # names of the encodings that they list, in order, by the logical
        # operation's full typed name.
        self._encoding_operations: dict[
            str,
            tuple[
                ast.LogicalOperationDefinition,
                dict[tuple[str, ...], validation_result.EncodingOperationAssociation],
            ],
        ] = {}
        # Each Encoding Operation that resolution chose, by the full typed
        # names of its logical operation and of the encodings that its
        # association lists, which identify the association, so that each
        # association is checked once however many executions choose it.
        self._chosen_encoding_operations: dict[
            tuple[str, tuple[str, ...]], ChosenEncodingOperation
        ] = {}

    def add_value(
        self, definition: ast.ValueDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Find the one encoding associated with a value quality, and return a diagnostic if it has none."""
        associated_encodings = self._definition_results[
            definition.typed_name
        ].associated_encodings
        if len(associated_encodings) > 1:
            # TODO: Choose between a value quality's encodings when each
            # particle is created, as the spec allows.
            raise NotImplementedError(
                f"{definition.typed_name.source_typed_name} has more than one encoding:"
                + f" {[edge.target_full_typed_name for edge in associated_encodings]}"
            )
        # Only the value quality's own universe can associate it with an
        # encoding, so without one nothing can ever hold the value.
        if not associated_encodings:
            return [
                diagnostics.ValueHasNoEncodingDiagnostic(
                    location=definition.typed_name.location,
                    value_quality=definition.typed_name.source_typed_name,
                )
            ]
        self._value_encodings[definition.typed_name.full_typed_name] = (
            associated_encodings[0]
        )
        return []

    def add_logical_operation(
        self, definition: ast.LogicalOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Add a logical operation's associations with Encoding Operations, and return a diagnostic for each association that cannot be used."""
        logical_operation_name = definition.typed_name.source_typed_name
        fqun = definition.typed_name.name_content.fqun
        encoding_operations: dict[
            tuple[str, ...], validation_result.EncodingOperationAssociation
        ] = {}
        association_diagnostics: list[diagnostics.Diagnostic] = []
        for association in self._definition_results[
            definition.typed_name
        ].encoding_operation_associations:
            view_diagnostics = _view_name_diagnostics(definition, association)
            if view_diagnostics:
                association_diagnostics.extend(view_diagnostics)
                continue
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
            first = encoding_operations.setdefault(tuple(encodings), association)
            if first is not association:
                encoding_operation = association.edge.global_name_reference
                first_encoding_operation = first.edge.global_name_reference
                association_diagnostics.append(
                    diagnostics.DuplicateAssociatedEncodingOperationDiagnostic(
                        location=encoding_operation.location,
                        encoding_operation_name=encoding_operation.source_typed_name,
                        first_encoding_operation_name=first_encoding_operation.source_typed_name,
                        logical_operation_name=logical_operation_name,
                        first_association_location=first_encoding_operation.location,
                    )
                )
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            definition,
            encoding_operations,
        )
        return association_diagnostics

    def value_encoding(
        self, value_quality: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the value quality's encoding, or None if it is not defined or has none, which is already reported."""
        edge = self._value_encodings.get(value_quality.full_typed_name)
        if edge is None:
            return None
        return edge.global_name_reference

    def choose_encoding_operation(
        self,
        logical_operation: ast.GlobalTypedNameReference,
        encodings: tuple[str, ...],
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Encoding Operation whose association with the logical operation lists the encodings with the full typed names ``encodings``, in their order, if one does, and record that resolution chose it."""
        definition, encoding_operations = self._encoding_operations[
            logical_operation.full_typed_name
        ]
        association = encoding_operations.get(encodings)
        if association is None:
            return None
        key = (logical_operation.full_typed_name, encodings)
        # Resolution chooses concurrently, but every choice of this association
        # records the same value, so concurrent writes of a key are harmless and
        # need no lock.
        if key not in self._chosen_encoding_operations:
            self._chosen_encoding_operations[key] = ChosenEncodingOperation(
                logical_operation=definition,
                encoding_operation_association=association,
            )
        return association.edge.global_name_reference

    def chosen_encoding_operations(self) -> list[ChosenEncodingOperation]:
        """Return each Encoding Operation that resolution chose, with the association that chose it, once every definition is resolved.

        They are ordered by logical operation and by the encodings that the
        association lists, not by when resolution chose them, which depends
        on thread timing.
        """
        chosen_encoding_operations: list[ChosenEncodingOperation] = []
        for key in sorted(self._chosen_encoding_operations):
            chosen_encoding_operations.append(self._chosen_encoding_operations[key])
        return chosen_encoding_operations

    def chosen_edges(self) -> list[reference_graph.ReferenceEdge]:
        """Return the edge to each encoding and Encoding Operation that resolution chose, once every definition is resolved."""
        edges = list(self._value_encodings.values())
        for chosen in self._chosen_encoding_operations.values():
            edges.append(chosen.encoding_operation_association.edge)
        return edges

    def value_encodings(self) -> Mapping[str, ast.GlobalTypedNameReference]:
        """Return each value quality's encoding, by the value quality's full typed name, once every value quality is added."""
        value_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for value_quality, edge in self._value_encodings.items():
            value_encodings[value_quality] = edge.global_name_reference
        return value_encodings


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
