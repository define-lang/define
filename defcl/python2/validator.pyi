from defcl.python2 import errors

def validate(
    source: str, descriptor_set: bytes, top_level_message_type: str
) -> list[errors.DclDiagnostic]: ...
