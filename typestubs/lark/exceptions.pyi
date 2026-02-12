from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeVar

from lark.lexer import Token
from lark.tree import Tree

_T = TypeVar("_T")

class LarkError(Exception): ...
class ConfigurationError(LarkError, ValueError): ...
class GrammarError(LarkError): ...
class ParseError(LarkError): ...
class LexError(LarkError): ...

class UnexpectedInput(LarkError):
    line: int
    column: int
    pos_in_stream: int | None
    state: Any

    def get_context(self, text: str, span: int = 40) -> str: ...
    def match_examples(
        self,
        parse_fn: Callable[[str], Tree[Token]],
        examples: (Mapping[_T, Iterable[str]] | Iterable[tuple[_T, Iterable[str]]]),
        token_type_match_fallback: bool = False,
        use_accepts: bool = True,
    ) -> _T | None: ...

class UnexpectedCharacters(LexError, UnexpectedInput):
    allowed: set[str]
    considered_tokens: set[Any]
    char: str
    token_history: list[Token] | None
    considered_rules: set[str] | None

    def __init__(
        self,
        seq: str,
        lex_pos: int,
        line: int,
        column: int,
        allowed: set[str] | None = None,
        considered_tokens: set[Any] | None = None,
        state: Any = None,
        token_history: list[Token] | None = None,
        terminals_by_name: Any = None,
        considered_rules: set[str] | None = None,
    ) -> None: ...

class UnexpectedToken(ParseError, UnexpectedInput):
    expected: set[str]
    considered_rules: set[str]
    token: Token
    token_history: list[Token] | None

    @property
    def accepts(self) -> set[str]: ...
    def __init__(
        self,
        token: Token,
        expected: set[str],
        considered_rules: set[str] | None = None,
        state: Any = None,
        interactive_parser: Any = None,
        terminals_by_name: Any = None,
        token_history: list[Token] | None = None,
    ) -> None: ...

class UnexpectedEOF(ParseError, UnexpectedInput):
    expected: list[Token]
    token: Token

    def __init__(
        self,
        expected: list[Token],
        state: Any = None,
        terminals_by_name: Any = None,
    ) -> None: ...

class VisitError(LarkError):
    obj: Tree[Token] | Token
    orig_exc: Exception

class MissingVariableError(LarkError): ...
