from collections.abc import Iterator
from typing import Generic, TypeVar, Union

from lark.lexer import Token

_Leaf_T = TypeVar("_Leaf_T")
Branch = Union[_Leaf_T, "Tree[_Leaf_T]", None]
ParseTree = Tree[Token]

class Meta:
    empty: bool
    line: int
    column: int
    start_pos: int
    end_line: int
    end_column: int
    end_pos: int

class Tree(Generic[_Leaf_T]):
    data: str
    children: list[Branch[_Leaf_T]]

    def __init__(
        self,
        data: str,
        children: list[Branch[_Leaf_T]],
        meta: Meta | None = None,
    ) -> None: ...
    @property
    def meta(self) -> Meta: ...
    def pretty(self, indent_str: str = "  ") -> str: ...
    def find_data(self, data: str) -> Iterator[Tree[_Leaf_T]]: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __repr__(self) -> str: ...
