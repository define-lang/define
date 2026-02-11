"""Shared parser test helpers."""

import lark


def get_tokens_by_type(tree: lark.Tree[lark.Token], token_type: str) -> list[str]:
    """Collect all token values of a given type from a parse tree."""
    tokens: list[str] = []
    for child in tree.children:
        if isinstance(child, lark.Tree):
            tokens.extend(get_tokens_by_type(child, token_type))
        elif isinstance(child, lark.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens
