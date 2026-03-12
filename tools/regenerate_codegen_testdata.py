"""Regenerate expected output files for code generation testdata."""

import contextlib
import sys
from pathlib import Path

from define.compiler import driver

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTDATA_ROOT = REPO_ROOT / "define/compiler/codegen/testdata"


def _regenerate_case(case_dir: Path) -> bool:
    """Regenerate expected output for a single test case. Returns True on success."""
    if not (case_dir / "test.def").exists():
        return True

    with contextlib.chdir(case_dir):
        result = driver.Driver().compile_program(Path("test.def"))
        if result.result.has_errors():
            print(f"  {case_dir.name}: FAILED")
            for exc in result.result.all_exceptions:
                print(f"    {exc}")
            for diag in result.result.all_diagnostics:
                print(f"    {diag}")
            return False
        if result.generated_code is None:
            print(f"  {case_dir.name}: FAILED (no code generated)")
            return False

    _ = (case_dir / "expected.py").write_text(result.generated_code)
    print(f"  {case_dir.name}: OK")
    return True


def main():
    """Regenerate all expected output files."""
    case_dirs = sorted(
        d for d in TESTDATA_ROOT.iterdir() if d.is_dir() and (d / "test.def").exists()
    )
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
