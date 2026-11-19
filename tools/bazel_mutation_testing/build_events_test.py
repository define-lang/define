from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from tools.bazel_mutation_testing import build_events

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable

_LIBRARY = "//crates/example:example"
_TEST = "//crates/example:example_test"
_GENRULE = "//crates/example:generated"


def _action(
    label: str,
    mnemonic: str,
    *,
    success: bool,
    failure_detail: dict[str, object] | None = None,
    streams: dict[str, pathlib.Path] | None = None,
) -> dict[str, object]:
    action: dict[str, object] = {"type": mnemonic, "label": label, "exitCode": 1}
    if success:
        action["success"] = True
    if failure_detail is not None:
        action["failureDetail"] = failure_detail
    for stream, path in (streams or {}).items():
        action[stream] = {"name": stream, "uri": path.as_uri()}
    return {"id": {"actionCompleted": {"label": label}}, "action": action}


def _test_result(
    label: str, status: str, log: pathlib.Path | None = None
) -> dict[str, object]:
    result: dict[str, object] = {"status": status}
    if log is not None:
        result["testActionOutput"] = [
            {"name": "test.xml", "uri": log.with_name("test.xml").as_uri()},
            {"name": "test.log", "uri": log.as_uri()},
        ]
    return {
        "id": {"testResult": {"label": label, "run": 1, "shard": 1, "attempt": 1}},
        "testResult": result,
    }


def _write(path: pathlib.Path, events: Iterable[dict[str, object]]) -> pathlib.Path:
    _ = path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_no_failure(tmp_path: pathlib.Path):
    events = _write(
        tmp_path / "events.json",
        [
            _action(_LIBRARY, "Rustc", success=True),
            _test_result(_TEST, "PASSED"),
        ],
    )
    assert build_events.first_failure(events) is None


def test_failed_action(tmp_path: pathlib.Path):
    events = _write(
        tmp_path / "events.json",
        [
            _action(_LIBRARY, "Clippy", success=False),
            _action(_LIBRARY, "Rustc", success=False),
        ],
    )
    assert build_events.first_failure(events) == build_events.ActionFailure(
        label=_LIBRARY, mnemonic="Clippy", outputs_missing=False, output=""
    )


def test_failed_test(tmp_path: pathlib.Path):
    events = _write(
        tmp_path / "events.json",
        [
            _action(_TEST, "TestRunner", success=False),
            _test_result(_TEST, "FAILED"),
        ],
    )
    assert build_events.first_failure(events) == build_events.TestFailure(
        label=_TEST, timed_out=False, log=""
    )


def test_timed_out_test(tmp_path: pathlib.Path):
    events = _write(
        tmp_path / "events.json",
        [_test_result(_TEST, "TIMEOUT")],
    )
    assert build_events.first_failure(events) == build_events.TestFailure(
        label=_TEST, timed_out=True, log=""
    )


def test_descriptions():
    assert (
        build_events.ActionFailure(
            label=_LIBRARY, mnemonic="Rustc", outputs_missing=False, output=""
        ).describe()
        == f"Rustc {_LIBRARY}"
    )
    assert (
        build_events.ActionFailure(
            label=_GENRULE, mnemonic="Genrule", outputs_missing=True, output=""
        ).describe()
        == f"Genrule {_GENRULE} (an output was not created)"
    )
    assert (
        build_events.TestFailure(label=_TEST, timed_out=False, log="").describe()
        == _TEST
    )


def test_outputs_missing_locally(tmp_path: pathlib.Path):
    detail: dict[str, object] = {"execution": {"code": "ACTION_OUTPUTS_NOT_CREATED"}}
    events = _write(
        tmp_path / "events.json",
        [_action(_GENRULE, "Genrule", success=False, failure_detail=detail)],
    )
    assert build_events.first_failure(events) == build_events.ActionFailure(
        label=_GENRULE, mnemonic="Genrule", outputs_missing=True, output=""
    )


def test_outputs_missing_remotely(tmp_path: pathlib.Path):
    detail: dict[str, object] = {
        "message": "remote spawn failed: mandatory output example.txt was not created",
        "spawn": {"code": "EXECUTION_FAILED"},
    }
    events = _write(
        tmp_path / "events.json",
        [_action(_GENRULE, "Genrule", success=False, failure_detail=detail)],
    )
    assert build_events.first_failure(events) == build_events.ActionFailure(
        label=_GENRULE, mnemonic="Genrule", outputs_missing=True, output=""
    )


def test_failed_action_output(tmp_path: pathlib.Path):
    stdout = tmp_path / "stdout-5"
    _ = stdout.write_text("lib.py:1:1: F401\n", encoding="utf-8", newline="\n")
    stderr = tmp_path / "stderr-5"
    _ = stderr.write_text("Found 1 error.\n", encoding="utf-8", newline="\n")
    events = _write(
        tmp_path / "events.json",
        [
            _action(
                _LIBRARY,
                "Ruff",
                success=False,
                streams={"stdout": stdout, "stderr": stderr},
            )
        ],
    )
    failure = build_events.first_failure(events)
    assert isinstance(failure, build_events.ActionFailure)
    assert failure.output == "lib.py:1:1: F401\nFound 1 error.\n"


def test_failed_test_log(tmp_path: pathlib.Path):
    log = tmp_path / "test.log"
    _ = log.write_text("FAILED test_one\n", encoding="utf-8", newline="\n")
    events = _write(tmp_path / "events.json", [_test_result(_TEST, "FAILED", log)])
    assert build_events.first_failure(events) == build_events.TestFailure(
        label=_TEST, timed_out=False, log="FAILED test_one\n"
    )


def test_remote_stderr_is_refused(tmp_path: pathlib.Path):
    event = _action(_LIBRARY, "Rustc", success=False)
    action = cast("dict[str, object]", event["action"])
    action["stderr"] = {"name": "stderr", "uri": "bytestream://rbe/blobs/abc/5"}
    events = _write(tmp_path / "events.json", [event])
    with pytest.raises(ValueError, match="not local"):
        _ = build_events.first_failure(events)
