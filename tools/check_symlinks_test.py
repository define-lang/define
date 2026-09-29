from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from tools import check_symlinks

if TYPE_CHECKING:
    from pathlib import Path


def _git(repository: Path, *arguments: str):
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required for these tests")
    _ = subprocess.run([git, *arguments], cwd=repository, check=True)


def _repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    return tmp_path


def _track(repository: Path, *paths: str):
    _git(repository, "add", "--", *paths)


def test_symlink_to_existing_file_is_not_broken(tmp_path: Path):
    repository = _repository(tmp_path)
    _ = (repository / "target.txt").write_text("target\n")
    (repository / "link").symlink_to("target.txt")
    _track(repository, "target.txt", "link")

    assert check_symlinks.broken_symlinks(repository) == []


def test_symlink_whose_target_was_deleted_is_broken(tmp_path: Path):
    repository = _repository(tmp_path)
    (repository / "cases").mkdir()
    (repository / "cases" / "case").mkdir()
    _ = (repository / "cases" / "case" / "test.dfn").write_text("\n")
    (repository / "link").symlink_to("cases/case")
    (repository / "other_link").symlink_to("cases")
    _track(repository, "cases/case/test.dfn", "link", "other_link")
    shutil.rmtree(repository / "cases" / "case")

    assert check_symlinks.broken_symlinks(repository) == ["link"]


def test_untracked_broken_symlink_is_ignored(tmp_path: Path):
    repository = _repository(tmp_path)
    (repository / "link").symlink_to("missing")

    assert check_symlinks.broken_symlinks(repository) == []
