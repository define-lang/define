"""DCL parser that validates syntax and parses to protobuf messages."""

import os
from functools import cached_property

from google.protobuf import message, text_format

from defcl.python.validator import semantics, syntax


class Parser:
    """Parses DCL text into protobuf messages."""

    @cached_property
    def _validator(self) -> syntax.Parser:
        return syntax.Parser()

    def parse[M: message.Message](
        self,
        text: str,
        message_type: type[M],
        path_name: str | os.PathLike[str] | None = None,
    ) -> M:
        """Parse DCL text into a protobuf message.

        Args:
            text: DCL text to parse.
            message_type: The protobuf message class to parse into.
            path_name: Optional file path for error messages.

        Raises:
            DclSyntaxError: If the text fails DCL syntax or semantic validation.
            text_format.ParseError: If the text fails protobuf parsing.
        """
        tree = self._validator.parse(text, path_name=path_name)
        semantics.validate(tree, message_type, path_name=path_name)

        return text_format.Parse(text, message_type())

    def parse_file[M: message.Message](
        self, path: str | os.PathLike[str], message_type: type[M]
    ) -> M:
        """Parse a DCL file into a protobuf message."""
        with open(path, encoding="utf-8", newline="") as f:
            return self.parse(f.read(), message_type, path_name=path)
