"""Encode literals in the encoding of the value type they become."""

from __future__ import annotations

import typing

from define.compiler import ast, constants, diagnostics, literal_parsers

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


class LiteralEncoder:
    """Encodes literals written in one definition."""

    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _enclosing_fqun: ast.Fqun

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        enclosing_fqun: ast.Fqun,
    ):
        """Initialize with the known definitions and the FQUN of the definition containing the literals."""
        self._definition_results = definition_results
        self._enclosing_fqun = enclosing_fqun

    def encode(
        self, literal: ast.Literal, value_type: ast.GlobalTypedNameReference
    ) -> tuple[str | None, list[diagnostics.Diagnostic]]:
        """Return the literal in the value's encoding, if it can be encoded, and the diagnostics explaining why not."""
        potential_literal = literal.potential_literal
        # TODO: Remove this special case once the Define Standard Library
        # defines the built-in names.
        literal_encoding = constants.BUILT_IN_LITERAL_ENCODINGS.get(
            potential_literal.full_typed_name
        )
        if literal_encoding is None:
            definition_result = self._definition_results.get(potential_literal)
            # A missing Potential Literal was already reported when its
            # reference was resolved.
            if definition_result is None:
                return None, []
            definition = typing.cast(
                "ast.PotentialLiteralDefinition", definition_result.definition
            )
            literal_encoding = definition.encoding.full_typed_name
            literal_encoding_name = definition.encoding.source_form_in_universe(
                self._enclosing_fqun
            )
        else:
            literal_encoding_name = literal_encoding
        # TODO: Translate the literal into any encoding its target requires,
        # instead of always using the value type's own encoding.
        value_encoding = constants.BUILT_IN_VALUE_ENCODINGS.get(
            value_type.full_typed_name
        )
        if value_encoding is None:
            return None, [
                diagnostics.ValueHasNoEncodingDiagnostic(
                    location=potential_literal.location,
                    value_type=value_type.source_form_in_universe(self._enclosing_fqun),
                )
            ]
        parser = literal_parsers.LITERAL_PARSERS.get((literal_encoding, value_encoding))
        if parser is None:
            return None, [
                self._literal_cannot_set_value(
                    potential_literal, literal_encoding_name, value_type, value_encoding
                )
            ]
        try:
            return parser(literal.content), []
        except literal_parsers.LiteralParseError as e:
            return None, [
                diagnostics.InvalidLiteralContentDiagnostic(
                    location=literal.content_character_location(e.content_index),
                    content=literal.content,
                    potential_literal=potential_literal.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    value_encoding=value_encoding,
                    reason=e.reason,
                )
            ]

    def _literal_cannot_set_value(
        self,
        potential_literal: ast.GlobalTypedNameReference,
        literal_encoding_name: str,
        value_type: ast.GlobalTypedNameReference,
        value_encoding: str,
    ) -> diagnostics.LiteralCannotSetValueDiagnostic:
        supported_encodings: list[str] = []
        for source_encoding, destination_encoding in literal_parsers.LITERAL_PARSERS:
            if destination_encoding == value_encoding:
                supported_encodings.append(source_encoding)
        return diagnostics.LiteralCannotSetValueDiagnostic(
            location=potential_literal.location,
            potential_literal=potential_literal.source_form_in_universe(
                self._enclosing_fqun
            ),
            literal_encoding=literal_encoding_name,
            value_type=value_type.source_form_in_universe(self._enclosing_fqun),
            supported_encodings=supported_encodings,
        )
