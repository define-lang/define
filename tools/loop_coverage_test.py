from __future__ import annotations

import sys
import typing
from unittest import mock

import pytest

from tools import loop_coverage

if typing.TYPE_CHECKING:
    import collections.abc
    from pathlib import Path


def _execute_source(source_path: Path) -> dict[str, object]:
    namespace: dict[str, object] = {}
    # The collector matches runtime code to the manifest using this filename.
    exec(  # noqa: S102
        compile(source_path.read_text(), source_path, "exec"), namespace
    )
    return namespace


def test_collector_reports_loop_body_executed_more_than_once(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def collect(values):\n"
        + "    result = []\n"
        + "    for value in values:\n"
        + "        result.append(value)\n"
        + "    return result\n"
    )
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"
    namespace = _execute_source(source_path)
    collect = namespace["collect"]
    assert callable(collect)

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector.start()
    try:
        assert collect([1, 2]) == [1, 2]
    finally:
        collector.stop()

    assert report_path.read_text() == (
        f"SF:{source_path}\n"
        + "BRDA:3,1,loop body executes more than once,1\n"
        + "BRF:1\n"
        + "BRH:1\n"
        + "end_of_record\n"
    )


def test_collector_handles_multiline_loop_header(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def consume(values):\n"
        + "    for (\n"
        + "        value\n"
        + "    ) in values:\n"
        + "        str(value)\n"
    )
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"
    namespace = _execute_source(source_path)
    consume = typing.cast(
        "collections.abc.Callable[[object], object]",
        namespace["consume"],
    )

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector.start()
    try:
        _ = consume([1, 2])
    finally:
        collector.stop()

    assert "BRDA:2,1,loop body executes more than once,1\n" in report_path.read_text()


def test_collector_does_not_combine_nested_loop_activations(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def consume(values):\n"
        + "    for value in values:\n"
        + "        for (\n"
        + "            inner\n"
        + "        ) in [value]:\n"
        + "            str(inner)\n"
    )
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"
    namespace = _execute_source(source_path)
    consume = typing.cast(
        "collections.abc.Callable[[object], object]",
        namespace["consume"],
    )

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector.start()
    try:
        _ = consume([1, 2])
    finally:
        collector.stop()

    assert report_path.read_text() == (
        f"SF:{source_path}\n"
        + "BRDA:2,1,loop body executes more than once,1\n"
        + "BRDA:3,1,loop body executes more than once,-\n"
        + "BRF:2\n"
        + "BRH:1\n"
        + "end_of_record\n"
    )


def test_collector_does_not_combine_single_iterations_across_calls(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def consume(values):\n" + "    for value in values:\n" + "        str(value)\n"
    )
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"
    namespace = _execute_source(source_path)
    consume = typing.cast(
        "collections.abc.Callable[[object], object]",
        namespace["consume"],
    )

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector.start()
    try:
        _ = consume([1])
        _ = consume([2])
    finally:
        collector.stop()

    assert "BRDA:2,1,loop body executes more than once,-\n" in report_path.read_text()


def test_collector_reports_every_loop_type_executed_only_once(tmp_path: Path):
    source_path = tmp_path / "example.py"
    _ = source_path.write_text(
        "def consume_for(values):\n"
        + "    for value in values:\n"
        + "        str(value)\n"
        + "\n"
        + "def consume_while():\n"
        + "    keep_going = True\n"
        + "    while keep_going:\n"
        + "        keep_going = False\n"
        + "\n"
        + "async def consume_async_for(values):\n"
        + "    async for value in values:\n"
        + "        str(value)\n"
    )
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"
    namespace = _execute_source(source_path)
    consume_for = typing.cast(
        "collections.abc.Callable[[object], object]",
        namespace["consume_for"],
    )
    consume_while = typing.cast(
        "collections.abc.Callable[[], object]",
        namespace["consume_while"],
    )
    consume_async_for = typing.cast(
        "collections.abc.Callable[[object], collections.abc.Coroutine[object, object, object]]",
        namespace["consume_async_for"],
    )

    async def values():
        yield 1

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector.start()
    try:
        _ = consume_for([1])
        _ = consume_while()
        consume_coroutine = consume_async_for(values())
        with pytest.raises(StopIteration):
            _ = consume_coroutine.send(None)
    finally:
        collector.stop()

    assert report_path.read_text() == (
        f"SF:{source_path}\n"
        + "BRDA:2,1,loop body executes more than once,-\n"
        + "BRDA:7,1,loop body executes more than once,-\n"
        + "BRDA:11,1,loop body executes more than once,-\n"
        + "BRF:3\n"
        + "BRH:0\n"
        + "end_of_record\n"
    )


def test_collector_rejects_an_existing_monitoring_tool(tmp_path: Path):
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text("")
    collector = loop_coverage.LoopCoverageCollector(
        manifest_path, tmp_path / "loop_coverage.dat"
    )

    claimed_tool_ids: list[int] = []
    for tool_id in (4, 3):
        if sys.monitoring.get_tool(tool_id) is None:
            sys.monitoring.use_tool_id(tool_id, "existing")
            claimed_tool_ids.append(tool_id)
    try:
        with pytest.raises(
            RuntimeError,
            match="loop coverage monitoring tool IDs are already in use",
        ):
            collector.start()
    finally:
        for tool_id in claimed_tool_ids:
            sys.monitoring.free_tool_id(tool_id)


def test_collector_ignores_test_modules(tmp_path: Path):
    source_path = tmp_path / "example_test.py"
    _ = source_path.write_text("for value in [1, 2]:\n    str(value)\n")
    manifest_path = tmp_path / "manifest.txt"
    _ = manifest_path.write_text(f"{source_path}\n")
    report_path = tmp_path / "loop_coverage.dat"

    collector = loop_coverage.LoopCoverageCollector(manifest_path, report_path)
    collector._write_report()  # pyright: ignore[reportPrivateUsage]

    assert report_path.read_text() == ""


def test_append_report_adds_records_and_removes_partial_file(tmp_path: Path):
    report_path = tmp_path / "loop_coverage.part"
    _ = report_path.write_text("SF:example.py\nend_of_record\n")
    coverage_output_path = tmp_path / "coverage.dat"
    _ = coverage_output_path.write_text("SF:other.py\nend_of_record\n")

    loop_coverage._append_report(  # pyright: ignore[reportPrivateUsage]
        report_path, coverage_output_path
    )

    assert coverage_output_path.read_text() == (
        "SF:other.py\nend_of_record\nSF:example.py\nend_of_record\n"
    )
    assert not report_path.exists()


def test_pytest_hooks_are_inactive_without_bazel_coverage(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("COVERAGE_DIR", raising=False)
    monkeypatch.delenv("COVERAGE_MANIFEST", raising=False)
    monkeypatch.delenv("COVERAGE_OUTPUT_FILE", raising=False)

    with mock.patch.object(
        loop_coverage, "LoopCoverageCollector", autospec=True
    ) as collector_class:
        config = mock.Mock(spec=pytest.Config)
        config.stash = pytest.Stash()
        loop_coverage.pytest_configure(config)
        loop_coverage.pytest_unconfigure(config)

    collector_class.assert_not_called()
