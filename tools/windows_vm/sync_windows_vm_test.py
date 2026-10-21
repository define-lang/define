from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from tools.windows_vm import sync_windows_vm

if TYPE_CHECKING:
    from pathlib import Path


_GIT = str(shutil.which("git"))


def _git(checkout: Path, *arguments: str) -> str:
    return subprocess.run(
        [
            _GIT,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *arguments,
        ],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_snapshot_includes_working_tree_without_changing_checkout(tmp_path: Path):
    _ = _git(tmp_path, "init", "--quiet")
    _ = (tmp_path / ".gitignore").write_text("ignored.txt\n")
    _ = (tmp_path / "committed.txt").write_text("committed\n")
    _ = (tmp_path / "staged.txt").write_text("staged\n")
    _ = _git(tmp_path, "add", ".")
    _ = _git(tmp_path, "commit", "--quiet", "--message=Initial")
    _ = (tmp_path / "committed.txt").write_text("modified\n")
    _ = (tmp_path / "staged.txt").write_text("staged change\n")
    _ = _git(tmp_path, "add", "staged.txt")
    _ = (tmp_path / "untracked.txt").write_text("untracked\n")
    _ = (tmp_path / "ignored.txt").write_text("ignored\n")
    head = _git(tmp_path, "rev-parse", "HEAD")
    status = _git(tmp_path, "status", "--porcelain")

    commit = sync_windows_vm.snapshot_commit(_GIT, tmp_path)

    assert _git(tmp_path, "ls-tree", "--name-only", commit).split() == [
        ".gitignore",
        "committed.txt",
        "staged.txt",
        "untracked.txt",
    ]
    assert _git(tmp_path, "show", f"{commit}:committed.txt") == "modified\n"
    assert _git(tmp_path, "show", f"{commit}:staged.txt") == "staged change\n"
    assert _git(tmp_path, "rev-parse", f"{commit}^") == head
    assert _git(tmp_path, "rev-parse", "HEAD") == head
    assert _git(tmp_path, "status", "--porcelain") == status
