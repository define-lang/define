from collections.abc import Callable, Iterable, Mapping
from typing import Self, TypeVar

_Label_T = TypeVar("_Label_T")

class Meta:
    empty: bool
    line: int
    column: int
    start_pos: int
    end_line: int
    end_column: int
    end_pos: int

class Tree[LeafT]:
    data: str
    children: list[LeafT | Self | None]

    def __init__(
        self,
        data: str,
        children: list[LeafT | Self],
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
        type: str,  # noqa: A002
        value,
        start_pos: int | None = None,
        line: int | None = None,
        column: int | None = None,
        end_line: int | None = None,
        end_column: int | None = None,
        end_pos: int | None = None,
    ) -> Self: ...

class UnexpectedInput(Exception):  # noqa: N818
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

class Transformer[LeafT, ReturnT]:
    def transform(self, tree: Tree[LeafT]) -> ReturnT: ...

def v_args[DecoratorReturnT](
    inline: bool = False,
    meta: bool = False,
    tree: bool = False,
    wrapper: Callable[
        [Callable[..., DecoratorReturnT]], Callable[..., DecoratorReturnT]
    ]
    | None = None,
) -> Callable[[Callable[..., DecoratorReturnT]], Callable[..., DecoratorReturnT]]: ...

class Lark:
    def parse(
        self,
        text: str,
        start: str | None = None,
        on_error: Callable[[UnexpectedInput], bool] | None = None,
    ) -> Tree[Token]: ...

def Lark_StandAlone(**kwargs: object) -> Lark: ...  # noqa: N802
