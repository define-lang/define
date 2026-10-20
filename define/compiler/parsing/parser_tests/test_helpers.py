"""Shared parser test helpers."""

from __future__ import annotations

import lark_cython

from define.compiler import ast
from define.compiler.parsing.lark import lark_standalone


def get_tokens_by_type(
    tree: lark_standalone.Tree[lark_cython.Token], token_type: str
) -> list[str]:
    """Collect all token values of a given type from a parse tree."""
    tokens: list[str] = []
    for child in tree.children:
        if isinstance(child, lark_standalone.Tree):
            tokens.extend(get_tokens_by_type(child, token_type))
        elif isinstance(child, lark_cython.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens


def global_typed_names(program: ast.Program) -> list[str]:
    """Return every global typed name in the program as written, in source order."""
    names: list[str] = []
    for definition in program.definitions:
        names.append(definition.typed_name.source_typed_name)
        if isinstance(definition, ast.QualityDefinition):
            names.extend(
                implication.typed_global_name.source_typed_name
                for implication in definition.quality_implications
            )
        if isinstance(definition, ast.PositionDefinition) and definition.constraints:
            names.extend(
                requirement.typed_global_name.source_typed_name
                for requirement in definition.constraints.requirements
            )
    return names
