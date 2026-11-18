"""Encode literals in the encoding of the value quality they become."""

from __future__ import annotations

import typing

from define.compiler import literal_parsers
from define.compiler.association_resolution import concrete_program
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from define.compiler import ast


class LiteralEncoder:
    """Translates literals into the encodings their uses require."""

    _definitions: Mapping[str, ast.GlobalDefinition]

    def __init__(
        self,
        definitions: Mapping[str, ast.GlobalDefinition],
    ):
        """Initialize with the known definitions."""
        self._definitions = definitions

    def encode(
        self,
        literal: ast.Literal,
        value_quality: ast.GlobalTypedNameReference,
        value_encoding: ast.GlobalTypedNameReference,
        enclosing_fqun: ast.Fqun,
    ) -> tuple[concrete_program.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
        """Return the literal in value_encoding, the encoding of value_quality, if it can be encoded, and the diagnostics explaining why not.

        The diagnostics name things as they are written in the universe whose
        FQUN is enclosing_fqun, the universe of the definition that contains
        the literal.
        """
        potential_literal = literal.potential_literal
        literal_encoding = self._literal_encoding(potential_literal)
        # A missing Potential Literal was already reported when its reference
        # was resolved.
        if literal_encoding is None:
            return None, []
        # TODO: Translate the literal into any encoding its target requires,
        # instead of always using the value quality's own encoding.
        parser = literal_parsers.LITERAL_PARSERS.get(
            (literal_encoding.full_typed_name, value_encoding.full_typed_name)
        )
        if parser is None:
            return None, [
                diagnostics.LiteralCannotSetValueDiagnostic(
                    location=potential_literal.location,
                    potential_literal=potential_literal.source_form_in_universe(
                        enclosing_fqun
                    ),
                    literal_encoding=literal_encoding.source_form_in_universe(
                        enclosing_fqun
                    ),
                    value_quality=value_quality.source_form_in_universe(enclosing_fqun),
                    supported_encodings=_supported_encodings(
                        value_encoding.full_typed_name
                    ),
                )
            ]
        return _parse(literal, parser, value_encoding, enclosing_fqun)

    def encode_in_encoding(
        self,
        literal: ast.Literal,
        encoding: ast.GlobalTypedNameReference,
        enclosing_fqun: ast.Fqun,
    ) -> tuple[concrete_program.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
        """Return the literal in the encoding, if it can be translated, and the diagnostics explaining why not, which name things as they are written in the universe whose FQUN is enclosing_fqun."""
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
                        enclosing_fqun
                    ),
                    literal_encoding=literal_encoding.source_form_in_universe(
                        enclosing_fqun
                    ),
                    encoding=encoding.source_form_in_universe(enclosing_fqun),
                    supported_encodings=_supported_encodings(encoding.full_typed_name),
                )
            ]
        return _parse(literal, parser, encoding, enclosing_fqun)

    def _literal_encoding(
        self, potential_literal: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Potential Literal's encoding, if the Potential Literal is defined."""
        potential_literal_definition = self._definitions.get(
            potential_literal.full_typed_name
        )
        if potential_literal_definition is None:
            return None
        definition = typing.cast(
            "ast.PotentialLiteralDefinition", potential_literal_definition
        )
        return definition.encoding


def _parse(
    literal: ast.Literal,
    parser: Callable[[str], str],
    destination_encoding: ast.GlobalTypedNameReference,
    enclosing_fqun: ast.Fqun,
) -> tuple[concrete_program.EncodedLiteral | None, list[diagnostics.Diagnostic]]:
    try:
        return concrete_program.EncodedLiteral(
            encoding=destination_encoding, content=parser(literal.content)
        ), []
    except literal_parsers.LiteralParseError as e:
        return None, [
            diagnostics.InvalidLiteralContentDiagnostic(
                location=literal.content_character_location(e.content_index),
                content=literal.content,
                potential_literal=literal.potential_literal.source_form_in_universe(
                    enclosing_fqun
                ),
                value_encoding=destination_encoding.full_typed_name,
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
