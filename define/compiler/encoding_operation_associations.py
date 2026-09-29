"""The Encoding Operation that performs each Value Operation."""

from __future__ import annotations

from define.compiler import ast, constants, name_types


def encoding_operation_reference(
    value_operation: ast.ValueOperationDefinition,
) -> ast.GlobalTypedNameReference | None:
    """Return a reference to the Encoding Operation that performs a Value Operation, if one does.

    The reference is located at the Value Operation's name, so diagnostics
    about it point there.
    """
    # TODO: Stop synthesizing a reference that has no source once DLP 48
    # decides where associations are written. Either the parser produces it
    # from Define source, or references stop requiring AST nodes so that
    # configuration can supply them.
    path = constants.BUILT_IN_ENCODING_OPERATIONS.get(
        value_operation.typed_name.full_typed_name
    )
    if path is None:
        return None
    location = value_operation.typed_name.location
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
        enclosing_fqun=value_operation.typed_name.name_content.fqun,
        location=location,
    )
