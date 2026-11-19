"""Global names written in config files."""

from __future__ import annotations

import typing

from define.compiler import ast, constants
from define.compiler.errors import config_diagnostics, syntax_errors
from define.compiler.parsing import parser
from define.compiler.validator.structural import name_validators

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from defcl.python import validator as defcl_validator
    from define.compiler import name_types
    from define.compiler.config import local_deps_config
    from define.compiler.errors import diagnostics


def config_global_name(
    file: defcl_validator.ValidatedFile,
    field_path: config_diagnostics.FieldPath,
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


def config_fqun(
    file: defcl_validator.ValidatedFile,
    field_path: config_diagnostics.FieldPath,
    name: str,
) -> tuple[ast.Fqun | None, list[diagnostics.Diagnostic]]:
    """Parse and validate the fully qualified universe name in the config file's field at field_path.

    Returns it, located at its value in the file, or None if it is not valid,
    with its diagnostics.
    """
    # Each field's value is a string, so it is located at its opening quote,
    # and the name starts after it.
    # TODO: This is only right when the string has no escapes. Locate the
    # name by its value's text once defcl gives that location.
    quote = file.location_of(field_path)
    fqun = parser.parse_fqun(
        name.encode(), quote.file_path, quote.line, quote.column + 1
    )
    if isinstance(fqun, syntax_errors.DefineSyntaxError):
        return None, [fqun]
    fqun_diagnostics = name_validators.validate_fqun(fqun)
    return (None if fqun_diagnostics else fqun), fqun_diagnostics


def check_global_name_in_this_universe(
    field_name: str, content: ast.ReferenceGlobalNameContent, fqun: str
) -> diagnostics.Diagnostic | None:
    """Return a diagnostic if the name in the field named field_name is not in the same universe as the project, whose FQUN is fqun."""
    # A short name is in the project's universe. `config_global_name` rejects
    # a name with the project's own FQUN, so any other name with an FQUN is
    # in another universe.
    if content.fqun is None:
        return None
    return config_diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=content.location,
        field_name=field_name,
        name=content.source_name,
        fqun=fqun,
    )


def universe_needs_configuration(fqun: str) -> bool:
    """Whether a project must configure a universe as a sub-root before referencing it."""
    # TODO: Remove this once the Define Standard Library exists.
    return fqun != constants.STANDARD_UNIVERSE


def associated_reference(
    name_type: name_types.NameType,
    name: ast.ReferenceGlobalNameContent,
    fqun: ast.Fqun,
) -> ast.GlobalTypedNameReference:
    """Return a reference to the definition of name_type named name, which a project config whose universe is fqun associates with one of the project's definitions, located where the config writes it."""
    return ast.GlobalTypedNameReference(
        name_type=name_type,
        name_content=name,
        enclosing_fqun=fqun,
        location=name.location,
    )


def check_universe_configured(
    name: ast.ReferenceGlobalNameContent,
    fqun: ast.Fqun,
    sub_roots: Mapping[str, local_deps_config.LocalDependencyEntry],
) -> config_diagnostics.ExternalUniverseNotConfiguredDiagnostic | None:
    """Return a diagnostic if name is in a universe that the project whose universe is fqun and whose sub-roots are sub_roots must configure before referencing it, and does not."""
    name_fqun = name.fqun
    if (
        name_fqun is None
        or not universe_needs_configuration(name_fqun.canonical)
        or name_fqun.canonical in sub_roots
    ):
        return None
    return config_diagnostics.ExternalUniverseNotConfiguredDiagnostic(
        location=name_fqun.location,
        universe=name_fqun.canonical,
        current_universe_name=fqun.canonical,
    )
