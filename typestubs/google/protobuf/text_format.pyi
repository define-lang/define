from typing import TypeVar

from google.protobuf.message import Message

_M = TypeVar("_M", bound=Message)

def Parse(
    text: str | bytes,
    message: _M,
    allow_unknown_extension: bool = False,
    allow_field_number: bool = False,
    descriptor_pool: object | None = None,
    allow_unknown_field: bool = False,
) -> _M: ...
