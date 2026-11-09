"""Loads DCL files into protobuf messages."""

from __future__ import annotations

import functools
import typing

import msgspec
from google.protobuf import descriptor_pb2, message, text_format

from defcl.python import validator

if typing.TYPE_CHECKING:
    from defcl.python import errors
    from source_rendering.python import rendering


class LoadResult[M: message.Message](msgspec.Struct, frozen=True):
    """The message that a DCL file holds, or the diagnostics that keep it from loading."""

    # None when there are diagnostics.
    message: M | None
    diagnostics: list[errors.DclDiagnostic]


def load[M: message.Message](source: str, message_type: type[M]) -> LoadResult[M]:
    """Load the DCL text `source` into a message of `message_type`.

    Raises:
        text_format.ParseError: If `source` fails a check that only protobuf's
            text format parser makes.
    """
    diagnostics = validator.validate(
        source,
        _descriptor_set(message_type),
        message_type.DESCRIPTOR.full_name,
    )
    if diagnostics:
        return LoadResult(message=None, diagnostics=diagnostics)
    return LoadResult(message=text_format.Parse(source, message_type()), diagnostics=[])


def load_file[M: message.Message](
    path: str, message_type: type[M], source_map: rendering.SourceMap
) -> LoadResult[M]:
    """Load the DCL file at `path` into a message of `message_type`, registering it with `source_map`.

    Raises:
        OSError: If the file cannot be read.
        text_format.ParseError: If the file fails a check that only protobuf's
            text format parser makes.
    """
    source, diagnostics = validator.validate_file(
        path,
        source_map,
        _descriptor_set(message_type),
        message_type.DESCRIPTOR.full_name,
    )
    if diagnostics:
        return LoadResult(message=None, diagnostics=diagnostics)
    # The file's text, not a second read of the file, so that the text that is
    # parsed is the text that was validated.
    return LoadResult(message=text_format.Parse(source, message_type()), diagnostics=[])


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
