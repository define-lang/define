"""Loads defcl files into protobuf messages."""

from __future__ import annotations

import functools
import typing

import msgspec
from google.protobuf import descriptor_pb2, message, text_format

from defcl.python import validator

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from defcl.python import errors


class LoadResult[M: message.Message](msgspec.Struct, frozen=True):
    """The message that a defcl file holds, if it still means exactly one message, and its diagnostics."""

    # None when a diagnostic leaves the file's meaning unclear. Otherwise the
    # message is here even if the file has diagnostics, so that a caller can go
    # on to find other errors. The diagnostics still mean the file is invalid.
    message: M | None
    diagnostics: list[errors.DefclDiagnostic]


class LoadedMessage[M: message.Message](msgspec.Struct, frozen=True):
    """The message that a defcl file holds, with the file, which can find the location of each field."""

    message: M
    file: validator.ValidatedFile


class LoadFileResult[M: message.Message](msgspec.Struct, frozen=True):
    """A defcl file's message and the file, if the file still means exactly one message, and its diagnostics."""

    # None when a diagnostic leaves the file's meaning unclear, as for
    # `LoadResult.message`.
    loaded: LoadedMessage[M] | None
    diagnostics: list[errors.DefclDiagnostic]


def load[M: message.Message](source: str, message_type: type[M]) -> LoadResult[M]:
    """Load the defcl text `source` into a message of `message_type`.

    Raises:
        text_format.ParseError: If `source` fails a check that only protobuf's
            text format parser makes.
    """
    understood, diagnostics = validator.validate(
        source,
        _descriptor_set(message_type),
        message_type.DESCRIPTOR.full_name,
    )
    if not understood:
        return LoadResult(message=None, diagnostics=diagnostics)
    return LoadResult(
        message=text_format.Parse(source, message_type()), diagnostics=diagnostics
    )


# TODO: Consider returning objects built straight from the syntax tree, with
# each value's location attached, instead of protobuf messages, using the
# schema only to validate the file. Callers would then read a field's
# location from the field itself, instead of looking up its field path in the
# file. It needs a type for each schema's messages, and a replacement for
# protovalidate's rules, which check only protobuf messages.
def load_file[M: message.Message](
    path: str, message_type: type[M], source_map: rendering.SourceMap
) -> LoadFileResult[M]:
    """Load the defcl file at `path` into a message of `message_type`, registering it with `source_map`.

    Raises:
        OSError: If the file cannot be read.
        text_format.ParseError: If the file fails a check that only protobuf's
            text format parser makes.
    """
    file, diagnostics = validator.validate_file(
        path,
        source_map,
        _descriptor_set(message_type),
        message_type.DESCRIPTOR.full_name,
    )
    if file is None:
        return LoadFileResult(loaded=None, diagnostics=diagnostics)
    # The file's text, not a second read of the file, so that the text that is
    # parsed is the text that was validated.
    parsed_message = text_format.Parse(file.text(), message_type())
    return LoadFileResult(
        loaded=LoadedMessage(message=parsed_message, file=file),
        diagnostics=diagnostics,
    )


# TODO: Move the walk over the imports into defcl/rust when the Rust crate
# writes the binary encoding: Rust follows each file's imports and asks the
# extension for each file by name from Python's descriptor pool.
#
# A message type's descriptors never change once its module is imported, so
# its descriptor set is built once. Building and serializing it took most of
# the time of loading a small file, and a program loads a config for every
# universe it uses.
@functools.cache
def _descriptor_set(message_type: type[message.Message]) -> bytes:
    """Return the binary `FileDescriptorSet` of the file that defines `message_type` and every file it imports."""
    descriptor_set = descriptor_pb2.FileDescriptorSet()
    added_names: set[str] = set()
    pending = [message_type.DESCRIPTOR.file]
    while pending:
        current = pending.pop()
        if current.name in added_names:
            continue
        added_names.add(current.name)
        current.CopyToProto(descriptor_set.file.add())
        pending.extend(current.dependencies)
    return descriptor_set.SerializeToString()
