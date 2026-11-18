from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tools.bazel_mutation_testing import build_events

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable

_LIBRARY = "//crates/example:example"
_TEST = "//crates/example:example_test"


def _action(label: str, mnemonic: str, *, success: bool) -> dict[str, object]:
    action: dict[str, object] = {"type": mnemonic, "label": label, "exitCode": 1}
    if success:
        action["success"] = True
    return {"id": {"actionCompleted": {"label": label}}, "action": action}


def _test_result(label: str, status: str) -> dict[str, object]:
    return {
        "id": {"testResult": {"label": label, "run": 1, "shard": 1, "attempt": 1}},
        "testResult": {"status": status},
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
        label=_LIBRARY, mnemonic="Clippy"
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
        label=_TEST, timed_out=False
    )


def test_timed_out_test(tmp_path: pathlib.Path):
    events = _write(
        tmp_path / "events.json",
        [_test_result(_TEST, "TIMEOUT")],
    )
    assert build_events.first_failure(events) == build_events.TestFailure(
        label=_TEST, timed_out=True
    )


def test_descriptions():
    assert (
        build_events.ActionFailure(label=_LIBRARY, mnemonic="Rustc").describe()
        == f"Rustc {_LIBRARY}"
    )
    assert build_events.TestFailure(label=_TEST, timed_out=False).describe() == _TEST
