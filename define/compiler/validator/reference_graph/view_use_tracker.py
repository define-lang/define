"""Track how an operation's statements read and write its views, according to Single Assignment."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from define.compiler import name_types


class _ViewUse(msgspec.Struct):
    """How the statements so far have used one view."""

    definition: ast.InterfaceViewDefinition | ast.LocalViewDefinition
    is_read: bool = False
    # Where the view is first written, if a statement has written it.
    first_write: ast.SourceLocation | None = None
    # A statement has already been reported for reading or writing the view
    # in a way Single Assignment does not allow. Fixing that statement also
    # fixes whether the view ends up unread or unwritten, so the mistake is
    # reported only once.
    has_reported_read_or_write_violation: bool = False
    # A statement looked at the view for a missing executed definition, or
    # with a view the executed definition does not define, so whether it read
    # or wrote the view is unknown.
    has_unknown_use: bool = False


class ViewUseTracker:
    """Records each read and write of an operation's views, and reports the ones Single Assignment does not allow.

    Is mutable and not thread-safe.
    """

    _operation_name_type: name_types.NameType
    _uses: dict[str, _ViewUse]

    def __init__(self, operation_name_type: name_types.NameType):
        """Initialize with the name type of the operation whose views are tracked."""
        self._operation_name_type = operation_name_type
        self._uses = {}

    def add_view(self, view: ast.InterfaceViewDefinition | ast.LocalViewDefinition):
        """Start tracking a view that the operation defines."""
        self._uses[view.typed_name.source_typed_name] = _ViewUse(definition=view)

    def mark_unknown_use(self, looking_at: ast.LocalTypedNameReference):
        """Record that a statement looks at the view without a known read or write."""
        use = self._uses.get(looking_at.source_typed_name)
        # Structural validation reports undefined views.
        if use is not None:
            use.has_unknown_use = True

    def record_use(
        self,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        looking_at: ast.LocalTypedNameReference,
        executed_view: ast.ViewDefinition | None,
        operation_name: str,
    ) -> list[diagnostics.Diagnostic]:
        """Record whether the executed view reads or writes the looked-at view, and return a diagnostic for each use Single Assignment does not allow."""
        use = self._uses[looking_at.source_typed_name]
        # An undefined view of the executed operation is reported when the
        # arguments are validated.
        if executed_view is None:
            use.has_unknown_use = True
            return []
        if isinstance(use.definition, ast.LocalViewDefinition):
            return _record_local_view_use(
                use, argument, looking_at, executed_view, operation_name
            )
        return _record_interface_view_use(
            use, use.definition, argument, looking_at, executed_view, operation_name
        )

    def fulfill_every_interface_view_direction(self, location: ast.SourceLocation):
        """Record a statement at `location` that reads every input view and writes every output view of the operation."""
        for use in self._uses.values():
            view = use.definition
            if isinstance(view, ast.LocalViewDefinition):
                continue
            if view.is_input:
                use.is_read = True
            if view.is_output and use.first_write is None:
                use.first_write = location

    def check_operation_end(self) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each view that the whole operation leaves unread or unwritten."""
        end_diagnostics: list[diagnostics.Diagnostic] = []
        for use in self._uses.values():
            if use.has_unknown_use or use.has_reported_read_or_write_violation:
                continue
            # Structural validation reports views that are never referenced.
            if not use.is_read and use.first_write is None:
                continue
            view = use.definition
            view_name = view.typed_name.source_typed_name
            if isinstance(view, ast.LocalViewDefinition):
                if not use.is_read:
                    end_diagnostics.append(
                        diagnostics.UnreadLocalViewDiagnostic(
                            location=view.typed_name.location, view_name=view_name
                        )
                    )
                continue
            if view.is_input and not use.is_read:
                end_diagnostics.append(
                    diagnostics.UnreadInputViewDiagnostic(
                        location=view.typed_name.location,
                        view_name=view_name,
                        operation_name_type=self._operation_name_type,
                    )
                )
            if view.is_output and use.first_write is None:
                end_diagnostics.append(
                    diagnostics.UnwrittenOutputViewDiagnostic(
                        location=view.typed_name.location,
                        view_name=view_name,
                        operation_name_type=self._operation_name_type,
                    )
                )
        return end_diagnostics


def _record_interface_view_use(
    use: _ViewUse,
    view: ast.InterfaceViewDefinition,
    argument: ast.OperationArgumentStatement[ast.LookedAt],
    looking_at: ast.LocalTypedNameReference,
    executed_view: ast.ViewDefinition,
    operation_name: str,
) -> list[diagnostics.Diagnostic]:
    use_diagnostics: list[diagnostics.Diagnostic] = []
    if executed_view.is_input:
        use.is_read = True
        # A statement whose use of the view is unknown may have written it.
        if not view.is_input and use.first_write is None and not use.has_unknown_use:
            use.has_reported_read_or_write_violation = True
            use_diagnostics.append(
                diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                )
            )
    if executed_view.is_output:
        if use.first_write is None:
            use.first_write = looking_at.location
        if not view.is_output:
            use.has_reported_read_or_write_violation = True
            use_diagnostics.append(
                diagnostics.WriteToInputOnlyViewDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                )
            )
    return use_diagnostics


def _record_local_view_use(
    use: _ViewUse,
    argument: ast.OperationArgumentStatement[ast.LookedAt],
    looking_at: ast.LocalTypedNameReference,
    executed_view: ast.ViewDefinition,
    operation_name: str,
) -> list[diagnostics.Diagnostic]:
    # A statement whose use of the view is unknown may have written it, so
    # neither a later read nor a later write is known to be a mistake.
    if use.has_unknown_use:
        return []
    use_diagnostics: list[diagnostics.Diagnostic] = []
    view_name = looking_at.source_typed_name
    if executed_view.is_input:
        use.is_read = True
        if use.first_write is None:
            use.has_reported_read_or_write_violation = True
            use_diagnostics.append(
                diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
                    location=looking_at.location,
                    looked_at_name=view_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                )
            )
    if not executed_view.is_output:
        return use_diagnostics
    if use.first_write is None:
        use.first_write = looking_at.location
        return use_diagnostics
    use.has_reported_read_or_write_violation = True
    use_diagnostics.append(
        diagnostics.LocalViewWrittenTwiceDiagnostic(
            location=looking_at.location,
            looked_at_name=view_name,
            view_name=argument.view.source_typed_name,
            operation_name=operation_name,
            first_write=use.first_write,
        )
    )
    return use_diagnostics
