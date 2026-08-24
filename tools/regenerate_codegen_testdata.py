"""Regenerate expected code generation and tracing output files.

Run this script with: bazelisk run --noshow_progress //tools:regenerate_codegen_testdata
"""

from __future__ import annotations

import contextlib
import shutil
import sys
from pathlib import Path

from define.compiler import driver
from define.compiler.codegen import generated_program_runner

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEGEN_TESTDATA_ROOT = REPO_ROOT / "define/testdata/codegen"
TRACING_TESTDATA_ROOT = REPO_ROOT / "define/testdata/tracing/tracing_integration"


def _compile_case(
    expected_dir: Path,
    *,
    trace_operations: bool,
    testdata_root: Path,
) -> bool:
    case_dir = expected_dir.parent
    if expected_dir.exists():
        shutil.rmtree(expected_dir)
    with contextlib.chdir(case_dir):
        result = driver.Driver().compile_program(
            Path("test.dfn"),
            expected_dir,
            trace_operations=trace_operations,
        )
        if result.has_errors():
            print(f"  {case_dir.relative_to(testdata_root)}: FAILED")
            for exc in result.all_exceptions:
                print(f"    {exc}")
            for diag in result.all_diagnostics:
                print(f"    {diag}")
            return False
    return True


def _run_case(
    expected_dir: Path,
    *,
    testdata_root: Path,
    operation_dependencies_file: Path | None = None,
    max_threads: int | None = None,
) -> generated_program_runner.GeneratedProgramResult | None:
    case_dir = expected_dir.parent
    runtime_result = generated_program_runner.run_generated_program(
        expected_dir,
        operation_dependencies_file=operation_dependencies_file,
        max_threads=max_threads,
    )
    if runtime_result.process.returncode != 0:
        print(f"  {case_dir.relative_to(testdata_root)}: FAILED")
        print(runtime_result.process.stderr)
        return None
    return runtime_result


def _regenerate_codegen_case(case_dir: Path) -> bool:
    expected_dir = case_dir / "expected"
    if not _compile_case(
        expected_dir,
        trace_operations=False,
        testdata_root=CODEGEN_TESTDATA_ROOT,
    ):
        return False

    # Existing occupancy is a behavioral expectation; execution is only needed
    # when a new case does not have that expectation yet.
    occupied_positions = case_dir / "occupied_positions.txt"
    if occupied_positions.exists():
        return True
    runtime_result = _run_case(
        expected_dir,
        testdata_root=CODEGEN_TESTDATA_ROOT,
    )
    if runtime_result is None:
        return False
    _ = occupied_positions.write_text(runtime_result.occupied_positions)
    return True


def _regenerate_tracing_case(case_dir: Path) -> bool:
    expected_dir = case_dir / "expected_trace"
    if not _compile_case(
        expected_dir,
        trace_operations=True,
        testdata_root=TRACING_TESTDATA_ROOT,
    ):
        return False

    # Existing runtime behavior is an expectation; execution is only needed
    # when a new case does not have that expectation yet.
    operation_dependencies_file = case_dir / "operation_dependencies.json"
    if operation_dependencies_file.exists():
        return True
    return (
        _run_case(
            expected_dir,
            testdata_root=TRACING_TESTDATA_ROOT,
            operation_dependencies_file=operation_dependencies_file,
            max_threads=1,
        )
        is not None
    )


def main():
    """Regenerate ordinary and traced expected output files."""
    codegen_case_dirs = sorted(
        test_file.parent for test_file in CODEGEN_TESTDATA_ROOT.glob("*/*/test.dfn")
    )
    tracing_case_dirs = sorted(
        test_file.parent for test_file in TRACING_TESTDATA_ROOT.glob("*/test.dfn")
    )
    print(f"Regenerating {len(codegen_case_dirs)} codegen test cases...")
    success = True
    for case_dir in codegen_case_dirs:
        if not _regenerate_codegen_case(case_dir):
            success = False
    print(f"Regenerating {len(tracing_case_dirs)} tracing test cases...")
    for case_dir in tracing_case_dirs:
        if not _regenerate_tracing_case(case_dir):
            success = False
    if not success:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
