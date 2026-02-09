from collections.abc import Callable
from typing import Any, Generic, TypeVar

from lark.lexer import Token
from lark.tree import Tree

_Leaf_T = TypeVar("_Leaf_T")
_Return_T = TypeVar("_Return_T")
_F = TypeVar("_F", bound=Callable[..., object])

class _DiscardType:
    def __repr__(self) -> str: ...

Discard: _DiscardType

def v_args(
    inline: bool = False,
    meta: bool = False,
    tree: bool = False,
    wrapper: Callable[..., object] | None = None,
) -> Callable[[_F], _F]: ...

class Transformer(Generic[_Leaf_T, _Return_T]):
    def transform(self, tree: Tree[_Leaf_T]) -> _Return_T: ...
    def __default__(
        self, data: str, children: list[Any], meta: Any
    ) -> Any: ...
    def __default_token__(self, token: Token) -> Token: ...
