"""Run basedpyright type-checking on a directory within a Bazel test."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tools import runfiles


def _write_config(pyproject: Path, import_paths: list[str], directory: Path) -> Path:
    """Write a config that extends pyproject and imports from import_paths."""
    # Only a venv's .pth files can add import paths to every execution
    # environment in pyproject at once, so import_paths go in a stand-in venv.
    site_packages = directory / "venv" / "lib" / "site-packages"
    site_packages.mkdir(parents=True)
    _ = (site_packages / "import_paths.pth").write_text(
        "".join(f"{path}\n" for path in import_paths),
        encoding="utf-8",
        newline="\n",
    )
    config = directory / "pyrightconfig.json"
    _ = config.write_text(
        json.dumps(
            {
                "extends": str(pyproject),
                # The project root is this config's directory, so imports from the
                # workspace would otherwise resolve only through import_paths, as
                # third-party imports.
                "extraPaths": [str(pyproject.parent)],
                "venvPath": str(directory),
                "venv": "venv",
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    return config


def main():
    """Run basedpyright on the given arguments."""
    # Left alone, basedpyright starts the venv's interpreter to find the import
    # paths of third-party packages. In a deep package, that interpreter's path
    # is longer than the 260 characters that Windows can start an executable
    # from, so basedpyright silently finds no third-party packages. Every value
    # typed through one, such as a pytest fixture, then becomes unknown, which
    # fails the test with thousands of warnings. This script already runs in
    # that interpreter, so it gives basedpyright its own sys.path through a
    # venv's .pth file, which basedpyright reads without starting anything.
    # sys.path[0] is this script's directory, which the interpreter wouldn't
    # report to basedpyright.
    config = _write_config(
        runfiles.resolve(sys.argv[2]),
        sys.path[1:],
        Path(os.environ["TEST_TMPDIR"]),
    )
    # basedpyright would also start the interpreter to find the Python version,
    # which fails the same way on Windows.
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    result = subprocess.run(
        [
            runfiles.resolve(sys.argv[1]),
            "--project",
            config,
            "--pythonversion",
            version,
            *sys.argv[3:],
        ],
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
