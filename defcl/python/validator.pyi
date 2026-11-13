from crates.source_rendering.python import rendering
from defcl.python import errors

def validate(
    source: str, descriptor_set: bytes, top_level_message_type: str
) -> tuple[bool, list[errors.DefclDiagnostic]]: ...

class ValidatedFile:
    def text(self) -> str: ...
    def location_of(
        self, field_path: tuple[str | int, ...]
    ) -> rendering.SourceLocation: ...

def validate_file(
    path: str,
    source_map: rendering.SourceMap,
    descriptor_set: bytes,
    top_level_message_type: str,
) -> tuple[ValidatedFile | None, list[errors.DefclDiagnostic]]: ...
