"""Regenerate expected output files for code generation testdata.

Run this script with: bazelisk run --noshow_progress //tools:regenerate_codegen_testdata
"""

import contextlib
import shutil
import sys
from pathlib import Path

from define.compiler import driver

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTDATA_ROOT = REPO_ROOT / "define/testdata/codegen"


def _regenerate_case(case_dir: Path) -> bool:
    """Regenerate expected output for a single test case. Returns True on success."""
    expected_dir = case_dir / "expected"
    if expected_dir.exists():
        shutil.rmtree(expected_dir)
    with contextlib.chdir(case_dir):
        result = driver.Driver().compile_program(Path("test.dfn"), expected_dir)
        if result.result.has_errors():
            print(f"  {case_dir.relative_to(TESTDATA_ROOT)}: FAILED")
            for exc in result.result.all_exceptions:
                print(f"    {exc}")
            for diag in result.result.all_diagnostics:
                print(f"    {diag}")
            return False
    print(f"  {case_dir.relative_to(TESTDATA_ROOT)}: OK")
    return True


def main():
    """Regenerate all expected output files."""
    case_dirs = sorted(path.parent for path in TESTDATA_ROOT.glob("*/*/test.dfn"))
    print(f"Regenerating {len(case_dirs)} test cases...")
    success = True
    for case_dir in case_dirs:
        if not _regenerate_case(case_dir):
            success = False
    if not success:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
