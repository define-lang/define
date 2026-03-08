"""Semantic validation for DCL parse trees against protobuf descriptors."""

import os
from typing import cast

from google.protobuf import descriptor, message

from defcl.python import exceptions
from defcl.python.lark import lark_standalone


def validate(
    tree: lark_standalone.Tree[lark_standalone.Token],
    message_type: type[message.Message],
    path_name: str | os.PathLike[str] | None = None,
) -> None:
    """Validate a DCL parse tree against a protobuf message type.

    The tree must come from syntax.Parser and its field names must match
    the protobuf descriptor.

    Args:
        tree: The parse tree produced by syntax.Parser.
        message_type: The protobuf message class for the top-level message.
        path_name: Optional file path for error messages.
    """
    msg_desc = message_type.DESCRIPTOR
    for top_level in tree.children:
        top_level = cast("lark_standalone.Tree[lark_standalone.Token]", top_level)
        name_token = cast("lark_standalone.Token", top_level.children[0])
        field_desc = msg_desc.fields_by_name.get(str(name_token))
        if field_desc is None or field_desc.message_type is None:
            raise ValueError(
                f"unexpected unknown field {str(name_token)!r} in"
                + f" {msg_desc.full_name} (should have been caught by proto parser)"
            )
        msg_tree = cast(
            "lark_standalone.Tree[lark_standalone.Token]", top_level.children[1]
        )
        _check_message(msg_tree, field_desc.message_type, path_name)


def _check_message(
    msg_tree: lark_standalone.Tree[lark_standalone.Token],
    msg_desc: descriptor.Descriptor,
    path_name: str | os.PathLike[str] | None,
) -> None:
    """Check all fields within a message_value node."""
    for field_tree in msg_tree.children:
        field_tree = cast("lark_standalone.Tree[lark_standalone.Token]", field_tree)
        name_token = cast("lark_standalone.Token", field_tree.children[0])
        field_desc = msg_desc.fields_by_name[str(name_token)]
        value_tree = cast(
            "lark_standalone.Tree[lark_standalone.Token]", field_tree.children[1]
        )
        _check_field(name_token, field_desc, value_tree, path_name)


def _check_field(
    name_token: lark_standalone.Token,
    field_desc: descriptor.FieldDescriptor,
    value_tree: lark_standalone.Tree[lark_standalone.Token],
    path_name: str | os.PathLike[str] | None,
) -> None:
    """Check a field's value against its descriptor, including repeated syntax."""
    child = value_tree.children[0]

    if field_desc.label == descriptor.FieldDescriptor.LABEL_REPEATED:
        if not (
            isinstance(child, lark_standalone.Tree) and child.data == "repeated_value"
        ):
            raise exceptions.RepeatedFieldWithoutBracketsError(
                name_token.line or 0,
                name_token.column or 0,
                str(name_token),
                path_name,
            )
        for item_value in child.children:
            # Empty repeated fields (e.g. `[]`) produce a None child in Lark.
            if item_value is None:
                continue  # pragma: no mutate
            item_value = cast("lark_standalone.Tree[lark_standalone.Token]", item_value)
            _check_value(name_token, field_desc, item_value, path_name)
        return

    _check_value(name_token, field_desc, value_tree, path_name)


def _check_value(
    name_token: lark_standalone.Token,
    field_desc: descriptor.FieldDescriptor,
    value_tree: lark_standalone.Tree[lark_standalone.Token],
    path_name: str | os.PathLike[str] | None,
) -> None:
    """Check a single value against its field type."""
    child = value_tree.children[0]
    if isinstance(child, lark_standalone.Token):
        if (
            field_desc.type == descriptor.FieldDescriptor.TYPE_ENUM
            and child.type == "INTEGER"
        ):
            raise exceptions.IntegerEnumError(
                name_token.line or 0,
                name_token.column or 0,
                str(name_token),
                path_name,
            )
    elif isinstance(child, lark_standalone.Tree) and child.data == "message_value":
        if field_desc.message_type is None:
            raise ValueError(
                f"unexpected unknown field {str(name_token)!r} has message value"
                + " but no message type in descriptor"
                + " (should have been caught by proto parser)"
            )
        _check_message(child, field_desc.message_type, path_name)
