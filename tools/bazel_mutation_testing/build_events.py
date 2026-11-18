"""Read what failed in a `bazel test` run from its build events."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    import pathlib


class ActionFailure(msgspec.Struct, frozen=True):
    """A failed build action."""

    label: str
    mnemonic: str

    def describe(self) -> str:
        """Return the failure as the results store records it."""
        return f"{self.mnemonic} {self.label}"


class TestFailure(msgspec.Struct, frozen=True):
    """A test that failed or timed out."""

    label: str
    timed_out: bool

    def describe(self) -> str:
        """Return the failure as the results store records it."""
        return self.label


class _TargetId(msgspec.Struct, frozen=True):
    label: str


class _EventId(msgspec.Struct, frozen=True, rename="camel"):
    test_result: _TargetId | None = None


class _Action(msgspec.Struct, frozen=True):
    success: bool = False
    type: str = ""
    label: str = ""


class _TestResult(msgspec.Struct, frozen=True):
    status: str = ""


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
                return ActionFailure(
                    label=event.action.label, mnemonic=event.action.type
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
                )
    return None
