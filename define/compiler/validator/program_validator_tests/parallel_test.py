from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers

_POSITION_WITH_REF = (
    "define the potential position<my.domain.com:my_lib:/{name}> {{\n"
    "it may only contain dimension points where {{\n"
    "it has the position</{ref}>.\n"
    "}}\n"
    "}}\n"
)


def _write_def(tmp_path: Path, name: str, content: str):
    _ = (tmp_path / f"{name}.def").write_text(content, encoding="utf-8")


def _simple_position(name: str) -> str:
    return f"define the potential position<my.domain.com:my_lib:/{name}>.\n"


def _position_with_ref(name: str, ref: str) -> str:
    return _POSITION_WITH_REF.format(name=name, ref=ref)


def _position_with_refs(name: str, refs: list[str]) -> str:
    ref_lines = "".join(f"it has the position</{r}>.\n" for r in refs)
    return (
        f"define the potential position<my.domain.com:my_lib:/{name}> {{\n"
        f"it may only contain dimension points where {{\n"
        f"{ref_lines}"
        f"}}\n"
        f"}}\n"
    )


def test_fan_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    leaf_names = [f"leaf_{i}" for i in range(10)]
    _write_def(tmp_path, "root", _position_with_refs("root", leaf_names))
    for name in leaf_names:
        _write_def(tmp_path, name, _simple_position(name))
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("root.def"), max_workers=4
    )
    assert len(results) == 11
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)


def test_deep_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    chain = ["a", "b", "c", "d", "e"]
    for i, name in enumerate(chain[:-1]):
        _write_def(tmp_path, name, _position_with_ref(name, chain[i + 1]))
    _write_def(tmp_path, chain[-1], _simple_position(chain[-1]))
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("a.def"), max_workers=4
    )
    assert len(results) == 5
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)


def test_diamond_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_def(tmp_path, "top", _position_with_refs("top", ["left", "right"]))
    _write_def(tmp_path, "left", _position_with_ref("left", "bottom"))
    _write_def(tmp_path, "right", _position_with_ref("right", "bottom"))
    _write_def(tmp_path, "bottom", _simple_position("bottom"))
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("top.def"), max_workers=4
    )
    assert len(results) == 4
    assert all(r.exception is None for r in results)
    assert all(r.diagnostics == [] for r in results)


def test_wrong_type_detected_without_deferral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_def(tmp_path, "root", _position_with_ref("root", "hub"))
    _write_def(tmp_path, "hub", _position_with_refs("hub", ["target", "checker"]))
    _write_def(
        tmp_path,
        "target",
        "define the potential action<my.domain.com:my_lib:/target>.\n",
    )
    _write_def(tmp_path, "checker", _position_with_ref("checker", "target"))
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("root.def"), max_workers=1
    )
    checker_result = next(
        r for r in results if r.file_path == PurePosixPath("checker.def")
    )
    assert [type(d) for d in checker_result.diagnostics] == [
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    ]
