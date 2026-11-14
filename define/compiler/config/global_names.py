"""Global names written in config files."""

from __future__ import annotations

import typing

from define.compiler.errors import diagnostics, syntax_errors
from define.compiler.parsing import parser
from define.compiler.validator.structural import name_validators

if typing.TYPE_CHECKING:
    from defcl.python import validator as defcl_validator
    from define.compiler import ast


def config_global_name(
    file: defcl_validator.ValidatedFile,
    field_path: diagnostics.FieldPath,
    name: str,
    fqun: str,
) -> tuple[ast.ReferenceGlobalNameContent | None, list[diagnostics.Diagnostic]]:
    """Parse and validate the global name in the config file's field at field_path.

    Returns the name's content, located at its value in the file, or None if
    the name is not valid, with the name's diagnostics. fqun is the project's
    universe, whose names must be in short form.
    """
    # Each field's value is a string, so it is located at its opening quote,
    # and the name starts after it.
    # TODO: This is only right when the string has no escapes. Locate the
    # name by its value's text once defcl gives that location.
    quote = file.location_of(field_path)
    name_content = parser.parse_global_name(
        name.encode(), quote.file_path, quote.line, quote.column + 1
    )
    if isinstance(name_content, syntax_errors.DefineSyntaxError):
        return None, [name_content]
    content_diagnostics = name_validators.validate_global_name(
        name_content, must_use_short_form=fqun
    )
    return (None if content_diagnostics else name_content), content_diagnostics


def check_global_name_in_this_universe(
    field_name: str, content: ast.ReferenceGlobalNameContent, fqun: str
) -> diagnostics.Diagnostic | None:
    """Return a diagnostic if the name in the field named field_name is not in the same universe as the project, whose FQUN is fqun."""
    # A short name is in the project's universe. `config_global_name` rejects
    # a name with the project's own FQUN, so any other name with an FQUN is
    # in another universe.
    if content.fqun is None:
        return None
    return diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=content.location,
        field_name=field_name,
        name=content.source_name,
        fqun=fqun,
    )
