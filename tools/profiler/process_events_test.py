from __future__ import annotations

import os
import time
import typing

import pytest

from tools.profiler import process_events

if typing.TYPE_CHECKING:
    import subprocess


class _Process:
    pid: int = 71
    returncode: int | None = None


def _target_process(
    process_file_descriptor: int,
) -> process_events.TargetProcess:
    process = typing.cast(
        "subprocess.Popen[str]",
        typing.cast("object", _Process()),
    )
    return process_events.TargetProcess(
        process=process,
        process_file_descriptor=process_file_descriptor,
        trace_attached=False,
    )


# PRF-002: Independent sampling schedule. PRF-049: Event-driven coordination.
# PRF-051: Schedule-isolated persistence.
@pytest.mark.parametrize(
    ("ready_file_descriptor", "expected_event"),
    [
        ("processor", process_events.ScheduleEvent.PROCESSOR_FAILED),
        ("target", process_events.ScheduleEvent.TARGET_EXITED),
        ("timer", process_events.ScheduleEvent.DEADLINE),
    ],
)
def test_schedule_wait_reports_the_readable_event(
    ready_file_descriptor: str,
    expected_event: process_events.ScheduleEvent,
):
    target_file_descriptor = os.eventfd(0, os.EFD_CLOEXEC)
    timer_file_descriptor = os.timerfd_create(
        time.CLOCK_MONOTONIC,
        flags=os.TFD_CLOEXEC,
    )
    processor_file_descriptor = os.eventfd(0, os.EFD_CLOEXEC)
    try:
        if ready_file_descriptor == "processor":
            os.eventfd_write(processor_file_descriptor, 1)
        elif ready_file_descriptor == "target":
            os.eventfd_write(target_file_descriptor, 1)
        else:
            process_events.arm_schedule(timer_file_descriptor, 0.001)
        event = process_events.wait_for_schedule(
            _target_process(target_file_descriptor),
            timer_file_descriptor,
            processor_file_descriptor,
        )
    finally:
        os.close(processor_file_descriptor)
        os.close(timer_file_descriptor)
        os.close(target_file_descriptor)

    assert event is expected_event
