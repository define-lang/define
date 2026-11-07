import os
from collections.abc import Sequence

from defcl.python import errors, locations

def validate(
    source: str, descriptor_set: bytes, top_level_message_type: str
) -> list[errors.DclDiagnostic]: ...
def validate_file(
    path: str | os.PathLike[str], descriptor_set: bytes, top_level_message_type: str
) -> tuple[str, list[errors.DclDiagnostic]]: ...
def location_of(
    source: str, field_path: Sequence[str | int]
) -> locations.FieldPathLocation | None: ...
