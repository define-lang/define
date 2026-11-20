"""Run Bazel in a worktree."""

from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, final

import msgspec

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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


# The tester does not mutate the sources of targets with this tag, such as code
# generators.
NO_MUTATION_TAG = "no-mutation"


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


# Each worker has its own Bazel server, so several servers run at once. Without
# a limit, each server's heap grows to a quarter of the machine's memory before
# the JVM collects it. A server stays running for hours after a run unless it
# exits when idle. A worker is never idle for long during a run.
_STARTUP_OPTIONS = ("--host_jvm_args=-Xmx3g", "--max_idle_secs=300")


def _command(arguments: list[str]) -> list[str]:
    return [
        executable("bazelisk"),
        *_STARTUP_OPTIONS,
        arguments[0],
        "--noshow_progress",
        "--ui_event_filters=-info",
        *arguments[1:],
    ]


def start(workspace: pathlib.Path, arguments: list[str]) -> subprocess.Popen[str]:
    """Start `bazelisk` in `workspace`, with pipes for its output."""
    return subprocess.Popen(
        _command(arguments),
        cwd=workspace,
        env=child_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run(
    workspace: pathlib.Path, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    """Run `bazelisk` in `workspace`, capturing its output."""
    return subprocess.run(
        _command(arguments),
        cwd=workspace,
        env=child_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


# Bazel exits with these codes when its server runs out of memory or fails in
# another way that has nothing to do with what it builds.
SERVER_FAILURE_EXIT_CODES = frozenset({33, 37})

# A server that no longer responds may not respond to a request to exit either.
_KILL = signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL


def output_base(workspace: pathlib.Path) -> pathlib.Path:
    """Return the output base of `workspace`'s Bazel server."""
    return pathlib.Path(run_checked(workspace, ["info", "output_base"]).strip())


def kill_server(base: pathlib.Path):
    """Kill the Bazel server of the output base `base`, also when the server no longer responds.

    A Bazel client whose server exits fails, and the next command starts a new
    server.
    """
    process = int((base / "server/server.pid.txt").read_text(encoding="utf-8"))
    # The server can exit by itself before it is killed.
    with contextlib.suppress(ProcessLookupError):
        os.kill(process, _KILL)


@final
class Progress:
    """Tells when a Bazel command has written no build events for too long."""

    def __init__(
        self,
        build_event_file: pathlib.Path,
        silent_seconds: float,
        clock: Callable[[], float],
    ):
        """Watch `build_event_file`, which a command that started now writes.

        The command has stopped responding once the file has not changed for
        `silent_seconds`, as `clock` measures them.
        """
        self._build_event_file = build_event_file
        self._silent_seconds = silent_seconds
        self._clock = clock
        self._size = self._current_size()
        self._changed = clock()

    def stalled(self) -> bool:
        """Return whether the command has written no build event for too long."""
        size = self._current_size()
        now = self._clock()
        if size != self._size:
            self._size = size
            self._changed = now
            return False
        return now - self._changed >= self._silent_seconds

    def _current_size(self) -> int:
        try:
            return self._build_event_file.stat().st_size
        except FileNotFoundError:
            # Bazel creates the file once the command starts.
            return 0


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


def query_expression(patterns: Iterable[str]) -> str:
    """Return the query expression for target patterns.

    As in `bazel test`, a pattern that starts with `-` removes its targets.
    """
    expression = ""
    for pattern in patterns:
        if pattern.startswith("-"):
            expression += f" - {pattern.removeprefix('-')}"
        elif expression:
            expression += f" + {pattern}"
        else:
            expression = pattern
    return expression


class Attribute(msgspec.Struct, frozen=True, rename="camel"):
    """An attribute of a rule in a query's `streamed_jsonproto` output."""

    name: str
    string_value: str = ""
    string_list_value: list[str] = msgspec.field(default_factory=list)
    boolean_value: bool = False


class Rule(msgspec.Struct, frozen=True, rename="camel"):
    """A rule in a query's `streamed_jsonproto` output."""

    name: str
    rule_class: str
    attribute: list[Attribute]

    def value(self, name: str) -> Attribute:
        """Return the attribute named `name`.

        Raises:
            KeyError: The rule has no such attribute.
        """
        for attribute in self.attribute:
            if attribute.name == name:
                return attribute
        raise KeyError(name)


class _Target(msgspec.Struct, frozen=True):
    rule: Rule


def rules(output: str) -> list[Rule]:
    """Return the rules in a query's `streamed_jsonproto` output."""
    decoder = msgspec.json.Decoder(_Target)
    return [decoder.decode(line).rule for line in output.splitlines()]


def source_path(label: str) -> str:
    """Return the workspace-relative path of the source file `label`."""
    package, name = label.removeprefix("//").split(":", 1)
    return f"{package}/{name}" if package else name
