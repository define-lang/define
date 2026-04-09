from collections.abc import Callable, Iterable, Mapping
from typing import Generic, Self, TypeVar

_Leaf_T = TypeVar("_Leaf_T")
_Return_T = TypeVar("_Return_T")
_Label_T = TypeVar("_Label_T")
_DecRetT = TypeVar("_DecRetT")

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
    children: list[_Leaf_T | Self | None]

    def __init__(
        self,
        data: str,
        children: list[_Leaf_T | Self],
        meta: Meta | None = None,
    ) -> None: ...
    @property
    def meta(self) -> Meta: ...

class Token(str):
    type: str
    start_pos: int | None
    value: str
    line: int | None
    column: int | None
    end_line: int | None
    end_column: int | None
    end_pos: int | None

    def __new__(
        cls,
        type: str,
        value,
        start_pos: int | None = None,
        line: int | None = None,
        column: int | None = None,
        end_line: int | None = None,
        end_column: int | None = None,
        end_pos: int | None = None,
    ) -> Token: ...

class UnexpectedInput(Exception):
    line: int
    column: int

    def get_context(self, text: str, span: int = 40) -> str: ...
    def match_examples(
        self,
        parse_fn: Callable[[str], Tree[Token]],
        examples: Mapping[_Label_T, Iterable[str]]
        | Iterable[tuple[_Label_T, Iterable[str]]],
        token_type_match_fallback: bool = False,
        use_accepts: bool = True,
    ) -> _Label_T | None: ...

class InteractiveParser:
    def feed_token(self, token: Token) -> None: ...

class UnexpectedCharacters(UnexpectedInput):
    allowed: set[str]
    char: str
    token_history: list[Token] | None
    interactive_parser: InteractiveParser

class UnexpectedToken(UnexpectedInput):
    token: Token
    expected: set[str]
    token_history: list[Token] | None
    interactive_parser: InteractiveParser | None

    @property
    def accepts(self) -> set[str]: ...

class VisitError(Exception):
    orig_exc: Exception

class _DiscardType: ...

Discard: _DiscardType

class Transformer(Generic[_Leaf_T, _Return_T]):
    def transform(self, tree: Tree[_Leaf_T]) -> _Return_T: ...

def v_args(
    inline: bool = False,
    meta: bool = False,
    tree: bool = False,
    wrapper: Callable[[Callable[..., _DecRetT]], Callable[..., _DecRetT]] | None = None,
) -> Callable[[Callable[..., _DecRetT]], Callable[..., _DecRetT]]: ...

class Lark:
    def parse(
        self,
        text: str,
        start: str | None = None,
        on_error: Callable[[UnexpectedInput], bool] | None = None,
    ) -> Tree[Token]: ...

def Lark_StandAlone(**kwargs: object) -> Lark: ...
