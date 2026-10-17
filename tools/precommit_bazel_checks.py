"""Run every pre-commit check that needs Bazel with a single Bazel command.

Bazel commands that share a server run one at a time, so the checks share one
command: it runs every pyright_test and every target tagged precommit, and
builds the formatter and ast-grep, which then run from bazel-bin.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_BAZEL_TAGS = "pyright,precommit"
_BUILD_FILE_NAMES = ("BUILD.bazel", "BUILD")

# Bazel's exit codes for a successful build whose tests passed or failed.
_BAZEL_TESTS_PASSED = 0
_BAZEL_TESTS_FAILED = 3


def _find_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"{name} is required for the Bazel checks")
    return executable


_GIT = _find_executable("git")


def _git_files(repository: Path, *arguments: str) -> list[str]:
    listing = subprocess.run(
        [_GIT, *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [path for path in listing.split("\0") if path]


def untracked_packages(repository: Path) -> list[str]:
    """Return the packages whose BUILD files git does not track.

    Pre-commit leaves untracked files in place, so Bazel must treat these
    packages as deleted, or a package that is not part of the commit could
    fail it.
    """
    untracked = _git_files(
        repository,
        "ls-files",
        "-z",
        "--others",
        "--exclude-standard",
        "--",
        *(f":(glob)**/{name}" for name in _BUILD_FILE_NAMES),
    )
    return [Path(path).parent.as_posix() for path in untracked]


def main():
    """Run the Bazel checks, then format and scan BUILD files from bazel-bin."""
    repository = Path.cwd()
    command = [
        _find_executable("bazelisk"),
        "test",
        "--noshow_progress",
        f"--build_tag_filters={_BAZEL_TAGS}",
        f"--test_tag_filters={_BAZEL_TAGS}",
    ]
    packages_to_ignore = untracked_packages(repository)
    if packages_to_ignore:
        command.append(f"--deleted_packages={','.join(packages_to_ignore)}")
    bazel = subprocess.run([*command, "//..."], cwd=repository, check=False)
    # After a failed build, bazel-bin can hold tools from an older build.
    if bazel.returncode not in {_BAZEL_TESTS_PASSED, _BAZEL_TESTS_FAILED}:
        sys.exit(bazel.returncode)

    bazel_bin = repository / "bazel-bin"
    format_files = subprocess.run(
        [bazel_bin / "tools" / "format" / "format_" / "format"],
        cwd=repository,
        env={**os.environ, "BUILD_WORKSPACE_DIRECTORY": str(repository)},
        check=False,
    )
    build_files = _git_files(
        repository,
        "ls-files",
        "-z",
        "--",
        *(f":(glob)**/{name}" for name in _BUILD_FILE_NAMES),
        ":(exclude)vendored/**",
    )
    scan_build_files = subprocess.run(
        [bazel_bin / "tools" / "ast-grep", "scan", *build_files],
        cwd=repository,
        check=False,
    )
    succeeded = (
        bazel.returncode == _BAZEL_TESTS_PASSED
        and format_files.returncode == 0
        and scan_build_files.returncode == 0
    )
    sys.exit(0 if succeeded else 1)


if __name__ == "__main__":
    main()
