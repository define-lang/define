from __future__ import annotations

from typing import TYPE_CHECKING, final

from tools.bazel_mutation_testing import bazel

if TYPE_CHECKING:
    import pathlib


def test_query_expression_of_patterns():
    assert (
        bazel.query_expression(
            ["//define/...", "-//define/examples/...", "//crates/..."]
        )
        == "//define/... - //define/examples/... + //crates/..."
    )


@final
class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


def _progress(tmp_path: pathlib.Path) -> tuple[bazel.Progress, pathlib.Path, _Clock]:
    clock = _Clock()
    build_events_file = tmp_path / "build_events.json"
    return (
        bazel.Progress(build_events_file, 10, clock.monotonic),
        build_events_file,
        clock,
    )


def test_a_command_that_writes_no_build_events_stalls(tmp_path: pathlib.Path):
    progress, _, clock = _progress(tmp_path)
    clock.now = 9.0
    assert not progress.stalled()
    clock.now = 10.0
    assert progress.stalled()


def test_each_new_build_event_restarts_the_wait(tmp_path: pathlib.Path):
    progress, build_events_file, clock = _progress(tmp_path)
    for second in (8.0, 16.0, 24.0):
        clock.now = second
        with build_events_file.open("a", encoding="utf-8", newline="\n") as events:
            _ = events.write("{}\n")
        assert not progress.stalled()
    clock.now = 33.0
    assert not progress.stalled()
    clock.now = 34.0
    assert progress.stalled()
