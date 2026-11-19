from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tools import runfiles
from tools.bazel_mutation_testing import diagnostics, lint_flags

if TYPE_CHECKING:
    import pathlib

# Each example starts with what rejects it under the repository's lints and in
# mutation runs, such as "// Rejected: unused_variables" and "// Rejected in
# mutation runs: nothing". A third line may give more rustc flags, such as
# "// Flags: --extern=dependency", which names a crate that the test compiles.
_REPOSITORY = "// Rejected: "
_MUTATION_RUN = "// Rejected in mutation runs: "
_FLAGS = "// Flags: "
_EXAMPLES = sorted(
    runfiles.resolve(location) for location in os.environ["LINT_EXAMPLES"].split()
)
_EXAMPLE_PARAMETERS = [pytest.param(example, id=example.stem) for example in _EXAMPLES]
_LINT_FLAGS = lint_flags.load()


def _expected(line: str, prefix: str) -> frozenset[str]:
    assert line.startswith(prefix)
    names = line.removeprefix(prefix)
    return frozenset() if names == "nothing" else frozenset(names.split(", "))


def _header(example: pathlib.Path) -> list[str]:
    return example.read_text(encoding="utf-8").splitlines()[:3]


def _rejections(command: list[str | pathlib.Path]) -> frozenset[str]:
    clippy_configuration = runfiles.resolve_from_env("CLIPPY_CONFIGURATION").parent
    completed = subprocess.run(
        command,
        env={**os.environ, "CLIPPY_CONF_DIR": str(clippy_configuration)},
        capture_output=True,
        text=True,
        check=False,
    )
    found = diagnostics.rust_rejections(completed.stderr)
    # A tool that fails while reporting nothing must not pass an example that
    # expects nothing.
    assert (completed.returncode == 0) == (not found)
    return found


def _all_rejections(
    example: pathlib.Path, output_directory: pathlib.Path, *, mutation_run: bool
) -> frozenset[str]:
    flags = _LINT_FLAGS.mutation_run if mutation_run else _LINT_FLAGS.repository
    rustc = runfiles.resolve_from_env("RUSTC")
    common: list[str | pathlib.Path] = [
        "--crate-type=lib",
        "--edition=2024",
        f"--sysroot={rustc.parent.parent}",
        "--emit=metadata",
        "--error-format=json",
        f"--out-dir={output_directory}",
    ]
    header = _header(example)
    extra_flags = (
        header[2].removeprefix(_FLAGS).split() if header[2].startswith(_FLAGS) else []
    )
    if "--extern=dependency" in extra_flags:
        dependency = output_directory / "dependency.rs"
        _ = dependency.write_text(
            "pub const ONE: u32 = 1;\n", encoding="utf-8", newline="\n"
        )
        _ = subprocess.run(
            [rustc, *common, dependency], capture_output=True, check=True
        )
    # rustc reports an unused dependency only when its path is given.
    common.extend(
        flag.replace(
            "--extern=dependency",
            f"--extern=dependency={output_directory / 'libdependency.rmeta'}",
        )
        for flag in extra_flags
    )
    # rules_rust orders the flags of the compile and clippy actions this way.
    return _rejections([rustc, *common, *flags.rustc, example]) | _rejections(
        [
            runfiles.resolve_from_env("CLIPPY_DRIVER"),
            *common,
            *flags.rustc,
            *flags.clippy,
            example,
        ]
    )


@pytest.mark.parametrize("example", _EXAMPLE_PARAMETERS)
def test_repository_lints(example: pathlib.Path, tmp_path: pathlib.Path):
    assert _all_rejections(example, tmp_path, mutation_run=False) == _expected(
        _header(example)[0], _REPOSITORY
    )


@pytest.mark.parametrize("example", _EXAMPLE_PARAMETERS)
def test_mutation_run_lints(example: pathlib.Path, tmp_path: pathlib.Path):
    assert _all_rejections(example, tmp_path, mutation_run=True) == _expected(
        _header(example)[1], _MUTATION_RUN
    )


def test_examples_cover_the_turned_off_lints():
    turned_off: set[str] = set()
    for example in _EXAMPLES:
        header = _header(example)
        turned_off.update(
            _expected(header[0], _REPOSITORY) - _expected(header[1], _MUTATION_RUN)
        )
    assert turned_off == _LINT_FLAGS.turned_off.rust
