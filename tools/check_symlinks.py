"""Fail when any symlink that git tracks points at nothing.

Every tracked symlink is checked, not just changed ones, because a change can
delete or move the target of a symlink that it does not touch.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_SYMLINK_MODE = "120000"


def broken_symlinks(repository: Path) -> list[str]:
    """Return the repository-relative paths of tracked symlinks with no target."""
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required to list tracked symlinks")
    listing = subprocess.run(
        [git, "ls-files", "--stage", "-z"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    broken: list[str] = []
    for entry in listing.split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        # Path.exists follows the symlink, so it is false when the target is missing.
        if (
            metadata.split(" ", 1)[0] == _SYMLINK_MODE
            and not (repository / path).exists()
        ):
            broken.append(path)
    return broken


def main():
    """Report every broken tracked symlink and exit nonzero if there are any."""
    broken = broken_symlinks(Path.cwd())
    for path in broken:
        print(f"broken symlink: {path}")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
