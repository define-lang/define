"""Discovery and compilation of expected-output code generation cases."""

from __future__ import annotations

import contextlib
from pathlib import Path

from define.compiler import driver

# A filesystem case compiles its project from this entry file.
_FILESYSTEM_ENTRY = "test.dfn"
# A non-filesystem case compiles this file's text as its entry source.
_NON_FILESYSTEM_SOURCE = "source.dfn"


def case_directories(testdata_root: Path) -> list[Path]:
    """Return every case directory in every category."""
    case_dirs: list[Path] = []
    for entry_name in (_FILESYSTEM_ENTRY, _NON_FILESYSTEM_SOURCE):
        for entry in testdata_root.glob(f"*/*/{entry_name}"):
            case_dirs.append(entry.parent)
    return sorted(case_dirs)


def compile_case(
    case_dir: Path, output_dir: Path, *, trace_operations: bool = False
) -> driver.CompilationResult:
    """Compile a case into ``output_dir``."""
    source_path = case_dir / _NON_FILESYSTEM_SOURCE
    source = source_path.read_text(encoding="utf-8") if source_path.is_file() else None
    # A non-filesystem source can still reference definitions in the case's
    # project, so both kinds of case compile from the case directory.
    with contextlib.chdir(case_dir):
        if source is not None:
            return driver.Driver().compile_source(
                source, output_dir, trace_operations=trace_operations
            )
        return driver.Driver().compile_program(
            Path(_FILESYSTEM_ENTRY),
            output_dir,
            trace_operations=trace_operations,
        )
