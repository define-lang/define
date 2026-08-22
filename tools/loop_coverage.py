"""Collect coverage of loop bodies that execute more than once."""

from __future__ import annotations

import ast
import atexit
import dis
import os
import sys
import typing
from itertools import chain
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from types import CodeType, FrameType

_COVERAGE_DESCRIPTION = "loop body executes more than once"
_LOOP_COVERAGE_FILE = "loop_coverage.part"
_MONITORING_TOOL_IDS = (4, 3)
_MONITORING_TOOL_NAME = "define.loop_coverage"

type LoopLocation = tuple[Path, int]


@typing.final
class LoopCoverageCollector:
    """Collect loop-body entry counts and write them as LCOV branches."""

    def __init__(self, manifest_path: Path, report_path: Path):
        """Create a collector for the Python files in a Bazel coverage manifest."""
        self._report_path: Path = report_path
        self._loops_by_filename: dict[
            str, tuple[dict[int, LoopLocation], dict[int, LoopLocation]]
        ] = {}
        self._loop_lines_by_path: dict[Path, list[int]] = {}
        self._covered_loops: set[LoopLocation] = set()
        self._pending_by_frame: dict[FrameType, set[LoopLocation]] = {}
        self._locations_by_code: dict[CodeType, dict[int, LoopLocation]] = {}
        self._lines_by_offset: dict[CodeType, dict[int, int]] = {}
        self._monitoring_tool_id: int | None = None
        for reported_path, runtime_path in _manifest_python_paths(manifest_path):
            entries = _loop_entries(runtime_path)
            if entries:
                locations_by_entry_line: dict[int, LoopLocation] = {}
                locations_by_target_line: dict[int, LoopLocation] = {}
                for loop_line, entry_line in entries:
                    location = (reported_path, loop_line)
                    locations_by_entry_line[entry_line] = location
                    locations_by_target_line[loop_line] = location
                    self._loop_lines_by_path.setdefault(reported_path, []).append(
                        loop_line
                    )
                location_maps = (
                    locations_by_entry_line,
                    locations_by_target_line,
                )
                self._loops_by_filename[str(reported_path)] = location_maps
                self._loops_by_filename[str(reported_path.absolute())] = location_maps
                self._loops_by_filename[str(runtime_path)] = location_maps

    def start(self):
        """Start collecting loop-body entries."""
        for candidate_tool_id in _MONITORING_TOOL_IDS:
            if sys.monitoring.get_tool(candidate_tool_id) is None:
                self._monitoring_tool_id = candidate_tool_id
                break
        if self._monitoring_tool_id is None:
            raise RuntimeError("loop coverage monitoring tool IDs are already in use")
        tool_id = self._monitoring_tool_id
        sys.monitoring.use_tool_id(tool_id, _MONITORING_TOOL_NAME)
        _ = sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.JUMP, self._record_jump
        )
        _ = sys.monitoring.register_callback(
            tool_id,
            sys.monitoring.events.BRANCH_LEFT,
            self._record_jump,
        )
        _ = sys.monitoring.register_callback(
            tool_id,
            sys.monitoring.events.BRANCH_RIGHT,
            self._record_jump,
        )
        _ = sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.LINE, self._record_line
        )
        _ = sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.PY_RETURN, self._finish_frame
        )
        _ = sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.PY_UNWIND, self._unwind_frame
        )
        events = (
            sys.monitoring.events.JUMP
            | sys.monitoring.events.BRANCH_LEFT
            | sys.monitoring.events.BRANCH_RIGHT
            | sys.monitoring.events.PY_UNWIND
        )
        sys.monitoring.set_events(tool_id, events)

    def stop(self):
        """Stop collecting and write the LCOV report."""
        tool_id = self._tool_id()
        sys.monitoring.set_events(tool_id, sys.monitoring.events.NO_EVENTS)
        for code in self._locations_by_code:
            sys.monitoring.set_local_events(
                tool_id, code, sys.monitoring.events.NO_EVENTS
            )
        for event in (
            sys.monitoring.events.JUMP,
            sys.monitoring.events.BRANCH_LEFT,
            sys.monitoring.events.BRANCH_RIGHT,
            sys.monitoring.events.LINE,
            sys.monitoring.events.PY_RETURN,
            sys.monitoring.events.PY_UNWIND,
        ):
            _ = sys.monitoring.register_callback(tool_id, event, None)
        sys.monitoring.free_tool_id(tool_id)
        self._monitoring_tool_id = None
        self._pending_by_frame.clear()
        self._write_report()

    # Python suspends monitoring events while a monitoring callback runs.
    def _record_jump(  # pragma: no cover
        self, code: CodeType, instruction_offset: int, destination_offset: int
    ):
        if destination_offset >= instruction_offset:
            return
        location_maps = self._loops_by_filename.get(code.co_filename)
        if location_maps is None:
            return
        locations_by_entry_line, locations_by_target_line = location_maps

        lines_by_offset = self._lines_by_offset.get(code)
        if lines_by_offset is None:
            lines_by_offset = dict(
                chain.from_iterable(
                    map(_instruction_line_pairs, dis.get_instructions(code))
                )
            )
            self._lines_by_offset[code] = lines_by_offset
        target_line = lines_by_offset.get(destination_offset)
        if target_line is None:
            return
        location = locations_by_target_line.get(target_line)
        source_line = lines_by_offset.get(instruction_offset)
        if (
            location is None
            or source_line == target_line
            or location in self._covered_loops
        ):
            return

        frame = _monitored_frame()
        self._pending_by_frame.setdefault(frame, set()).add(location)

        events = sys.monitoring.events.LINE | sys.monitoring.events.PY_RETURN
        self._locations_by_code[code] = locations_by_entry_line
        sys.monitoring.set_local_events(self._tool_id(), code, events)

    def _record_line(  # pragma: no cover
        self, code: CodeType, line_number: int
    ):
        locations_by_entry_line = self._locations_by_code[code]
        location = locations_by_entry_line.get(line_number)
        frame = _monitored_frame()
        pending = self._pending_by_frame.get(frame)
        if location is None or pending is None or location not in pending:
            return

        self._covered_loops.add(location)
        pending.remove(location)
        if not pending:
            del self._pending_by_frame[frame]

    def _finish_frame(  # pragma: no cover
        self, _code: CodeType, _instruction_offset: int, _return_value: object
    ):
        self._remove_frame(_monitored_frame())

    def _unwind_frame(  # pragma: no cover
        self, _code: CodeType, _instruction_offset: int, _exception: BaseException
    ):
        self._remove_frame(_monitored_frame())

    def _remove_frame(self, frame: FrameType):  # pragma: no cover
        _ = self._pending_by_frame.pop(frame, None)

    def _tool_id(self) -> int:
        if self._monitoring_tool_id is None:
            raise RuntimeError("loop coverage collector is not active")
        return self._monitoring_tool_id

    def _write_report(self):
        lines: list[str] = []
        for reported_path in sorted(self._loop_lines_by_path):
            loop_lines = sorted(self._loop_lines_by_path[reported_path])
            covered_count = 0
            lines.append(f"SF:{reported_path}")
            for loop_line in loop_lines:
                taken = "-"
                if (reported_path, loop_line) in self._covered_loops:
                    taken = "1"
                    covered_count += 1
                lines.append(f"BRDA:{loop_line},1,{_COVERAGE_DESCRIPTION},{taken}")
            lines.append(f"BRF:{len(loop_lines)}")
            lines.append(f"BRH:{covered_count}")
            lines.append("end_of_record")

        report = "\n".join(lines)
        if lines:
            report += "\n"
        _ = self._report_path.write_text(report)


def _monitored_frame() -> FrameType:  # pragma: no cover
    return sys._getframe(2)  # pyright: ignore[reportPrivateUsage]


def _instruction_line_pairs(  # pragma: no cover
    instruction: dis.Instruction,
) -> tuple[tuple[int, int], ...]:
    positions = instruction.positions
    if positions is None or positions.lineno is None:
        return ()
    return ((instruction.offset, positions.lineno),)


def _manifest_python_paths(manifest_path: Path) -> list[tuple[Path, Path]]:
    paths: list[tuple[Path, Path]] = []
    for manifest_line in manifest_path.read_text().splitlines():
        reported_path = Path(manifest_line)
        if reported_path.suffix == ".py" and not reported_path.stem.endswith("_test"):
            paths.append((reported_path, reported_path.resolve()))
    return paths


def _loop_entries(source_path: Path) -> list[tuple[int, int]]:
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    entries: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            entry_line = node.body[0].lineno
            entries.append((node.lineno, entry_line))
    return entries


def _append_report(report_path: Path, coverage_output_path: Path):
    with coverage_output_path.open("a") as coverage_output:
        _ = coverage_output.write(report_path.read_text())
    report_path.unlink()


_COLLECTOR_KEY = pytest.StashKey[LoopCoverageCollector]()


def pytest_configure(config: pytest.Config):
    """Start loop coverage when pytest runs under Bazel coverage."""
    coverage_directory = os.environ.get("COVERAGE_DIR")
    coverage_manifest = os.environ.get("COVERAGE_MANIFEST")
    coverage_output = os.environ.get("COVERAGE_OUTPUT_FILE")
    if (
        coverage_directory is None
        or coverage_manifest is None
        or coverage_output is None
    ):
        return
    report_path = Path(coverage_directory) / _LOOP_COVERAGE_FILE
    collector = LoopCoverageCollector(Path(coverage_manifest), report_path)
    collector.start()
    config.stash[_COLLECTOR_KEY] = collector
    _ = atexit.register(_append_report, report_path, Path(coverage_output))


def pytest_unconfigure(config: pytest.Config):
    """Finish loop coverage after pytest completes."""
    collector = config.stash.get(_COLLECTOR_KEY, None)
    if collector is None:
        return
    collector.stop()
    del config.stash[_COLLECTOR_KEY]
