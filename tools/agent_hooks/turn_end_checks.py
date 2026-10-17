"""Claude Code and Codex Stop hook that runs checks on the changed files.

It formats, fixes Python BUILD dependencies, and lints changed protos. When a
step fails, it asks the agent to keep working with the failures as feedback, at
most once per turn. It does nothing when no file has changed since the last
time every step passed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_BAZEL_FLAGS = ("--noshow_progress", "--ui_event_filters=-info")


class _StopHookInput(TypedDict):
    cwd: str
    stop_hook_active: bool


@dataclasses.dataclass(frozen=True)
class _Command:
    arguments: tuple[str, ...]
    # Appends the changed paths that the step applies to.
    passes_paths: bool = False


@dataclasses.dataclass(frozen=True)
class _ChangedPath:
    # Relative to the top of the repository.
    path: str
    deleted: bool


@dataclasses.dataclass(frozen=True)
class _TurnEndStep:
    # The step runs when any changed path matches.
    applies_to: Callable[[_ChangedPath], bool]
    commands: tuple[_Command, ...]


@dataclasses.dataclass(frozen=True)
class _FailedCommand:
    command: str
    command_output: str


def _any_path(_changed: _ChangedPath) -> bool:
    return True


def _existing_python_dependency_owner(changed: _ChangedPath) -> bool:
    # Deleted files have no targets left to fix.
    return not changed.deleted and (
        changed.path.endswith((".py", ".pyi"))
        or Path(changed.path).name == "BUILD.bazel"
    )


def _linted_by_buf(changed: _ChangedPath) -> bool:
    return changed.path.startswith(("defcl/schema/", "define/config/"))


# Steps run in this order, so BUILD dependency fixes come before format, and
# buf lint reads formatted files.
_TURN_END_STEPS = (
    _TurnEndStep(
        applies_to=_existing_python_dependency_owner,
        commands=(
            _Command(("uv", "run", "tools/check_python_deps.py"), passes_paths=True),
        ),
    ),
    _TurnEndStep(
        applies_to=_any_path,
        commands=(_Command(("bazelisk", "run", *_BAZEL_FLAGS, "//:format")),),
    ),
    _TurnEndStep(
        applies_to=_linted_by_buf,
        commands=(
            # buf.yaml loads its lint plugin from bazel-bin.
            _Command(("bazelisk", "build", *_BAZEL_FLAGS, "//defcl/buf")),
            _Command(
                (
                    "bazelisk",
                    "run",
                    *_BAZEL_FLAGS,
                    "@multitool//tools/buf:cwd",
                    "--",
                    "lint",
                )
            ),
        ),
    ),
)


def _find_git() -> str:
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required to find changed files")
    return git


_GIT = _find_git()


def _git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        [_GIT, *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _changed_paths(repository: Path) -> list[_ChangedPath]:
    # These are the same paths that `//:format` formats by default. git status
    # finds them much faster than git diff plus git ls-files, because it uses
    # the untracked cache and fsmonitor. It must not take the index lock, which
    # would make the user's own git commands fail while the hook runs.
    status = _git(
        repository,
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "-z",
        "--no-renames",
    )
    changed: list[_ChangedPath] = []
    untracked_directories: list[str] = []
    for entry in status.split("\0"):
        if not entry:
            continue
        path = entry[3:]
        # Status lists a wholly untracked directory instead of its files.
        if entry.startswith("??") and path.endswith("/"):
            untracked_directories.append(path)
        else:
            # The first status letter is the index and the second is the
            # working tree, which is blank after a staged deletion.
            deleted = entry[1] == "D" or entry[:2] == "D "
            changed.append(_ChangedPath(path, deleted))
    if untracked_directories:
        untracked_files = _git(
            repository,
            "ls-files",
            "-z",
            "--others",
            "--exclude-standard",
            "--",
            *untracked_directories,
        )
        for path in untracked_files.split("\0"):
            if path:
                changed.append(_ChangedPath(path, deleted=False))
    return changed


def _working_tree_fingerprint(repository: Path, changed: Sequence[_ChangedPath]) -> str:
    digest = hashlib.sha256()
    for changed_path in changed:
        if changed_path.deleted:
            digest.update(f"{changed_path.path}\0deleted\n".encode())
        else:
            status = (repository / changed_path.path).lstat()
            digest.update(
                f"{changed_path.path}\0{status.st_mtime_ns}\0{status.st_size}\n".encode()
            )
    return digest.hexdigest()


def _fingerprint_path(repository: Path) -> Path:
    # The git directory is per worktree and outside the working tree, so the
    # fingerprint never shows up as a change itself.
    return (
        repository
        / _git(
            repository, "rev-parse", "--git-path", "agent-hooks/turn-end-fingerprint"
        ).strip()
    )


def _run_command(
    repository: Path, arguments: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(arguments[0])
    if executable is None:
        raise FileNotFoundError(f"{arguments[0]} is required by turn-end checks")
    return subprocess.run(
        [executable, *arguments[1:]],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _run_turn_end_steps(
    repository: Path, changed: Sequence[_ChangedPath]
) -> list[_FailedCommand]:
    failed_commands: list[_FailedCommand] = []
    for step in _TURN_END_STEPS:
        step_paths: list[str] = []
        for changed_path in changed:
            if step.applies_to(changed_path):
                step_paths.append(changed_path.path)
        if not step_paths:
            continue
        for command in step.commands:
            arguments = list(command.arguments)
            if command.passes_paths:
                arguments.extend(step_paths)
            result = _run_command(repository, arguments)
            if result.returncode != 0:
                failed_commands.append(
                    _FailedCommand(" ".join(arguments), result.stdout)
                )
                break
    return failed_commands


def _failure_report(failed_commands: Sequence[_FailedCommand]) -> str:
    sections = ["These turn-end checks failed. Fix them:"]
    for failed_command in failed_commands:
        sections.append(
            f"$ {failed_command.command}\n{failed_command.command_output.rstrip()}"
        )
    return "\n\n".join(sections)


def main():
    """Read the Stop hook input and print the hook's response, if any."""
    hook_input = cast("_StopHookInput", json.load(sys.stdin))
    repository = Path(
        _git(Path(hook_input["cwd"]), "rev-parse", "--show-toplevel").strip()
    )
    changed = _changed_paths(repository)
    if not changed:
        return
    fingerprint_path = _fingerprint_path(repository)
    if fingerprint_path.exists() and fingerprint_path.read_text() == (
        _working_tree_fingerprint(repository, changed)
    ):
        return
    failed_commands = _run_turn_end_steps(repository, changed)
    # The fingerprint is taken after the steps so that their own fixes do not
    # count as changes. A failure is not recorded, so it is checked again at
    # every end of turn until it is fixed.
    if not failed_commands:
        fingerprint_path.parent.mkdir(exist_ok=True)
        _ = fingerprint_path.write_text(
            _working_tree_fingerprint(repository, _changed_paths(repository))
        )
        return
    report = _failure_report(failed_commands)
    # A second continuation could loop forever on a failure the agent cannot
    # fix, so the second time only the user hears about it.
    if hook_input["stop_hook_active"]:
        print(json.dumps({"systemMessage": report}))
    else:
        print(json.dumps({"decision": "block", "reason": report}))


if __name__ == "__main__":
    main()
