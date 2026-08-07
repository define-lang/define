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
        + "    return value\n"
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\n"
        + "BRDA:2,0,jump to line 3,0\n"
        + "BRDA:2,0,jump to line 4,0\n"
        + "BRDA:2,0,return from function 'choose',1\n"
        + "end_of_record\n"
    )

    actionable, exception_only = analyze_coverage.analyze_report(report_path, tmp_path)

    assert actionable == [
        analyze_coverage.UncoveredBranch(
            source_file=Path("example.py"),
            source_line=2,
            description="jump to line 4",
            target_line=4,
        )
    ]
    assert exception_only == [
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
        'def fail() -> None:\n    raise ValueError(\n        "invalid value"\n    )\n'
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:1,0,jump to line 3,-\nend_of_record\n"
    )

    actionable, exception_only = analyze_coverage.analyze_report(report_path, tmp_path)

    assert actionable == []
    assert len(exception_only) == 1


def test_analyze_report_omits_wildcard_case_that_only_raises(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def choose(value: int) -> int:\n"
        + "    match value:\n"
        + "        case 1:\n"
        + "            return value\n"
        + "        case _:\n"
        + '            raise TypeError("unexpected value")\n'
    )
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        "SF:example.py\nBRDA:3,0,jump to line 5,0\nend_of_record\n"
    )

    actionable, exception_only = analyze_coverage.analyze_report(report_path, tmp_path)

    assert actionable == []
    assert len(exception_only) == 1


def test_format_report_includes_branch_source_and_destination(tmp_path: Path):
    source_path = tmp_path / "example.go"
    _ = source_path.write_text("if ready {\n\trun()\n}\n")
    branch = analyze_coverage.UncoveredBranch(
        source_file=Path("example.go"),
        source_line=1,
        description="jump to line 2",
        target_line=2,
    )

    report = analyze_coverage.format_report([branch], [], tmp_path)

    assert report == (
        "example.go:1:\n"
        "  branch source: if ready {\n"
        "  uncovered destination: line 2: run()\n"
        "1 uncovered branches reported; 0 exception-only branches omitted."
    )


def test_analyze_report_keeps_non_python_branch(tmp_path: Path):
    source_path = tmp_path / "example.go"
    _ = source_path.write_text('panic("invalid value")\n')
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text(
        f"SF:{source_path}\nBRDA:1,0,jump to line 1,0\nend_of_record\n"
    )

    actionable, exception_only = analyze_coverage.analyze_report(report_path, tmp_path)

    assert len(actionable) == 1
    assert exception_only == []


def test_format_report_describes_implicit_return_and_empty_result(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text("def choose() -> None:\n    return\n")
    branch = analyze_coverage.UncoveredBranch(
        source_file=source_path,
        source_line=1,
        description="return from function 'choose'",
        target_line=None,
    )

    report = analyze_coverage.format_report([branch], [], tmp_path)
    empty_report = analyze_coverage.format_report([], [branch], tmp_path)

    assert report == (
        f"{source_path}:1:\n"
        "  branch source: def choose() -> None:\n"
        "  uncovered destination: return from function 'choose'\n"
        "1 uncovered branches reported; 0 exception-only branches omitted."
    )
    assert empty_report == (
        "No uncovered non-exception branches.\n"
        "0 uncovered branches reported; 1 exception-only branches omitted."
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
        + "            return 0\n"
    )
    branch = analyze_coverage.UncoveredBranch(
        source_file=source_path,
        source_line=source_line,
        description=description,
        target_line=target_line,
    )

    report = analyze_coverage.format_report([branch], [], tmp_path)

    assert f"  uncovered outcome: {expected_outcome}\n" in report


def test_parse_rejects_branch_before_source_file(tmp_path: Path):
    report_path = tmp_path / "coverage.dat"
    _ = report_path.write_text("BRDA:1,0,jump to line 2,0\n")

    with pytest.raises(ValueError, match="BRDA record appeared before an SF record"):
        _ = analyze_coverage.parse_uncovered_branches(report_path)


def _write_cli_coverage_report(workspace: Path):
    for source_name in ("first.py", "second.py", "third.py"):
        _ = (workspace / source_name).write_text(
            "def choose(value: bool) -> int:\n    if value:\n        return 1\n    return 0\n"
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
        + "end_of_record\n"
    )


def test_cli_filters_to_multiple_workspace_relative_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_cli_coverage_report(tmp_path)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
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
        "2 uncovered branches reported; 0 exception-only branches omitted.\n"
    )


def test_cli_analyzes_all_files_without_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write_cli_coverage_report(tmp_path)
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("BUILD_WORKING_DIRECTORY", raising=False)
    monkeypatch.chdir(tmp_path)

    result = click.testing.CliRunner().invoke(analyze_coverage.main)

    assert result.exit_code == 0
    assert Path.cwd() == tmp_path
    assert result.output.endswith(
        "3 uncovered branches reported; 0 exception-only branches omitted.\n"
    )


def test_cli_includes_files_transitively_under_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package_path = tmp_path / "package"
    child_path = package_path / "child"
    child_path.mkdir(parents=True)
    source = "def choose(value: bool) -> int:\n    if value:\n        return 1\n    return 0\n"
    _ = (package_path / "direct.py").write_text(source)
    _ = (child_path / "descendant.py").write_text(source)
    _ = (tmp_path / "unrelated.py").write_text(source)
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
        + "end_of_record\n"
    )
    monkeypatch.setenv("BUILD_WORKSPACE_DIRECTORY", str(tmp_path))

    result = click.testing.CliRunner().invoke(analyze_coverage.main, ["package"])

    assert result.exit_code == 0
    assert "package/direct.py:2:" in result.output
    assert "package/child/descendant.py:2:" in result.output
    assert "unrelated.py" not in result.output
    assert result.output.endswith(
        "2 uncovered branches reported; 0 exception-only branches omitted.\n"
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
