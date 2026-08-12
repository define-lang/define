import dataclasses
import io
import os
import random
import select
import signal
import subprocess
import threading
import types
import typing
from pathlib import Path
from unittest import mock

import click.testing
import pytest

from tools.profiler import process_events, profiler, remote_frame_names, schema


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
    python_stack_observed: bool = False,
) -> profiler._CaptureState:  # pyright: ignore[reportPrivateUsage]
    return profiler._CaptureState(  # pyright: ignore[reportPrivateUsage]
        random_generator=random.Random(1),  # noqa: S311
        mode="wall",
        python_stack_observed=python_stack_observed,
    )


def _attached_runtime() -> profiler._AttachedRuntime:  # pyright: ignore[reportPrivateUsage]
    return profiler._AttachedRuntime(  # pyright: ignore[reportPrivateUsage]
        runtime={
            "version": "3.14.0",
            "free_threaded": True,
            "executable": {
                "path": "/python",
                "device": 1,
                "inode": 2,
            },
        },
        observed_ns=20,
        observed_target_running_ns=10,
    )


def _observation_timing() -> schema.ObservationBase:
    return {
        "scheduled_interval_ns": 10,
        "target_running_ns": 15,
        "pause_started_ns": 20,
        "pause_ended_ns": 25,
    }


def _raw_stopped_thread(
    os_thread_id: int,
    start_time_ticks: int,
    *,
    state: str = "t",
    schedstat: bytes | None = None,
) -> profiler._RawStoppedThread:  # pyright: ignore[reportPrivateUsage]
    fields_before_start_time = " ".join(["0"] * 18)
    stat = (
        f"{os_thread_id} (python worker) {state} "
        f"{fields_before_start_time} {start_time_ticks} 0\n"
    ).encode("ascii")
    return profiler._RawStoppedThread(  # pyright: ignore[reportPrivateUsage]
        os_thread_id=str(os_thread_id),
        stat=stat,
        schedstat=schedstat,
    )


def _raw_profile(*, complete: bool, success: bool) -> schema.RawProfile:
    observations: list[schema.Observation] = []
    frames: dict[int, schema.Frame] = {}
    if success:
        frames[0] = {"filename": "source.py", "function": "work", "line": 1}
        observations.append(
            {
                "scheduled_interval_ns": 10,
                "target_running_ns": 1,
                "pause_started_ns": 1,
                "pause_ended_ns": 1,
                "status": "successful",
                "threads": [
                    {
                        "os_thread_id": 71,
                        "start_time_ticks": 1,
                        "pre_stop_state": "R",
                        "stack": [0],
                    }
                ],
            }
        )
    return schema.RawProfile(
        schema_version=schema.SCHEMA_VERSION,
        process_id=71,
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
            "minimum_interval_ns": None,
            "mean_interval_ns": None,
            "maximum_interval_ns": None,
            "total_pause_ns": 0,
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
        frames=frames,
        observations=observations,
        failures=[],
        observation_counts={
            "successful": len(observations),
            "discarded": 0,
            "missed": 0,
        },
        compiler_exit_status=0 if success else (-signal.SIGTERM if not complete else 1),
        diagnostics_status="none",
        interruption_signal=None if complete else signal.SIGTERM,
    )


def _qualified_remote_unwinder() -> remote_frame_names.QualifiedRemoteUnwinder:
    resolver = remote_frame_names.QualifiedRemoteUnwinder.__new__(
        remote_frame_names.QualifiedRemoteUnwinder
    )
    resolver._process_id = 71  # pyright: ignore[reportPrivateUsage]
    resolver._debug_offsets = remote_frame_names._DebugOffsets(  # pyright: ignore[reportPrivateUsage]
        runtime_interpreters_head=0,
        interpreter_next=0,
        interpreter_threads_head=0,
        thread_next=0,
        thread_current_frame=0,
        thread_native_id=0,
        frame_previous=8,
        frame_localsplus=16,
        pyobject_type=24,
        type_name=32,
    )
    resolver._type_names = {}  # pyright: ignore[reportPrivateUsage]
    return resolver


def test_remote_unwinder_copies_generated_dataclass_type_name():
    resolver = _qualified_remote_unwinder()
    remote_frame = types.SimpleNamespace(
        filename="<string>",
        funcname="__create_fn__.<locals>.__init__",
        lineno=4,
    )
    remote_thread = types.SimpleNamespace(thread_id=17, frame_info=[remote_frame])

    with (
        mock.patch.object(
            resolver,
            "_thread_frames",
            autospec=True,
            return_value={17: 100},
        ),
        mock.patch.object(
            resolver,
            "_dataclass_type_name",
            autospec=True,
            return_value=b"Sampled\0" + bytes(504),
        ),
        mock.patch.object(
            remote_frame_names,
            "_remote_memory",
            autospec=True,
            return_value=io.BytesIO(),
        ),
    ):
        frame_names = resolver._capture_frame_names(  # pyright: ignore[reportPrivateUsage]
            [remote_thread]
        )

    assert frame_names == [(17, 0, b"Sampled\0" + bytes(504))]


def test_remote_unwinder_copies_multiple_names_from_matching_thread():
    resolver = _qualified_remote_unwinder()
    ordinary_frame = types.SimpleNamespace(
        filename="compiler.py",
        funcname="compile",
        lineno=3,
    )
    generated_frame = types.SimpleNamespace(
        filename="<string>",
        funcname="__create_fn__.<locals>.__init__",
        lineno=4,
    )
    matching_thread = types.SimpleNamespace(
        thread_id=17,
        frame_info=[ordinary_frame, generated_frame, ordinary_frame, generated_frame],
    )
    ordinary_thread = types.SimpleNamespace(thread_id=18, frame_info=[ordinary_frame])

    with (
        mock.patch.object(
            resolver,
            "_thread_frames",
            autospec=True,
            return_value={17: 100},
        ),
        mock.patch.object(
            resolver,
            "_dataclass_type_name",
            autospec=True,
            side_effect=[b"First\0", b"Second\0"],
        ),
        mock.patch.object(
            remote_frame_names,
            "_remote_memory",
            autospec=True,
            return_value=io.BytesIO(),
        ),
        mock.patch.object(
            remote_frame_names,
            "_read_pointer",
            autospec=True,
            side_effect=[200, 300, 400],
        ),
    ):
        frame_names = resolver._capture_frame_names(  # pyright: ignore[reportPrivateUsage]
            [matching_thread, ordinary_thread]
        )

    assert frame_names == [(17, 1, b"First\0"), (17, 3, b"Second\0")]


def test_remote_unwinder_skips_remote_reads_without_generated_constructor():
    resolver = _qualified_remote_unwinder()
    remote_frame = types.SimpleNamespace(
        filename="compiler.py",
        funcname="compile",
        lineno=4,
    )
    remote_thread = types.SimpleNamespace(thread_id=17, frame_info=[remote_frame])

    with mock.patch.object(
        remote_frame_names,
        "_remote_memory",
        autospec=True,
    ) as remote_memory:
        frame_names = resolver._capture_frame_names(  # pyright: ignore[reportPrivateUsage]
            [remote_thread]
        )

    assert frame_names == []
    remote_memory.assert_not_called()


def test_remote_unwinder_reads_matching_interpreter_thread_frame():
    resolver = _qualified_remote_unwinder()
    resolver._runtime_address = 1_000  # pyright: ignore[reportPrivateUsage]
    resolver._debug_offsets = remote_frame_names._DebugOffsets(  # pyright: ignore[reportPrivateUsage]
        runtime_interpreters_head=0,
        interpreter_next=8,
        interpreter_threads_head=16,
        thread_next=24,
        thread_current_frame=32,
        thread_native_id=40,
        frame_previous=48,
        frame_localsplus=56,
        pyobject_type=64,
        type_name=72,
    )
    memory = typing.cast(
        "remote_frame_names._Readable",  # pyright: ignore[reportPrivateUsage]
        io.BytesIO(),
    )
    pointers = {
        1_000: 2_000,
        2_016: 3_000,
        3_040: 17,
        3_032: 4_000,
        3_024: 3_100,
        3_140: 18,
        3_124: 0,
        2_008: 0,
    }

    def read_pointer(_memory: object, address: int) -> int:
        return pointers[address]

    with mock.patch.object(
        remote_frame_names,
        "_read_pointer",
        autospec=True,
        side_effect=read_pointer,
    ):
        frames = resolver._thread_frames(  # pyright: ignore[reportPrivateUsage]
            memory,
            {17: [0]},
        )

    assert frames == {17: 4_000}


def test_remote_unwinder_reads_each_matching_interpreter_thread_frame():
    resolver = _qualified_remote_unwinder()
    resolver._runtime_address = 1_000  # pyright: ignore[reportPrivateUsage]
    resolver._debug_offsets = remote_frame_names._DebugOffsets(  # pyright: ignore[reportPrivateUsage]
        runtime_interpreters_head=0,
        interpreter_next=8,
        interpreter_threads_head=16,
        thread_next=24,
        thread_current_frame=32,
        thread_native_id=40,
        frame_previous=48,
        frame_localsplus=56,
        pyobject_type=64,
        type_name=72,
    )
    memory = typing.cast(
        "remote_frame_names._Readable",  # pyright: ignore[reportPrivateUsage]
        io.BytesIO(),
    )
    pointers = {
        1_000: 2_000,
        2_016: 3_000,
        3_040: 17,
        3_032: 4_000,
        3_024: 3_100,
        3_140: 19,
        3_124: 3_200,
        3_240: 18,
        3_232: 4_100,
    }

    def read_pointer(_memory: object, address: int) -> int:
        return pointers[address]

    with mock.patch.object(
        remote_frame_names,
        "_read_pointer",
        autospec=True,
        side_effect=read_pointer,
    ):
        frames = resolver._thread_frames(  # pyright: ignore[reportPrivateUsage]
            memory,
            {17: [0], 18: [0]},
        )

    assert frames == {17: 4_000, 18: 4_100}


def test_remote_unwinder_finishes_search_when_matching_thread_is_absent():
    resolver = _qualified_remote_unwinder()
    resolver._runtime_address = 1_000  # pyright: ignore[reportPrivateUsage]
    resolver._debug_offsets = remote_frame_names._DebugOffsets(  # pyright: ignore[reportPrivateUsage]
        runtime_interpreters_head=0,
        interpreter_next=8,
        interpreter_threads_head=16,
        thread_next=24,
        thread_current_frame=32,
        thread_native_id=40,
        frame_previous=48,
        frame_localsplus=56,
        pyobject_type=64,
        type_name=72,
    )
    memory = typing.cast(
        "remote_frame_names._Readable",  # pyright: ignore[reportPrivateUsage]
        io.BytesIO(),
    )
    pointers = {
        1_000: 2_000,
        2_016: 3_000,
        3_040: 18,
        3_024: 0,
        2_008: 0,
    }

    def read_pointer(_memory: object, address: int) -> int:
        return pointers[address]

    with mock.patch.object(
        remote_frame_names,
        "_read_pointer",
        autospec=True,
        side_effect=read_pointer,
    ):
        frames = resolver._thread_frames(  # pyright: ignore[reportPrivateUsage]
            memory,
            {17: [0]},
        )

    assert frames == {}


def test_remote_unwinder_streams_only_matching_executable_mappings():
    maps = """\
1000-2000 r-xp 00000000 00:00 41 /other
3000-4000 r-xp 00001000 00:00 42 /python
"""
    with mock.patch.object(Path, "read_text", autospec=True, return_value=maps):
        mappings = list(
            remote_frame_names._executable_mappings(  # pyright: ignore[reportPrivateUsage]
                71,
                42,
            )
        )

    assert mappings == [(0x3000, 0x4000, 0x1000)]


def test_remote_runtime_address_requires_a_local_runtime_mapping():
    def address_of(_value: object) -> int:
        return 123

    def in_dll(_python_api: object, _name: str) -> object:
        return object()

    with (
        mock.patch.object(
            remote_frame_names,
            "ctypes",
            new=types.SimpleNamespace(
                addressof=address_of,
                c_char=types.SimpleNamespace(in_dll=in_dll),
                pythonapi=object(),
            ),
        ),
        mock.patch.object(Path, "stat", autospec=True),
        mock.patch.object(
            remote_frame_names,
            "_executable_mappings",
            autospec=True,
            return_value=iter(()),
        ),
        pytest.raises(ValueError, match="profiler's Python runtime was not mapped"),
    ):
        _ = remote_frame_names._runtime_address(71)  # pyright: ignore[reportPrivateUsage]


def test_remote_unwinder_caches_dataclass_type_name():
    resolver = _qualified_remote_unwinder()
    memory = typing.cast(
        "remote_frame_names._Readable",  # pyright: ignore[reportPrivateUsage]
        io.BytesIO(),
    )

    with (
        mock.patch.object(
            remote_frame_names,
            "_read_pointer",
            autospec=True,
            side_effect=[101, 200, 300, 101, 200],
        ),
        mock.patch.object(
            remote_frame_names,
            "_read_exact",
            autospec=True,
            return_value=b"Sampled\0" + bytes(504),
        ) as read_exact,
    ):
        first_name = resolver._dataclass_type_name(  # pyright: ignore[reportPrivateUsage]
            memory,
            100,
        )
        second_name = resolver._dataclass_type_name(  # pyright: ignore[reportPrivateUsage]
            memory,
            100,
        )

    assert first_name == b"Sampled\0" + bytes(504)
    assert second_name == b"Sampled\0" + bytes(504)
    read_exact.assert_called_once_with(memory, 300, 512)


def test_remote_unwinder_decodes_copied_type_name():
    raw_type_name = b"Sampled\0" + bytes(504)
    with mock.patch.object(
        remote_frame_names,
        "_decode_c_string",
        autospec=True,
        return_value="Sampled",
    ) as decode_c_string:
        frame_names = remote_frame_names.decode_frame_names(
            [(17, 0, raw_type_name), (18, 2, raw_type_name)]
        )

    assert frame_names == {
        (17, 0): "Sampled.__init__",
        (18, 2): "Sampled.__init__",
    }
    decode_c_string.assert_called_once_with(raw_type_name)


def test_normalization_applies_copied_dataclass_type_name():
    remote_frame = types.SimpleNamespace(
        filename="<string>",
        funcname="__create_fn__.<locals>.__init__",
        lineno=4,
    )
    remote_thread = types.SimpleNamespace(thread_id=17, frame_info=[remote_frame])
    raw_observation = profiler._RawObservation(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        evidence={17: profiler._ThreadEvidence(101, "R")},  # pyright: ignore[reportPrivateUsage]
        stopped_threads=[_raw_stopped_thread(17, 101)],
        remote_threads=typing.cast(
            "list[remote_frame_names.RemoteThread]",
            [remote_thread],
        ),
        frame_names=[(17, 0, b"Sampled\0" + bytes(504))],
    )

    result = profiler._normalize_observation(raw_observation)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(
        result,
        profiler._SuccessfulObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert result.threads[0].stack[0]["function"] == "Sampled.__init__"


def test_normalization_retains_os_thread_without_python_stack():
    raw_observation = profiler._RawObservation(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        evidence={17: profiler._ThreadEvidence(101, "R")},  # pyright: ignore[reportPrivateUsage]
        stopped_threads=[_raw_stopped_thread(17, 101)],
        remote_threads=[],
        frame_names=[],
    )

    result = profiler._normalize_observation(raw_observation)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(
        result,
        profiler._SuccessfulObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert result.threads[0].stack == []


def test_normalization_decodes_copied_scheduler_runtime():
    raw_observation = profiler._RawObservation(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        evidence={17: profiler._ThreadEvidence(101, "R")},  # pyright: ignore[reportPrivateUsage]
        stopped_threads=[_raw_stopped_thread(17, 101, schedstat=b"1234 50 7\n")],
        remote_threads=[],
        frame_names=[],
    )

    result = profiler._normalize_observation(raw_observation)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(
        result,
        profiler._SuccessfulObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert result.threads[0].scheduler_runtime_ns == 1234


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
def test_cpu_observation_record_preserves_scheduler_runtime():
    writer = profiler._ProfileWriter(io.StringIO())  # pyright: ignore[reportPrivateUsage]
    evidence = profiler._ThreadEvidence(  # pyright: ignore[reportPrivateUsage]
        start_time_ticks=101,
        state="R",
    )
    captured_thread = profiler._CapturedThread(  # pyright: ignore[reportPrivateUsage]
        os_thread_id=11,
        evidence=evidence,
        stack=[
            {
                "filename": "source.py",
                "function": "work",
                "line": 7,
            }
        ],
        scheduler_runtime_ns=1234,
    )
    result = profiler._SuccessfulObservationResult(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        threads=[captured_thread],
    )

    records, observation = writer.observation_record(result)

    expected_observation: schema.SuccessfulObservation = {
        "scheduled_interval_ns": 10,
        "target_running_ns": 15,
        "pause_started_ns": 20,
        "pause_ended_ns": 25,
        "status": "successful",
        "threads": [
            {
                "os_thread_id": 11,
                "start_time_ticks": 101,
                "pre_stop_state": "R",
                "stack": [0],
                "scheduler_runtime_ns": 1234,
            }
        ],
    }
    assert observation == expected_observation
    assert records == [
        {
            "record_type": "frame",
            "frame_id": 0,
            "frame": {
                "filename": "source.py",
                "function": "work",
                "line": 7,
            },
        },
        {"record_type": "observation", "observation": expected_observation},
    ]


def test_observation_record_reuses_frame_definition():
    writer = profiler._ProfileWriter(io.StringIO())  # pyright: ignore[reportPrivateUsage]
    frame: schema.Frame = {
        "filename": "source.py",
        "function": "work",
        "line": 7,
    }
    result = profiler._SuccessfulObservationResult(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        threads=[
            profiler._CapturedThread(  # pyright: ignore[reportPrivateUsage]
                os_thread_id=11,
                evidence=profiler._ThreadEvidence(101, "R"),  # pyright: ignore[reportPrivateUsage]
                stack=[frame, frame],
                scheduler_runtime_ns=None,
            )
        ],
    )

    records, observation = writer.observation_record(result)

    assert len(records) == 2
    assert observation["status"] == "successful"
    assert observation["threads"][0]["stack"] == [0, 0]


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
    assert isinstance(result, dict)
    assert result["scheduled_interval_ns"] == 250_000_000
    assert result["pause_started_ns"] >= 100
    assert result["target_running_ns"] == result["pause_started_ns"] - 100
    assert result["pause_ended_ns"] == result["pause_started_ns"]
    assert result["status"] == "missed"
    assert (
        result["failure_kind"]
        is schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
    )
    assert result["failure_reason"] == "the target exited before the scheduled stop"
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
    arm_schedule.assert_called_once_with(32, 0.25)
    assert profile_path.read_text(encoding="utf-8")


# PRF-050: Minimal stopped section.
@pytest.mark.parametrize("state", ["T", "t"])
def test_stopped_state_check_accepts_stopped_states(state: str):
    stat = _raw_stopped_thread(17, 101, state=state).stat

    reached_stopped_state = profiler._thread_reached_stopped_state(  # pyright: ignore[reportPrivateUsage]
        stat
    )

    assert reached_stopped_state is True


def test_stopped_state_check_rejects_running_state():
    stat = _raw_stopped_thread(17, 101, state="R").stat

    reached_stopped_state = profiler._thread_reached_stopped_state(  # pyright: ignore[reportPrivateUsage]
        stat
    )

    assert reached_stopped_state is False


# PRF-050: Minimal stopped section.
def test_stopped_capture_copies_raw_stat_without_decoding(
    tmp_path: Path,
):
    thread_directory = tmp_path / "17"
    thread_directory.mkdir()
    raw_thread = _raw_stopped_thread(17, 101)
    _ = (thread_directory / "stat").write_bytes(raw_thread.stat)

    with (
        mock.patch.object(
            Path,
            "iterdir",
            autospec=True,
            return_value=iter([thread_directory]),
        ),
        mock.patch.object(
            profiler,
            "_decode_thread_stat",
            autospec=True,
            side_effect=AssertionError("decoded during stopped capture"),
        ),
    ):
        stopped_threads = profiler._capture_raw_stopped_threads(  # pyright: ignore[reportPrivateUsage]
            71,
            "wall",
        )

    assert stopped_threads == [raw_thread]


# PRF-050: Minimal stopped section.
def test_observation_prepares_unwinder_before_stopping_target():
    timeline: list[str] = []
    raw_unwinder = typing.cast(
        "profiler._Unwinder",  # pyright: ignore[reportPrivateUsage]
        typing.cast("object", types.SimpleNamespace()),
    )
    qualified_unwinder = typing.cast(
        "profiler._Unwinder",  # pyright: ignore[reportPrivateUsage]
        typing.cast("object", types.SimpleNamespace()),
    )

    def construct_unwinder(
        _process_id: int,
        *,
        all_threads: bool,
    ) -> profiler._Unwinder:  # pyright: ignore[reportPrivateUsage]
        assert all_threads is True
        timeline.append("construct-unwinder")
        return raw_unwinder

    def qualify_unwinder(
        _process_id: int,
        unwinder: object,
    ) -> profiler._Unwinder:  # pyright: ignore[reportPrivateUsage]
        assert unwinder is raw_unwinder
        timeline.append("qualify-unwinder")
        return qualified_unwinder

    def read_evidence(
        _process_id: int,
    ) -> dict[int, profiler._ThreadEvidence]:  # pyright: ignore[reportPrivateUsage]
        timeline.append("read-evidence")
        return {}

    def signal_target(_process_id: int, signal_number: int):
        timeline.append(
            "stop-target" if signal_number == signal.SIGSTOP else "resume-target"
        )

    def capture_stopped_threads(
        _target_process: process_events.TargetProcess,
        unwinder: profiler._Unwinder,  # pyright: ignore[reportPrivateUsage]
        _mode: schema.CaptureMode,
        _event_file_descriptor: int | None,
    ) -> tuple[
        list[profiler._RawStoppedThread],  # pyright: ignore[reportPrivateUsage]
        list[remote_frame_names.RemoteThread],
        remote_frame_names.CapturedFrameNames,
    ]:
        assert unwinder is qualified_unwinder
        timeline.append("capture-stopped")
        return [], [], []

    with (
        mock.patch.object(
            profiler,
            "_REMOTE_UNWINDER",
            autospec=True,
            side_effect=construct_unwinder,
        ),
        mock.patch.object(
            remote_frame_names,
            "QualifiedRemoteUnwinder",
            autospec=True,
            side_effect=qualify_unwinder,
        ),
        mock.patch.object(
            profiler,
            "_thread_evidence",
            autospec=True,
            side_effect=read_evidence,
        ),
        mock.patch.object(
            os,
            "kill",
            autospec=True,
            side_effect=signal_target,
        ),
        mock.patch.object(
            profiler,
            "_capture_stopped_threads",
            autospec=True,
            side_effect=capture_stopped_threads,
        ),
    ):
        captured = profiler._capture_observation(  # pyright: ignore[reportPrivateUsage]
            _target_process(),
            None,
            scheduled_interval_ns=10,
            launched_ns=0,
            total_pause_ns=0,
            mode="wall",
            event_file_descriptor=None,
        )

    assert captured.unwinder is qualified_unwinder
    assert timeline == [
        "construct-unwinder",
        "qualify-unwinder",
        "read-evidence",
        "stop-target",
        "capture-stopped",
        "resume-target",
    ]


def test_observation_records_stopped_capture_failure():
    retained_unwinder = typing.cast(
        "profiler._Unwinder",  # pyright: ignore[reportPrivateUsage]
        typing.cast("object", types.SimpleNamespace()),
    )
    with (
        mock.patch.object(
            profiler,
            "_thread_evidence",
            autospec=True,
            return_value={},
        ),
        mock.patch.object(os, "kill", autospec=True),
        mock.patch.object(
            profiler,
            "_capture_stopped_threads",
            autospec=True,
            side_effect=RuntimeError("unwind failed"),
        ),
    ):
        captured = profiler._capture_observation(  # pyright: ignore[reportPrivateUsage]
            _target_process(),
            retained_unwinder,
            scheduled_interval_ns=10,
            launched_ns=0,
            total_pause_ns=0,
            mode="wall",
            event_file_descriptor=None,
        )

    assert isinstance(captured.result, dict)
    assert (
        captured.result["failure_kind"]
        is schema.ObservationFailureKind.STACK_UNWIND_FAILED
    )
    assert captured.unwinder is None


def _missed_observation(
    sequence_number: int,
) -> schema.FailedObservation:
    return {
        "scheduled_interval_ns": 10,
        "target_running_ns": 15 + sequence_number,
        "pause_started_ns": 20 + sequence_number,
        "pause_ended_ns": 20 + sequence_number,
        "status": "missed",
        "failure_kind": (
            schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
        ),
        "failure_reason": "target exited",
    }


# PRF-004: No stale-stack reuse. PRF-007: Consistent stack.
# PRF-050: Minimal stopped section.
@pytest.mark.parametrize(
    ("evidence", "stopped_threads", "remote_thread_ids", "expected_reason"),
    [
        (
            {11: profiler._ThreadEvidence(101, "R")},  # pyright: ignore[reportPrivateUsage]
            [_raw_stopped_thread(11, 101)],
            [12],
            "a Python thread changed identity during the observation",
        ),
        (
            {},
            [_raw_stopped_thread(11, 101)],
            [],
            "an OS thread changed identity during the observation",
        ),
        (
            {11: profiler._ThreadEvidence(102, "R")},  # pyright: ignore[reportPrivateUsage]
            [_raw_stopped_thread(11, 101)],
            [],
            "an OS thread identifier was reused during the observation",
        ),
    ],
)
def test_normalization_discards_thread_identity_changes(
    evidence: dict[int, profiler._ThreadEvidence],  # pyright: ignore[reportPrivateUsage]
    stopped_threads: list[profiler._RawStoppedThread],  # pyright: ignore[reportPrivateUsage]
    remote_thread_ids: list[int],
    expected_reason: str,
):
    remote_threads = [
        typing.cast(
            "remote_frame_names.RemoteThread",
            typing.cast(
                "object",
                types.SimpleNamespace(thread_id=thread_id, frames=[]),
            ),
        )
        for thread_id in remote_thread_ids
    ]
    raw_observation = profiler._RawObservation(  # pyright: ignore[reportPrivateUsage]
        timing=_observation_timing(),
        evidence=evidence,
        stopped_threads=stopped_threads,
        remote_threads=remote_threads,
        frame_names=[],
    )

    result = profiler._normalize_observation(raw_observation)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(result, dict)
    assert result["failure_kind"] is schema.ObservationFailureKind.INCONSISTENT_STACK
    assert result["failure_reason"] == (
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
    processed_times: list[int] = []

    def persist_observation(
        _writer: object,
        _state: object,
        work: profiler._ObservationWork,  # pyright: ignore[reportPrivateUsage]
        _attached_runtime: object,
        _event_file_descriptor: object,
    ):
        target_running_ns = (
            work.timing["target_running_ns"]
            if isinstance(work, profiler._RawObservation)  # pyright: ignore[reportPrivateUsage]
            else work["target_running_ns"]
        )
        processed_times.append(target_running_ns)
        if target_running_ns == 15:
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

    assert processed_times == [15, 16]


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
    processed_times: list[int] = []

    def persist_observation(
        _writer: object,
        _state: object,
        work: profiler._ObservationWork,  # pyright: ignore[reportPrivateUsage]
        _attached_runtime: object,
        _event_file_descriptor: object,
    ):
        processed_times.append(
            work.timing["target_running_ns"]
            if isinstance(work, profiler._RawObservation)  # pyright: ignore[reportPrivateUsage]
            else work["target_running_ns"]
        )
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

    assert processed_times == [15]


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
    ("python_stack_observed", "records_failure"),
    [(False, True), (True, False)],
)
def test_attached_capture_requires_a_python_stack(
    *,
    python_stack_observed: bool,
    records_failure: bool,
):
    target_process = _target_process()
    writer = profiler._ProfileWriter(io.StringIO())  # pyright: ignore[reportPrivateUsage]
    state = _capture_state(python_stack_observed=python_stack_observed)
    attached_runtime = dataclasses.replace(
        _attached_runtime(),
        observed_target_running_ns=8,
    )
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
    assert state.python_attached is True
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
