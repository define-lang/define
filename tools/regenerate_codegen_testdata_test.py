from __future__ import annotations

import typing
from pathlib import Path
from unittest import mock

import pytest

from define.compiler import driver
from tools import regenerate_codegen_testdata


@typing.final
class _CompilationResult:
    def __init__(self, *, failed: bool):
        self.all_exceptions = ["compilation failed"] if failed else []
        self.all_diagnostics: list[str] = []
        self._failed = failed

    def has_errors(self) -> bool:
        return self._failed


def test_compile_failure_preserves_output_and_does_not_stop_later_cases(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    codegen_root = tmp_path / "codegen"
    failed_case = codegen_root / "category" / "failed"
    successful_case = codegen_root / "category" / "successful"
    for case_dir in (failed_case, successful_case):
        case_dir.mkdir(parents=True)
        _ = (case_dir / "test.dfn").write_text("")
    failed_expected = failed_case / "expected"
    failed_expected.mkdir()
    failed_expected_file = failed_expected / "generated.py"
    _ = failed_expected_file.write_text("existing output")
    _ = (successful_case / "operation_trace.txt").write_text("existing trace")

    def compile_program(
        driver_instance: driver.Driver,
        path: Path,
        output_dir: Path,
        *,
        trace_operations: bool = False,
        max_threads: int | None = None,
    ) -> driver.CompilationResult:
        _ = driver_instance, path, trace_operations, max_threads
        failed = Path.cwd() == failed_case
        if not failed:
            output_dir.mkdir()
            _ = (output_dir / "generated.py").write_text("new output")
        result = typing.cast("object", _CompilationResult(failed=failed))
        return typing.cast("driver.CompilationResult", result)

    with (
        mock.patch.object(
            driver.Driver,
            "compile_program",
            autospec=True,
            side_effect=compile_program,
        ),
        pytest.raises(SystemExit) as raised,
    ):
        regenerate_codegen_testdata.main(
            codegen_testdata_root=codegen_root,
        )

    assert raised.value.code == 1
    assert failed_expected_file.read_text() == "existing output"
    assert (successful_case / "expected" / "generated.py").read_text() == "new output"
    assert (
        successful_case / "expected_trace" / "generated.py"
    ).read_text() == "new output"
    assert (successful_case / "operation_trace.txt").read_text() == "existing trace"
    assert capsys.readouterr().out == (
        "  category/failed: FAILED\n"
        "    compilation failed\n"
        "  category/failed: FAILED\n"
        "    compilation failed\n"
        "Regenerated 1 of 2 codegen cases and 1 of 2 tracing cases.\n"
    )
