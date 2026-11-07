"""The Encoding Operations that perform each logical operation and each Value Operation."""

from __future__ import annotations

from define.compiler import ast, constants, name_types


def _standard_encoding_operation_reference(
    path: str, location: ast.SourceLocation, enclosing_fqun: ast.Fqun
) -> ast.GlobalTypedNameReference:
    """Return a reference, located at ``location``, to the Encoding Operation at ``path`` in the standard universe."""
    # TODO: Stop synthesizing references that have no source once DLP 48
    # decides where associations are written. Either the parser produces them
    # from Define source, or references stop requiring AST nodes so that
    # configuration can supply them.
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


def logical_operation_encoding_operation_references(
    logical_operation_name: str,
    location: ast.SourceLocation,
    enclosing_fqun: ast.Fqun,
) -> list[ast.GlobalTypedNameReference]:
    """Return references to the Encoding Operations that perform the logical operation with the full typed name ``logical_operation_name``.

    The references are located at ``location``, so diagnostics about them point
    there.
    """
    paths = constants.BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS.get(
        logical_operation_name, ()
    )
    references: list[ast.GlobalTypedNameReference] = []
    for path in paths:
        references.append(
            _standard_encoding_operation_reference(path, location, enclosing_fqun)
        )
    return references


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
