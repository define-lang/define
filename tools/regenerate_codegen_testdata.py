"""Regenerate expected code generation and tracing output files.

Run this script with: bazelisk run --noshow_progress //tools:regenerate_codegen_testdata
"""

from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
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
    with tempfile.TemporaryDirectory(dir=case_dir) as temporary_dir:
        regenerated_dir = Path(temporary_dir) / expected_dir.name
        with contextlib.chdir(case_dir):
            result = driver.Driver().compile_program(
                Path("test.dfn"),
                regenerated_dir,
                trace_operations=trace_operations,
            )
            if result.has_errors():
                print(f"  {case_dir.relative_to(testdata_root)}: FAILED")
                for exc in result.all_exceptions:
                    print(f"    {exc}")
                for diag in result.all_diagnostics:
                    print(f"    {diag}")
                return False
        if expected_dir.exists():
            shutil.rmtree(expected_dir)
        _ = regenerated_dir.replace(expected_dir)
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


def _regenerate_codegen_case(case_dir: Path, *, testdata_root: Path) -> bool:
    expected_dir = case_dir / "expected"
    if not _compile_case(
        expected_dir,
        trace_operations=False,
        testdata_root=testdata_root,
    ):
        return False

    # Existing occupancy is a behavioral expectation; execution is only needed
    # when a new case does not have that expectation yet.
    occupied_positions = case_dir / "occupied_positions.txt"
    if occupied_positions.exists():
        return True
    runtime_result = _run_case(
        expected_dir,
        testdata_root=testdata_root,
    )
    if runtime_result is None:
        return False
    _ = occupied_positions.write_text(runtime_result.occupied_positions)
    return True


def _regenerate_tracing_case(case_dir: Path, *, testdata_root: Path) -> bool:
    expected_dir = case_dir / "expected_trace"
    if not _compile_case(
        expected_dir,
        trace_operations=True,
        testdata_root=testdata_root,
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
            testdata_root=testdata_root,
            operation_dependencies_file=operation_dependencies_file,
            max_threads=1,
        )
        is not None
    )


def main(
    *,
    codegen_testdata_root: Path = CODEGEN_TESTDATA_ROOT,
    tracing_testdata_root: Path = TRACING_TESTDATA_ROOT,
):
    """Regenerate ordinary and traced expected output files."""
    codegen_case_dirs = sorted(
        test_file.parent for test_file in codegen_testdata_root.glob("*/*/test.dfn")
    )
    tracing_case_dirs = sorted(
        test_file.parent for test_file in tracing_testdata_root.glob("*/test.dfn")
    )
    regenerated_codegen_case_count = 0
    regenerated_tracing_case_count = 0
    success = True
    for case_dir in codegen_case_dirs:
        if _regenerate_codegen_case(case_dir, testdata_root=codegen_testdata_root):
            regenerated_codegen_case_count += 1
        else:
            success = False
    for case_dir in tracing_case_dirs:
        if _regenerate_tracing_case(case_dir, testdata_root=tracing_testdata_root):
            regenerated_tracing_case_count += 1
        else:
            success = False
    print(
        f"Regenerated {regenerated_codegen_case_count} of {len(codegen_case_dirs)} codegen cases and {regenerated_tracing_case_count} of {len(tracing_case_dirs)} tracing cases."
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
