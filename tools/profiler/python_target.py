"""Find the Python interpreter and script behind a Bazel Python launcher."""

from __future__ import annotations

import contextlib
import pathlib


def bazel_entry_point(
    launcher_path: pathlib.Path,
    environment: dict[str, str],
) -> tuple[pathlib.Path, pathlib.Path] | None:
    """Return the interpreter and main script that a native Bazel launcher runs."""
    runfiles_directory = environment.get("RUNFILES_DIR")
    launcher_runfile: pathlib.Path | None = None
    if runfiles_directory is None:
        runfiles_path = launcher_path.with_name(launcher_path.name + ".runfiles")
        launcher_parts = launcher_path.parts
        if "bazel-bin" in launcher_parts:
            bazel_bin_index = launcher_parts.index("bazel-bin")
            launcher_runfile = pathlib.Path("_main").joinpath(
                *launcher_parts[bazel_bin_index + 1 :]
            )
    else:
        runfiles_path = pathlib.Path(runfiles_directory)
        with contextlib.suppress(ValueError):
            launcher_runfile = launcher_path.relative_to(runfiles_path)
    if launcher_runfile is None:
        return None
    venv_binaries = (
        runfiles_path
        / launcher_runfile.parent
        / f"._{launcher_path.name.removesuffix('.exe')}.venv/bin"
    )
    interpreter = venv_binaries / (
        "python.exe" if launcher_path.suffix == ".exe" else "python"
    )
    main = runfiles_path / launcher_runfile.with_suffix(".py")
    if not interpreter.is_file() or not main.is_file():
        return None
    return interpreter, main
