from __future__ import annotations

import os
import shutil
import subprocess
import typing

from tools import runfiles

if typing.TYPE_CHECKING:
    from pathlib import Path


def test_uv_lock_matches_pyproject(tmp_path: Path):
    # uv resolves the vendored re2 package relative to pyproject.toml, so the
    # test lays the project out the way the source tree does.
    re2_package = tmp_path / "vendored" / "re2" / "python"
    re2_package.mkdir(parents=True)
    _ = shutil.copy(runfiles.resolve_from_env("PYPROJECT"), tmp_path)
    _ = shutil.copy(runfiles.resolve_from_env("UV_LOCK"), tmp_path)
    for location in os.environ["RE2_UV_METADATA"].split():
        _ = shutil.copy(runfiles.resolve(location), re2_package)

    result = subprocess.run(
        [runfiles.resolve_from_env("UV"), "lock", "--locked"],
        cwd=tmp_path,
        check=False,
    )
    # To fix, run: bazel run //:update_lock
    assert result.returncode == 0
