from collections.abc import Callable
from typing import IO, Any, TypeVar

from lark.exceptions import UnexpectedInput
from lark.tree import ParseTree

_T = TypeVar("_T", bound="Lark")

class Lark:
    source_path: str
    source_grammar: str

    def __init__(self, grammar: str | IO[str], **options: Any) -> None: ...
    @classmethod
    def open(
        cls: type[_T],
        grammar_filename: str,
        rel_to: str | None = None,
        **options: Any,
    ) -> _T: ...
    def parse(
        self,
        text: str | bytes,
        start: str | None = None,
        on_error: Callable[[UnexpectedInput], bool] | None = None,
    ) -> ParseTree: ...
