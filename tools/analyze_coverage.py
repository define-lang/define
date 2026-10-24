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

from tools import runfiles, rust_source

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_JUMP_DESCRIPTION = re.compile(r"jump to line (?P<line>\d+)")
# How //tools/rust_coverage:collect_rust_coverage describes the code
# region of each of its branch records.
_RUST_REGION_DESCRIPTION = re.compile(
    r"region from (?P<start_line>\d+):(?P<start_column>\d+)"
    + r" to (?P<end_line>\d+):(?P<end_column>\d+)"
)
# Macros that end a Rust program, which a region consisting only of one of
# them calls only for a defensive check.
_RUST_PANIC_MACROS = ("panic!", "todo!", "unimplemented!", "unreachable!")
# A match arm that only passes on an exception that Python raised while the
# parser built the AST.
_RUST_PYTHON_EXCEPTION_ARM = re.compile(
    r"^\s*(?:Err\()?ParseError::Python\((?P<error>\w+)\)\)?\s*=>\s*"
    + r"(?:return\s+)?(?:Err\()?(?P=error)\)?,?\s*$"
)
# Coverage puts the code that this attribute generates, such as the methods of
# a complex enum's base class, on the attribute's line.
_RUST_PYCLASS_ATTRIBUTE = "#[pyclass"
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
            lines = source_path.read_text(encoding="utf-8").splitlines()
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

    def region_is_pyclass_attribute(self, region: UncoveredRegion) -> bool:
        """Return whether a code region is on the line of a `#[pyclass]` attribute."""
        line = self._lines(region.source_file)[region.start_line - 1]
        return line.lstrip().startswith(_RUST_PYCLASS_ATTRIBUTE)

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
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"), filename=str(source_path)
            )
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
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"), filename=str(source_path)
            )
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
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"), filename=str(source_path)
            )
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


class RustRegions(msgspec.Struct, frozen=True):
    """Uncovered Rust code regions, by whether covering them is worthwhile."""

    actionable: list[UncoveredRegion]
    pyclass_generated: list[UncoveredRegion]
    """Regions of code that a `#[pyclass]` attribute generates."""
    panic_only: list[UncoveredRegion]
    python_exception_only: list[UncoveredRegion]
    """Regions that only pass on or convert an exception that Python raised."""


def analyze_rust_regions(
    report_path: Path,
    source_root: Path,
    generated_sources: Mapping[Path, Path],
    source_paths: Sequence[Path] = (),
) -> RustRegions:
    """Classify uncovered Rust code regions.

    `generated_sources` maps the workspace path of each generated Rust source
    file to where the file is.
    """
    source_analysis = SourceAnalysis(source_root)
    python_exceptions = _RustPythonExceptions(source_root, generated_sources)
    selection = _SourceSelection(source_analysis, source_paths)
    regions = RustRegions(
        actionable=[],
        pyclass_generated=[],
        panic_only=[],
        python_exception_only=[],
    )
    for branch in parse_uncovered_branches(report_path):
        region = _rust_region(branch)
        if region is None or not selection.includes(region.source_file):
            continue
        if source_analysis.region_is_pyclass_attribute(region):
            regions.pyclass_generated.append(region)
        elif source_analysis.region_only_panics(region):
            regions.panic_only.append(region)
        elif python_exceptions.region_only_handles_python_exception(
            region, source_analysis.region_text(region)
        ):
            regions.python_exception_only.append(region)
        else:
            regions.actionable.append(region)
    return regions


class _RustPythonExceptions:
    """Which code in Rust source files only handles exceptions that Python raised."""

    def __init__(self, source_root: Path, generated_sources: Mapping[Path, Path]):
        """Read sources under `source_root`, and generated sources from `generated_sources`."""
        self._source_root: Path = source_root
        self._generated_sources: Mapping[Path, Path] = generated_sources
        self._sources: dict[Path, rust_source.RustSource] = {}
        self._crates: dict[Path, rust_source.RustCrate] = {}

    def region_only_handles_python_exception(
        self, region: UncoveredRegion, text: str
    ) -> bool:
        """Return whether `region`, whose source text is `text`, only passes on or converts an exception that Python raised."""
        if text == "?":
            return self._question_mark_only_passes_on_python_exception(region)
        source = self._source(region.source_file)
        function = source.declaring_function(
            source.offset(region.start_line, region.start_column)
        )
        if function is not None and function.parameter_types == ("PyErr",):
            return True
        return (
            region.start_line == region.end_line
            and _RUST_PYTHON_EXCEPTION_ARM.match(source.code_line(region.start_line))
            is not None
        )

    def _question_mark_only_passes_on_python_exception(
        self, region: UncoveredRegion
    ) -> bool:
        """Return whether the `?` that is `region` can only pass on an exception that Python raised."""
        source = self._source(region.source_file)
        offset = source.offset(region.start_line, region.start_column)
        function = source.enclosing_function(offset)
        callee = source.callee_before(offset)
        if function is None or callee is None:
            return False
        returns_python_result = self._crate(
            self._crate_directory(region.source_file.parent)
        ).returns_python_result(callee)
        if returns_python_result is not None:
            return returns_python_result
        # A function from outside the crate, such as a PyO3 method, can only
        # fail with a Python exception where its error becomes a `PyErr`.
        return function.returns_python_result

    def _source(self, source_file: Path) -> rust_source.RustSource:
        source = self._sources.get(source_file)
        if source is None:
            path = self._generated_sources.get(
                source_file, self._source_root / source_file
            )
            source = rust_source.RustSource(path.read_text(encoding="utf-8"))
            self._sources[source_file] = source
        return source

    def _crate_directory(self, directory: Path) -> Path:
        """Return the directory of the crate root's module, for a source file of the crate in `directory`."""
        # A module's submodules are in a directory named after it, beside its
        # file.
        while (self._source_root / directory.parent / f"{directory.name}.rs").exists():
            directory = directory.parent
        return directory

    def _module_files(self, directory: Path) -> set[Path]:
        """Return the Rust source files in `directory` and in the directories of their submodules."""
        source_files: set[Path] = set()
        for path in (self._source_root / directory).glob("*.rs"):
            source_file = path.relative_to(self._source_root)
            source_files.add(source_file)
            if path.with_suffix("").is_dir():
                source_files |= self._module_files(source_file.with_suffix(""))
        return source_files

    def _crate(self, directory: Path) -> rust_source.RustCrate:
        """Return the crate whose crate root's module is in `directory`."""
        crate = self._crates.get(directory)
        if crate is None:
            source_files = self._module_files(directory)
            for generated_source in self._generated_sources:
                if generated_source.parent == directory:
                    source_files.add(generated_source)
            crate = rust_source.RustCrate(
                self._source(source_file) for source_file in sorted(source_files)
            )
            self._crates[directory] = crate
        return crate


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


def format_rust_regions(regions: RustRegions, source_root: Path) -> str:
    """Format the actionable uncovered Rust code regions with their source text."""
    source_analysis = SourceAnalysis(source_root)
    output_lines = ["Uncovered Rust code regions:"]
    for region in regions.actionable:
        output_lines.append(
            f"{region.source_file.as_posix()}:{region.start_line}:{region.start_column}-"
            + f"{region.end_line}:{region.end_column}: "
            + source_analysis.region_text(region)
        )
    output_lines.append(
        f"{len(regions.actionable)} uncovered Rust code regions reported; "
        + f"{len(regions.pyclass_generated)} pyclass-generated regions omitted; "
        + f"{len(regions.panic_only)} panic-only regions omitted; "
        + f"{len(regions.python_exception_only)} Python-exception-only regions omitted."
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
                f"{branch.source_file.as_posix()}:{branch.source_line}:",
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
    regions that only panic, report source the parser does not support yet,
    or pass on an exception that Python raised.
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
    # Bazel gives the generated Rust sources as runfiles, since they are not in
    # the workspace.
    generated_sources: dict[Path, Path] = {}
    for location in os.environ["RUST_GENERATED_SOURCES"].split():
        workspace_path = Path(*Path(location).parts[1:])
        generated_sources[workspace_path] = runfiles.resolve(location)
    regions = analyze_rust_regions(
        report_path, source_root, generated_sources, source_paths
    )
    if (
        regions.actionable
        or regions.pyclass_generated
        or regions.panic_only
        or regions.python_exception_only
    ):
        click.echo(format_rust_regions(regions, source_root))
    actionable, low_value, explicit_exit_only = analyze_report(
        report_path, source_root, source_paths
    )
    click.echo(format_report(actionable, low_value, explicit_exit_only, source_root))


if __name__ == "__main__":
    main()
