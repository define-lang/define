# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import validator
from define.compiler.validator_tests import test_helpers


def _write_source(tmp_path: Path, rel_path: str, source: str) -> Path:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_nested_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "test.example.com:my_lib")
    _write_source(
        tmp_path,
        "sub/dir/leaf.def",
        "define the potential position<test.example.com:my_lib:/sub/dir/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("sub/dir/leaf.def")
    )
    assert len(results) == 1
    result = results[0]
    assert result.exception is None
    assert result.diagnostics == []
    assert result.file_path == PurePosixPath("sub/dir/leaf.def")


def test_walk_returns_results_in_encounter_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "mv:define-lang.org:walk_order")
    _write_source(
        tmp_path,
        "test.def",
        (
            "define the potential position<mv:define-lang.org:walk_order:/test> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</middle>.\n"
            + "}\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "middle.def",
        (
            "define the potential position<mv:define-lang.org:walk_order:/middle> {\n"
            + "it may only contain dimension points where {\n"
            + "it has the position</leaf>.\n"
            + "}\n"
            + "}\n"
        ),
    )
    _write_source(
        tmp_path,
        "leaf.def",
        "define the potential position<mv:define-lang.org:walk_order:/leaf>.\n",
    )
    monkeypatch.chdir(tmp_path)

    results = validator.Validator().parse_and_validate_program(
        PurePosixPath("test.def")
    )
    assert [result.file_path for result in results] == [
        PurePosixPath("test.def"),
        PurePosixPath("middle.def"),
        PurePosixPath("leaf.def"),
    ]
