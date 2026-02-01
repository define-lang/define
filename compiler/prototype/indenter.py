"""Indentation handling for the Define grammar."""

from lark.indenter import Indenter


class DefineIndenter(Indenter):
    """Configure indentation handling for the Define grammar tests."""

    # We have to do all of this as properties to make pyright happy.

    @property
    def NL_type(self) -> str:  # noqa: N802
        """Return the token type for newlines."""
        return "_NEWLINE"

    @property
    def OPEN_PAREN_types(self) -> list[str]:  # noqa: N802
        """Return the list of token types for opening parentheses."""
        return []

    @property
    def CLOSE_PAREN_types(self) -> list[str]:  # noqa: N802
        """Return the list of token types for closing parentheses."""
        return []

    @property
    def INDENT_type(self) -> str:  # noqa: N802
        """Return the token type for indentation."""
        return "INDENT"

    @property
    def DEDENT_type(self) -> str:  # noqa: N802
        """Return the token type for dedentation."""
        return "DEDENT"

    @property
    def tab_len(self) -> int:
        """Return the tab length in spaces."""
        return 4
