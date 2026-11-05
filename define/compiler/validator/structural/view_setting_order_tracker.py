"""Track the View Setting Statement rules that depend on the statements before and after each one."""

from __future__ import annotations

from define.compiler import ast
from define.compiler.errors import diagnostics


class ViewSettingOrderTracker:
    """Records an operation's View Setting Statements in order, and reports the ones that the statements around them do not allow.

    Is mutable and not thread-safe.
    """

    # The line of the first View Setting Statement that targets each view.
    _target_lines: dict[str, int]
    # The View Setting Statements that set a local view since the last
    # statement that is not a View Setting Statement. The next statement that
    # is not a View Setting Statement must look at each one's source and
    # target.
    _pending_view_setting_statements: list[ast.ViewSettingStatement]

    def __init__(self):
        """Initialize with no View Setting Statements recorded."""
        self._target_lines = {}
        self._pending_view_setting_statements = []

    def check_source(
        self, source: ast.LocalTypedNameReference
    ) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic if an earlier View Setting Statement targets `source`, the source of a View Setting Statement."""
        target_line = self._target_lines.get(source.full_typed_name)
        if target_line is None:
            return []
        return [
            diagnostics.ViewSettingSourceWasTargetDiagnostic(
                location=source.location,
                view_name=source.source_typed_name,
                target_line=target_line,
            )
        ]

    def record_target(self, target: ast.LocalTypedNameReference):
        """Record `target`, the target of a View Setting Statement, so later View Setting Statements may not use it as their source."""
        # A view that two View Setting Statements target is written twice,
        # which Single Assignment reports.
        _ = self._target_lines.setdefault(target.full_typed_name, target.location.line)

    def require_execution_after(self, view_setting_statement: ast.ViewSettingStatement):
        """Require the next statement that is not a View Setting Statement to be an execution statement that looks at the source and target of `view_setting_statement`."""
        self._pending_view_setting_statements.append(view_setting_statement)

    def check_next_statement(
        self, statement: ast.OperationStatement
    ) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each View Setting Statement whose requirement `statement`, which is not a View Setting Statement, does not meet."""
        if not self._pending_view_setting_statements:
            return []
        if not isinstance(
            statement,
            ast.OperationExecutionStatement | ast.LogicalOperationExecutionStatement,
        ):
            return self._report_without_execution()
        looked_at: set[str] = set()
        for argument in statement.arguments:
            if isinstance(argument.looking_at, ast.LocalTypedNameReference):
                looked_at.add(argument.looking_at.full_typed_name)
        not_looked_at_diagnostics: list[diagnostics.Diagnostic] = []
        for view_setting_statement in self._pending_view_setting_statements:
            target = view_setting_statement.target
            source = view_setting_statement.source
            if (
                target.full_typed_name in looked_at
                and source.full_typed_name in looked_at
            ):
                continue
            not_looked_at_diagnostics.append(
                diagnostics.ViewSettingLocalTargetNotLookedAtDiagnostic(
                    location=target.location,
                    target_name=target.source_typed_name,
                    source_name=source.source_typed_name,
                )
            )
        self._pending_view_setting_statements.clear()
        return not_looked_at_diagnostics

    def check_operation_end(self) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each View Setting Statement that ends the Operation Statements Block without the execution statement it requires."""
        return self._report_without_execution()

    def _report_without_execution(self) -> list[diagnostics.Diagnostic]:
        without_execution_diagnostics: list[diagnostics.Diagnostic] = []
        for view_setting_statement in self._pending_view_setting_statements:
            target = view_setting_statement.target
            without_execution_diagnostics.append(
                diagnostics.ViewSettingLocalTargetWithoutExecutionDiagnostic(
                    location=target.location, target_name=target.source_typed_name
                )
            )
        self._pending_view_setting_statements.clear()
        return without_execution_diagnostics
