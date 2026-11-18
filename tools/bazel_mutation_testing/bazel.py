"""Run Bazel in a worktree."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

# The tester runs under `bazel run`, which sets these for its own runfiles and
# workspace. Programs it starts must find their own runfiles, and Bazel runs in
# a worktree rather than the workspace.
_BAZEL_RUN_VARIABLES = frozenset(
    {
        "BUILD_WORKING_DIRECTORY",
        "BUILD_WORKSPACE_DIRECTORY",
        "JAVA_RUNFILES",
        "PYTHON_RUNFILES",
        "RUNFILES_DIR",
        "RUNFILES_MANIFEST_FILE",
    }
)


def executable(name: str) -> str:
    """Return the path of the program `name` on `PATH`.

    Raises:
        FileNotFoundError: No program on `PATH` has that name.
    """
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(f"The mutation tester needs {name} on PATH")
    return path


def child_environment(**variables: str) -> dict[str, str]:
    """Return the tester's environment without `bazel run`'s variables, plus `variables`."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in _BAZEL_RUN_VARIABLES
    }
    environment.update(variables)
    return environment


def run(
    workspace: pathlib.Path, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    """Run `bazelisk` in `workspace`, capturing its output."""
    return subprocess.run(
        [
            executable("bazelisk"),
            arguments[0],
            "--noshow_progress",
            "--ui_event_filters=-info",
            *arguments[1:],
        ],
        cwd=workspace,
        env=child_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


class BazelError(Exception):
    """A Bazel command failed."""

    def __init__(
        self, arguments: list[str], completed: subprocess.CompletedProcess[str]
    ):
        """Describe the failed command `arguments` and its output."""
        super().__init__(
            f"`bazelisk {' '.join(arguments)}` exited with "
            + f"{completed.returncode}:\n{completed.stderr}"
        )


def run_checked(workspace: pathlib.Path, arguments: list[str]) -> str:
    """Run `bazelisk` in `workspace` and return its standard output.

    Raises:
        BazelError: Bazel failed.
    """
    completed = run(workspace, arguments)
    if completed.returncode != 0:
        raise BazelError(arguments, completed)
    return completed.stdout
