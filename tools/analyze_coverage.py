"""Report uncovered LCOV branches that do not only raise an exception.

The coverage of Rust code has code regions instead of branches, which it
reports apart from the branches.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click
import msgspec

if TYPE_CHECKING:
    from collections.abc import Sequence

_JUMP_DESCRIPTION = re.compile(r"jump to line (?P<line>\d+)")
# How //tools/rust_coverage:collect_extension_coverage describes the code
# region of each of its branch records.
_RUST_REGION_DESCRIPTION = re.compile(
    r"region from (?P<start_line>\d+):(?P<start_column>\d+)"
    + r" to (?P<end_line>\d+):(?P<end_column>\d+)"
)
# Macros that end a Rust program, which a region consisting only of one of
# them calls only for a defensive check.
_RUST_PANIC_MACROS = ("panic!(", "todo!(", "unimplemented!(", "unreachable!(")
_COVERAGE_REPORT = Path("bazel-out/_coverage/_coverage_report.dat")
_RUNFILES_WORKSPACE = Path(__file__).resolve().parent.parent


class UncoveredBranch(msgspec.Struct, frozen=True):
    """An uncovered branch from an LCOV report."""

    source_file: Path
    source_line: int
    description: str
    target_line: int | None


def parse_uncovered_branches(report_path: Path) -> list[UncoveredBranch]:
    """Parse uncovered branch records from an LCOV report."""
    branches: list[UncoveredBranch] = []
    source_file: Path | None = None

    for report_line in report_path.read_text(encoding="utf-8").splitlines():
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


class UncoveredRegion(msgspec.Struct, frozen=True):
    """A code region of a Rust source file that never ran.

    Lines and columns are 1-based, columns count bytes, and the end column is
    the column after the region.
    """

    source_file: Path
    start_line: int
    start_column: int
    end_line: int
    end_column: int


def _rust_region(branch: UncoveredBranch) -> UncoveredRegion | None:
    """Return the code region that a branch record of Rust coverage stands for."""
    match = _RUST_REGION_DESCRIPTION.fullmatch(branch.description)
    if match is None:
        return None
    return UncoveredRegion(
        source_file=branch.source_file,
        start_line=int(match.group("start_line")),
        start_column=int(match.group("start_column")),
        end_line=int(match.group("end_line")),
        end_column=int(match.group("end_column")),
    )


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

    def region_text(self, region: UncoveredRegion) -> str:
        """Return the source text of a code region, with its lines joined by spaces."""
        lines = self._lines(region.source_file)[region.start_line - 1 : region.end_line]
        encoded = [line.encode() for line in lines]
        encoded[-1] = encoded[-1][: region.end_column - 1]
        encoded[0] = encoded[0][region.start_column - 1 :]
        return " ".join(line.decode(errors="replace").strip() for line in encoded)

    def region_only_panics(self, region: UncoveredRegion) -> bool:
        """Return whether a code region only calls a macro that ends the program."""
        text = self.region_text(region).strip("{}; ")
        return text.startswith(_RUST_PANIC_MACROS)

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
            elif isinstance(node, ast.Expr) and _expression_is_assert_never(
                node, branch.target_line
            ):
                return True
            elif isinstance(node, ast.If) and node.lineno == branch.source_line:
                if _suite_only_exits_pytest(
                    node.body, branch.target_line
                ) or _suite_only_exits_pytest(node.orelse, branch.target_line):
                    return True
            elif isinstance(node, ast.match_case):
                if _case_is_final_raise(node, branch.target_line):
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


def _expression_is_assert_never(expression: ast.Expr, target_line: int) -> bool:
    return expression.lineno <= target_line <= cast(
        "int", expression.end_lineno
    ) and _expression_calls(expression, "typing", "assert_never")


def _case_is_final_raise(case: ast.match_case, target_line: int) -> bool:
    pattern = case.pattern
    if not isinstance(pattern, ast.MatchAs):
        return False
    if (
        pattern.pattern is not None
        or pattern.name is not None
        or case.guard is not None
    ):
        return False
    if len(case.body) != 1 or not isinstance(case.body[0], ast.Raise):
        return False
    return pattern.lineno <= target_line <= pattern.end_lineno


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
    selection = _SourceSelection(source_analysis, source_paths)
    actionable: list[UncoveredBranch] = []
    low_value: list[UncoveredBranch] = []
    explicit_exit_only: list[UncoveredBranch] = []
    for branch in uncovered:
        if _rust_region(branch) is not None or not selection.includes(
            branch.source_file
        ):
            continue
        if source_analysis.branch_is_explicit_exit(branch):
            explicit_exit_only.append(branch)
        elif source_analysis.branch_is_final_case_nonmatch(branch):
            low_value.append(branch)
        else:
            actionable.append(branch)
    return actionable, low_value, explicit_exit_only


def analyze_rust_regions(
    report_path: Path,
    source_root: Path,
    source_paths: Sequence[Path] = (),
) -> tuple[list[UncoveredRegion], list[UncoveredRegion]]:
    """Classify uncovered Rust code regions as actionable or panic-only."""
    source_analysis = SourceAnalysis(source_root)
    selection = _SourceSelection(source_analysis, source_paths)
    actionable: list[UncoveredRegion] = []
    panic_only: list[UncoveredRegion] = []
    for branch in parse_uncovered_branches(report_path):
        region = _rust_region(branch)
        if region is None or not selection.includes(region.source_file):
            continue
        if source_analysis.region_only_panics(region):
            panic_only.append(region)
        else:
            actionable.append(region)
    return actionable, panic_only


class _SourceSelection:
    """The source files that command-line paths select."""

    def __init__(self, source_analysis: SourceAnalysis, source_paths: Sequence[Path]):
        """Select the files and directories in `source_paths`, or every file if it is empty."""
        self._source_analysis: SourceAnalysis = source_analysis
        self._files: set[Path] = set()
        self._directories: set[Path] = set()
        for source_path in source_paths:
            resolved_path = source_analysis.resolve_path(source_path)
            if resolved_path.is_dir():
                self._directories.add(resolved_path)
            else:
                self._files.add(resolved_path)

    def includes(self, source_file: Path) -> bool:
        """Return whether the selection includes `source_file`."""
        if not self._files and not self._directories:
            return True
        resolved_path = self._source_analysis.resolve_path(source_file)
        return resolved_path in self._files or not self._directories.isdisjoint(
            resolved_path.parents
        )


def format_rust_regions(
    actionable: Sequence[UncoveredRegion],
    panic_only: Sequence[UncoveredRegion],
    source_root: Path,
) -> str:
    """Format uncovered Rust code regions with their source text."""
    source_analysis = SourceAnalysis(source_root)
    output_lines = ["Uncovered Rust code regions:"]
    for region in actionable:
        output_lines.append(
            f"{region.source_file}:{region.start_line}:{region.start_column}-"
            + f"{region.end_line}:{region.end_column}: "
            + source_analysis.region_text(region)
        )
    output_lines.append(
        f"{len(actionable)} uncovered Rust code regions reported; "
        + f"{len(panic_only)} panic-only regions omitted."
    )
    return "\n".join(output_lines)


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
        output_lines.extend(
            (
                f"{branch.source_file}:{branch.source_line}:",
                f"  branch source: {origin}",
            )
        )
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
    destination only raises a Python exception are omitted. Rust coverage has
    code regions instead of branches, which are reported first, apart from
    regions that only panic.
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
    actionable_regions, panic_only_regions = analyze_rust_regions(
        report_path, source_root, source_paths
    )
    if actionable_regions or panic_only_regions:
        click.echo(
            format_rust_regions(actionable_regions, panic_only_regions, source_root)
        )
    actionable, low_value, explicit_exit_only = analyze_report(
        report_path, source_root, source_paths
    )
    click.echo(format_report(actionable, low_value, explicit_exit_only, source_root))


if __name__ == "__main__":
    main()
