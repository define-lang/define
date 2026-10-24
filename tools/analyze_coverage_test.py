from __future__ import annotations

import os
from pathlib import Path

import click.testing
import pytest

from tools import analyze_coverage


def test_analyze_report_omits_branch_that_only_raises(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: bool) -> bool:\n"
        + "    if value:\n"
        + '        raise ValueError("invalid value")\n'
        + "    return value\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "BRDA:2,0,jump to line 4,0\n"
        + "BRDA:2,0,return from function 'choose',1\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == [
        analyze_coverage.UncoveredBranch(
            source_file=Path("example.py"),
            source_line=2,
            description="jump to line 4",
            target_line=4,
        )
    ]
    assert low_value == []
    assert explicit_exit_only == [
        analyze_coverage.UncoveredBranch(
            source_file=Path("example.py"),
            source_line=2,
            description="jump to line 3",
            target_line=3,
        )
    ]


def test_analyze_report_omits_jump_into_multiline_raise(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        'def fail() -> None:\n    raise ValueError(\n        "invalid value"\n    )\n',
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:1,0,jump to line 3,-\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert len(explicit_exit_only) == 1


def test_analyze_report_omits_branch_that_only_calls_pytest_fail(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def check(success: bool):\n"
        + "    if not success:\n"
        + "        pytest.fail(\n"
        + '            "operation failed"\n'
        + "        )\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:2,0,jump to line 4,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert len(explicit_exit_only) == 1


def test_analyze_report_omits_branch_that_only_calls_pytest_skip(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def check(available: bool):\n"
        + "    if not available:\n"
        + '        pytest.skip("dependency unavailable")\n',
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:2,0,jump to line 3,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert len(explicit_exit_only) == 1


def test_analyze_report_keeps_branch_with_work_before_pytest_fail(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def check(success: bool):\n"
        + "    if not success:\n"
        + "        log_failure()\n"
        + '        pytest.fail("operation failed")\n',
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:2,0,jump to line 4,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert len(actionable) == 1
    assert low_value == []
    assert explicit_exit_only == []


def test_analyze_report_omits_wildcard_case_that_only_raises(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int) -> int:\n"
        + "    match value:\n"
        + "        case 1:\n"
        + "            return value\n"
        + "        case _:\n"
        + '            raise TypeError("unexpected value")\n',
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:3,0,jump to line 5,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert len(explicit_exit_only) == 1


@pytest.mark.parametrize(
    ("case_pattern", "case_body"),
    [
        ("_ if value > 0", 'raise TypeError("unexpected value")'),
        ("remaining", 'raise TypeError("unexpected value")'),
        ("_", "return value"),
    ],
)
def test_analyze_report_keeps_case_that_can_continue(
    tmp_path: Path, case_pattern: str, case_body: str
):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int) -> int:\n"
        + "    match value:\n"
        + "        case 1:\n"
        + "            return value\n"
        + f"        case {case_pattern}:\n"
        + f"            {case_body}\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:3,0,jump to line 5,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == [
        analyze_coverage.UncoveredBranch(
            source_file=Path("example.py"),
            source_line=3,
            description="jump to line 5",
            target_line=5,
        )
    ]
    assert low_value == []
    assert explicit_exit_only == []


def test_analyze_report_omits_branch_to_typing_assert_never(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int | str) -> int:\n"
        + "    match value:\n"
        + "        case int():\n"
        + "            return value\n"
        + "        case str():\n"
        + "            return len(value)\n"
        + "    typing.assert_never(value)\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:5,0,jump to line 7,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert len(explicit_exit_only) == 1


def test_analyze_report_separates_final_case_nonmatch(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int | str) -> int:\n"
        + "    match value:\n"
        + "        case int():\n"
        + "            return value\n"
        + "        case str():\n"
        + "            return len(value)\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\n"
        + "BRDA:3,0,jump to line 5,0\n"
        + "BRDA:5,0,return from function 'choose',0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert len(actionable) == 1
    assert len(low_value) == 1
    assert low_value[0].source_line == 5
    assert explicit_exit_only == []


def test_analyze_report_keeps_guarded_final_case_nonmatch(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int) -> int:\n"
        + "    match value:\n"
        + "        case int() if value > 0:\n"
        + "            return value\n"
        + "    return 0\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:3,0,jump to line 5,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert len(actionable) == 1
    assert low_value == []
    assert explicit_exit_only == []


def test_format_report_includes_branch_source_and_destination(tmp_path: Path):
    source_path = tmp_path / "example.go"
    _ = source_path.write_text(
        "if ready {\n\trun()\n}\n", encoding="utf-8", newline="\n"
    )
    branch = analyze_coverage.UncoveredBranch(
        source_file=Path("example.go"),
        source_line=1,
        description="jump to line 2",
        target_line=2,
    )

    report = analyze_coverage.format_report([branch], [], [], tmp_path)

    assert report == (
        "example.go:1:\n"
        "  branch source: if ready {\n"
        "  uncovered destination: line 2: run()\n"
        "1 actionable uncovered branches reported; "
        "0 low-value final-case non-match branches reported; "
        "0 explicit-exit-only branches omitted."
    )


def test_format_report_separates_low_value_branches(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "match value:\n    case int():\n        handle(value)\n",
        encoding="utf-8",
        newline="\n",
    )
    branch = analyze_coverage.UncoveredBranch(
        source_file=source_path,
        source_line=2,
        description="return from function 'choose'",
        target_line=None,
    )

    report = analyze_coverage.format_report([], [branch], [], tmp_path)

    assert report == (
        "Low-value final-case non-match branches:\n"
        + f"{source_path.as_posix()}:2:\n"
        + "  branch source: case int():\n"
        + "  uncovered outcome: pattern does not match\n"
        + "  uncovered destination: return from function 'choose'\n"
        + "No uncovered actionable branches.\n"
        + "0 actionable uncovered branches reported; "
        + "1 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted."
    )


def test_analyze_report_keeps_non_python_branch(tmp_path: Path):
    source_path = tmp_path / "example.go"
    _ = source_path.write_text(
        'panic("invalid value")\n', encoding="utf-8", newline="\n"
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\nBRDA:1,0,jump to line 1,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert len(actionable) == 1
    assert low_value == []
    assert explicit_exit_only == []


def test_format_report_describes_implicit_return_and_empty_result(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose() -> None:\n    return\n", encoding="utf-8", newline="\n"
    )
    branch = analyze_coverage.UncoveredBranch(
        source_file=source_path,
        source_line=1,
        description="return from function 'choose'",
        target_line=None,
    )

    report = analyze_coverage.format_report([branch], [], [], tmp_path)
    empty_report = analyze_coverage.format_report([], [], [branch], tmp_path)

    assert report == (
        f"{source_path.as_posix()}:1:\n"
        "  branch source: def choose() -> None:\n"
        "  uncovered destination: return from function 'choose'\n"
        "1 actionable uncovered branches reported; "
        "0 low-value final-case non-match branches reported; "
        "0 explicit-exit-only branches omitted."
    )
    assert empty_report == (
        "No uncovered actionable branches.\n"
        "0 actionable uncovered branches reported; "
        "0 low-value final-case non-match branches reported; "
        "1 explicit-exit-only branches omitted."
    )


@pytest.mark.parametrize(
    ("source_line", "target_line", "description", "expected_outcome"),
    [
        (2, 3, "jump to line 3", "condition is true"),
        (2, 4, "jump to line 4", "condition is false"),
        (5, 6, "jump to line 6", "pattern matches"),
        (5, None, "return from function 'choose'", "pattern does not match"),
    ],
)
def test_format_report_describes_python_branch_outcome(
    tmp_path: Path,
    source_line: int,
    target_line: int | None,
    description: str,
    expected_outcome: str,
):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int) -> int:\n"
        + "    if value > 0:\n"
        + "        return 1\n"
        + "    match value:\n"
        + "        case 0:\n"
        + "            return 0\n",
        encoding="utf-8",
        newline="\n",
    )
    branch = analyze_coverage.UncoveredBranch(
        source_file=source_path,
        source_line=source_line,
        description=description,
        target_line=target_line,
    )

    report = analyze_coverage.format_report([branch], [], [], tmp_path)

    assert f"  uncovered outcome: {expected_outcome}\n" in report


def test_parse_rejects_branch_before_source_file(tmp_path: Path):
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "BRDA:1,0,jump to line 2,0\n", encoding="utf-8", newline="\n"
    )

    with pytest.raises(ValueError, match="BRDA record appeared before an SF record"):
        _ = analyze_coverage.parse_uncovered_branches(report_path)


def _write_cli_coverage_report(workspace: Path):
    for source_name in ("first.py", "second.py", "third.py"):
        _ = (workspace / source_name).write_text(
            "def choose(value: bool) -> int:\n    if value:\n        return 1\n    return 0\n",
            encoding="utf-8",
            newline="\n",
        )
    report_path = workspace / "bazel-out/_coverage/_coverage_report.dat"
    report_path.parent.mkdir(parents=True)
    _ = report_path.write_text(
        "SF:first.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n"
        + "SF:second.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n"
        + "SF:third.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )


def test_cli_filters_to_multiple_workspace_relative_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_cli_coverage_report(tmp_path)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("RUST_GENERATED_SOURCES", "")
    monkeypatch.setenv("BUILD_WORKING_DIRECTORY", str(tmp_path))

    result = click.testing.CliRunner().invoke(
        analyze_coverage.main, ["first.py", "third.py"]
    )

    assert result.exit_code == 0
    assert Path.cwd() == tmp_path
    assert "first.py:2:" in result.output
    assert "second.py" not in result.output
    assert "third.py:2:" in result.output
    assert result.output.endswith(
        "2 actionable uncovered branches reported; "
        + "0 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted.\n"
    )


def test_cli_analyzes_all_files_without_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_cli_coverage_report(tmp_path)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("RUST_GENERATED_SOURCES", "")
    monkeypatch.delenv("BUILD_WORKING_DIRECTORY", raising=False)
    monkeypatch.chdir(tmp_path)

    result = click.testing.CliRunner().invoke(analyze_coverage.main)

    assert result.exit_code == 0
    assert Path.cwd() == tmp_path
    assert result.output.endswith(
        "3 actionable uncovered branches reported; "
        + "0 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted.\n"
    )


def test_cli_includes_files_transitively_under_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package_path = tmp_path / "package"
    child_path = package_path / "child"
    child_path.mkdir(parents=True)
    source = "def choose(value: bool) -> int:\n    if value:\n        return 1\n    return 0\n"
    _ = (package_path / "direct.py").write_text(source, encoding="utf-8", newline="\n")
    _ = (child_path / "descendant.py").write_text(
        source, encoding="utf-8", newline="\n"
    )
    _ = (tmp_path / "unrelated.py").write_text(source, encoding="utf-8", newline="\n")
    report_path = tmp_path / "bazel-out/_coverage/_coverage_report.dat"
    report_path.parent.mkdir(parents=True)
    _ = report_path.write_text(
        "SF:package/direct.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n"
        + "SF:package/child/descendant.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n"
        + "SF:unrelated.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("RUST_GENERATED_SOURCES", "")

    result = click.testing.CliRunner().invoke(analyze_coverage.main, ["package"])

    assert result.exit_code == 0
    assert "package/direct.py:2:" in result.output
    assert "package/child/descendant.py:2:" in result.output
    assert "unrelated.py" not in result.output
    assert result.output.endswith(
        "2 actionable uncovered branches reported; "
        + "0 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted.\n"
    )


def test_cli_help_describes_file_filtering():
    result = click.testing.CliRunner().invoke(analyze_coverage.main, ["--help"])

    assert result.exit_code == 0
    assert "optionally limited to SOURCE_PATHS" in result.output
    assert "files or directories relative to the workspace root" in result.output
    assert "Directories include source files at every depth" in result.output
    assert "analyze_coverage define/compiler/driver.py" in result.output


def test_cli_rejects_missing_source_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_cli_coverage_report(tmp_path)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))

    result = click.testing.CliRunner().invoke(analyze_coverage.main, ["missing.py"])

    assert result.exit_code == 2
    assert "source path does not exist: missing.py" in result.output


def test_workspace_root_falls_back_to_runfiles_workspace(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("BUILD_WORKSPACE_DIRECTORY", raising=False)

    assert (
        analyze_coverage.workspace_root()
        == Path(analyze_coverage.__file__).resolve().parent.parent
    )


def test_analyze_rust_regions_reports_region_with_source_text(tmp_path: Path):
    source_path = tmp_path / "example.rs"
    _ = source_path.write_text(
        "fn f(a: bool, b: bool) -> bool {\n    a || b\n}\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\n"
        + "BRDA:2,0,region from 2:5 to 2:6,4\n"
        + "BRDA:2,0,region from 2:10 to 2:11,0\n"
        + "BRDA:1,0,region from 1:1 to 3:2,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(report_path, tmp_path, {})

    assert regions == analyze_coverage.RustRegions(
        actionable=[
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=2,
                start_column=10,
                end_line=2,
                end_column=11,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=1,
                start_column=1,
                end_line=3,
                end_column=2,
            ),
        ],
        pyclass_generated=[],
        panic_only=[],
        python_exception_only=[],
    )
    assert analyze_coverage.format_rust_regions(regions, tmp_path) == (
        "Uncovered Rust code regions:\n"
        + f"{source_path.as_posix()}:2:10-2:11: b\n"
        + f"{source_path.as_posix()}:1:1-3:2: fn f(a: bool, b: bool) -> bool {{ a || b }}\n"
        + "2 uncovered Rust code regions reported; "
        + "0 pyclass-generated regions omitted; 0 panic-only regions omitted; "
        + "0 Python-exception-only regions omitted."
    )


def test_analyze_rust_regions_omits_region_that_only_panics(tmp_path: Path):
    source_path = tmp_path / "example.rs"
    _ = source_path.write_text(
        "fn f(a: usize) {\n    if a < 32 {\n"
        + '        unreachable!("a is at least 32");\n    }\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\n"
        + "BRDA:2,0,region from 2:15 to 4:6,0\n"
        + "BRDA:3,0,region from 3:9 to 3:21,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(report_path, tmp_path, {})

    assert regions == analyze_coverage.RustRegions(
        actionable=[],
        pyclass_generated=[],
        panic_only=[
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=2,
                start_column=15,
                end_line=4,
                end_column=6,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=3,
                start_column=9,
                end_line=3,
                end_column=21,
            ),
        ],
        python_exception_only=[],
    )


def test_analyze_report_leaves_rust_regions_out_of_branches(tmp_path: Path):
    source_path = tmp_path / "example.rs"
    _ = source_path.write_text("fn f() {}\n", encoding="utf-8", newline="\n")
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\nBRDA:1,0,region from 1:8 to 1:10,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    actionable, low_value, explicit_exit_only = analyze_coverage.analyze_report(
        report_path, tmp_path
    )

    assert actionable == []
    assert low_value == []
    assert explicit_exit_only == []


def test_cli_reports_rust_regions_before_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _ = (tmp_path / "example.rs").write_text(
        "fn f(a: bool) -> bool {\n    !a\n}\n", encoding="utf-8", newline="\n"
    )
    report_path = tmp_path / "bazel-out/_coverage/_coverage_report.dat"
    report_path.parent.mkdir(parents=True)
    _ = report_path.write_text(
        "SF:example.rs\nBRDA:2,0,region from 2:5 to 2:7,0\nend_of_record\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("RUST_GENERATED_SOURCES", "")

    result = click.testing.CliRunner().invoke(analyze_coverage.main)

    assert result.exit_code == 0
    assert result.output == (
        "Uncovered Rust code regions:\n"
        + "example.rs:2:5-2:7: !a\n"
        + "1 uncovered Rust code regions reported; "
        + "0 pyclass-generated regions omitted; 0 panic-only regions omitted; "
        + "0 Python-exception-only regions omitted.\n"
        + "No uncovered actionable branches.\n"
        + "0 actionable uncovered branches reported; "
        + "0 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted.\n"
    )


def test_analyze_rust_regions_omits_regions_on_a_pyclass_attribute(tmp_path: Path):
    source_path = tmp_path / "example.rs"
    _ = source_path.write_text(
        "#[pyclass(frozen)]\n"
        + "enum Statement {\n"
        + "    Create { position: String },\n"
        + "}\n"
        + "fn f() {}\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\n"
        + "BRDA:1,0,region from 1:18 to 1:19,0\n"
        + "BRDA:5,0,region from 5:1 to 5:10,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(report_path, tmp_path, {})

    assert regions == analyze_coverage.RustRegions(
        actionable=[
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=5,
                start_column=1,
                end_line=5,
                end_column=10,
            ),
        ],
        pyclass_generated=[
            analyze_coverage.UncoveredRegion(
                source_file=source_path,
                start_line=1,
                start_column=18,
                end_line=1,
                end_column=19,
            ),
        ],
        panic_only=[],
        python_exception_only=[],
    )


def _question_mark_region(source_file: Path, line: int, column: int):
    return analyze_coverage.UncoveredRegion(
        source_file=source_file,
        start_line=line,
        start_column=column,
        end_line=line,
        end_column=column + 1,
    )


def test_analyze_rust_regions_omits_question_marks_that_only_pass_on_python_exceptions(
    tmp_path: Path,
):
    crate_path = tmp_path / "crate"
    crate_path.mkdir()
    _ = (crate_path / "lib.rs").write_text(
        "fn python() -> PyResult<u8> {\n"
        + "    Ok(1)\n"
        + "}\n"
        + "fn syntax() -> ParseResult<u8> {\n"
        + "    Ok(2)\n"
        + "}\n"
        + "fn parse(ast: &AstBuilder, first: Option<u8>) -> ParseResult<u8> {\n"
        + "    let a = python()?;\n"
        + "    let b = syntax()?;\n"
        + "    let c = ast.location()?;\n"
        + "    let d = first?;\n"
        + "    Ok(a + b + c + d)\n"
        + "}\n"
        + "fn build(object: &Bound<PyAny>) -> PyResult<u8> {\n"
        + '    object.getattr("name")?.extract()\n'
        + "}\n",
        encoding="utf-8",
        newline="\n",
    )
    generated_path = tmp_path / "bazel-bin" / "generated.rs"
    generated_path.parent.mkdir()
    _ = generated_path.write_text(
        "impl AstBuilder {\n"
        + "    pub fn location(&self) -> PyResult<u8> {\n"
        + "        Ok(3)\n"
        + "    }\n"
        + "}\n",
        encoding="utf-8",
        newline="\n",
    )
    source_file = Path("crate/lib.rs")
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_file}\n"
        + "BRDA:8,0,region from 8:21 to 8:22,0\n"
        + "BRDA:9,0,region from 9:21 to 9:22,0\n"
        + "BRDA:10,0,region from 10:27 to 10:28,0\n"
        + "BRDA:11,0,region from 11:18 to 11:19,0\n"
        + "BRDA:15,0,region from 15:27 to 15:28,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(
        report_path,
        tmp_path,
        {
            Path("crate/generated.rs"): generated_path,
            Path("other_crate/generated.rs"): generated_path,
        },
    )

    assert regions == analyze_coverage.RustRegions(
        actionable=[
            _question_mark_region(source_file, 9, 21),
            _question_mark_region(source_file, 11, 18),
        ],
        pyclass_generated=[],
        panic_only=[],
        python_exception_only=[
            _question_mark_region(source_file, 8, 21),
            _question_mark_region(source_file, 10, 27),
            _question_mark_region(source_file, 15, 27),
        ],
    )


def test_analyze_rust_regions_finds_callees_in_other_modules_of_the_crate(
    tmp_path: Path,
):
    crate_path = tmp_path / "crate"
    (crate_path / "parser").mkdir(parents=True)
    _ = (crate_path / "lib.rs").write_text(
        "mod parser;\n", encoding="utf-8", newline="\n"
    )
    _ = (crate_path / "builder.rs").write_text(
        "fn python() -> PyResult<u8> {\n" + "    Ok(1)\n" + "}\n",
        encoding="utf-8",
        newline="\n",
    )
    _ = (crate_path / "parser.rs").write_text(
        "mod names;\n", encoding="utf-8", newline="\n"
    )
    _ = (crate_path / "parser" / "names.rs").write_text(
        "fn syntax() -> ParseResult<u8> {\n"
        + "    Ok(2)\n"
        + "}\n"
        + "fn parse() -> ParseResult<u8> {\n"
        + "    let a = python()?;\n"
        + "    let b = syntax()?;\n"
        + "    Ok(a + b)\n"
        + "}\n",
        encoding="utf-8",
        newline="\n",
    )
    source_file = Path("crate/parser/names.rs")
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_file}\n"
        + "BRDA:5,0,region from 5:21 to 5:22,0\n"
        + "BRDA:6,0,region from 6:21 to 6:22,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(report_path, tmp_path, {})

    assert regions == analyze_coverage.RustRegions(
        actionable=[_question_mark_region(source_file, 6, 21)],
        pyclass_generated=[],
        panic_only=[],
        python_exception_only=[_question_mark_region(source_file, 5, 21)],
    )


def test_analyze_rust_regions_omits_code_that_only_converts_python_exceptions(
    tmp_path: Path,
):
    crate_path = tmp_path / "crate"
    crate_path.mkdir()
    _ = (crate_path / "lib.rs").write_text(
        "impl From<PyErr> for ParseError {\n"
        + "    fn from(error: PyErr) -> Self {\n"
        + "        Self::Python(error)\n"
        + "    }\n"
        + "}\n"
        + "fn parse(result: ParseResult<u8>) -> PyResult<u8> {\n"
        + "    match result {\n"
        + "        Ok(value) => Ok(value),\n"
        + "        Err(ParseError::Syntax(error)) => Err(error),\n"
        + "        Err(ParseError::Python(error)) => return Err(error),\n"
        + "    }\n"
        + "}\n"
        + "fn log(error: PyErr, message: &str) {}\n",
        encoding="utf-8",
        newline="\n",
    )
    source_file = Path("crate/lib.rs")
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_file}\n"
        + "BRDA:2,0,region from 2:5 to 2:34,0\n"
        + "BRDA:3,0,region from 3:9 to 3:28,0\n"
        + "BRDA:4,0,region from 4:5 to 4:6,0\n"
        + "BRDA:9,0,region from 9:32 to 9:37,0\n"
        + "BRDA:10,0,region from 10:32 to 10:37,0\n"
        + "BRDA:10,0,region from 10:42 to 10:59,0\n"
        + "BRDA:13,0,region from 13:1 to 13:40,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )

    regions = analyze_coverage.analyze_rust_regions(report_path, tmp_path, {})

    assert regions == analyze_coverage.RustRegions(
        actionable=[
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=9,
                start_column=32,
                end_line=9,
                end_column=37,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=13,
                start_column=1,
                end_line=13,
                end_column=40,
            ),
        ],
        pyclass_generated=[],
        panic_only=[],
        python_exception_only=[
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=2,
                start_column=5,
                end_line=2,
                end_column=34,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=3,
                start_column=9,
                end_line=3,
                end_column=28,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=4,
                start_column=5,
                end_line=4,
                end_column=6,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=10,
                start_column=32,
                end_line=10,
                end_column=37,
            ),
            analyze_coverage.UncoveredRegion(
                source_file=source_file,
                start_line=10,
                start_column=42,
                end_line=10,
                end_column=59,
            ),
        ],
    )


def test_cli_reads_generated_rust_sources_from_runfiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    crate_path = tmp_path / "define/compiler/parsing"
    crate_path.mkdir(parents=True)
    _ = (crate_path / "lib.rs").write_text(
        "fn parse(ast: &mut AstBuilder) -> ParseResult<u8> {\n"
        + "    ast.position_definition()?;\n"
        + "}\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = tmp_path / "bazel-out/_coverage/_coverage_report.dat"
    report_path.parent.mkdir(parents=True)
    _ = report_path.write_text(
        "SF:define/compiler/parsing/lib.rs\n"
        + "BRDA:2,0,region from 2:30 to 2:31,0\n"
        + "end_of_record\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv(
        "RUST_GENERATED_SOURCES", os.environ["ANALYZE_COVERAGE_TEST_GENERATED_SOURCES"]
    )

    result = click.testing.CliRunner().invoke(analyze_coverage.main)

    assert result.exit_code == 0
    assert result.output == (
        "Uncovered Rust code regions:\n"
        + "0 uncovered Rust code regions reported; "
        + "0 pyclass-generated regions omitted; 0 panic-only regions omitted; "
        + "1 Python-exception-only regions omitted.\n"
        + "No uncovered actionable branches.\n"
        + "0 actionable uncovered branches reported; "
        + "0 low-value final-case non-match branches reported; "
        + "0 explicit-exit-only branches omitted.\n"
    )
