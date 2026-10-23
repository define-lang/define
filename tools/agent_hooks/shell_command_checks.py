"""Claude Code and Codex hook for shell commands that remove worktrees or run uv.

Before `git worktree remove`, it expunges the worktree's Bazel output base, so
that no output base or Bazel server is left behind. Before `uv run`, it
runs `setup_local_dev` when the Bazel-generated files that it copies into the
source tree may be out of date.
"""

from __future__ import annotations

import dataclasses
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_BAZEL_FLAGS = ("--noshow_progress", "--ui_event_filters=-info")
_SEPARATOR_CHARACTERS = frozenset(";&|()\n")


class _ToolInput(TypedDict):
    command: str


class _PreToolUseHookInput(TypedDict):
    cwd: str
    tool_input: _ToolInput


@dataclasses.dataclass(frozen=True)
class _ProgramRun:
    # The directory it runs in, after any earlier cd in the same command.
    directory: Path
    program: str
    arguments: list[str]


def _removed_worktree(directory: Path, arguments: Sequence[str]) -> Path | None:
    for argument in arguments:
        if not argument.startswith("-"):
            return (directory / argument).resolve()
    return None


def _repository_toplevel(directory: Path, _arguments: Sequence[str]) -> Path:
    return Path(_git(directory, "rev-parse", "--show-toplevel").strip())


def _has_bazel_output_base(worktree: Path) -> bool:
    # Bazel creates this symlink when it first builds in a workspace.
    return (worktree / "bazel-out").is_symlink()


def _generated_files_may_be_stale(repository: Path) -> bool:
    # tools/setup_local_dev.py writes this after each successful run.
    stamp = (
        repository
        / _git(repository, "rev-parse", "--git-path", "setup-local-dev-stamp").strip()
    )
    if not stamp.exists():
        return True
    stamp_time = stamp.stat().st_mtime_ns
    # MODULE.bazel.lock pins the Bazel Python interpreter that the local venv
    # uses. Rust sources and templates build the native extensions and the
    # generated Rust sources that setup_local_dev copies.
    sources = _git(
        repository,
        "ls-files",
        "-z",
        "*.proto",
        "*.lark",
        "*.rs",
        "*.j2",
        "MODULE.bazel.lock",
    )
    for source in sources.split("\0"):
        if source and (repository / source).stat().st_mtime_ns > stamp_time:
            return True
    return False


@dataclasses.dataclass(frozen=True)
class _ShellCommandCheck:
    program: str
    # Words that must come next to each other among the program's arguments.
    subcommand: tuple[str, ...]
    # Takes the directory the program runs in and the arguments after the
    # subcommand, and returns where the check runs, if anywhere.
    finds_directory: Callable[[Path, Sequence[str]], Path | None]
    needs_run: Callable[[Path], bool]
    # Runs in each directory that needs it, before the shell command. A
    # failure does not stop the shell command.
    command: tuple[str, ...]
    shows_agent_failure_output: bool


_SHELL_COMMAND_CHECKS = (
    _ShellCommandCheck(
        program="git",
        subcommand=("worktree", "remove"),
        finds_directory=_removed_worktree,
        needs_run=_has_bazel_output_base,
        # Bazel moves the output base aside and deletes it in the background,
        # so the removal does not wait for the deletion.
        command=("bazelisk", "clean", *_BAZEL_FLAGS, "--expunge_async"),
        # A daily cleanup deletes output bases that outlive their workspace.
        shows_agent_failure_output=False,
    ),
    _ShellCommandCheck(
        program="uv",
        subcommand=("run",),
        finds_directory=_repository_toplevel,
        needs_run=_generated_files_may_be_stale,
        command=("bazelisk", "run", *_BAZEL_FLAGS, "//tools:setup_local_dev"),
        shows_agent_failure_output=True,
    ),
)


def _find_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"{name} is required by shell command checks")
    return executable


_GIT = _find_executable("git")


def _git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        [_GIT, *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _simple_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    simple_commands: list[list[str]] = [[]]
    # Redirections such as `2>&1` stay as words. Nothing reads the words after
    # the ones the checks look for.
    for word in lexer:
        if set(word) <= _SEPARATOR_CHARACTERS:
            simple_commands.append([])
        else:
            simple_commands[-1].append(word)
    return [words for words in simple_commands if words]


def _program_and_arguments(words: Sequence[str]) -> list[str]:
    """Return the words that name the program that runs, and its arguments."""
    index = 0
    # Variable assignments come before the program, as in `FOO=1 uv run`.
    while (
        index < len(words)
        and "=" in words[index]
        and words[index].split("=", 1)[0].isidentifier()
    ):
        index += 1
    return list(words[index:])


def _program_runs(hook_directory: Path, command: str) -> list[_ProgramRun]:
    directory = hook_directory
    program_runs: list[_ProgramRun] = []
    for words in _simple_commands(command):
        program_and_arguments = _program_and_arguments(words)
        if not program_and_arguments:
            continue
        program = Path(program_and_arguments[0]).name
        arguments = program_and_arguments[1:]
        if program == "cd":
            directory /= arguments[0]
        else:
            program_runs.append(_ProgramRun(directory, program, arguments))
    return program_runs


def _check_directories(
    check: _ShellCommandCheck, program_runs: Sequence[_ProgramRun]
) -> list[Path]:
    directories: list[Path] = []
    length = len(check.subcommand)
    for program_run in program_runs:
        if program_run.program != check.program:
            continue
        arguments = program_run.arguments
        for start in range(len(arguments) - length + 1):
            if tuple(arguments[start : start + length]) == check.subcommand:
                directory = check.finds_directory(
                    program_run.directory, arguments[start + length :]
                )
                if directory is not None and directory not in directories:
                    directories.append(directory)
                break
    return directories


def _run_command(
    directory: Path, command: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_find_executable(command[0]), *command[1:]],
        cwd=directory,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def main():
    """Read the PreToolUse hook input and act on the shell command it names."""
    hook_input = cast("_PreToolUseHookInput", json.load(sys.stdin))
    program_runs = _program_runs(
        Path(hook_input["cwd"]), hook_input["tool_input"]["command"]
    )

    failure_reports: list[str] = []
    for check in _SHELL_COMMAND_CHECKS:
        for directory in _check_directories(check, program_runs):
            if not check.needs_run(directory):
                continue
            result = _run_command(directory, check.command)
            if result.returncode != 0 and check.shows_agent_failure_output:
                failure_reports.append(
                    f"`{' '.join(check.command)}` failed in {directory} before"
                    + f" this command ran. Its output:\n{result.stdout}"
                )
    if failure_reports:
        # Both agents give this to the model without blocking the command.
        hook_specific_output = {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n\n".join(failure_reports),
        }
        print(json.dumps({"hookSpecificOutput": hook_specific_output}))


if __name__ == "__main__":
    main()
