from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from tools import precommit_bazel_checks

if TYPE_CHECKING:
    from pathlib import Path


def _git(repository: Path, *arguments: str):
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required for these tests")
    _ = subprocess.run([git, *arguments], cwd=repository, check=True)


def _write(repository: Path, path: str):
    file = repository / path
    file.parent.mkdir(parents=True, exist_ok=True)
    _ = file.write_text("\n", encoding="utf-8", newline="\n")


def _repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    _write(tmp_path, "BUILD.bazel")
    _write(tmp_path, "tracked/BUILD.bazel")
    _git(tmp_path, "add", "--", "BUILD.bazel", "tracked/BUILD.bazel")
    return tmp_path


def test_tracked_packages_are_not_untracked(tmp_path: Path):
    repository = _repository(tmp_path)
    _write(repository, "tracked/untracked.py")

    assert precommit_bazel_checks.untracked_packages(repository) == []


def test_untracked_package_and_its_child_package(tmp_path: Path):
    repository = _repository(tmp_path)
    _write(repository, "new/BUILD.bazel")
    _write(repository, "new/child/BUILD")

    assert precommit_bazel_checks.untracked_packages(repository) == [
        "new",
        "new/child",
    ]


def test_untracked_directory_without_packages(tmp_path: Path):
    repository = _repository(tmp_path)
    _write(repository, "tracked/data/file.txt")

    assert precommit_bazel_checks.untracked_packages(repository) == []


def test_untracked_build_file_in_tracked_directory(tmp_path: Path):
    repository = _repository(tmp_path)
    _write(repository, "tracked/child/file.py")
    _git(repository, "add", "--", "tracked/child/file.py")
    _write(repository, "tracked/child/BUILD.bazel")

    assert precommit_bazel_checks.untracked_packages(repository) == ["tracked/child"]


def test_ignored_package_is_not_untracked(tmp_path: Path):
    repository = _repository(tmp_path)
    _ = (repository / ".gitignore").write_text(
        "ignored/\n", encoding="utf-8", newline="\n"
    )
    _write(repository, "ignored/BUILD.bazel")

    assert precommit_bazel_checks.untracked_packages(repository) == []
