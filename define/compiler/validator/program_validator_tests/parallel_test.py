"""Parallel validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

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


def test_chain_element_validated_without_deferral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # With max_workers=1, root discovers child before test, so child.def
    # completes before test.def is processed. This forces the "target already
    # available" branch in _process_deferred_chained_names, where the chain
    # element is validated immediately instead of being deferred.
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_def(tmp_path, "root", _position_with_refs("root", ["child", "test"]))
    _write_def(tmp_path, "child", _position_with_ref("child", "leaf"))
    _write_def(tmp_path, "leaf", _simple_position("leaf"))
    _write_def(tmp_path, "wrong", _simple_position("wrong"))
    _write_def(
        tmp_path,
        "test",
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "define the position<pos_a> {\n"
            "it may only contain dimension points where {\n"
            "it has the position</child>.\n"
            "}\n"
            "}\n"
            "it happens when {\n"
            "} and it does {\n"
            "create a dimension point in"
            " position<pos_a>::position</child>::position</wrong>.\n"
            "}\n"
            "}\n"
        ),
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("root.def"), max_workers=1
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert [type(d) for d in test_result.diagnostics] == [
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    ]


def test_chain_continuation_validated_without_deferral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # With max_workers=1, hub discovers pos_c before pos_b, so the
    # processing order is: hub → pos_c → test → pos_b → pos_d.
    # When pos_b completes, deferred chain validation runs for test.def's
    # chain (pos_a::pos_b::pos_c::pos_d). After validating pos_c against
    # pos_b's constraints, _defer_chain_continuation finds pos_c.def already
    # loaded, so it validates pos_d immediately (target_result is not None).
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    _write_def(
        tmp_path,
        "hub",
        (
            "define the potential position<my.domain.com:my_lib:/hub> {\n"
            "it may only contain dimension points where {\n"
            "it has the position</pos_c>.\n"
            "it has the action</test>.\n"
            "it has the position</pos_b>.\n"
            "}\n"
            "}\n"
        ),
    )
    _write_def(tmp_path, "pos_b", _position_with_ref("pos_b", "pos_c"))
    _write_def(tmp_path, "pos_c", _simple_position("pos_c"))
    _write_def(tmp_path, "pos_d", _simple_position("pos_d"))
    _write_def(
        tmp_path,
        "test",
        (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "define the position<pos_a> {\n"
            "it may only contain dimension points where {\n"
            "it has the position</pos_b>.\n"
            "}\n"
            "}\n"
            "it happens when {\n"
            "} and it does {\n"
            "create a dimension point in"
            " position<pos_a>::position</pos_b>::position</pos_c>::position</pos_d>.\n"
            "}\n"
            "}\n"
        ),
    )
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("hub.def"), max_workers=1
    )
    test_result = next(r for r in results if r.file_path == PurePosixPath("test.def"))
    assert [type(d) for d in test_result.diagnostics] == [
        diagnostics.ChainElementNotInConstraintsDiagnostic,
    ]
    diag = test_result.diagnostics[0]
    assert isinstance(diag, diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert diag.position.line == 9
    assert diag.position.column == 82


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
