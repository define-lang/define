"""Encode literals in the encoding of the value type they become."""

from __future__ import annotations

import typing

from define.compiler import constants, literal_parsers
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
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
    ) -> tuple[codegen_input.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
        """Return the literal in the value's encoding, if it can be encoded, and the diagnostics explaining why not."""
        potential_literal = literal.potential_literal
        literal_encoding = self._literal_encoding(potential_literal)
        # A missing Potential Literal was already reported when its reference
        # was resolved.
        if literal_encoding is None:
            return None, []
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
        parser = literal_parsers.LITERAL_PARSERS.get(
            (literal_encoding.full_typed_name, value_encoding)
        )
        if parser is None:
            return None, [
                diagnostics.LiteralCannotSetValueDiagnostic(
                    location=potential_literal.location,
                    potential_literal=potential_literal.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    literal_encoding=literal_encoding.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    value_type=value_type.source_form_in_universe(self._enclosing_fqun),
                    supported_encodings=_supported_encodings(value_encoding),
                )
            ]
        return self._parse(literal, parser, value_encoding)

    def encode_in_encoding(
        self, literal: ast.Literal, encoding: ast.GlobalTypedNameReference
    ) -> tuple[codegen_input.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
        """Return the literal in the encoding, if it can be translated, and the diagnostics explaining why not."""
        potential_literal = literal.potential_literal
        literal_encoding = self._literal_encoding(potential_literal)
        # A missing Potential Literal was already reported when its reference
        # was resolved.
        if literal_encoding is None:
            return None, []
        parser = literal_parsers.LITERAL_PARSERS.get(
            (literal_encoding.full_typed_name, encoding.full_typed_name)
        )
        if parser is None:
            return None, [
                diagnostics.LiteralCannotBeConvertedDiagnostic(
                    location=potential_literal.location,
                    potential_literal=potential_literal.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    literal_encoding=literal_encoding.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    encoding=encoding.source_form_in_universe(self._enclosing_fqun),
                    supported_encodings=_supported_encodings(encoding.full_typed_name),
                )
            ]
        return self._parse(literal, parser, encoding.full_typed_name)

    def _literal_encoding(
        self, potential_literal: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Potential Literal's encoding, if the Potential Literal is defined."""
        definition_result = self._definition_results.get(potential_literal)
        if definition_result is None:
            return None
        definition = typing.cast(
            "ast.PotentialLiteralDefinition", definition_result.definition
        )
        return definition.encoding

    def _parse(
        self,
        literal: ast.Literal,
        parser: Callable[[str], str],
        destination_encoding: str,
    ) -> tuple[codegen_input.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
        try:
            return codegen_input.EncodedLiteral(
                encoding=destination_encoding, content=parser(literal.content)
            ), []
        except literal_parsers.LiteralParseError as e:
            return None, [
                diagnostics.InvalidLiteralContentDiagnostic(
                    location=literal.content_character_location(e.content_index),
                    content=literal.content,
                    potential_literal=literal.potential_literal.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    value_encoding=destination_encoding,
                    reason=e.reason,
                )
            ]


def _supported_encodings(destination_encoding: str) -> list[str]:
    """Return the literal encodings that can be translated into the destination encoding."""
    supported_encodings: list[str] = []
    for source_encoding, parser_destination in literal_parsers.LITERAL_PARSERS:
        if parser_destination == destination_encoding:
            supported_encodings.append(source_encoding)
    return supported_encodings
