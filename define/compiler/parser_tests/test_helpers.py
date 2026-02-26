"""Shared parser test helpers."""

from define.compiler.lark import lark_standalone


def get_tokens_by_type(
    tree: lark_standalone.Tree[lark_standalone.Token], token_type: str
) -> list[str]:
    """Collect all token values of a given type from a parse tree."""
    tokens: list[str] = []
    for child in tree.children:
        if isinstance(child, lark_standalone.Tree):
            tokens.extend(get_tokens_by_type(child, token_type))
        elif isinstance(child, lark_standalone.Token) and child.type == token_type:
            tokens.append(str(child))
    return tokens
