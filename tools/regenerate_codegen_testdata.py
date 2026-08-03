"""Regenerate expected code generation and tracing output files.

Run this script with: bazelisk run --noshow_progress //tools:regenerate_codegen_testdata
"""

import contextlib
import glob
import shutil
import sys
from pathlib import Path

from define.compiler import driver
from define.compiler.codegen import generated_program_runner

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEGEN_TESTDATA_ROOT = REPO_ROOT / "define/testdata/codegen"
TRACING_TESTDATA_ROOT = REPO_ROOT / "define/testdata/tracing/tracing_integration"


def _regenerate_case(
    case_dir: Path,
    expected_directory_name: str,
    *,
    trace_operations: bool,
    display_root: Path,
    trace_file: Path | None = None,
    max_threads: int | None = None,
) -> tuple[bool, str]:
    expected_dir = case_dir / expected_directory_name
    if expected_dir.exists():
        shutil.rmtree(expected_dir)
    with contextlib.chdir(case_dir):
        result = driver.Driver().compile_program(
            Path("test.dfn"),
            expected_dir,
            trace_operations=trace_operations,
        )
        if result.result.has_errors():
            print(f"  {case_dir.relative_to(display_root)}: FAILED")
            for exc in result.result.all_exceptions:
                print(f"    {exc}")
            for diag in result.result.all_diagnostics:
                print(f"    {diag}")
            return False, ""
    runtime_result = generated_program_runner.run_generated_program(
        expected_dir,
        trace_file=trace_file,
        max_threads=max_threads,
    )
    if runtime_result.process.returncode != 0:
        print(f"  {case_dir.relative_to(display_root)}: FAILED")
        print(runtime_result.process.stderr)
        return False, ""
    print(f"  {case_dir.relative_to(display_root)}: OK")
    return True, runtime_result.occupied_positions


def _regenerate_codegen_case(case_dir: Path) -> bool:
    success, occupied_positions_output = _regenerate_case(
        case_dir,
        "expected",
        trace_operations=False,
        display_root=CODEGEN_TESTDATA_ROOT,
    )
    if not success:
        return False
    occupied_positions = case_dir / "occupied_positions.txt"
    if not occupied_positions.exists():
        _ = occupied_positions.write_text(occupied_positions_output)
    return True


def main():
    """Regenerate ordinary and traced expected output files."""
    codegen_case_dirs = sorted(
        Path(path).parent
        for path in glob.glob(str(CODEGEN_TESTDATA_ROOT / "*/*/test.dfn"))
    )
    tracing_case_dirs = sorted(
        Path(path).parent
        for path in glob.glob(str(TRACING_TESTDATA_ROOT / "*/test.dfn"))
    )
    print(f"Regenerating {len(codegen_case_dirs)} codegen test cases...")
    success = True
    for case_dir in codegen_case_dirs:
        if not _regenerate_codegen_case(case_dir):
            success = False
    print(f"Regenerating {len(tracing_case_dirs)} tracing test cases...")
    for case_dir in tracing_case_dirs:
        case_success, _ = _regenerate_case(
            case_dir,
            "expected_trace",
            trace_operations=True,
            display_root=TRACING_TESTDATA_ROOT,
            trace_file=case_dir / "operation_trace.json",
            max_threads=1,
        )
        if not case_success:
            success = False
    if not success:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
