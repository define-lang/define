class Descriptor:
    name: str
    full_name: str
    fields_by_name: dict[str, FieldDescriptor]

class FieldDescriptor:
    LABEL_OPTIONAL: int
    LABEL_REPEATED: int
    LABEL_REQUIRED: int

    TYPE_BOOL: int
    TYPE_BYTES: int
    TYPE_DOUBLE: int
    TYPE_ENUM: int
    TYPE_FIXED32: int
    TYPE_FIXED64: int
    TYPE_FLOAT: int
    TYPE_GROUP: int
    TYPE_INT32: int
    TYPE_INT64: int
    TYPE_MESSAGE: int
    TYPE_SFIXED32: int
    TYPE_SFIXED64: int
    TYPE_SINT32: int
    TYPE_SINT64: int
    TYPE_STRING: int
    TYPE_UINT32: int
    TYPE_UINT64: int

    name: str
    full_name: str
    type: int
    label: int
    message_type: Descriptor | None
