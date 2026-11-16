"""The program's resolved associations: each value quality's encoding, and each logical operation's Encoding Operations."""

from __future__ import annotations

import typing

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler import ast
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
        # Each logical operation's Encoding Operations, by the full typed names
        # of their views' encodings, by the logical operation's full typed
        # name.
        self._encoding_operations: dict[
            str, dict[tuple[str, ...], ast.EncodingOperationDefinition]
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
        self,
        definition: ast.LogicalOperationDefinition,
        encoding_operations: dict[tuple[str, ...], ast.EncodingOperationDefinition],
    ):
        """Add a validated logical operation's Encoding Operations, by the full typed names of their views' encodings."""
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            encoding_operations
        )

    def value_encoding(
        self, value_quality: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the value quality's encoding, or None if it is not defined or has none, which is already reported."""
        return self._value_encodings.get(value_quality.full_typed_name)

    def encoding_operation(
        self,
        logical_operation: ast.GlobalTypedNameReference,
        encodings: tuple[str, ...],
    ) -> ast.EncodingOperationDefinition | None:
        """Return the Encoding Operation that performs the logical operation when its views have the encodings with the full typed names ``encodings``, in their order, if one does."""
        return self._encoding_operations[logical_operation.full_typed_name].get(
            encodings
        )

    def value_encodings(self) -> Mapping[str, ast.GlobalTypedNameReference]:
        """Return each value quality's encoding, by the value quality's full typed name.

        Call it only once every value quality is added, since adding one
        changes what it returns.
        """
        return self._value_encodings
