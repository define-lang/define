"""Parser for Define language statements."""

import os

from define.compiler import parser_error_classification
from define.compiler.lark import lark_standalone

UnexpectedInput = lark_standalone.UnexpectedInput


class Parser:
    """Parser for Define language source code."""

    _lark: lark_standalone.Lark

    def __init__(self):
        """Initialize the parser with the Define grammar."""
        self._lark = lark_standalone.Lark_StandAlone()

    def parse(
        self, source: str, file_path: str | os.PathLike[str] | None = None
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Parse Define source code and return a parse tree.

        file_path is only used for error messages.
        """
        try:
            return self._lark.parse(source)
        except lark_standalone.UnexpectedCharacters as e:
            exc_class = parser_error_classification.classify_char_error(e, source)
            if exc_class is not None:
                raise exc_class.from_lark_exception(e, source, e.char, file_path) from e
            raise
        except lark_standalone.UnexpectedToken as e:
            parser_error_classification.raise_token_error(e, source, file_path)
            raise
