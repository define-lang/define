from collections.abc import Sequence

from defcl.python import errors
from source_rendering.python import rendering

def validate(
    source: str, descriptor_set: bytes, top_level_message_type: str
) -> list[errors.DclDiagnostic]: ...
def validate_file(
    path: str,
    source_map: rendering.SourceMap,
    descriptor_set: bytes,
    top_level_message_type: str,
) -> tuple[str, list[errors.DclDiagnostic]]: ...
def locate_field(
    source_map: rendering.SourceMap, path: str, field_path: Sequence[str | int]
) -> rendering.SourceLocation | None: ...
