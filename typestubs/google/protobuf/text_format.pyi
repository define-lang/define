from google.protobuf.message import Message

def Parse[MessageT: Message](  # noqa: N802
    text: str | bytes,
    message: MessageT,
    allow_unknown_extension: bool = False,
    allow_field_number: bool = False,
    descriptor_pool: object | None = None,
    allow_unknown_field: bool = False,
) -> MessageT: ...
