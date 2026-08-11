import io
import random
import select
import subprocess
import threading
import types
import typing
from pathlib import Path
from unittest import mock

import click.testing
import pytest

from tools.profiler import process_events, profiler, schema


class _Process:
    pid: int = 71
    returncode: int = 4

    def poll(self) -> int | None:
        return None

    def wait(self) -> int:
        return self.returncode


def _process() -> tuple[subprocess.Popen[str], _Process]:
    process = _Process()
    target = typing.cast("subprocess.Popen[str]", typing.cast("object", process))
    return target, process


def _target_process() -> process_events.TargetProcess:
    process, _ = _process()
    return process_events.TargetProcess(
        process=process,
        process_file_descriptor=31,
        trace_attached=False,
    )


def _capture_state(
    *,
    python_stack_observations: int = 0,
) -> profiler._CaptureState:  # pyright: ignore[reportPrivateUsage]
    return profiler._CaptureState(  # pyright: ignore[reportPrivateUsage]
        random_generator=random.Random(1),  # noqa: S311
        mode="wall",
        counts={
            "attempted": 0,
            "successful": 0,
            "discarded": 0,
            "missed": 0,
        },
        python_stack_observations=python_stack_observations,
    )


def _attached_runtime(
    attachment_pause_ns: int = 0,
) -> profiler._AttachedRuntime:  # pyright: ignore[reportPrivateUsage]
    return profiler._AttachedRuntime(  # pyright: ignore[reportPrivateUsage]
        runtime={
            "version": "3.14.0",
            "minor_version": "3.14",
            "free_threaded": True,
            "executable": {
                "path": "/python",
                "device": 1,
                "inode": 2,
            },
        },
        observed_ns=20,
        observed_target_running_ns=10,
        attachment_pause_ns=attachment_pause_ns,
    )


def _raw_profile(*, complete: bool, success: bool) -> schema.RawProfile:
    return schema.RawProfile(
        schema_version=schema.SCHEMA_VERSION,
        complete=complete,
        success=success,
        command=["target"],
        working_directory="/work",
        workload_path="/work/source.py",
        workload_sha256="0" * 64,
        sampling={
            "schedule": "poisson",
            "mean_interval_seconds": 0.01,
            "random_seed": 1,
            "attachment_timeout_seconds": 1,
            "mode": "wall",
        },
        sampling_statistics={
            "interval_count": 0,
            "minimum_interval_ns": None,
            "mean_interval_ns": None,
            "maximum_interval_ns": None,
            "total_pause_ns": 0,
            "discarded_rate": 0.0,
        },
        launcher_executable={"path": "/bin/sh", "device": 1, "inode": 1},
        python_runtime=None,
        lifecycle={
            "launched_ns": 0,
            "python_observed_ns": None,
            "python_observed_target_running_ns": None,
            "exited_ns": 1,
            "exited_target_running_ns": 1,
        },
        frames={},
        observations=[],
        failures=[],
        thread_lifecycles=[],
        observation_counts={
            "attempted": 0,
            "successful": 0,
            "discarded": 0,
            "missed": 0,
        },
        compiler_exit_status=0,
        diagnostics_status="none",
        interruption_signal=None,
    )


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
def test_cpu_observation_record_preserves_scheduler_runtime():
    writer = profiler._ProfileWriter(io.StringIO())  # pyright: ignore[reportPrivateUsage]
    evidence = profiler._ThreadEvidence(  # pyright: ignore[reportPrivateUsage]
        start_time_ticks=101,
        state="R",
        wait_channel="0",
        voluntary_context_switches=2,
        nonvoluntary_context_switches=3,
    )
    captured_thread = profiler._CapturedThread(  # pyright: ignore[reportPrivateUsage]
        os_thread_id=11,
        evidence=evidence,
        stopped_state="t",
        stack=[
            profiler._CapturedFrame(  # pyright: ignore[reportPrivateUsage]
                filename="source.py",
                function="work",
                line=7,
            )
        ],
        scheduler_runtime_ns=1234,
    )
    result = profiler._SuccessfulObservationResult(  # pyright: ignore[reportPrivateUsage]
        observation_index=0,
        scheduled_interval_ns=10,
        host_monotonic_ns=20,
        target_running_ns=15,
        pause_started_ns=20,
        pause_ended_ns=25,
        pause_duration_ns=5,
        process_id=9,
        threads=[captured_thread],
    )

    records, observation = writer.observation_record(result)

    expected_observation: schema.SuccessfulObservation = {
        "observation_index": 0,
        "scheduled_interval_ns": 10,
        "host_monotonic_ns": 20,
        "target_running_ns": 15,
        "pause_started_ns": 20,
        "pause_ended_ns": 25,
        "pause_duration_ns": 5,
        "process_id": 9,
        "status": "successful",
        "threads": [
            {
                "os_thread_id": 11,
                "start_time_ticks": 101,
                "pre_stop_state": "R",
                "wait_channel": "0",
                "voluntary_context_switches": 2,
                "nonvoluntary_context_switches": 3,
                "stopped_state": "t",
                "stack": [0],
                "scheduler_runtime_ns": 1234,
            }
        ],
    }
    assert observation == expected_observation
    assert records == [
        {
            "record_type": "frame",
            "frame": {
                "frame_id": 0,
                "filename": "source.py",
                "function": "work",
                "line": 7,
            },
        },
        {"record_type": "observation", "observation": expected_observation},
    ]


# PRF-002: Independent sampling schedule. PRF-004: No stale-stack reuse.
# PRF-024: Explicit failures.
def test_scheduled_exit_is_persisted_as_one_missed_observation(tmp_path: Path):
    target_process = _target_process()
    state = _capture_state()
    scheduled_observation = profiler._scheduled_observation  # pyright: ignore[reportPrivateUsage]
    processor = typing.cast(
        "profiler._ObservationProcessor",  # pyright: ignore[reportPrivateUsage]
        typing.cast("object", types.SimpleNamespace(failure_file_descriptor=33)),
    )

    with (
        mock.patch.object(
            process_events,
            "wait_for_schedule",
            autospec=True,
            return_value=process_events.ScheduleEvent.TARGET_EXITED,
        ),
    ):
        result, target_exited = scheduled_observation(
            target_process,
            state,
            processor,
            scheduled_interval_ns=250_000_000,
            launched_ns=100,
            timer_file_descriptor=32,
            event_file_descriptor=None,
        )

    assert target_exited is True
    assert isinstance(
        result,
        profiler._FailedObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert result.observation_index == 0
    assert result.scheduled_interval_ns == 250_000_000
    assert result.host_monotonic_ns >= 100
    assert result.target_running_ns == result.host_monotonic_ns - 100
    assert result.pause_started_ns == result.host_monotonic_ns
    assert result.pause_ended_ns == result.host_monotonic_ns
    assert result.pause_duration_ns == 0
    assert result.process_id == 71
    assert result.status == "missed"
    assert (
        result.failure_kind
        is schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
    )
    assert result.failure_reason == "the target exited before the scheduled stop"

    sample_state = _capture_state()
    sample_until_exit = profiler._sample_until_exit  # pyright: ignore[reportPrivateUsage]
    profile_path = tmp_path / "observations.jsonl"
    with profile_path.open("w", encoding="utf-8") as profile_file:
        writer = profiler._ProfileWriter(  # pyright: ignore[reportPrivateUsage]
            profile_file
        )
        with (
            mock.patch.object(
                profiler,
                "_next_interval_seconds",
                autospec=True,
                return_value=0.25,
            ),
            mock.patch.object(
                profiler,
                "_scheduled_observation",
                autospec=True,
                return_value=(result, True),
            ),
            mock.patch.object(
                process_events,
                "arm_schedule",
                autospec=True,
            ) as arm_schedule,
        ):
            sample_until_exit(
                target_process,
                writer,
                sample_state,
                _attached_runtime(),
                mean_interval_seconds=1,
                launched_ns=100,
                timer_file_descriptor=32,
                event_file_descriptor=None,
            )

    assert sample_state.total_pause_ns == 0
    assert sample_state.observation_pause_ns == 0
    assert sample_state.observation_times == [result.target_running_ns]
    assert sample_state.observation_index == 1
    assert sample_state.counts == {
        "attempted": 0,
        "successful": 0,
        "discarded": 0,
        "missed": 1,
    }
    arm_schedule.assert_called_once_with(32, 0.25)
    assert profile_path.read_text(encoding="utf-8")


def _missed_observation(
    observation_index: int,
) -> profiler._FailedObservationResult:  # pyright: ignore[reportPrivateUsage]
    return profiler._FailedObservationResult(  # pyright: ignore[reportPrivateUsage]
        observation_index=observation_index,
        scheduled_interval_ns=10,
        host_monotonic_ns=20 + observation_index,
        target_running_ns=15 + observation_index,
        pause_started_ns=20 + observation_index,
        pause_ended_ns=20 + observation_index,
        pause_duration_ns=0,
        process_id=71,
        status="missed",
        failure_kind=(
            schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
        ),
        failure_reason="target exited",
    )


# PRF-004: No stale-stack reuse. PRF-024: Explicit failures.
def test_discarded_observation_updates_attempted_and_discarded_counts():
    state = _capture_state()
    observation: schema.FailedObservation = {
        "observation_index": 0,
        "scheduled_interval_ns": 10,
        "host_monotonic_ns": 20,
        "target_running_ns": 15,
        "pause_started_ns": 20,
        "pause_ended_ns": 25,
        "pause_duration_ns": 5,
        "process_id": 71,
        "status": "discarded",
        "failure_kind": schema.ObservationFailureKind.INCONSISTENT_STACK,
        "failure_reason": "thread identity changed",
    }

    profiler._update_observation_state(  # pyright: ignore[reportPrivateUsage]
        state,
        observation,
        has_python_stack=False,
    )

    assert state.counts == {
        "attempted": 1,
        "successful": 0,
        "discarded": 1,
        "missed": 0,
    }


# PRF-004: No stale-stack reuse. PRF-007: Consistent stack.
# PRF-050: Minimal stopped section.
@pytest.mark.parametrize(
    ("evidence", "stopped_threads", "remote_thread_ids", "expected_reason"),
    [
        (
            {11: profiler._ThreadEvidence(101, "R", "0", 0, 0)},  # pyright: ignore[reportPrivateUsage]
            {11: profiler._StoppedThread(101, "t", None)},  # pyright: ignore[reportPrivateUsage]
            [12],
            "a Python thread changed identity during the observation",
        ),
        (
            {},
            {11: profiler._StoppedThread(101, "t", None)},  # pyright: ignore[reportPrivateUsage]
            [],
            "an OS thread changed identity during the observation",
        ),
        (
            {11: profiler._ThreadEvidence(102, "R", "0", 0, 0)},  # pyright: ignore[reportPrivateUsage]
            {11: profiler._StoppedThread(101, "t", None)},  # pyright: ignore[reportPrivateUsage]
            [],
            "an OS thread identifier was reused during the observation",
        ),
    ],
)
def test_normalization_discards_thread_identity_changes(
    evidence: dict[int, profiler._ThreadEvidence],  # pyright: ignore[reportPrivateUsage]
    stopped_threads: dict[int, profiler._StoppedThread],  # pyright: ignore[reportPrivateUsage]
    remote_thread_ids: list[int],
    expected_reason: str,
):
    remote_threads = [
        typing.cast(
            "profiler._RemoteThread",  # pyright: ignore[reportPrivateUsage]
            typing.cast(
                "object",
                types.SimpleNamespace(thread_id=thread_id, frames=[]),
            ),
        )
        for thread_id in remote_thread_ids
    ]
    raw_observation = profiler._RawObservation(  # pyright: ignore[reportPrivateUsage]
        observation_index=0,
        scheduled_interval_ns=10,
        host_monotonic_ns=20,
        target_running_ns=15,
        pause_started_ns=20,
        pause_ended_ns=25,
        pause_duration_ns=5,
        process_id=71,
        evidence=evidence,
        stopped_threads=stopped_threads,
        remote_threads=remote_threads,
    )

    result = profiler._normalize_observation(raw_observation)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(
        result,
        profiler._FailedObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert result.failure_kind is schema.ObservationFailureKind.INCONSISTENT_STACK
    assert result.failure_reason == (
        f"_InconsistentStackObservationError: {expected_reason}"
    )


# PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
def test_scheduled_observation_raises_processor_failure():
    expected_error = profiler._ObservationProcessorError(  # pyright: ignore[reportPrivateUsage]
        schema.CaptureFailureKind.PROFILE_WRITE_FAILED,
        "write failed",
    )

    class FailedProcessor:
        failure_file_descriptor: int = 33

        def raise_failure(self) -> typing.Never:
            raise expected_error

    processor = typing.cast(
        "profiler._ObservationProcessor",  # pyright: ignore[reportPrivateUsage]
        typing.cast("object", FailedProcessor()),
    )
    with (
        mock.patch.object(
            process_events,
            "wait_for_schedule",
            autospec=True,
            return_value=process_events.ScheduleEvent.PROCESSOR_FAILED,
        ),
        pytest.raises(profiler._ObservationProcessorError) as raised,  # pyright: ignore[reportPrivateUsage]
    ):
        _ = profiler._scheduled_observation(  # pyright: ignore[reportPrivateUsage]
            _target_process(),
            _capture_state(),
            processor,
            scheduled_interval_ns=10,
            launched_ns=0,
            timer_file_descriptor=32,
            event_file_descriptor=None,
        )

    assert raised.value is expected_error


# PRF-051: Schedule-isolated persistence.
def test_observation_processor_handoff_does_not_wait_for_processing():
    first_processing_started = threading.Event()
    release_first_observation = threading.Event()
    processed_indices: list[int] = []

    def persist_observation(
        _writer: object,
        _state: object,
        work: profiler._ObservationWork,  # pyright: ignore[reportPrivateUsage]
        _attached_runtime: object,
        _event_file_descriptor: object,
    ):
        processed_indices.append(work.observation_index)
        if work.observation_index == 0:
            first_processing_started.set()
            assert release_first_observation.wait(5)

    with (
        mock.patch.object(
            profiler,
            "_persist_observation",
            autospec=True,
            side_effect=persist_observation,
        ),
        profiler._ObservationProcessor(  # pyright: ignore[reportPrivateUsage]
            profiler._ProfileWriter(io.StringIO()),  # pyright: ignore[reportPrivateUsage]
            _capture_state(),
            _attached_runtime(),
            None,
        ) as processor,
    ):
        processor.submit(_missed_observation(0))
        assert first_processing_started.wait(5)
        processor.submit(_missed_observation(1))
        release_first_observation.set()

    assert processed_indices == [0, 1]


# PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
@pytest.mark.parametrize(
    ("processing_error", "expected_kind"),
    [
        (OSError("write failed"), schema.CaptureFailureKind.PROFILE_WRITE_FAILED),
        (
            TypeError("serialization failed"),
            schema.CaptureFailureKind.OBSERVATION_SERIALIZATION_FAILED,
        ),
    ],
)
def test_observation_processor_failure_signals_event(
    processing_error: OSError | TypeError,
    expected_kind: schema.CaptureFailureKind,
):
    processor = profiler._ObservationProcessor(  # pyright: ignore[reportPrivateUsage]
        profiler._ProfileWriter(io.StringIO()),  # pyright: ignore[reportPrivateUsage]
        _capture_state(),
        _attached_runtime(),
        None,
    )

    def process_until_failure():
        with processor:
            processor.submit(_missed_observation(0))
            readable, _, _ = select.select(
                [processor.failure_file_descriptor],
                [],
                [],
                5,
            )
            assert readable == [processor.failure_file_descriptor]

    with (
        mock.patch.object(
            profiler,
            "_persist_observation",
            autospec=True,
            side_effect=processing_error,
        ),
        pytest.raises(profiler._ObservationProcessorError) as raised,  # pyright: ignore[reportPrivateUsage]
    ):
        process_until_failure()

    assert raised.value.kind is expected_kind


# PRF-024: Explicit failures. PRF-051: Schedule-isolated persistence.
def test_observation_processor_discards_queued_work_after_failure():
    first_processing_started = threading.Event()
    release_first_observation = threading.Event()
    processed_indices: list[int] = []

    def persist_observation(
        _writer: object,
        _state: object,
        work: profiler._ObservationWork,  # pyright: ignore[reportPrivateUsage]
        _attached_runtime: object,
        _event_file_descriptor: object,
    ):
        processed_indices.append(work.observation_index)
        first_processing_started.set()
        assert release_first_observation.wait(5)
        raise OSError("write failed")

    processor = profiler._ObservationProcessor(  # pyright: ignore[reportPrivateUsage]
        profiler._ProfileWriter(io.StringIO()),  # pyright: ignore[reportPrivateUsage]
        _capture_state(),
        _attached_runtime(),
        None,
    )

    def process_work():
        with processor:
            processor.submit(_missed_observation(0))
            assert first_processing_started.wait(5)
            processor.submit(_missed_observation(1))
            release_first_observation.set()

    with (
        mock.patch.object(
            profiler,
            "_persist_observation",
            autospec=True,
            side_effect=persist_observation,
        ),
        pytest.raises(profiler._ObservationProcessorError),  # pyright: ignore[reportPrivateUsage]
    ):
        process_work()

    assert processed_indices == [0]


# PRF-002: Independent sampling schedule.
# PRF-051: Schedule-isolated persistence.
def test_next_deadline_is_armed_before_observation_handoff():
    timeline: list[str] = []
    first_result = _missed_observation(0)
    final_result = _missed_observation(1)

    def scheduled_observation(*_args: object, **_kwargs: object):
        timeline.append("capture")
        if timeline.count("capture") == 1:
            return first_result, False
        return final_result, True

    def arm_schedule(_timer_file_descriptor: int, _interval_seconds: float):
        timeline.append("arm")

    def submit_observation(
        _processor: profiler._ObservationProcessor,  # pyright: ignore[reportPrivateUsage]
        _work: profiler._ObservationWork,  # pyright: ignore[reportPrivateUsage]
    ):
        timeline.append("submit")

    with (
        mock.patch.object(
            profiler._ObservationProcessor,  # pyright: ignore[reportPrivateUsage]
            "submit",
            autospec=True,
            side_effect=submit_observation,
        ),
        mock.patch.object(
            profiler,
            "_next_interval_seconds",
            autospec=True,
            side_effect=[0.1, 0.2],
        ),
        mock.patch.object(
            profiler,
            "_scheduled_observation",
            autospec=True,
            side_effect=scheduled_observation,
        ),
        mock.patch.object(
            process_events,
            "arm_schedule",
            autospec=True,
            side_effect=arm_schedule,
        ),
    ):
        profiler._sample_until_exit(  # pyright: ignore[reportPrivateUsage]
            _target_process(),
            profiler._ProfileWriter(io.StringIO()),  # pyright: ignore[reportPrivateUsage]
            _capture_state(),
            _attached_runtime(),
            mean_interval_seconds=1,
            launched_ns=0,
            timer_file_descriptor=32,
            event_file_descriptor=None,
        )

    assert timeline == ["arm", "capture", "arm", "submit", "capture", "submit"]


# PRF-011: Complete invocation. PRF-026: No silent partial success.
@pytest.mark.parametrize(
    ("python_stack_observations", "records_failure"),
    [(0, True), (1, False)],
)
def test_attached_capture_requires_a_python_stack(
    python_stack_observations: int,
    *,
    records_failure: bool,
):
    target_process = _target_process()
    writer = profiler._ProfileWriter(io.StringIO())  # pyright: ignore[reportPrivateUsage]
    state = _capture_state(python_stack_observations=python_stack_observations)
    attached_runtime = _attached_runtime(attachment_pause_ns=7)
    expected_python: schema.ExecutableIdentity = {
        "path": "/python",
        "device": 1,
        "inode": 2,
    }
    capture_attached_process = profiler._capture_attached_process  # pyright: ignore[reportPrivateUsage]

    with (
        mock.patch.object(
            profiler,
            "_emit_profiler_event",
            autospec=True,
        ) as emit_event,
        mock.patch.object(
            profiler,
            "_attach_runtime",
            autospec=True,
            return_value=attached_runtime,
        ),
        mock.patch.object(
            profiler,
            "_sample_until_exit",
            autospec=True,
        ),
        mock.patch.object(
            profiler,
            "_record_capture_failure",
            autospec=True,
        ) as record_failure,
    ):
        exit_status = capture_attached_process(
            target_process,
            writer,
            state,
            expected_python,
            attachment_timeout_seconds=1,
            mean_interval_seconds=0.01,
            launched_ns=5,
            timer_file_descriptor=32,
            event_file_descriptor=33,
        )

    assert exit_status == 4
    assert state.attached_runtime == attached_runtime
    assert state.total_pause_ns == 7
    assert emit_event.mock_calls == [
        mock.call(33, "launcher-recorded"),
        mock.call(33, "python-attached"),
    ]
    if records_failure:
        record_failure.assert_called_once_with(
            writer,
            state,
            schema.CaptureFailureKind.TARGET_EXITED_BEFORE_VALID_STACK,
            "the target exited before a valid Python stack was observed",
            5,
            python_observed=True,
        )
    else:
        record_failure.assert_not_called()


# PRF-020: Machine and human interfaces. PRF-026: No silent partial success.
@pytest.mark.parametrize(
    ("complete", "success", "expected_exit_code", "expected_error"),
    [
        (False, False, 1, "Aborted!\n"),
        (True, False, 1, "Error: profile capture was not successful\n"),
        (True, True, 0, ""),
    ],
)
def test_main_reports_profile_completion_and_success(
    tmp_path: Path,
    *,
    complete: bool,
    success: bool,
    expected_exit_code: int,
    expected_error: str,
):
    profile_path = tmp_path / "profile.jsonl"
    workload_path = tmp_path / "source.py"
    _ = workload_path.write_text("pass\n", encoding="utf-8")
    captured_profile = _raw_profile(complete=complete, success=success)

    with mock.patch.object(
        profiler,
        "capture",
        autospec=True,
        return_value=captured_profile,
    ):
        result = click.testing.CliRunner().invoke(
            profiler.main,
            [
                "--profile",
                str(profile_path),
                "--workload",
                str(workload_path),
                "--",
                "target",
            ],
        )

    assert result.exit_code == expected_exit_code
    assert result.output.endswith(expected_error)
    assert (
        f"Capture: {'complete' if complete else 'incomplete'}; "
        f"{'successful' if success else 'unsuccessful'};"
    ) in result.output
