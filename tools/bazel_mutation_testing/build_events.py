"""Read what failed in a test run, or the coverage of each test, from build events."""

from __future__ import annotations

import pathlib
import urllib.parse
import urllib.request

import msgspec


class ActionFailure(msgspec.Struct, frozen=True):
    """A failed build action."""

    label: str
    mnemonic: str
    outputs_missing: bool
    """The action ran, but did not create an output that it declares."""
    output: str
    """What the action wrote to its standard output and then to its standard
    error."""

    def describe(self) -> str:
        """Return the failure as the results store records it."""
        description = f"{self.mnemonic} {self.label}"
        if self.outputs_missing:
            description += " (an output was not created)"
        return description


class TestFailure(msgspec.Struct, frozen=True):
    """A test that failed or timed out."""

    label: str
    timed_out: bool
    log: str
    """The test's log."""

    def describe(self) -> str:
        """Return the failure as the results store records it."""
        return self.label


class _TargetId(msgspec.Struct, frozen=True):
    label: str


class _EventId(msgspec.Struct, frozen=True, rename="camel"):
    test_result: _TargetId | None = None


class _Code(msgspec.Struct, frozen=True):
    code: str = ""


class _FailureDetail(msgspec.Struct, frozen=True):
    message: str = ""
    execution: _Code | None = None

    def outputs_missing(self) -> bool:
        # Local execution gives this code. Remote execution only says so in
        # its message, and fails the build with Bazel's remote error.
        return (
            self.execution is not None
            and self.execution.code == "ACTION_OUTPUTS_NOT_CREATED"
        ) or ("mandatory output" in self.message and "was not created" in self.message)


class _File(msgspec.Struct, frozen=True):
    uri: str
    name: str = ""


class _Action(msgspec.Struct, frozen=True, rename="camel"):
    success: bool = False
    type: str = ""
    label: str = ""
    failure_detail: _FailureDetail | None = None
    stdout: _File | None = None
    stderr: _File | None = None


def _read(file: _File | None) -> str:
    if file is None:
        return ""
    # Bazel names a local file only with --experimental_build_event_upload_strategy=local.
    if not file.uri.startswith("file://"):
        raise ValueError(f"Build events name a file that is not local: {file.uri}")
    # On Windows, a file URI's path starts with a slash before the drive, as in
    # file:///C:/work/test.log.
    path = urllib.request.url2pathname(urllib.parse.urlparse(file.uri).path)
    return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")


class _TestResult(msgspec.Struct, frozen=True, rename="camel"):
    status: str = ""
    test_action_output: list[_File] = msgspec.field(default_factory=list)

    def log(self) -> _File | None:
        return self._output("test.log")

    def coverage(self) -> _File | None:
        return self._output("test.lcov")

    def _output(self, name: str) -> _File | None:
        for output in self.test_action_output:
            if output.name == name:
                return output
        return None


class _Event(msgspec.Struct, frozen=True, rename="camel"):
    id: _EventId
    action: _Action | None = None
    test_result: _TestResult | None = None


def first_failure(
    build_event_file: pathlib.Path,
) -> ActionFailure | TestFailure | None:
    """Return the first failure in a run's build events, if any."""
    decoder = msgspec.json.Decoder(_Event)
    with build_event_file.open("rb") as events:
        for line in events:
            event = decoder.decode(line)
            # A failed test's action fails too, but its test result tells
            # whether it timed out.
            if (
                event.action is not None
                and not event.action.success
                and event.action.type != "TestRunner"
            ):
                failure_detail = event.action.failure_detail
                return ActionFailure(
                    label=event.action.label,
                    mnemonic=event.action.type,
                    outputs_missing=failure_detail is not None
                    and failure_detail.outputs_missing(),
                    output=_read(event.action.stdout) + _read(event.action.stderr),
                )
            if (
                event.test_result is not None
                and event.id.test_result is not None
                and event.test_result.status in {"FAILED", "TIMEOUT"}
            ):
                label = event.id.test_result.label
                return TestFailure(
                    label=label,
                    timed_out=event.test_result.status == "TIMEOUT",
                    log=_read(event.test_result.log()),
                )
    return None


def coverage_reports(build_event_file: pathlib.Path) -> dict[str, list[str]]:
    """Return the lcov coverage reports of each test, one for each of its shards."""
    decoder = msgspec.json.Decoder(_Event)
    reports: dict[str, list[str]] = {}
    with build_event_file.open("rb") as events:
        for line in events:
            event = decoder.decode(line)
            if event.test_result is not None and event.id.test_result is not None:
                reports.setdefault(event.id.test_result.label, []).append(
                    _read(event.test_result.coverage())
                )
    return reports
