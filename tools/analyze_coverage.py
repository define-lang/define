"""Report uncovered LCOV branches that do not only raise an exception."""

import ast
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import click

_JUMP_DESCRIPTION = re.compile(r"jump to line (?P<line>\d+)")
_COVERAGE_REPORT = Path("bazel-out/_coverage/_coverage_report.dat")
_RUNFILES_WORKSPACE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class UncoveredBranch:
    """An uncovered branch from an LCOV report."""

    source_file: Path
    source_line: int
    description: str
    target_line: int | None


def parse_uncovered_branches(report_path: Path) -> list[UncoveredBranch]:
    """Parse uncovered branch records from an LCOV report."""
    branches: list[UncoveredBranch] = []
    source_file: Path | None = None

    for report_line in report_path.read_text().splitlines():
        if report_line.startswith("SF:"):
            source_file = Path(report_line.removeprefix("SF:"))
            continue
        if not report_line.startswith("BRDA:"):
            continue
        if source_file is None:
            raise ValueError("BRDA record appeared before an SF record")

        branch_data = report_line.removeprefix("BRDA:")
        source_line_text, _block, remainder = branch_data.split(",", maxsplit=2)
        description, taken_text = remainder.rsplit(",", maxsplit=1)
        if taken_text not in {"-", "0"}:
            continue

        target_match = _JUMP_DESCRIPTION.fullmatch(description)
        target_line = int(target_match.group("line")) if target_match else None
        branches.append(
            UncoveredBranch(
                source_file=source_file,
                source_line=int(source_line_text),
                description=description,
                target_line=target_line,
            )
        )

    return branches


class SourceAnalysis:
    """Source text and syntax needed to describe and classify branches."""

    def __init__(self, source_root: Path):
        """Initialize analysis relative to the given source directory."""
        self._source_root: Path = source_root
        self._lines_by_path: dict[Path, list[str]] = {}
        self._trees_by_path: dict[Path, ast.AST] = {}

    def _path(self, source_file: Path) -> Path:
        if source_file.is_absolute():
            return source_file
        return self._source_root / source_file

    def _lines(self, source_file: Path) -> list[str]:
        source_path = self._path(source_file)
        lines = self._lines_by_path.get(source_path)
        if lines is None:
            lines = source_path.read_text().splitlines()
            self._lines_by_path[source_path] = lines
        return lines

    def line(self, source_file: Path, line_number: int) -> str:
        """Return one stripped source line."""
        return self._lines(source_file)[line_number - 1].strip()

    def resolve_path(self, source_file: Path) -> Path:
        """Resolve an LCOV or command-line source path."""
        return self._path(source_file).resolve()

    def branch_outcome(self, branch: UncoveredBranch) -> str | None:
        """Describe the source-level outcome that leads to an uncovered edge."""
        if branch.source_file.suffix != ".py":
            return None

        source_path = self._path(branch.source_file)
        tree = self._trees_by_path.get(source_path)
        if tree is None:
            tree = ast.parse(source_path.read_text(), filename=str(source_path))
            self._trees_by_path[source_path] = tree

        for node in ast.walk(tree):
            if isinstance(node, ast.If) and node.lineno == branch.source_line:
                if branch.target_line is not None and _line_is_in_statements(
                    branch.target_line, node.body
                ):
                    return "condition is true"
                return "condition is false"
            if isinstance(node, ast.match_case):
                pattern = node.pattern
                if pattern.lineno != branch.source_line or node.guard is not None:
                    continue
                if branch.target_line is not None and _line_is_in_statements(
                    branch.target_line, node.body
                ):
                    return "pattern matches"
                return "pattern does not match"
        return None

    def branch_is_explicit_exit(self, branch: UncoveredBranch) -> bool:
        """Return whether a branch leads only to an explicit exit."""
        if branch.target_line is None or branch.source_file.suffix != ".py":
            return False

        source_path = self._path(branch.source_file)
        tree = self._trees_by_path.get(source_path)
        if tree is None:
            tree = ast.parse(source_path.read_text(), filename=str(source_path))
            self._trees_by_path[source_path] = tree

        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                end_line = cast("int", node.end_lineno)
                if node.lineno <= branch.target_line <= end_line:
                    return True
            elif (
                isinstance(node, ast.Expr)
                and node.lineno <= branch.target_line <= cast("int", node.end_lineno)
                and _expression_calls(node, "typing", "assert_never")
            ) or (
                isinstance(node, ast.If)
                and node.lineno == branch.source_line
                and (
                    _suite_only_exits_pytest(node.body, branch.target_line)
                    or _suite_only_exits_pytest(node.orelse, branch.target_line)
                )
            ):
                return True
            elif isinstance(node, ast.match_case):
                pattern = node.pattern
                if (
                    isinstance(pattern, ast.MatchAs)
                    and pattern.pattern is None
                    and pattern.name is None
                    and node.guard is None
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Raise)
                    and pattern.lineno <= branch.target_line <= pattern.end_lineno
                ):
                    return True
        return False

    def branch_is_final_case_nonmatch(self, branch: UncoveredBranch) -> bool:
        """Return whether a branch is the non-match edge of an unguarded final case."""
        if branch.source_file.suffix != ".py":
            return False

        source_path = self._path(branch.source_file)
        tree = self._trees_by_path.get(source_path)
        if tree is None:
            tree = ast.parse(source_path.read_text(), filename=str(source_path))
            self._trees_by_path[source_path] = tree

        for node in ast.walk(tree):
            if not isinstance(node, ast.Match) or not node.cases:
                continue
            final_case = node.cases[-1]
            if (
                final_case.pattern.lineno == branch.source_line
                and final_case.guard is None
                and (
                    branch.target_line is None
                    or not _line_is_in_statements(branch.target_line, final_case.body)
                )
            ):
                return True
        return False


def _suite_only_exits_pytest(statements: Sequence[ast.stmt], target_line: int) -> bool:
    if len(statements) != 1 or not isinstance(statements[0], ast.Expr):
        return False
    expression = statements[0]
    return expression.lineno <= target_line <= cast("int", expression.end_lineno) and (
        _expression_calls(expression, "pytest", "fail")
        or _expression_calls(expression, "pytest", "skip")
    )


def _expression_calls(expression: ast.Expr, module: str, function: str) -> bool:
    call = expression.value
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == module
        and call.func.attr == function
    )


def analyze_report(
    report_path: Path,
    source_root: Path,
    source_paths: Sequence[Path] = (),
) -> tuple[list[UncoveredBranch], list[UncoveredBranch], list[UncoveredBranch]]:
    """Classify actionable, low-value, and explicit-exit-only branches."""
    source_analysis = SourceAnalysis(source_root)
    uncovered = parse_uncovered_branches(report_path)
    selected_source_files: set[Path] = set()
    selected_source_directories: set[Path] = set()
    for source_path in source_paths:
        resolved_path = source_analysis.resolve_path(source_path)
        if resolved_path.is_dir():
            selected_source_directories.add(resolved_path)
        else:
            selected_source_files.add(resolved_path)
    actionable: list[UncoveredBranch] = []
    low_value: list[UncoveredBranch] = []
    explicit_exit_only: list[UncoveredBranch] = []
    for branch in uncovered:
        if selected_source_files or selected_source_directories:
            branch_source_path = source_analysis.resolve_path(branch.source_file)
            if (
                branch_source_path not in selected_source_files
                and selected_source_directories.isdisjoint(branch_source_path.parents)
            ):
                continue
        if source_analysis.branch_is_explicit_exit(branch):
            explicit_exit_only.append(branch)
        elif source_analysis.branch_is_final_case_nonmatch(branch):
            low_value.append(branch)
        else:
            actionable.append(branch)
    return actionable, low_value, explicit_exit_only


def format_report(
    actionable: Sequence[UncoveredBranch],
    low_value: Sequence[UncoveredBranch],
    explicit_exit_only: Sequence[UncoveredBranch],
    source_root: Path,
) -> str:
    """Format uncovered branches with their source and destination lines."""
    source_analysis = SourceAnalysis(source_root)
    output_lines: list[str] = []
    _append_formatted_branches(output_lines, actionable, source_analysis)

    if low_value:
        output_lines.append("Low-value final-case non-match branches:")
        _append_formatted_branches(output_lines, low_value, source_analysis)

    if not actionable:
        output_lines.append("No uncovered actionable branches.")
    output_lines.append(
        f"{len(actionable)} actionable uncovered branches reported; "
        + f"{len(low_value)} low-value final-case non-match branches reported; "
        + f"{len(explicit_exit_only)} explicit-exit-only branches omitted."
    )
    return "\n".join(output_lines)


def _append_formatted_branches(
    output_lines: list[str],
    branches: Sequence[UncoveredBranch],
    source_analysis: SourceAnalysis,
):
    for branch in branches:
        origin = source_analysis.line(branch.source_file, branch.source_line)
        output_lines.append(f"{branch.source_file}:{branch.source_line}:")
        output_lines.append(f"  branch source: {origin}")
        if outcome := source_analysis.branch_outcome(branch):
            output_lines.append(f"  uncovered outcome: {outcome}")
        if branch.target_line is None:
            destination = branch.description
        else:
            target = source_analysis.line(branch.source_file, branch.target_line)
            destination = f"line {branch.target_line}: {target}"
        output_lines.append(f"  uncovered destination: {destination}")


def _line_is_in_statements(line: int, statements: Sequence[ast.stmt]) -> bool:
    return any(
        statement.lineno <= line <= cast("int", statement.end_lineno)
        for statement in statements
    )


def workspace_root() -> Path:
    """Return the workspace containing source files and Bazel's coverage report."""
    return Path(os.environ.get("BUILD_WORKSPACE_DIRECTORY", _RUNFILES_WORKSPACE))


@click.command(
    epilog=(
        "Examples:\n\n"
        "  analyze_coverage\n\n"
        "  analyze_coverage define/compiler/driver.py\n\n"
        "  analyze_coverage define/compiler define/runtime/literal.py"
    )
)
@click.argument(
    "source_paths",
    nargs=-1,
    type=click.Path(path_type=Path, file_okay=True, dir_okay=True),
)
def main(source_paths: tuple[Path, ...]):
    """Report uncovered branches, optionally limited to SOURCE_PATHS.

    SOURCE_PATHS are files or directories relative to the workspace root.
    Directories include source files at every depth. When no paths are given,
    all files in Bazel's combined LCOV report are analyzed. Branches whose
    destination only raises a Python exception are omitted.
    """
    if build_working_directory := os.environ.get("BUILD_WORKING_DIRECTORY"):
        os.chdir(build_working_directory)
    source_root = workspace_root()
    for source_path in source_paths:
        if not (source_root / source_path).exists():
            raise click.BadParameter(
                f"source path does not exist: {source_path}",
                param_hint="SOURCE_PATHS",
            )
    report_path = source_root / _COVERAGE_REPORT
    if not report_path.is_file():
        raise click.ClickException(
            "coverage report not found; run Bazel coverage with "
            + "--combined_report=lcov first"
        )
    actionable, low_value, explicit_exit_only = analyze_report(
        report_path, source_root, source_paths
    )
    click.echo(format_report(actionable, low_value, explicit_exit_only, source_root))


if __name__ == "__main__":
    main()
