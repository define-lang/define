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

    def branch_only_raises(self, branch: UncoveredBranch) -> bool:
        """Return whether a branch leads only to a raise statement."""
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


def analyze_report(
    report_path: Path,
    source_root: Path,
    source_paths: Sequence[Path] = (),
) -> tuple[list[UncoveredBranch], list[UncoveredBranch]]:
    """Separate actionable uncovered branches from exception-only branches."""
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
    exception_only: list[UncoveredBranch] = []
    for branch in uncovered:
        if selected_source_files or selected_source_directories:
            branch_source_path = source_analysis.resolve_path(branch.source_file)
            if (
                branch_source_path not in selected_source_files
                and selected_source_directories.isdisjoint(branch_source_path.parents)
            ):
                continue
        if source_analysis.branch_only_raises(branch):
            exception_only.append(branch)
        else:
            actionable.append(branch)
    return actionable, exception_only


def format_report(
    actionable: Sequence[UncoveredBranch],
    exception_only: Sequence[UncoveredBranch],
    source_root: Path,
) -> str:
    """Format uncovered branches with their source and destination lines."""
    source_analysis = SourceAnalysis(source_root)
    output_lines: list[str] = []
    for branch in actionable:
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

    if not actionable:
        output_lines.append("No uncovered non-exception branches.")
    output_lines.append(
        f"{len(actionable)} uncovered branches reported; "
        + f"{len(exception_only)} exception-only branches omitted."
    )
    return "\n".join(output_lines)


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
    actionable, exception_only = analyze_report(report_path, source_root, source_paths)
    click.echo(format_report(actionable, exception_only, source_root))


if __name__ == "__main__":
    main()
