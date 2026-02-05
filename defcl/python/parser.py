"""DCL parser that validates syntax and parses to protobuf messages."""

import os

from google.protobuf import message, text_format

from defcl.python.validator import syntax


def parse[M: message.Message](text: str, message_type: type[M]) -> M:
    """Parse DCL text into a protobuf message.

    Args:
        text: DCL text to parse.
        message_type: The protobuf message class to parse into.

    Raises:
        DCLSyntaxError: If the text fails DCL syntax validation.
        text_format.ParseError: If the text fails protobuf parsing.
    """
    validator = syntax.Parser()
    validator.parse(text)

    msg = message_type()
    text_format.Parse(text, msg)
    return msg


def parse_file[M: message.Message](
    path: str | os.PathLike[str], message_type: type[M]
) -> M:
    """Parse a DCL file into a protobuf message."""
    with open(path, encoding="utf-8", newline="") as f:
        return parse(f.read(), message_type)
