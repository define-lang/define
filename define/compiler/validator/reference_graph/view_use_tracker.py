"""Track how an operation's statements read and write its views, and report the reads and writes that Define does not allow."""

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

    def record_use(
        self,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        looking_at: ast.LocalTypedNameReference,
        executed_view: ast.ViewDefinition,
        operation_name: str,
    ) -> list[diagnostics.Diagnostic]:
        """Record whether `executed_view` reads or writes the view, which `looking_at` looks at, and return a diagnostic for each use Single Assignment does not allow."""
        view = self.definition
        if isinstance(view, ast.LocalViewDefinition):
            return self._record_local_view_use(
                argument, looking_at, executed_view, operation_name
            )
        return self._record_interface_view_use(
            view, argument, looking_at, executed_view, operation_name
        )

    def _record_interface_view_use(
        self,
        view: ast.InterfaceViewDefinition,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        looking_at: ast.LocalTypedNameReference,
        executed_view: ast.ViewDefinition,
        operation_name: str,
    ) -> list[diagnostics.Diagnostic]:
        use_diagnostics: list[diagnostics.Diagnostic] = []
        if executed_view.is_input:
            self.is_read = True
            # A statement whose use of the view is unknown may have written it.
            if (
                not view.is_input
                and self.first_write is None
                and not self.has_unknown_use
            ):
                self.has_reported_read_or_write_violation = True
                use_diagnostics.append(
                    diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
                        location=looking_at.location,
                        looked_at_name=looking_at.source_typed_name,
                        view_name=argument.view.source_typed_name,
                        operation_name=operation_name,
                    )
                )
            if view.is_input and self.first_write is not None:
                self.has_reported_read_or_write_violation = True
                use_diagnostics.append(
                    diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
                        location=looking_at.location,
                        looked_at_name=looking_at.source_typed_name,
                        view_name=argument.view.source_typed_name,
                        operation_name=operation_name,
                        write=self.first_write,
                    )
                )
        if not executed_view.is_output:
            return use_diagnostics
        if not view.is_output:
            self.has_reported_read_or_write_violation = True
            use_diagnostics.append(
                diagnostics.WriteToInputOnlyViewDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                )
            )
            return use_diagnostics
        first_write = self._record_write(looking_at.location)
        if first_write is not None:
            use_diagnostics.append(
                diagnostics.InterfaceViewWrittenTwiceDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                    first_write=first_write,
                )
            )
        return use_diagnostics

    def _record_local_view_use(
        self,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        looking_at: ast.LocalTypedNameReference,
        executed_view: ast.ViewDefinition,
        operation_name: str,
    ) -> list[diagnostics.Diagnostic]:
        view_name = looking_at.source_typed_name
        use_diagnostics: list[diagnostics.Diagnostic] = []
        if executed_view.is_input:
            self.is_read = True
            # A statement whose use of the view is unknown may have written it.
            if self.first_write is None and not self.has_unknown_use:
                self.has_reported_read_or_write_violation = True
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
        first_write = self._record_write(looking_at.location)
        if first_write is not None:
            use_diagnostics.append(
                diagnostics.LocalViewWrittenTwiceDiagnostic(
                    location=looking_at.location,
                    looked_at_name=view_name,
                    view_name=argument.view.source_typed_name,
                    operation_name=operation_name,
                    first_write=first_write,
                )
            )
        return use_diagnostics

    def record_view_setting_read(
        self, source: ast.LocalTypedNameReference
    ) -> list[diagnostics.Diagnostic]:
        """Record that a View Setting Statement reads the view as `source`, and return a diagnostic if Single Assignment does not allow it."""
        self.is_read = True
        view = self.definition
        # A statement whose use of the view is unknown may have written it.
        is_unwritten = self.first_write is None and not self.has_unknown_use
        if isinstance(view, ast.LocalViewDefinition):
            if not is_unwritten:
                return []
            self.has_reported_read_or_write_violation = True
            return [
                diagnostics.ViewSettingReadFromUnwrittenLocalViewDiagnostic(
                    location=source.location, view_name=source.source_typed_name
                )
            ]
        if not view.is_input and is_unwritten:
            self.has_reported_read_or_write_violation = True
            return [
                diagnostics.ViewSettingReadFromUnwrittenOutputViewDiagnostic(
                    location=source.location, view_name=source.source_typed_name
                )
            ]
        if view.is_input and self.first_write is not None:
            self.has_reported_read_or_write_violation = True
            return [
                diagnostics.ViewSettingReadFromWrittenReadWriteViewDiagnostic(
                    location=source.location,
                    view_name=source.source_typed_name,
                    write=self.first_write,
                )
            ]
        return []

    def record_view_setting_write(
        self, target: ast.LocalTypedNameReference
    ) -> list[diagnostics.Diagnostic]:
        """Record that a View Setting Statement writes the view as `target`, and return a diagnostic if Single Assignment does not allow it."""
        view = self.definition
        # Structural validation reports an input-only or output-only interface
        # view target, which also decides whether the view ends up unwritten.
        if isinstance(view, ast.InterfaceViewDefinition) and not (
            view.is_input and view.is_output
        ):
            self.has_reported_read_or_write_violation = True
            return []
        first_write = self._record_write(target.location)
        if first_write is None:
            return []
        if isinstance(view, ast.LocalViewDefinition):
            return [
                diagnostics.ViewSettingLocalViewWrittenTwiceDiagnostic(
                    location=target.location,
                    view_name=target.source_typed_name,
                    first_write=first_write,
                )
            ]
        return [
            diagnostics.ViewSettingInterfaceViewWrittenTwiceDiagnostic(
                location=target.location,
                view_name=target.source_typed_name,
                first_write=first_write,
            )
        ]

    def fulfill_interface_view_direction(
        self, location: ast.SourceLocation, operation_name_type: name_types.NameType
    ) -> list[diagnostics.Diagnostic]:
        """Record a statement at `location` that reads the view if it is an input interface view and writes it if it is an output interface view, and return a diagnostic if an earlier statement already wrote it."""
        view = self.definition
        if isinstance(view, ast.LocalViewDefinition):
            return []
        # The statement reads a read/write view before it writes it, so a
        # read/write view written earlier is reported only as written twice.
        if view.is_input:
            self.is_read = True
        if not view.is_output:
            return []
        first_write = self._record_write(location)
        if first_write is None:
            return []
        return [
            diagnostics.InterfaceViewWrittenTwiceByAllViewsStatementDiagnostic(
                location=location,
                view_name=view.typed_name.source_typed_name,
                operation_name_type=operation_name_type,
                first_write=first_write,
            )
        ]

    def check_operation_end(
        self, operation_name_type: name_types.NameType
    ) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic if the whole operation, of `operation_name_type`, leaves the view unread or unwritten."""
        if self.has_unknown_use or self.has_reported_read_or_write_violation:
            return []
        # Structural validation reports views that are never referenced.
        if not self.is_read and self.first_write is None:
            return []
        view = self.definition
        view_name = view.typed_name.source_typed_name
        if isinstance(view, ast.LocalViewDefinition):
            if self.is_read:
                return []
            return [
                diagnostics.UnreadLocalViewDiagnostic(
                    location=view.typed_name.location, view_name=view_name
                )
            ]
        end_diagnostics: list[diagnostics.Diagnostic] = []
        if view.is_input and not self.is_read:
            end_diagnostics.append(
                diagnostics.UnreadInputViewDiagnostic(
                    location=view.typed_name.location,
                    view_name=view_name,
                    operation_name_type=operation_name_type,
                )
            )
        if view.is_output and self.first_write is None:
            end_diagnostics.append(
                diagnostics.UnwrittenOutputViewDiagnostic(
                    location=view.typed_name.location,
                    view_name=view_name,
                    operation_name_type=operation_name_type,
                )
            )
        return end_diagnostics

    def _record_write(self, location: ast.SourceLocation) -> ast.SourceLocation | None:
        """Record a write of the view at `location`, and return where an earlier statement first wrote it, if one did."""
        first_write = self.first_write
        if first_write is None:
            self.first_write = location
            return None
        self.has_reported_read_or_write_violation = True
        return first_write


class _ExecutionViewUses(msgspec.Struct):
    """The views of the operation that one execution statement reads and writes."""

    read: set[str] = msgspec.field(default_factory=set)
    written: set[str] = msgspec.field(default_factory=set)
    # The statement executes a missing definition, or passes a view to a view
    # the executed definition does not define, so what it reads and writes is
    # not fully known.
    has_unknown_use: bool = False


class ViewUseTracker:
    """Records each read and write of an operation's views, and reports the ones that Single Assignment and the View Setting Statement restrictions do not allow.

    Is mutable and not thread-safe.
    """

    _operation_name_type: name_types.NameType
    _uses: dict[str, _ViewUse]
    # The views that the last execution statement read and wrote.
    _last_execution: _ExecutionViewUses
    # The last statement other than a View Setting Statement is an execution
    # statement. A View Setting Statement whose target is a read/write
    # interface view must come after one.
    _is_after_execution: bool

    def __init__(self, operation_name_type: name_types.NameType):
        """Initialize with the name type of the operation whose views are tracked."""
        self._operation_name_type = operation_name_type
        self._uses = {}
        self._last_execution = _ExecutionViewUses()
        self._is_after_execution = False

    def start_statement(self, statement: ast.OperationStatement):
        """Record that the operation's next statement is `statement`."""
        if isinstance(statement, ast.ViewSettingStatement):
            return
        self._is_after_execution = isinstance(
            statement,
            ast.OperationExecutionStatement | ast.LogicalOperationExecutionStatement,
        )
        if self._is_after_execution:
            self._last_execution = _ExecutionViewUses()

    def add_view(self, view: ast.InterfaceViewDefinition | ast.LocalViewDefinition):
        """Start tracking a view that the operation defines."""
        self._uses[view.typed_name.source_typed_name] = _ViewUse(definition=view)

    def mark_unknown_use(self, looking_at: ast.LocalTypedNameReference):
        """Record that a statement looks at the view without a known read or write."""
        self._last_execution.has_unknown_use = True
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
        view_name = looking_at.source_typed_name
        use = self._uses[view_name]
        # An undefined view of the executed operation is reported when the
        # arguments are validated, and executing an operation that has a
        # read/write interface view is reported for the whole statement.
        if executed_view is None or (
            executed_view.is_input and executed_view.is_output
        ):
            use.has_unknown_use = True
            self._last_execution.has_unknown_use = True
            return []
        if executed_view.is_input:
            self._last_execution.read.add(view_name)
        if executed_view.is_output:
            self._last_execution.written.add(view_name)
        return use.record_use(argument, looking_at, executed_view, operation_name)

    def record_view_setting(
        self, statement: ast.ViewSettingStatement
    ) -> list[diagnostics.Diagnostic]:
        """Record that a View Setting Statement reads its source and writes its target, and return a diagnostic for each use that Single Assignment or the View Setting Statement restrictions do not allow."""
        source_use = self._uses.get(statement.source.source_typed_name)
        target_use = self._uses.get(statement.target.source_typed_name)
        # Structural validation reports a View Setting Statement whose source
        # and target are the same view.
        if source_use is not None and source_use is target_use:
            return []
        setting_diagnostics: list[diagnostics.Diagnostic] = []
        # Structural validation reports undefined views.
        if source_use is not None:
            setting_diagnostics.extend(
                source_use.record_view_setting_read(statement.source)
            )
        if target_use is None:
            return setting_diagnostics
        setting_diagnostics.extend(
            target_use.record_view_setting_write(statement.target)
        )
        target_view = target_use.definition
        if not (
            isinstance(target_view, ast.InterfaceViewDefinition)
            and target_view.is_input
            and target_view.is_output
        ):
            return setting_diagnostics
        # Structural validation reports a source that is undefined or is not a
        # local view.
        if source_use is None or not isinstance(
            source_use.definition, ast.LocalViewDefinition
        ):
            return setting_diagnostics
        target = statement.target
        source = statement.source
        if not self._is_after_execution:
            setting_diagnostics.append(
                diagnostics.ViewSettingReadWriteTargetWithoutExecutionDiagnostic(
                    location=target.location, target_name=target.source_typed_name
                )
            )
            return setting_diagnostics
        execution = self._last_execution
        if execution.has_unknown_use or (
            target.source_typed_name in execution.read
            and source.source_typed_name in execution.written
        ):
            return setting_diagnostics
        setting_diagnostics.append(
            diagnostics.ViewSettingReadWriteTargetNotFromExecutionDiagnostic(
                location=target.location,
                target_name=target.source_typed_name,
                source_name=source.source_typed_name,
            )
        )
        return setting_diagnostics

    def fulfill_every_interface_view_direction(
        self, location: ast.SourceLocation
    ) -> list[diagnostics.Diagnostic]:
        """Record a statement at `location` that reads every input view and writes every output view of the operation, and return a diagnostic for each output view that an earlier statement already wrote."""
        write_diagnostics: list[diagnostics.Diagnostic] = []
        for use in self._uses.values():
            write_diagnostics.extend(
                use.fulfill_interface_view_direction(
                    location, self._operation_name_type
                )
            )
        return write_diagnostics

    def check_operation_end(self) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each view that the whole operation leaves unread or unwritten."""
        end_diagnostics: list[diagnostics.Diagnostic] = []
        for use in self._uses.values():
            end_diagnostics.extend(use.check_operation_end(self._operation_name_type))
        return end_diagnostics
