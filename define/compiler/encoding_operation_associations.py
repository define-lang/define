"""The Encoding Operation that performs each Value Operation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, constants, name_types

if TYPE_CHECKING:
    from crates.source_rendering.python import rendering


def _standard_encoding_operation_reference(
    path: str, location: rendering.SourceLocation, enclosing_fqun: ast.Fqun
) -> ast.GlobalTypedNameReference:
    """Return a reference, located at ``location``, to the Encoding Operation at ``path`` in the standard universe."""
    # The reference has no source, since the built-in table writes the
    # association. The table goes away when the standard Value Operations are
    # compositions of logical operations.
    return ast.GlobalTypedNameReference(
        name_type=name_types.NameType.ENCODING_OPERATION,
        name_content=ast.ReferenceGlobalNameContent(
            fqun=ast.Fqun(
                multiverse=None,
                authority=None,
                universe=ast.Universe(
                    name=constants.STANDARD_UNIVERSE, location=location
                ),
                location=location,
            ),
            path=ast.GlobalPathName(name=path, location=location),
            location=location,
        ),
        enclosing_fqun=enclosing_fqun,
        location=location,
    )


def encoding_operation_reference(
    value_operation: ast.ValueOperationDefinition,
) -> ast.GlobalTypedNameReference | None:
    """Return a reference to the Encoding Operation that performs a Value Operation, if one does.

    The reference is located at the Value Operation's name, so diagnostics
    about it point there.
    """
    path = constants.BUILT_IN_ENCODING_OPERATIONS.get(
        value_operation.typed_name.full_typed_name
    )
    if path is None:
        return None
    return _standard_encoding_operation_reference(
        path,
        value_operation.typed_name.location,
        value_operation.typed_name.name_content.fqun,
    )
