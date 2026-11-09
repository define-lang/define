"""Check that compiling creates no cyclic garbage."""

# The compiler's entry point disables the cyclic garbage collector, so any
# reference cycle a compile leaves behind is never freed.

from __future__ import annotations

import collections
import contextlib
import functools
import gc
import io
import typing
from pathlib import Path

import pytest

from defcl.python import error_types, errors, locations
from define.compiler import driver
from define.compiler.codegen import test_helpers, testdata_cases
from define.compiler.resource_tests import resource_cases

if typing.TYPE_CHECKING:
    from collections.abc import Callable

# The DCL validator extension imports these modules when it first reads a DCL
# file. Importing a module leaves a fixed amount of cyclic garbage, so they are
# imported here instead of during the first measured compile.
_MODULES_IMPORTED_ON_FIRST_DCL_FILE = (error_types, errors, locations)


# Thread pools and futures are a common source of cycles, so compiles run both
# on one thread and on several.
_BOTH_THREAD_COUNTS = pytest.mark.parametrize("max_threads", [1, 4])
# One and several threads run the same pool code, so the large codegen corpus
# compiles only once, with several.
_CODEGEN_CORPUS_THREADS = 4


def _collected_garbage() -> collections.Counter[str]:
    _ = gc.collect()
    garbage = collections.Counter(
        f"{type(item).__module__}.{type(item).__qualname__}"
        for item in typing.cast("list[object]", gc.garbage)
    )
    # With DEBUG_SAVEALL the next collection would save these cycles again,
    # so free them now.
    gc.set_debug(0)
    gc.garbage.clear()
    _ = gc.collect()
    gc.set_debug(gc.DEBUG_SAVEALL)
    return garbage


def _compile_all(
    compiles: dict[str, Callable[[], driver.ExitCode]],
) -> tuple[dict[str, driver.ExitCode], dict[str, collections.Counter[str]]]:
    # This runs in the test body rather than in a fixture so that garbage
    # from pytest's own setup and from earlier failures is collected first.
    _ = gc.collect()
    was_enabled = gc.isenabled()
    debug_flags = gc.get_debug()
    previous_garbage = list(gc.garbage)
    gc.garbage.clear()
    gc.disable()
    gc.set_debug(gc.DEBUG_SAVEALL)
    garbage_by_case: dict[str, collections.Counter[str]] = {}
    try:
        exit_codes = {
            case_name: compile_case() for case_name, compile_case in compiles.items()
        }
        # A collection visits the whole heap, so one after every compile would
        # cost more than the compiles. Only when there is garbage are the cases
        # compiled again one at a time, to say which created it.
        if all_garbage := _collected_garbage():
            for case_name, compile_case in compiles.items():
                _ = compile_case()
                if garbage := _collected_garbage():
                    garbage_by_case[case_name] = garbage
            # Garbage that no single compile creates still fails the test.
            if not garbage_by_case:
                garbage_by_case["(the cases together)"] = all_garbage
    finally:
        gc.set_debug(debug_flags)
        gc.garbage[:] = previous_garbage
        if was_enabled:
            gc.enable()
    return exit_codes, garbage_by_case


def _compile_codegen_case(
    case_dir: Path, output_dir: Path, max_threads: int
) -> driver.ExitCode:
    result = testdata_cases.compile_case(case_dir, output_dir, max_threads=max_threads)
    return driver.ExitCode.ERROR if result.has_errors() else driver.ExitCode.SUCCESS


def _compile_source_file(
    source_path: Path, output_dir: Path, max_threads: int
) -> driver.ExitCode:
    source = source_path.read_text(encoding="utf-8")
    with contextlib.chdir(source_path.parent):
        return driver.Driver().run(
            mode=driver.DriverMode.COMPILE,
            error_stream=io.StringIO(),
            output_dir=output_dir,
            source=source,
            max_threads=max_threads,
        )


def _compile_project(
    entry_path: Path, output_dir: Path, max_threads: int
) -> driver.ExitCode:
    with contextlib.chdir(entry_path.parent):
        return driver.Driver().run(
            Path(entry_path.name),
            mode=driver.DriverMode.COMPILE,
            error_stream=io.StringIO(),
            output_dir=output_dir,
            max_threads=max_threads,
        )


def test_codegen_cases_create_no_cyclic_garbage(tmp_path: Path):
    compiles: dict[str, Callable[[], driver.ExitCode]] = {}
    for case_dir in test_helpers.codegen_test_cases():
        case_name = test_helpers.codegen_test_case_id(case_dir)
        compiles[case_name] = functools.partial(
            _compile_codegen_case,
            case_dir,
            tmp_path / case_name,
            _CODEGEN_CORPUS_THREADS,
        )

    exit_codes, garbage_by_case = _compile_all(compiles)

    assert compiles
    assert exit_codes == dict.fromkeys(compiles, driver.ExitCode.SUCCESS)
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_resource_control_programs_create_no_cyclic_garbage(
    max_threads: int, tmp_path: Path
):
    compiles: dict[str, Callable[[], driver.ExitCode]] = {}
    expected_exit_codes: dict[str, driver.ExitCode] = {}
    for case in resource_cases.CPU_GROWTH_CASES:
        # The filesystem control projects span thousands of files.
        if case.filesystem:
            continue
        source_path = Path(resource_cases.COMPILER_RESOURCES_DIRECTORY / case.control)
        compiles[case.name] = functools.partial(
            _compile_source_file, source_path, tmp_path / case.name, max_threads
        )
        expected_exit_codes[case.name] = (
            driver.ExitCode.ERROR
            if case.expect_diagnostics
            else driver.ExitCode.SUCCESS
        )

    exit_codes, garbage_by_case = _compile_all(compiles)

    assert exit_codes == expected_exit_codes
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_retained_memory_programs_create_no_cyclic_garbage(
    max_threads: int, tmp_path: Path
):
    compiles: dict[str, Callable[[], driver.ExitCode]] = {}
    for case in resource_cases.RETAINED_MEMORY_CASES:
        source_path = Path(resource_cases.COMPILER_RESOURCES_DIRECTORY / case.source)
        compile_file = _compile_project if case.filesystem else _compile_source_file
        compiles[case.name] = functools.partial(
            compile_file, source_path, tmp_path / case.name, max_threads
        )

    exit_codes, garbage_by_case = _compile_all(compiles)

    assert exit_codes == dict.fromkeys(compiles, driver.ExitCode.SUCCESS)
    assert garbage_by_case == {}


def _compile_failing_project(
    project_directory: Path, tmp_path: Path, max_threads: int
) -> tuple[dict[str, driver.ExitCode], dict[str, collections.Counter[str]]]:
    entry_path = project_directory / "test.dfn"
    return _compile_all(
        {
            "compile": functools.partial(
                _compile_project, entry_path, tmp_path / "generated", max_threads
            )
        }
    )


@_BOTH_THREAD_COUNTS
def test_invalid_config_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_missing_entry_file_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_syntax_error_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_structural_diagnostic_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_reference_graph_diagnostic_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}


@_BOTH_THREAD_COUNTS
def test_entry_point_diagnostic_creates_no_cyclic_garbage(
    testdata_project_directory: Path, max_threads: int, tmp_path: Path
):
    exit_codes, garbage_by_case = _compile_failing_project(
        testdata_project_directory, tmp_path, max_threads
    )

    assert exit_codes == {"compile": driver.ExitCode.ERROR}
    assert garbage_by_case == {}
