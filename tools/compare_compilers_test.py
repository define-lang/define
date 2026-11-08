from __future__ import annotations

import contextlib
import re
import sys
import typing
from unittest import mock

import click.testing
import pytest
from python.runfiles import runfiles as python_runfiles

from tools import compare_compilers, profile_orchestration, runfiles

if typing.TYPE_CHECKING:
    import collections.abc
    from pathlib import Path

_CONSTRUCTOR_SOURCE = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        define the position<created>.\n"
    "        create a particle in position<created>.\n"
    "    }\n"
    "}\n"
)

_OUTCOME = compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
    exit_code=0, stdout=b"", stderr=b"", generated_digests={"a.py": "1"}
)
_RUN = compare_compilers._Run(seconds=1.0, peak_rss_kb=2048)  # pyright: ignore[reportPrivateUsage]


def _invoke(
    tmp_path: Path,
    arguments: list[str],
    measured: collections.abc.Sequence[tuple[object, object]] | None = None,
) -> click.testing.Result:
    source = tmp_path / "test.dfn"
    _ = source.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")
    with (
        mock.patch.object(
            profile_orchestration,
            "build_compiler",
            autospec=True,
            return_value=runfiles.resolve_from_env("COMPILER_BINARY"),
        ),
        mock.patch.object(
            compare_compilers, "_build_stamp", autospec=True, return_value=0
        ),
        contextlib.ExitStack() as patches,
    ):
        if measured is not None:
            _ = patches.enter_context(
                mock.patch.object(
                    compare_compilers, "_measure", autospec=True, side_effect=measured
                )
            )
        return click.testing.CliRunner().invoke(
            compare_compilers.main,
            [
                "--baseline",
                str(tmp_path),
                "--candidate",
                str(tmp_path),
                "--source",
                str(source),
                *arguments,
            ],
        )


@pytest.mark.skipif(sys.platform == "win32", reason="needs os.wait4")
def test_compares_one_compiler_with_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runfiles_resolver = python_runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    environment = profile_orchestration.target_environment()
    environment.update(runfiles_resolver.EnvVars())
    monkeypatch.setattr(
        profile_orchestration, "target_environment", lambda: dict(environment)
    )
    result = _invoke(tmp_path, ["--rounds", "2", "--max-threads", "1"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    run = r"[\d.]+ s; peak RSS [\d,]+ MB"
    assert re.fullmatch(rf"Warm-up baseline: {run}", lines[0])
    assert re.fullmatch(rf"Warm-up candidate: {run}", lines[1])
    assert re.fullmatch(
        r"Outputs: identical; exit 0; [1-9]\d* generated files", lines[2]
    )
    assert re.fullmatch(rf"Round 1 candidate: {run}", lines[3])
    assert re.fullmatch(rf"Round 1 baseline: {run}", lines[4])
    assert re.fullmatch(rf"Round 2 baseline: {run}", lines[5])
    assert re.fullmatch(rf"Round 2 candidate: {run}", lines[6])
    assert re.fullmatch(r"baseline  median .* peak RSS [\d,]+ MB", lines[7])
    assert re.fullmatch(r"candidate median .* peak RSS [\d,]+ MB", lines[8])
    assert re.fullmatch(
        r"Candidate/baseline: median \d\.\d{3}; mean \d\.\d{3}; min \d\.\d{3}",
        lines[9],
    )
    assert len(lines) == 10


def test_reports_outputs_that_differ(tmp_path: Path):
    measured = [
        (_RUN, _OUTCOME),
        (
            _RUN,
            compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
                exit_code=1, stdout=b"", stderr=b"", generated_digests={}
            ),
        ),
    ]
    result = _invoke(tmp_path, [], measured)
    assert result.exit_code == 1
    assert result.output == (
        "Warm-up baseline: 1.000 s; peak RSS 2 MB\n"
        + "Warm-up candidate: 1.000 s; peak RSS 2 MB\n"
        + "Error: the outputs differ: exit 0 became 1\n"
    )


def test_reports_a_compiler_that_is_not_deterministic(tmp_path: Path):
    other = compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
        exit_code=0, stdout=b"", stderr=b"", generated_digests={"a.py": "2"}
    )
    result = _invoke(tmp_path, [], [(_RUN, _OUTCOME), (_RUN, _OUTCOME), (_RUN, other)])
    assert result.exit_code == 1
    assert result.output.endswith(
        "Error: the candidate compiler is not deterministic: "
        + "generated file a.py differs\n"
    )


@pytest.mark.parametrize("changed_stamp", [1, FileNotFoundError()])
def test_reports_a_compiler_that_changes_while_timed(
    tmp_path: Path, changed_stamp: int | FileNotFoundError
):
    source = tmp_path / "test.dfn"
    _ = source.write_text(_CONSTRUCTOR_SOURCE, encoding="utf-8", newline="\n")
    with (
        mock.patch.object(
            profile_orchestration,
            "build_compiler",
            autospec=True,
            return_value=tmp_path / "main",
        ),
        mock.patch.object(
            compare_compilers,
            "_build_stamp",
            autospec=True,
            side_effect=[0, 0, changed_stamp],
        ),
        mock.patch.object(
            compare_compilers, "_run", autospec=True, side_effect=_fake_run
        ),
    ):
        result = click.testing.CliRunner().invoke(
            compare_compilers.main,
            [
                "--baseline",
                str(tmp_path),
                "--candidate",
                str(tmp_path),
                "--source",
                str(source),
            ],
        )
    assert result.exit_code == 1
    assert result.output == (
        f"Error: the baseline compiler in {tmp_path} or its sources changed "
        + "while it was being timed, such as by another Bazel command in that "
        + "checkout\n"
    )


def _fake_run(_: object, logs: Path) -> tuple[object, int]:
    (logs / "stdout").touch()
    (logs / "stderr").touch()
    return _RUN, 0


@pytest.mark.parametrize("arguments", [[], ["--source", "test.dfn", "--project", "."]])
def test_requires_one_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test.dfn").touch()
    result = click.testing.CliRunner().invoke(
        compare_compilers.main,
        ["--baseline", ".", "--candidate", ".", *arguments],
    )
    assert result.exit_code == 2
    assert result.output.endswith(
        "Error: provide exactly one of --source or --project\n"
    )


@pytest.mark.parametrize(
    ("candidate", "difference"),
    [
        (_OUTCOME, None),
        (
            compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
                exit_code=0, stdout=b"x", stderr=b"", generated_digests={}
            ),
            "standard output differs",
        ),
        (
            compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
                exit_code=0, stdout=b"", stderr=b"x", generated_digests={}
            ),
            "standard error differs",
        ),
        (
            compare_compilers._Outcome(  # pyright: ignore[reportPrivateUsage]
                exit_code=0,
                stdout=b"",
                stderr=b"",
                generated_digests={"a.py": "1", "b.py": "1"},
            ),
            "1 generated files exist in only one, such as b.py",
        ),
    ],
)
def test_difference(
    candidate: compare_compilers._Outcome,  # pyright: ignore[reportPrivateUsage]
    difference: str | None,
):
    assert (
        compare_compilers._difference(_OUTCOME, candidate)  # pyright: ignore[reportPrivateUsage]
        == difference
    )


def test_build_stamp_changes_with_any_runfile(tmp_path: Path):
    launcher = tmp_path / "main"
    _ = launcher.write_text("launcher", encoding="utf-8", newline="\n")
    source = tmp_path / "main.runfiles" / "_main" / "source.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text("first", encoding="utf-8", newline="\n")
    _ = (tmp_path / "main.runfiles_manifest").write_text(
        "_main/source.py /elsewhere/source.py\n", encoding="utf-8", newline="\n"
    )
    stamp = compare_compilers._build_stamp(launcher)  # pyright: ignore[reportPrivateUsage]
    assert compare_compilers._build_stamp(launcher) == stamp  # pyright: ignore[reportPrivateUsage]
    _ = source.write_text("second", encoding="utf-8", newline="\n")
    assert compare_compilers._build_stamp(launcher) != stamp  # pyright: ignore[reportPrivateUsage]


def test_generated_digests_name_files_by_relative_path(tmp_path: Path):
    (tmp_path / "package").mkdir()
    _ = (tmp_path / "package" / "module.py").write_bytes(b"")
    assert compare_compilers._generated_digests(tmp_path) == {  # pyright: ignore[reportPrivateUsage]
        "package/module.py": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
    }
